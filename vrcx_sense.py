#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""状況認識 — VRCXのSQLiteからワールド・曲・プレイ時間・日記・場所のおもいで。stdlibのみ。

growth.py(人をおぼえる)と対になる「いまなにしてるか」側。
スレッドは書き先がファイルごとに1本(videos.json=resolver、diary.jsonl=diarist)なので
ロック不要。UIスレッドはstatus_line()を読むだけ。

python vrcx_sense.py で自己チェック(assert + VRCXライブ読み。VRChat不要)。
"""
import json, os, queue, random, re, sqlite3, threading, time, urllib.parse, urllib.request
from pathlib import Path

import growth   # _connect / _to_epoch / VRCX_DB を再利用

POLL_IV = 5.0
SONG_TTL = 600         # 「いまのきょく」と言い張れる秒数
CARE_IV = 3600         # よふかし注意の最短間隔秒

# muchio側DEFAULTSと同値のフォールバック(growth._KNOBSと同じ流儀)
_KNOBS = {
    "vrcx_enabled": True,
    "advanced_sense_enabled": True,
    "memory_conversation_enabled": True,
    "memory_diary_enabled": True,
    "world_comment_chance": 0.5,   # ワールドが変わったとき一言いう率
    "song_comment_chance": 0.25,   # 曲が流れはじめたとき一言いう率
    "care_hours": 6.0,             # きょうのプレイがこの時間を超えたら気づかう(0=off)
    "care_hour": 23,               # 気づかいを言い始める時刻(この時以降+あさ6時まで)
    "diary": True,                 # まいにち日記をかく(長期記憶)
}

_world = None          # {"row","id","name","visits","itype"}
_song = None           # {"ytid","url","plays","ts","said"}
_titles = {}           # ytid -> タイトル(data/videos.json、恒久キャッシュ)
_bad = set()           # 解決失敗ytid(メモリ内のみ=次回起動で再挑戦)
_memory = ""           # いまのワールドでの過去会話の断片
_windows = []          # いまのワールドの過去滞在窓(界隈切替時のおもいで引き直し用)
_diary = {"": [], "_en": []}   # 界隈別 [{"date","text"}] 直近3件
_playtime_h = 0.0      # きょう(あさ6時起点)のプレイ時間
_comment_q = None      # (text, ts) 自発コメント。growth._greet_qと同じ単一スロット
_vid_id = 0            # gamelog_video_play の読み込み済みid
_last_poll = 0.0
_last_care = 0.0
_dead = False
_data = None
_board = None          # to_board_text
_log = print
_get_cfg = None
_get_suffix = lambda: ""   # 界隈サフィックス(muchio_llm.db_suffix)。jp="" en="_en"
_fetch_q = queue.Queue()


def _conv_path(sfx=None):
    return _data / f"conversation{_get_suffix() if sfx is None else sfx}.jsonl"


def _diary_path(sfx):
    return _data / f"diary{sfx}.jsonl"


def _cfg(key):
    if _get_cfg:
        v = _get_cfg().get(key)
        if v is not None:
            return v
    return _KNOBS[key]


def init(data_dir, to_board_text, logger=print, get_cfg=None, get_suffix=None):
    """起動時1回。現在ワールドと動画カーソルをDB末尾から復元し、常駐スレッドを起こす。"""
    global _data, _board, _log, _get_cfg, _get_suffix, _vid_id, _dead
    _data = Path(data_dir)
    _board, _log, _get_cfg = to_board_text, logger, get_cfg
    _get_suffix = get_suffix or (lambda: "")
    vp = _data / "videos.json"
    if vp.exists():
        try:
            _titles.update(json.loads(vp.read_text(encoding="utf-8")))
        except (json.JSONDecodeError, OSError):
            pass
    for sfx in ("", "_en"):
        dp = _diary_path(sfx)
        if dp.exists():
            for line in dp.read_text(encoding="utf-8").splitlines()[-3:]:
                try:
                    _diary[sfx].append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    try:
        c = growth._connect()
        row = c.execute("select id, location, world_id, world_name from gamelog_location"
                        " order by id desc limit 1").fetchone()
        if row:
            rowid, loc, wid, wname = row
            visits = c.execute("select count(*) from gamelog_location"
                               " where world_id=? and id<=?", (wid, rowid)).fetchone()[0]
            _on_location(rowid, wid, wname, _itype(loc), visits,
                         _stay_windows(c, wid, rowid), announce=False)
        v = c.execute("select max(id) from gamelog_video_play").fetchone()
        _vid_id = (v and v[0]) or 0
        c.close()
        _log(f"状況: {status_line() or '(まだなにも)'}")
    except (sqlite3.Error, OSError) as e:
        _dead = True
        _log(f"状況: VRCXが読めないため休止({e})")
    threading.Thread(target=_resolver, daemon=True).start()
    threading.Thread(target=_diarist, daemon=True).start()


def reload_diary():
    """日記ファイルが外部で変わった(単語けし等)とき、メモリの直近3件を読み直す"""
    if not _data:
        return
    for sfx in ("", "_en"):
        del _diary[sfx][:]
        dp = _diary_path(sfx)
        if dp.exists():
            for line in dp.read_text(encoding="utf-8").splitlines()[-3:]:
                try:
                    _diary[sfx].append(json.loads(line))
                except json.JSONDecodeError:
                    pass

def reload_titles():
    """動画タイトルキャッシュがUIから消されたとき、メモリ上のキャッシュも読み直す"""
    if not _data:
        return
    _titles.clear()
    vp = _data / "videos.json"
    if vp.exists():
        try:
            _titles.update(json.loads(vp.read_text(encoding="utf-8")))
        except (json.JSONDecodeError, OSError):
            pass


def reload_memory():
    """おもいでを現在の界隈側の会話ファイルから引き直す(界隈切替・ワールド移動時)"""
    global _memory
    lines = []
    p = _data and _conv_path()
    if _windows and p and p.exists():
        try:
            rows = [json.loads(l) for l in
                    p.read_text(encoding="utf-8").splitlines() if l.strip()]
            lines = _lines_in_windows(rows, _windows)
        except (json.JSONDecodeError, OSError):
            pass
    _memory = " ／ ".join(lines)
    return lines


# ---------------------------------------------------------------- 純関数(テスト対象)
_YT_RE = re.compile(r"(?:youtu\.be/|/shorts/|/live/|[?&]v=)([\w-]{11})")


def _yt_id(url):
    """URL→YouTubeの11文字ID。watch/youtu.be/shorts表記ゆれを吸収。非YouTubeはNone"""
    m = _YT_RE.search(url or "")
    return m.group(1) if m else None


def _itype(location):
    """locationのインスタンス種別タグ→ひらがな名"""
    loc = location or ""
    for tag, name in (("~hidden", "ふれんどぷらす"), ("~friends", "ふれんど"),
                      ("~private", "しょうたい"), ("~group", "ぐるーぷ")):
        if tag in loc:
            return name
    return "ぱぶりっく"


def _sum_play(rows, now):
    """[(created_at_iso, time_ms)]→時間。timeが空(いまいる部屋)はnowまでを数える。
    ponytail: 日またぎのインスタンスは入室日に全部つく。ズレて困ったら区間クリップ"""
    sec = 0.0
    for iso, ms in rows:
        if ms:
            sec += float(ms) / 1000
        else:
            t0 = growth._to_epoch(iso)
            if t0:
                sec += max(0.0, now - t0)
    return sec / 3600


def _lines_in_windows(rows, windows, limit=3):
    """会話行(dictの列)からtsが滞在窓に入るものを新しい方からlimit件、40字切り(古い順で返す)"""
    out = []
    for r in reversed(rows):
        ts = r.get("ts", 0)
        if any(a <= ts <= b for a, b in windows):
            t = re.sub(r"^\[[^\]]+\] ", "", str(r.get("text", "")))[:40]
            if t:
                out.append(t)
                if len(out) >= limit:
                    break
    return out[::-1]


def _diary_input(date, worlds, met, songs, hours, conv, en=False):
    """日記の材料をLLMに渡す形に。データにあるものだけ並べる"""
    if en:
        out = [f"date: {date}", f"hours played: {hours:.1f}"]
        if worlds:
            out.append("places: " + ", ".join(worlds[:6]))
        if met:
            out.append("people met: " + ", ".join(met[:6]))
        if songs:
            out.append("songs: " + ", ".join(s[:30] for s in songs[:5]))
        if conv:
            out.append("conversation bits: " + " / ".join(conv))
        return "\n".join(out)
    out = [f"ひづけ: {date}", f"あそんだじかん: {hours:.1f}時間"]
    if worlds:
        out.append("いったばしょ: " + "、".join(worlds[:6]))
    if met:
        out.append("あったひと: " + "、".join(met[:6]))
    if songs:
        out.append("ながれたきょく: " + "、".join(s[:30] for s in songs[:5]))
    if conv:
        out.append("かいわのきれはし: " + " ／ ".join(conv))
    return "\n".join(out)


# ---------------------------------------------------------------- 状態更新
def _stay_windows(c, world_id, before_id, limit=20):
    """このワールドの過去の滞在時間帯[(開始epoch, 終了epoch)]。おもいで検索用"""
    out = []
    for ca, ms in c.execute("select created_at, time from gamelog_location"
                            " where world_id=? and id<? order by id desc limit ?",
                            (world_id, before_id, limit)):
        t0 = growth._to_epoch(ca)
        if t0 and ms:
            out.append((t0, t0 + float(ms) / 1000))
    return out


def _board_ok(text):
    """盤面で出せる名前か(growthの挨拶ガードと同じ基準)"""
    b = _board(text) if _board else text
    return bool(b) and len(b) * 2 >= len(text)


def _on_location(rowid, world_id, world_name, itype, visits, windows, announce=True):
    """ワールド移動1件を状態に反映。おもいでを引き、たまに一言キューに積む"""
    global _world, _windows
    _world = {"row": rowid, "id": world_id, "name": world_name,
              "visits": visits, "itype": itype}
    _windows = windows or []
    lines = reload_memory()
    if not announce or random.random() >= float(_cfg("world_comment_chance")):
        return
    name = world_name if world_name and _board_ok(world_name) else ""
    if lines:
        _set_comment(f"（{name or 'このばしょ'}にまたきた。まえにここで"
                     f"「{lines[-1]}」というはなしをした。ひとこと）")
    elif visits > 1:
        _set_comment(f"（ばしょが{name or 'べつのばしょ'}にかわった。"
                     f"{visits}かいめ。ひとこと）")
    else:
        _set_comment(f"（{name or 'あたらしいばしょ'}にきた。はじめてのばしょ。ひとこと）")


def _set_comment(text):
    global _comment_q
    _comment_q = (text, time.time())


def _pop_comment(quiet):
    """会話の切れ目まで保持、2分で失効(growth._pop_greetと同じ)"""
    global _comment_q
    if _comment_q is None:
        return None
    text, ts = _comment_q
    if time.time() - ts > 120:
        _comment_q = None
        return None
    if not quiet:
        return None
    _comment_q = None
    return text


def poll(now, quiet=True):
    """メインループから毎周期呼ぶ。5秒ごとにDBを見て、quietのときだけ一言を返す。"""
    global _last_poll, _vid_id, _song, _playtime_h, _last_care
    if not _cfg("vrcx_enabled") or not _cfg("advanced_sense_enabled"):
        return None
    if _dead or now - _last_poll < POLL_IV:
        return _pop_comment(quiet)
    _last_poll = now
    try:
        c = growth._connect()
        # ワールド移動
        last_row = _world["row"] if _world else 0
        for rowid, loc, wid, wname in c.execute(
                "select id, location, world_id, world_name from gamelog_location"
                " where id > ? order by id", (last_row,)):
            visits = c.execute("select count(*) from gamelog_location"
                               " where world_id=? and id<=?", (wid, rowid)).fetchone()[0]
            _on_location(rowid, wid, wname, _itype(loc), visits,
                         _stay_windows(c, wid, rowid))
        # 動画・曲
        for rowid, url in c.execute(
                "select id, video_url from gamelog_video_play where id > ?"
                " order by id", (_vid_id,)):
            _vid_id = rowid
            ytid = _yt_id(url)
            if not ytid:
                continue
            plays = c.execute("select count(*) from gamelog_video_play"
                              " where video_url like ?", (f"%{ytid}%",)).fetchone()[0]
            _song = {"ytid": ytid, "url": url, "plays": plays, "ts": now, "said": False}
            if ytid not in _titles and ytid not in _bad:
                _fetch_q.put(ytid)
        # 曲コメント(タイトル解決を待って一回だけ)
        if _song and not _song["said"] and now - _song["ts"] < SONG_TTL:
            title = _titles.get(_song["ytid"])
            if title:
                _song["said"] = True
                if (random.random() < float(_cfg("song_comment_chance"))
                        and _board_ok(title)):
                    rep = f"。きくのは{_song['plays']}かいめ" if _song["plays"] > 1 else ""
                    _set_comment(f"（いま「{title}」がながれはじめた{rep}。ひとこと）")
        # よふかしケア
        ch = float(_cfg("care_hours"))
        if ch > 0:
            lt = time.localtime(now)
            since_mid = lt.tm_hour * 3600 + lt.tm_min * 60 + lt.tm_sec
            day0 = now - ((since_mid - 6 * 3600) % 86400)   # ponytail: 一日の境界はあさ6時固定
            rows = c.execute("select created_at, time from gamelog_location"
                             " where created_at >= ?",
                             (time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(day0)),)
                             ).fetchall()
            _playtime_h = _sum_play(rows, now)
            hour_ok = lt.tm_hour >= int(_cfg("care_hour")) or lt.tm_hour < 6
            if _playtime_h >= ch and hour_ok and now - _last_care > CARE_IV:
                _last_care = now
                _set_comment(f"（きょうもう{int(_playtime_h)}じかんあそんでいる。"
                             "よふかしの飼い主をきづかうひとこと）")
        else:
            _playtime_h = 0.0
        c.close()
    except (sqlite3.Error, OSError):
        pass   # VRCX一時停止中など。次の周期でまた試す
    return _pop_comment(quiet)


# ---------------------------------------------------------------- プロンプト・UI
def prompt_lines(en=False):
    """system_prompt末尾に足す状況行。データ形だけで形容詞・文型は注入しない(アトラクタ対策)"""
    if not _cfg("vrcx_enabled") or not _cfg("advanced_sense_enabled"):
        return ""
    now = time.time()
    out = ""
    if _world:
        out += (f"Current place: {_world['name']} (visit #{_world['visits']}). " if en
                else f"いまのばしょ: {_world['name']}"
                     f"({_world['visits']}かいめ・{_world['itype']})。")
    if _song and now - _song["ts"] < SONG_TTL:
        t = _titles.get(_song["ytid"])
        if t:
            out += (f"Now playing: {t} (x{_song['plays']}). " if en
                    else f"いまのきょく: {t}({_song['plays']}かいめ)。")
    if _memory and _cfg("memory_conversation_enabled"):
        out += (f"Memories of this place: {_memory}. " if en
                else f"このばしょのおもいで: {_memory}。")
    ch = float(_cfg("care_hours"))
    if ch > 0 and _playtime_h >= ch:
        out += (f"Owner has played {_playtime_h:.0f}h today. " if en
                else f"きょうのぷれいじかん: {int(_playtime_h)}じかん。")
    d = _diary["_en" if en else ""] if _cfg("memory_diary_enabled") else []
    if d:
        ent = " ／ ".join(f"{int(e['date'][5:7])}/{int(e['date'][8:10])} {e['text'][:60]}"
                          for e in d[-3:])
        out += (f"Recent days: {ent}. " if en else f"さいきんのできごと: {ent}。")
    return out



def world_context(en=False):
    """Return the current world name for the local LLM, without world IDs."""
    if _dead or not _world:
        return ""
    name = str(_world.get("name") or "").strip()
    if not name or len(name) > 64:
        return ""
    if any(ord(ch) < 32 or ord(ch) == 127 for ch in name):
        return ""
    return f"Current world: {name}" if en else f"いまのワールド：{name}"

def status_line():
    """設定UIの/status用。プレーンテキスト"""
    parts = []
    if _world:
        parts.append(f"{_world['name']}({_world['visits']}かいめ)")
    if _song and time.time() - _song["ts"] < SONG_TTL:
        t = _titles.get(_song["ytid"])
        if t:
            parts.append("♪" + t[:30])
    if _playtime_h:
        parts.append(f"きょう{_playtime_h:.1f}h")
    return "　".join(parts)


# ---------------------------------------------------------------- 常駐スレッド
def _resolver():
    """oEmbedでYouTubeタイトルを解決してvideos.jsonへ。このスレッドだけが書く"""
    while True:
        ytid = _fetch_q.get()
        if ytid in _titles or ytid in _bad:
            continue
        try:
            u = urllib.parse.quote(f"https://www.youtube.com/watch?v={ytid}", safe="")
            req = urllib.request.Request(
                f"https://www.youtube.com/oembed?url={u}&format=json",
                headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=5) as r:
                title = (json.load(r).get("title") or "").strip()
        except Exception:
            title = ""
        if not title:
            _bad.add(ytid)
            continue
        _titles[ytid] = title[:80]
        try:
            tmp = _data / "videos.tmp"
            tmp.write_text(json.dumps(_titles, ensure_ascii=False, indent=0),
                           encoding="utf-8")
            os.replace(tmp, _data / "videos.json")
        except OSError:
            pass
        _log(f"きょく: {title[:50]}")


def _diarist():
    """1時間ごとに「書くべき日記がないか」を見る。書くのは最新の完了プレイ日1件だけ"""
    time.sleep(60)   # 起動直後(ウォームアップ・自己チェック)をさける
    while True:
        try:
            if (_cfg("vrcx_enabled") and _cfg("advanced_sense_enabled")
                    and _cfg("memory_diary_enabled") and _cfg("diary")):
                _write_diary()
        except Exception as e:
            _log(f"にっき失敗: {e}")
        time.sleep(3600)


def _llm(system, user, timeout=120, model=""):
    """日記用の生LLM呼び出し。盤面用ペルソナを混ぜないためollama_chatは使わない"""
    model = model or (_get_cfg().get("model") if _get_cfg else "") or "qwen3:30b"
    payload = {"model": model, "stream": False, "keep_alive": -1,
               "messages": [{"role": "system", "content": system},
                            {"role": "user", "content": user}],
               "options": {"num_ctx": 8192, "num_predict": 800},
               "think": False}
    for _ in range(2):
        req = urllib.request.Request("http://localhost:11434/api/chat",
                                     json.dumps(payload).encode(),
                                     {"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                out = json.loads(r.read())["message"]["content"]
            return re.sub(r"<think>.*?</think>", "", out, flags=re.S).strip()
        except urllib.error.HTTPError as e:
            if e.code == 400 and "think" in payload:
                payload.pop("think")   # think指定を受け付けないモデル
                continue
            raise
    return ""


def _day_conv(sfx, d0):
    """その日にその界隈の会話ファイルへ書かれた行(話者タグ剥がし・40字切り)"""
    out = []
    if not _data:
        return out
    p = _conv_path(sfx)
    if p.exists():
        for line in p.read_text(encoding="utf-8").splitlines():
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                continue
            if d0 <= r.get("ts", 0) < d0 + 86400:
                t = re.sub(r"^\[[^\]]+\] ", "", str(r.get("text", "")))[:40]
                if t:
                    out.append(t)
    return out


def _gen_diary(sfx, target, d0, worlds, met, songs, hours):
    """1界隈ぶんの日記本文を生成。EN側はその日のEN会話がなければ書かない"""
    conv = _day_conv(sfx, d0) if _cfg("memory_conversation_enabled") else []
    if sfx and not conv:
        return ""
    en = bool(sfx)
    cfg = _get_cfg() if _get_cfg else {}
    pn = str(cfg.get("pet_name") or "むちこ")
    pe = str(cfg.get("pet_name_en") or "muchiko")
    if en:
        sys = ("You are '" + pe + "', a small pet creature living in VRChat. "
               "Write yesterday's diary as yourself in first person. "
               "2-3 short sentences, 100 letters max, lowercase english only. "
               "Use place/people/song names as-is from the data. "
               "Never invent things not in the data. No bullet lists. "
               "Don't call yourself '" + pe + "'.")
        model = str(cfg.get("model_en") or "")
    else:
        sys = ("あなたはVRChatにすむペットの謎生物「" + pn + "」。きのうのじぶんの日記を一人称でかく。"
               "ひらがなだけで2〜3文、ぜんぶで100字いない。ばしょ・ひと・きょくのなまえは"
               "データのまま入れてよい(英語のままでよい)。データにないことは書かない。"
               "かじょうがきにしない。じぶんを「" + pn + "は」と呼ばない。")
        model = ""
    text = _llm(sys, _diary_input(target, worlds, met, songs, hours, conv[-8:], en=en),
                model=model)
    text = " ".join(text.split())[:200]
    end = "." if en else "。"
    if text and not text.endswith(end) and end in text:
        text = text[:text.rfind(end)]   # 途中で切れた最後の文は捨てる
    return text.rstrip(end)


def _append_diary(sfx, target, text):
    with _diary_path(sfx).open("a", encoding="utf-8") as f:
        f.write(json.dumps({"date": target, "text": text}, ensure_ascii=False) + "\n")
    _diary[sfx].append({"date": target, "text": text})
    del _diary[sfx][:-3]


def _write_diary():
    """最新の完了プレイ日の日記がまだなければ、生成して1件追記+ひとことつぶやく"""
    today = time.strftime("%Y-%m-%d")
    last = _diary[""][-1]["date"] if _diary[""] else ""   # 日付カーソルはJP側が持つ
    c = growth._connect()
    days = {}   # ローカル日付 -> [(created_at, time_ms, world_name)]
    for ca, ms, wname in c.execute(
            "select created_at, time, world_name from gamelog_location"
            " where created_at >= ? order by id",
            (time.strftime("%Y-%m-%dT00:00:00",
                           time.gmtime(time.time() - 14 * 86400)),)):
        d = time.strftime("%Y-%m-%d", time.localtime(growth._to_epoch(ca)))
        days.setdefault(d, []).append((ca, ms, wname))
    target = max((d for d in days if last < d < today), default="")
    if not target:
        c.close()
        return
    rows = days[target]
    d0 = time.mktime(time.strptime(target, "%Y-%m-%d"))
    iso0 = time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(d0))
    iso1 = time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(d0 + 86400))
    hours = _sum_play([(ca, ms) for ca, ms, _ in rows], min(time.time(), d0 + 86400))
    worlds = []
    for _, _, w in rows:
        if w and w not in worlds:
            worlds.append(w)
    met = []
    for uid, nm in c.execute(
            "select distinct user_id, display_name from gamelog_join_leave"
            " where type='OnPlayerJoined' and created_at >= ? and created_at < ?",
            (iso0, iso1)):
        if uid in growth._friends:
            n = growth.display_name(uid) or nm
            if n not in met:
                met.append(n)
    songs = []
    for (url,) in c.execute("select video_url from gamelog_video_play"
                            " where created_at >= ? and created_at < ?", (iso0, iso1)):
        t = _titles.get(_yt_id(url) or "")
        if t and t not in songs:
            songs.append(t)
    c.close()
    # JP側(日付カーソルの本流)。失敗ならカーソルが進まず次の時間に再挑戦
    text = _gen_diary("", target, d0, worlds, met, songs, hours)
    if text:
        _append_diary("", target, text)
        _log(f"にっき({target}): {text}")
        _set_comment(f"（きのうのにっきをかいた:「{text[:60]}」。ないようにふれてひとこと）")
    # EN側: その日のEN会話があるときだけ。JP失敗の再挑戦で二重書きしないようガード
    if not (_diary["_en"] and _diary["_en"][-1]["date"] >= target):
        text = _gen_diary("_en", target, d0, worlds, met, songs, hours)
        if text:
            _append_diary("_en", target, text)
            _log(f"diary({target}): {text}")


# ---------------------------------------------------------------- 自己チェック
if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")
    assert _yt_id("https://youtu.be/Bu5D58xdVCQ?si=rhrl") == "Bu5D58xdVCQ"
    assert _yt_id("https://www.youtube.com/watch?v=5e3RMzHcbqs") == "5e3RMzHcbqs"
    assert _yt_id("https://youtube.com/shorts/abcDEF12-_x") == "abcDEF12-_x"
    assert _yt_id("https://www.twitch.tv/somebody") is None
    assert _itype("wrld_x:1~hidden(usr_y)~region(jp)") == "ふれんどぷらす"
    assert _itype("wrld_x:1~region(jp)") == "ぱぶりっく"
    assert abs(_sum_play([("2026-07-30T00:00:00.000Z", 3600000)], 0) - 1.0) < 1e-9
    assert abs(_sum_play([("2026-07-30T00:00:00.000Z", None)],
                         growth._to_epoch("2026-07-30T01:00:00.000Z")) - 1.0) < 1e-9
    rows = [{"ts": 5, "text": "[とろ] たいやきのはなし"}, {"ts": 50, "text": "そとのはなし"}]
    assert _lines_in_windows(rows, [(0, 10)]) == ["たいやきのはなし"]
    assert _lines_in_windows(rows, [(0, 100)], limit=1) == ["そとのはなし"]
    assert "いったばしょ" in _diary_input("2026-07-30", ["Snow Rotunda"], [], [], 2.0, [])
    assert "places:" in _diary_input("2026-07-30", ["Snow Rotunda"], [], [], 2.0, [], en=True)
    # ライブ読み(VRCXが無ければ休止表示のみ)
    init(Path(__file__).parent / "data", lambda s: s)
    if not _dead:
        print("いまのばしょ:", _world and
              f"{_world['name']} {_world['visits']}かいめ {_world['itype']}")
        print("prompt:", prompt_lines() or "(なし)")
        print("status:", status_line() or "(なし)")
    print("ok")
