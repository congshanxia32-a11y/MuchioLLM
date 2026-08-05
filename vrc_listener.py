#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""VRChat音声リスナー — 他プレイヤーの声を文字起こしして data/others_heard.jsonl に流す。

仕組み: VRChatが鳴らしている出力デバイスをWASAPIループバックで取得
（自分のマイク音声はVRChatの出力に含まれないので、聞こえるのは他人の声＋ワールド音）
→ faster-whisper(CPU, int8)で日英自動判別の文字起こし。

注意: 出力デバイス全体を取るので、同じデバイスで音楽等を流すとそれも拾う。
音楽はWindowsの音量ミキサーでVRChatと別デバイスに分けると混ざらない。

  python vrc_listener.py            # 既定スピーカーのループバック → others_heard.jsonl
  python vrc_listener.py Shokz      # 名前の一部でデバイス指定
  python vrc_listener.py --mic      # 既定マイクを取る(飼い主の声) → owner_heard.jsonl
                                    # VRCPet起動中は自動で休止(二重認識防止)
  python vrc_listener.py --mic AG06 # マイクを名前で指定
  python vrc_listener.py --list     # 指定できるデバイスの一覧
毎回引数を打ちたくなければ、下の DEVICE_NAME に書いておく。
"""
import json, re, subprocess, sys, time
from pathlib import Path

import numpy as np
import pyaudiowpatch as pyaudio
from faster_whisper import WhisperModel

import voiceid   # 声紋(だれの声か)。speechbrain未導入なら自動休止

HERE = Path(__file__).parent
DATA = HERE / "data"

DEVICE_NAME = ""             # キャプチャするデバイス名の一部（空=既定スピーカーのループバック）
WHISPER_MODEL = "small"      # CPUフォールバック時のループバック用
GPU_MODEL_MIC = "large-v3-turbo"  # GPU時のマイク用(聞き間違い減。ループバックと同じ大型)
GPU_MODEL_LB = "large-v3-turbo"  # GPU時のループバック用(圧縮された遠い声には大型を)
RMS_GATE = 400               # これ未満の音量は無音扱い (int16)  ponytail: 環境依存、拾わな過ぎ/拾い過ぎたら調整
SILENCE_END = 0.45           # 発話終了とみなす無音秒数(短いほど反応が速いが文を切りやすい)
MIN_SPEECH = 0.4             # これより短い音は捨てる
MAX_SPEECH = 12.0            # 長すぎたら強制で区切る
CHUNK_SEC = 0.25

# whisperが無音・音楽で幻覚しがちな定型文（含まれていたら捨てる）
HALLUCINATIONS = ["ご視聴ありがとう", "チャンネル登録", "thank you for watching",
                  "thanks for watching", "subscribe"]

def log(msg):
    print(time.strftime("%H:%M:%S ") + msg, flush=True)

def list_devices(p):
    print("指定できるデバイス（[LB]=ループバック: そのデバイスに鳴っている音 / [MIC]=入力デバイス）:")
    for i in range(p.get_device_count()):
        d = p.get_device_info_by_index(i)
        if d.get("maxInputChannels", 0) > 0:
            kind = "LB " if d.get("isLoopbackDevice") else "MIC"
            print(f"  [{kind}] {d['name']}")

def pick_device(p, name_part=None, mic=False):
    if name_part:
        # 通常はループバック優先、--micではマイク優先で2周
        for loopback_only in ((False, True) if mic else (True, False)):
            for i in range(p.get_device_count()):
                d = p.get_device_info_by_index(i)
                if (d.get("maxInputChannels", 0) > 0
                        and bool(d.get("isLoopbackDevice")) == loopback_only
                        and name_part.lower() in d["name"].lower()):
                    return d
        log(f"'{name_part}' に一致するデバイスが見つからないので既定を使います（--list で一覧）")
    if mic:
        return p.get_device_info_by_index(p.get_default_input_device_info()["index"])
    return p.get_default_wasapi_loopback()

def _add_nvidia_dlls():
    """pipで入れたcuBLAS/cuDNNのDLLをctranslate2から見えるようにする"""
    import ctypes, glob, os, site
    bins = [d for sp in site.getsitepackages()
            for d in glob.glob(os.path.join(sp, "nvidia", "*", "bin"))]
    for d in bins:
        try:
            os.add_dll_directory(d)
        except OSError:
            pass
    # ctranslate2はDLL名だけのLoadLibraryで読むためadd_dll_directoryが効かない。
    # 入口のDLLをフルパスで先に読み込んでおくと、名前だけでも解決できるようになる。
    for d in bins:
        for pat in ("cublas64_*.dll", "cublasLt64_*.dll", "cudnn64_*.dll"):
            for dll in glob.glob(os.path.join(d, pat)):
                try:
                    ctypes.CDLL(dll)
                except OSError:
                    pass

def make_model(mic_mode):
    """GPU(large系)を試し、だめならCPUへフォールバック"""
    candidates = [
        (GPU_MODEL_MIC if mic_mode else GPU_MODEL_LB, "cuda", "int8_float16"),
        ("base" if mic_mode else WHISPER_MODEL, "cpu", "int8"),
    ]
    for name, dev, ct in candidates:
        try:
            if dev == "cuda":
                _add_nvidia_dlls()
            log(f"whisper({name}/{dev})ロード中...")
            m = WhisperModel(name, device=dev, compute_type=ct)
            segs, _ = m.transcribe(np.zeros(16000, dtype=np.float32),
                                   beam_size=1, language="ja")
            list(segs)   # 実際に1回動かして使えるか確認
            log(f"whisper 準備完了 ({name}/{dev})")
            return m
        except Exception as e:
            log(f"whisper {name}/{dev} 失敗: {e.__class__.__name__}: {str(e)[:100]}")
    raise RuntimeError("whisperをロードできませんでした")

def vrcpet_running():
    try:
        out = subprocess.run(["tasklist", "/FI", "IMAGENAME eq VRCPet.exe"],
                             capture_output=True, timeout=5).stdout
        return b"VRCPet.exe" in out   # 日本語WindowsのCP932出力をデコードせずバイト比較
    except Exception:
        return False

def to_16k_mono(raw, channels, rate):
    x = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
    if channels > 1:
        x = x.reshape(-1, channels).mean(axis=1)
    if rate != 16000:
        n = int(len(x) * 16000 / rate)
        x = np.interp(np.linspace(0, len(x), n, endpoint=False), np.arange(len(x)), x)
    return x.astype(np.float32)   # np.interpはfloat64を返す。whisperのVADはfloat32必須

def main():
    DATA.mkdir(exist_ok=True)
    args = sys.argv[1:]
    mic_mode = "--mic" in args
    if mic_mode:
        args.remove("--mic")
    name_part = args[0] if args else (DEVICE_NAME if not mic_mode and DEVICE_NAME else None)
    if name_part == "--list":
        list_devices(pyaudio.PyAudio())
        return
    out_path = DATA / ("owner_heard.jsonl" if mic_mode else "others_heard.jsonl")
    alive = DATA / ("ears_mic.alive" if mic_mode else "ears.alive")   # 設定UIの生存表示用
    DATA.mkdir(exist_ok=True)
    alive.touch()   # モデルDL/ロード中(数十秒)も「起動中」と分かるように先に打つ
    model = make_model(mic_mode)

    p = pyaudio.PyAudio()
    dev = pick_device(p, name_part, mic_mode)
    rate, ch = int(dev["defaultSampleRate"]), int(dev["maxInputChannels"])
    log(f"キャプチャ({'mic' if mic_mode else 'loopback'}): {dev['name']} ({rate}Hz {ch}ch)")
    chunk = int(rate * CHUNK_SEC)
    stream = p.open(format=pyaudio.paInt16, channels=ch, rate=rate, input=True,
                    input_device_index=dev["index"], frames_per_buffer=chunk)

    buf = []          # 発話中の生チャンク
    silence = 0.0
    pet_check, pet_present = 0.0, False
    last_hb = 0.0
    gate, sil_end = float(RMS_GATE), float(SILENCE_END)   # config.jsonから15秒毎に更新
    hint = "VRChatで、ペットと話している。"               # 認識ヒント(同上。config読込までの仮値)
    v_thresh = 0.55     # 声紋一致のcosine閾値(config voice_thresholdで調整)
    enabled = True      # 設定UIの「耳」カテゴリ。OFF中は音声を認識・保存しない
    lang_lock = None    # 日本語/英語モードでは言語を固定する(誤判定が消えて精度が上がる)
    while True:
        if mic_mode and time.time() - pet_check > 10:   # VRCPetと二重認識しない
            pet_check = time.time()
            was, pet_present = pet_present, vrcpet_running()
            if was != pet_present:
                log("VRCPet検出 → マイク取り休止" if pet_present else "VRCPet不在 → マイク取り再開")
        raw = stream.read(chunk, exception_on_overflow=False)
        x = np.frombuffer(raw, dtype=np.int16)
        rms = float(np.sqrt(np.mean(x.astype(np.float32) ** 2)))
        speaking = rms >= gate
        if time.time() - last_hb > 15:   # 生存確認 + 設定UIの変更を反映
            last_hb = time.time()
            try:
                alive.touch()
            except OSError:
                pass
            try:
                c = json.loads((HERE / "config.json").read_text(encoding="utf-8"))
                gate = float(c.get("rms_gate", RMS_GATE))
                sil_end = float(c.get("silence_end", SILENCE_END))
                v_thresh = float(c.get("voice_threshold", 0.55))
                enabled = bool(c.get("advanced_listener_enabled", True))
                mode = c.get("mode", "auto")
                lang_lock = {"jp": "ja", "en": "en"}.get(mode)
                key = "stt_hint_en" if mode == "en" else "stt_hint"
                # ヒント内の{name}をペット名へ(このファイルはDEFAULTSマージ無しの生読みなので既定値も持つ)
                name = str(c.get("pet_name_en" if mode == "en" else "pet_name", "") or "").strip() \
                    or ("muchiko" if mode == "en" else "むちこ")
                hint = (str(c.get(key, hint)).strip() or hint).replace("{name}", name)
            except Exception:
                pass
            log(f"音量RMS={rms:.0f} / ゲート{gate:.0f}  ※話してもRMSが上がらないなら別のデバイスを指定")

        if not enabled:
            buf, silence = [], 0.0
            continue

        if speaking:
            buf.append(raw)
            silence = 0.0
        elif buf:
            silence += CHUNK_SEC
            buf.append(raw)   # 語尾を切らない
        dur = len(buf) * CHUNK_SEC

        if buf and (silence >= sil_end or dur >= MAX_SPEECH):
            audio_raw = b"".join(buf)
            buf, silence = [], 0.0
            if dur < MIN_SPEECH + sil_end or (mic_mode and pet_present):
                continue
            audio = to_16k_mono(audio_raw, ch, rate)
            try:
                segments, info = model.transcribe(
                    audio, language=lang_lock, vad_filter=True, beam_size=1,
                    condition_on_previous_text=False,
                    initial_prompt=hint or None)
                text = " ".join(s.text.strip() for s in segments
                                if s.no_speech_prob < 0.6).strip()
            except Exception as e:
                log(f"文字起こし失敗: {e}")
                continue
            if not text or any(h in text.lower() for h in HALLUCINATIONS):
                continue
            # 無音・BGM時にヒント文(の断片)をそのまま幻覚することがある
            hint_parts = [p for p in re.split(r"[、。,.\s]", hint) if len(p) >= 6]
            if (text.strip("。、 ") == hint.strip("。、 ")
                    or any(p in text for p in hint_parts)):
                log(f"ヒント幻覚をスキップ: {text}")
                continue
            lang = info.language or "?"
            conf = info.language_probability or 0.0
            if lang_lock:
                lang = lang_lock          # 固定モードでは言語判定を使わない
            elif lang not in ("ja", "en"):
                if conf > 0.7:   # 高確度の外国語だけ除外
                    log(f"きこえた[{lang}:{conf:.2f}→対象外]: {text}")
                    continue
                lang = "ja"      # 短い発話は言語判定が不安定。捨てずに通す
            entry = {"ts": time.time(), "text": text, "lang": lang}
            tag = ""
            if not mic_mode:   # 声紋: だれの声か(飼い主のマイクは既知なので不要)
                vec = voiceid.embed(audio)
                if vec:
                    hit = voiceid.observe(entry["ts"], vec, lang, conf, v_thresh)
                    if hit:
                        entry["who"], entry["who_name"] = hit[0], hit[1]
                        tag = f"[{hit[1]}:{hit[2]:.2f}]"
            log(f"きこえた[{lang}]{tag}: {text}")
            with out_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")

if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    try:
        main()
    except KeyboardInterrupt:
        print("終了")
