#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""声紋(speaker embedding)の共通部品 — リスナー(埋め込み計算)とデーモンUI(ラベル付け)の両方から使う。

- data/voices.json  : 人ごとの声紋プロフィール {uid: {name, vecs:[[192]..max8]}}
- data/embeds.jsonl : リスナーが全発話の埋め込みをtsキーでstash(ラベル付け用)
torchはembed()内で遅延import。speechbrain未導入でもこのモジュール自体は読める。

python voiceid.py で自己チェック(合成ベクトル、モデル不要)。
"""
import json, math, os, time
from pathlib import Path

DATA = Path(__file__).parent / "data"
VOICES = DATA / "voices.json"
EMBEDS = DATA / "embeds.jsonl"
MAX_VECS = 8          # 1人あたり保持する声紋サンプル数(声は距離・エフェクトで揺れるので複数持つ)
EMBED_KEEP = 1500     # embeds.jsonlの切り詰め後行数
EMBED_TRIM_AT = 3000

_profiles = {}        # uid -> {"name": str, "vecs": [[float]..]}
_mtime = 0.0


def _norm(v):
    n = math.sqrt(sum(x * x for x in v)) or 1.0
    return [x / n for x in v]


def load_profiles():
    """mtimeが変わっていたら読み直す。返り値は共有dict(書き換え禁止)"""
    global _profiles, _mtime
    try:
        m = VOICES.stat().st_mtime
    except FileNotFoundError:
        _profiles, _mtime = {}, 0.0
        return _profiles
    if m != _mtime:
        try:
            _profiles = json.loads(VOICES.read_text(encoding="utf-8"))
            _mtime = m
        except (json.JSONDecodeError, OSError):
            pass
    return _profiles


def _save_profiles():
    global _mtime
    DATA.mkdir(exist_ok=True)
    tmp = VOICES.with_suffix(".tmp")
    tmp.write_text(json.dumps(_profiles, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, VOICES)
    _mtime = VOICES.stat().st_mtime


def match(vec, threshold):
    """全プロフィールの全サンプルとのcosine最大。閾値未満はNone。
    (uid, name, score) を返す。vecはunit-norm前提でなくてよい"""
    vec = _norm(vec)
    best, best_uid = 0.0, None
    for uid, p in load_profiles().items():
        for v in p.get("vecs", []):
            s = sum(a * b for a, b in zip(vec, v))
            if s > best:
                best, best_uid = s, uid
    if best_uid is None or best < threshold:
        return None
    return best_uid, _profiles[best_uid]["name"], best


# ---------------------------------------------------------------- stash(リスナー側)
def stash(ts, vec):
    """発話の埋め込みを保存(あとからUIでラベル付けするため)。肥大したら切り詰め"""
    DATA.mkdir(exist_ok=True)
    with EMBEDS.open("a", encoding="utf-8") as f:
        f.write(json.dumps({"ts": ts, "v": [round(x, 4) for x in _norm(vec)]}) + "\n")
    try:
        lines = EMBEDS.read_text(encoding="utf-8").splitlines()
        if len(lines) > EMBED_TRIM_AT:
            tmp = EMBEDS.with_suffix(".tmp")
            tmp.write_text("\n".join(lines[-EMBED_KEEP:]) + "\n", encoding="utf-8")
            os.replace(tmp, EMBEDS)
    except OSError:
        pass


def _find_embed(ts):
    if not EMBEDS.exists():
        return None
    for line in EMBEDS.read_text(encoding="utf-8").splitlines():
        try:
            j = json.loads(line)
            if abs(j["ts"] - ts) < 0.01:
                return j["v"]
        except (json.JSONDecodeError, KeyError):
            pass
    return None


# ---------------------------------------------------------------- ラベル付け(デーモンUI側)
def add_sample(uid, name, ts):
    """tsの発話の埋め込みをuidの声紋プロフィールに追加。見つからなければFalse"""
    v = _find_embed(ts)
    if v is None:
        return False
    load_profiles()
    p = _profiles.setdefault(uid, {"name": name, "vecs": []})
    p["name"] = name
    p["vecs"] = (p["vecs"] + [v])[-MAX_VECS:]   # 古いサンプルから捨てる
    _save_profiles()
    return True


def reset(uid):
    """誤登録の逃げ道: その人の声紋を全部忘れる"""
    load_profiles()
    if _profiles.pop(uid, None) is None:
        return False
    _save_profiles()
    return True


def summary():
    """UI表示用: [{uid, name, n}]"""
    return [{"uid": u, "name": p["name"], "n": len(p.get("vecs", []))}
            for u, p in load_profiles().items()]


# ---------------------------------------------------------------- 埋め込み(リスナー側)
_encoder = None
_dead = False


def embed(audio_f32_16k):
    """16kHz mono float32 → 192次元声紋。speechbrain未導入/失敗はNone(以後休止)"""
    global _encoder, _dead
    if _dead:
        return None
    if _encoder is None:
        try:
            import torch
            from speechbrain.inference.speaker import EncoderClassifier
            dev = "cuda" if torch.cuda.is_available() else "cpu"
            _encoder = EncoderClassifier.from_hparams(
                source="speechbrain/spkrec-ecapa-voxceleb",
                savedir=str(DATA / "ecapa"), run_opts={"device": dev})
            print(time.strftime("%H:%M:%S ") + f"こえ分類 準備完了 (ecapa/{dev})", flush=True)
        except Exception as e:
            _dead = True
            print(time.strftime("%H:%M:%S ") +
                  f"こえ分類は休止({e.__class__.__name__}: {str(e)[:80]})。"
                  "pip install speechbrain で有効になります", flush=True)
            return None
    try:
        import torch
        with torch.no_grad():
            t = torch.from_numpy(audio_f32_16k).unsqueeze(0)
            v = _encoder.encode_batch(t).squeeze()
        return [float(x) for x in v]
    except Exception:
        return None


# ---------------------------------------------------------------- 自己チェック
if __name__ == "__main__":
    import sys, tempfile
    sys.stdout.reconfigure(encoding="utf-8")
    # 実データを触らないよう一時dirへ
    _d = Path(tempfile.mkdtemp())
    VOICES, EMBEDS = _d / "voices.json", _d / "embeds.jsonl"
    DATA = _d

    assert match([1.0, 0.0], 0.5) is None, "空プロフィールでNoneにならない"
    stash(100.0, [1.0, 0.0])
    stash(200.0, [0.0, 1.0])
    assert add_sample("usr_a", "poyo", 100.0)
    assert not add_sample("usr_a", "poyo", 999.0), "無いtsで成功扱い"
    got = match([0.9, 0.1], 0.55)
    assert got and got[0] == "usr_a" and got[2] > 0.9, got
    assert match([0.0, 1.0], 0.55) is None, "直交ベクトルが一致扱い"
    assert add_sample("usr_b", "れお", 200.0)
    assert match([0.1, 0.95], 0.55)[1] == "れお"
    # MAX_VECSで古いのから捨てる
    for i in range(12):
        stash(300.0 + i, [1.0, float(i) * 0.01])
        add_sample("usr_a", "poyo", 300.0 + i)
    assert len(load_profiles()["usr_a"]["vecs"]) == MAX_VECS
    assert reset("usr_a") and not reset("usr_a")
    assert match([1.0, 0.0], 0.5) is None or match([1.0, 0.0], 0.5)[0] != "usr_a"
    print("ok")
