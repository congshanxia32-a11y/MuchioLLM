#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""成長機能 — 人を覚える(VRCXのSQLite読み) + なつき度。stdlibのみ。

python growth.py で自己チェック(VRCX DBを読んで在室フレンド表示 + assert数個)。
"""
import calendar, json, os, sqlite3, threading, time, unicodedata
from pathlib import Path

VRCX_DB = Path(os.environ.get("APPDATA", "")) / "VRCX" / "VRCX.sqlite3"
POLL_IV = 5.0          # VRCXを実際に見に行く間隔秒
SAVE_IV = 60.0         # growth.json保存の最短間隔秒
BOND_CAP = 50.0

# UIから調整できるノブ(config.json)。ここはmuchio側DEFAULTSと同値のフォールバック
_KNOBS = {
    "bond_gain": 1.0,          # なつきやすさ(倍率)
    "bond_halflife_days": 5.8, # なつき度の半減期(日)。旧実装の0.995^h≒5.76日相当
    "tier_regular": 10,        # 「よくあうこ」になる会った日数
    "absence_days": 14,        # 「ひさしぶり」判定(日)
    "auto_adopt_days": 5,      # フレンド外でも、会った日数がこれ以上なら自動でなかま入り(0=しない)
}

_state = {"bond": 0.0, "bond_ts": 0.0, "people": {}}
_path = None           # data/growth.json
_owner = ""
_board = None          # to_board_text
_log = print
_get_cfg = None        # muchioのCFGを覗くcallable(ホットリロード追従)


def _cfg(key):
    if _get_cfg:
        v = _get_cfg().get(key)
        if v is not None:
            return v
    return _KNOBS[key]

_friends = {}          # user_id -> display_name (自分を除く)
_present = set()       # いま同じインスタンスにいるフレンドのuser_id
_greeted = set()       # このインスタンスで挨拶済み
_greet_q = None        # 次に出す挨拶プロンプト(最新1件だけ)
_last_poll = 0.0
_last_save = 0.0
_dirty = False
_last_id = 0           # gamelog_join_leave の読み込み済みid
_loc_ts = ""           # 現インスタンスの入室時刻(gamelog_location)
_loc_epoch = 0.0       # 同上のepoch(met二重カウント防止用)
_dead = False          # VRCXが読めない→この起動中は休止
_anniv = {}            # uid -> 満N年。きょうがフレンド記念日の人だけ(日次で引き直す)
_anniv_day = ""        # _annivを計算した日付
_own = set()           # 自分のアカウント(ダッシュ無しhex)。自分をなかま扱いしないため


def _to_epoch(iso):
    """'2026-07-29T22:44:05.000Z' → epoch秒。失敗したら0"""
    try:
        return calendar.timegm(time.strptime(iso[:19], "%Y-%m-%dT%H:%M:%S"))
    except (ValueError, TypeError):
        return 0.0


def _uid_hex(uid):
    """'usr_deadbeef-1234-...' → 'deadbeef1234...'(ダッシュ抜きhex)。
    テーブル名のプレフィックス(ダッシュ無し)と突き合わせるための正規化"""
    return uid.replace("-", "")[4:]


def init(data_dir, owner_name, to_board_text, logger=print, get_cfg=None):
    """起動時1回。フレンド一覧を読み、現インスタンスの在室を復元する。"""
    global _path, _owner, _board, _log, _get_cfg, _friends, _last_id, _loc_ts, _loc_epoch, _dead
    _path = Path(data_dir) / "growth.json"
    _owner, _board, _log, _get_cfg = owner_name, to_board_text, logger, get_cfg
    if _path.exists():
        try:
            _state.update(json.loads(_path.read_text(encoding="utf-8")))
        except (json.JSONDecodeError, OSError):
            pass
    else:
        # 初回だけ: これまでの会話量からなつき度をシード(急に「よそよそしい」化しない)
        conv = Path(data_dir) / "conversation.jsonl"
        if conv.exists():
            n = sum(1 for l in conv.read_text(encoding="utf-8").splitlines()
                    if '"role": "user"' in l and "[friend]" not in l)
            _state["bond"] = min(BOND_CAP, n * 0.05)
            _state["bond_ts"] = time.time()
            _mark_dirty()
    # 手動登録(フレンド外の仲いい人)はフレンドと同じ扱いに合流させる
    for uid, p in _state["people"].items():
        if p.get("manual"):
            _friends[uid] = p["name"]
    try:
        c = _connect()
        own = _own   # 自分のアカウント(テーブル名のusrプレフィックス)
        for (t,) in c.execute("select name from sqlite_master where type='table'"
                              " and name like '%friend_log_current'"):
            own.add(t.split("_")[0][3:])   # 'usr<hex>_...' → ダッシュ無しhex
            for uid, nm in c.execute('select user_id, display_name from "%s"' % t):
                if nm != _owner:
                    _friends[uid] = nm
        for uid in [u for u in _friends if _uid_hex(u) in own]:
            _friends.pop(uid, None)   # 自分のalt垢をフレンド扱いしない(uidはダッシュ有り)
        if not _state["people"]:
            # 初回だけ: 過去ログから「会った日数」をシード(全員が「はじめて」にならないように)。
            # 日数で数えるのは、同日の再joinを1回の「会った」に潰すため
            for uid, days, last in c.execute(
                    "select user_id, count(distinct substr(created_at,1,10)),"
                    " max(created_at) from gamelog_join_leave"
                    " where type='OnPlayerJoined' group by user_id"):
                if uid in _friends:
                    _state["people"][uid] = {"name": _friends[uid], "met": days,
                                             "last": _to_epoch(last)}
            _mark_dirty()
        _load_anniv(c)
        row = c.execute("select created_at from gamelog_location"
                        " order by id desc limit 1").fetchone()
        _loc_ts = row[0] if row else ""
        _loc_epoch = _to_epoch(_loc_ts)
        for _id, typ, uid, nm in c.execute(
                "select id, type, user_id, display_name from gamelog_join_leave"
                " where created_at >= ? order by id", (_loc_ts,)):
            _last_id = _id
            _apply(typ, uid, nm, greet=False)   # 復元分は挨拶しない(入室済みの人に今さら言わない)
        c.close()
        _log(f"成長: フレンド{len(_friends)}人 在室{len(_present)}人"
             f" なつき{_state['bond']:.1f}")
    except (sqlite3.Error, OSError) as e:
        _dead = True
        _log(f"成長: VRCXが読めないため人の記憶は休止({e})。なつき度は動きます")


def _connect():
    c = sqlite3.connect(f"file:{VRCX_DB}?mode=ro", uri=True)
    c.execute("pragma query_only=1")
    return c


def _load_anniv(c):
    """フレンド成立日(friend_log_history)から、きょうが「まるN年」の人を拾う。
    ponytail: UTC日付で判定。時差の数時間ズレは気にしない"""
    global _anniv, _anniv_day
    _anniv_day = time.strftime("%Y-%m-%d", time.gmtime())
    _anniv = {}
    first = {}   # uid -> 最古の成立日時(複数アカウントの記録があれば早いほう)
    for (t,) in c.execute("select name from sqlite_master where type='table'"
                          " and name like '%friend_log_history'"):
        for uid, ts in c.execute('select user_id, min(created_at) from "%s"'
                                 " where type='Friend' group by user_id" % t):
            if ts and (uid not in first or ts < first[uid]):
                first[uid] = ts
    for uid, ts in first.items():
        years = int(_anniv_day[:4]) - int(ts[:4])
        if years >= 1 and ts[5:10] == _anniv_day[5:10]:
            _anniv[uid] = years


def _auto_adopt(uid, name):
    """フレンド外の人は、いま(この機能を入れた日)から会った回数を数えて、
    しきい値に届いたらなかま入り。過去ログはさかのぼらない。
    手動で忘れた人(declined)は二度と拾わない。"""
    days = int(_cfg("auto_adopt_days"))
    if not days or not name or uid in _state.get("declined", []):
        return False
    if name == _owner or _uid_hex(uid) in _own:   # 自分(alt垢ふくむ)はなかまじゃない
        return False
    s = _state.setdefault("seen", {}).setdefault(uid, {"name": name, "met": 0, "last": 0.0})
    s["name"] = name
    if s["last"] < _loc_epoch:   # 同じインスタンス内の再joinは1回に潰す
        s["met"] += 1
    s["last"] = time.time()
    _mark_dirty()
    if s["met"] < days:
        return False
    _state["seen"].pop(uid, None)
    _friends[uid] = name
    _state["people"][uid] = {"name": name, "met": s["met"], "last": s["last"],
                             "manual": True, "auto": True}
    _log(f"成長: {name} を自動でなかまにした(あった{s['met']}回)")
    return True


def _apply(typ, uid, name="", greet=True):
    """join/leaveイベント1件を在室集合に反映。新規在室なら記録+挨拶キュー。"""
    global _greet_q
    if uid not in _friends and not (typ == "OnPlayerJoined" and _auto_adopt(uid, name)):
        return
    if typ == "OnPlayerLeft":
        _present.discard(uid)
        return
    if typ != "OnPlayerJoined" or uid in _present:
        return
    _present.add(uid)
    p = _state["people"].setdefault(uid, {"name": _friends[uid], "met": 0, "last": 0.0})
    ago = time.time() - p["last"]
    if p["last"] < _loc_epoch:   # 同一インスタンス内の再joinやデーモン再起動で二重カウントしない
        p["met"] += 1
    p["last"] = time.time()
    p["name"] = _friends[uid]
    _mark_dirty()
    if not greet or uid in _greeted:
        return
    _greeted.add(uid)
    if p.get("greet") is False:   # この人には挨拶しない設定(記録は続ける)
        return
    name = p.get("nick") or _friends[uid]   # あだ名があればそれで呼ぶ
    b = _board(name)
    if not b or len(b) * 2 < len(name):   # 盤面で出せない名前は呼ばない(記録だけ)
        return
    tier = _tier(p["met"], ago)
    extra = (f"。きょうでともだちになってまる{_anniv[uid]}ねん"
             if uid in _anniv else "")
    _greet_q = (f"（なかまの{name}がきた。{tier}{extra}）", time.time())


_TIER_EN = {"はじめてあうこ": "first time meeting", "ひさしぶりにあうこ": "long time no see",
            "よくあうこ": "a regular", "たまにあうこ": "meet sometimes"}


def _tier(met, ago_sec, en=False):
    if met <= 1:
        t = "はじめてあうこ"
    elif ago_sec > float(_cfg("absence_days")) * 86400:
        t = "ひさしぶりにあうこ"
    else:
        t = "よくあうこ" if met >= int(_cfg("tier_regular")) else "たまにあうこ"
    return _TIER_EN[t] if en else t


def poll(now, quiet=True):
    """メインループから毎周期呼ぶ。quiet(会話の切れ目)のときだけ挨拶プロンプトを返す。"""
    global _last_poll, _last_id, _loc_ts, _loc_epoch, _greet_q
    if _dead or now - _last_poll < POLL_IV:
        return _pop_greet(quiet)
    _last_poll = now
    try:
        c = _connect()
        if _anniv_day != time.strftime("%Y-%m-%d", time.gmtime()):
            _load_anniv(c)   # 日付が変わったら記念日を引き直す
        row = c.execute("select created_at from gamelog_location"
                        " order by id desc limit 1").fetchone()
        if row and row[0] != _loc_ts:   # インスタンス移動→在室と挨拶済みをリセット
            _loc_ts = row[0]
            _loc_epoch = _to_epoch(_loc_ts)
            _present.clear()
            _greeted.clear()
            _greet_q = None
        for _id, typ, uid, nm in c.execute(
                "select id, type, user_id, display_name from gamelog_join_leave"
                " where id > ? order by id", (_last_id,)):
            _last_id = _id
            _apply(typ, uid, nm)
        c.close()
    except (sqlite3.Error, OSError):
        pass   # VRCX一時停止中など。次の周期でまた試す
    _save_maybe(now)
    return _pop_greet(quiet)


def _pop_greet(quiet):
    """会話の切れ目が来るまで保持。2分待っても出せなかったら捨てる(遅れた挨拶は不気味)。"""
    global _greet_q
    if _greet_q is None:
        return None
    text, ts = _greet_q
    if time.time() - ts > 120:
        _greet_q = None
        return None
    if not quiet:
        return None
    _greet_q = None
    return text


# ---------------------------------------------------------------- 界隈(言語)
def hear_lang(lang, uid=None):
    """フレンドの声の言語を界隈票として積む。uid指定(声紋一致)なら本人だけに正確に入れる。
    ponytail: 無記名時は在室全員に投票=混在部屋では濁るが、セッションを重ねると多数決で収束する"""
    if lang not in ("ja", "en"):
        return
    targets = [uid] if uid else _present
    for u in targets:
        p = _state["people"].get(u)
        if p is not None:
            v = p.setdefault("langs", {})
            v[lang] = v.get(lang, 0) + 1
    if targets:
        _mark_dirty()


def _person_lang(p):
    v = p.get("langs") or {}
    if sum(v.values()) < 5:   # 票が少ないうちは判定しない
        return None
    return "en" if v.get("en", 0) > v.get("ja", 0) else "jp"


def circle_lang():
    """在室フレンドの界隈の多数決。"en"/"jp"、判定不能(無人・票不足・同数)はNone"""
    votes = []
    for uid in _present:
        p = _state["people"].get(uid)
        l = _person_lang(p) if p else None
        if l:
            votes.append(l)
    en, jp = votes.count("en"), votes.count("jp")
    if en == jp:
        return None
    return "en" if en > jp else "jp"


# ---------------------------------------------------------------- なつき度
def _decay():
    now = time.time()
    if _state["bond_ts"]:
        h = (now - _state["bond_ts"]) / 3600
        rate = 0.5 ** (1 / (24 * max(0.02, float(_cfg("bond_halflife_days")))))
        _state["bond"] *= rate ** h
    _state["bond_ts"] = now


def bump(named):
    _decay()
    gain = float(_cfg("bond_gain")) * (0.5 if named else 0.05)
    _state["bond"] = min(BOND_CAP, _state["bond"] + gain)
    _mark_dirty()


def bond():
    _decay()
    return _state["bond"]


def prompt_lines(en=False):
    """system_promptの末尾に足す1〜2行。単語リストだけで文型は注入しない。"""
    out = ""
    names = []
    for uid in _present:
        p = _state["people"].get(uid)
        disp = p and (p.get("nick") or p["name"])
        if p and _board(disp):
            t = _tier(p["met"], 0, en)
            names.append(f"{disp}({t}, met {p['met']} days)" if en
                         else f"{disp}({t}・あった{p['met']}日)")
    if names:
        out += (("Friends here now: " + ", ".join(names[:5]) + ". ") if en
                else "いまいるフレンド: " + "、".join(names[:5]) + "。")
    b = bond()
    if b < 5:
        out += ("You barely know your owner yet; be distant and brief. " if en
                else "まだ飼い主とはよそよそしい。みじかく、そっけなく返す。")
    elif b >= 25:
        out += ("You are very attached to your owner; speak bluntly and freely. " if en
                else "飼い主にはとてもなついている。えんりょなくずけずけ言う。")
    return out


# ---------------------------------------------------------------- UI向けAPI
def bond_stage(b=None):
    b = bond() if b is None else b
    return "よそよそしい" if b < 5 else ("べったり" if b >= 25 else "ふつう")


def display_name(uid):
    """uid→むちこが呼ぶ名前(あだ名優先)。知らない人はNone"""
    p = _state["people"].get(uid) if uid else None
    return (p.get("nick") or p["name"]) if p else None


def present_names():
    """いま在室のなかま(あだ名優先)。ステータス表示用"""
    out = []
    for uid in _present:
        p = _state["people"].get(uid)
        if p:
            out.append(p.get("nick") or p["name"])
    return sorted(out)


def poke_names():
    """ちょっかいを出していい在室のなかま(poke=Falseの人を除く)"""
    out = []
    for uid in _present:
        p = _state["people"].get(uid)
        if p and p.get("poke") is not False:
            out.append(p.get("nick") or p["name"])
    return sorted(out)



SOCIAL_NAME_MAX = 24
SOCIAL_NAME_LIMIT = 5


def _social_name(value):
    """Return a safe, displayable name for the local LLM context."""
    raw = str(value or "").strip()
    if not raw or len(raw) > SOCIAL_NAME_MAX:
        return ""
    if any(unicodedata.category(ch).startswith("C") for ch in raw):
        return ""
    return raw


def social_context(en=False, max_names=SOCIAL_NAME_LIMIT):
    """Build compact local owner/friend context without exposing user IDs."""
    if _dead:
        return ""
    names = []
    seen = set()
    try:
        limit = min(SOCIAL_NAME_LIMIT, max(0, int(max_names)))
    except (TypeError, ValueError):
        limit = SOCIAL_NAME_LIMIT
    for uid in sorted(_present):
        p = _state.get("people", {}).get(uid)
        if not p:
            continue
        name = _social_name(p.get("nick") or p.get("name"))
        if not name or name.casefold() in seen:
            continue
        if _board:
            board_name = _board(name)
            if not board_name or len(board_name) * 2 < len(name):
                continue
        seen.add(name.casefold())
        names.append(name)
        if len(names) >= limit:
            break

    owner_name = _social_name(_owner)
    if en:
        parts = ([f"Owner: {owner_name}."] if owner_name else [])
        if names:
            parts.append("Friends here now: " + ", ".join(names) + ".")
        b = bond()
        relation = "very attached" if b >= 25 else ("still getting close" if b < 5 else "friendly")
        if owner_name:
            parts.append(f"Relationship with owner: {relation}.")
        return " ".join(parts)

    parts = ([f"\u4e3b\u4eba\uff1a{owner_name}\u3002"] if owner_name else [])
    if names:
        parts.append("\u3044\u307e\u8fd1\u304f\u306b\u3044\u308b\u53cb\u9054\uff1a" + "\u3001".join(names) + "\u3002")
    b = bond()
    relation = "\u304b\u306a\u308a\u89aa\u3057\u3044" if b >= 25 else ("\u307e\u3060\u5c11\u3057\u8ddd\u96e2\u304c\u3042\u308b" if b < 5 else "\u89aa\u3057\u3044")
    if owner_name:
        parts.append(f"\u4e3b\u4eba\u3068\u306e\u95a2\u4fc2\uff1a{relation}\u3002")
    return "".join(parts)

def remove(uid):
    """人の記録を削除。手動登録(manual)なら登録自体を解除=以後いない人あつかい。
    フレンドは記録が消えるだけで、次に会えばまた「はじめて」から数え直す"""
    p = _state["people"].pop(uid, None)
    if p is None:
        return False
    if p.get("manual"):
        _friends.pop(uid, None)
    if p.get("auto"):   # 自動で拾った人は、忘れたあと勝手に戻ってこないようにする
        _state.setdefault("declined", []).append(uid)
    _present.discard(uid)
    _greeted.discard(uid)
    _mark_dirty()
    _save_now()
    return True


def snapshot():
    """なかま一覧(UI用)。在室が先、あとは会った日数降順"""
    out = []
    for uid, p in _state["people"].items():
        disp = p.get("nick") or p["name"]
        b = _board(disp) if _board else disp
        out.append({"uid": uid, "name": p["name"], "nick": p.get("nick", ""),
                    "met": p["met"], "last": p["last"],
                    "lang": _person_lang(p) or "",
                    "greet": p.get("greet") is not False,
                    "poke": p.get("poke") is not False,
                    "here": uid in _present, "manual": bool(p.get("manual")),
                    "auto": bool(p.get("auto")),
                    "board_ok": bool(b) and len(b) * 2 >= len(disp)})
    out.sort(key=lambda r: (not r["here"], -r["met"]))
    return out


def set_person(uid, nick=None, greet=None, poke=None):
    """UIからのあだ名・挨拶・ちょっかい設定。即保存"""
    p = _state["people"].get(uid)
    if not p:
        return False
    if nick is not None:
        nick = nick.strip()[:24]
        if nick:
            p["nick"] = nick
        else:
            p.pop("nick", None)
    for key, val in (("greet", greet), ("poke", poke)):
        if val is not None:
            if val:
                p.pop(key, None)   # 既定値はキーを持たない(JSONを太らせない)
            else:
                p[key] = False
    _mark_dirty()
    _save_now()
    return True


def adopt(uid, name):
    """フレンドじゃない仲いい人を手動登録。過去ログから会った日数もシードする"""
    _friends[uid] = name
    p = _state["people"].setdefault(uid, {"name": name, "met": 0, "last": 0.0})
    p["manual"] = True
    p["name"] = name
    try:
        c = _connect()
        row = c.execute(
            "select count(distinct substr(created_at,1,10)), max(created_at)"
            " from gamelog_join_leave where user_id=? and type='OnPlayerJoined'",
            (uid,)).fetchone()
        c.close()
        if row and row[0]:
            p["met"] = max(p["met"], row[0])
            p["last"] = max(p["last"], _to_epoch(row[1]))
    except (sqlite3.Error, OSError):
        pass
    _mark_dirty()
    _save_now()
    return True


def lookup(q):
    """VRCXログからフレンド外・未登録の人を名前で検索(手動登録用)"""
    q = (q or "").strip()
    if len(q) < 2 or _dead:
        return []
    out = []
    try:
        c = _connect()
        for uid, name, days, last in c.execute(
                "select user_id, display_name, count(distinct substr(created_at,1,10)),"
                " max(created_at) from gamelog_join_leave"
                " where type='OnPlayerJoined' and display_name like ?"
                " group by user_id order by 3 desc limit 20", (f"%{q}%",)):
            if uid in _friends or uid in _state["people"]:
                continue
            out.append({"uid": uid, "name": name, "met": days, "last": _to_epoch(last)})
        c.close()
    except (sqlite3.Error, OSError):
        pass
    return out


# ---------------------------------------------------------------- 保存
_save_lock = threading.Lock()   # UIスレッドとメインループの二重書き込み防止


def _mark_dirty():
    global _dirty
    _dirty = True


def _save_now():
    global _dirty, _last_save
    if _path is None:
        return
    with _save_lock:
        _dirty = False
        _last_save = time.time()
        # 通りすがりの人数え(seen)は放置すると公開インスタンスで無限に増える。ごぶさたは捨てる
        old = _last_save - float(_cfg("absence_days")) * 86400
        for uid in [u for u, s in _state.get("seen", {}).items() if s["last"] < old]:
            _state["seen"].pop(uid)
        tmp = _path.with_suffix(".tmp")
        tmp.write_text(json.dumps(_state, ensure_ascii=False, indent=1), encoding="utf-8")
        os.replace(tmp, _path)


def _save_maybe(now):
    if not _dirty or now - _last_save < SAVE_IV:
        return
    _save_now()


# ---------------------------------------------------------------- 自己チェック
if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")
    # tier境界
    assert _tier(1, 0) == "はじめてあうこ"
    assert _tier(5, 0) == "たまにあうこ"
    assert _tier(10, 0) == "よくあうこ"
    assert _tier(10, 14 * 86400 + 1) == "ひさしぶりにあうこ"
    # 自動なかま入り: しきい値0で無効、忘れた人(declined)は拾い直さない
    _KNOBS["auto_adopt_days"] = 0
    assert not _auto_adopt("usr_x", "X") and not _state.get("seen")
    _KNOBS["auto_adopt_days"] = 3
    _state["declined"] = ["usr_x"]
    assert not _auto_adopt("usr_x", "X") and not _state.get("seen")
    _state.pop("declined")
    # 過去ログは見ない: 3回会ってはじめて登録される(同一インスタンス内の再joinは数えない)
    _loc_epoch = time.time()
    assert not _auto_adopt("usr_y", "Y") and not _auto_adopt("usr_y", "Y")
    assert _state["seen"]["usr_y"]["met"] == 1, _state["seen"]
    for i in (2, 3):
        _loc_epoch = time.time() + 1   # インスタンス移動のかわり
        got = _auto_adopt("usr_y", "Y")
        assert got == (i == 3), (i, got)
    assert _state["people"]["usr_y"]["met"] == 3 and not _state["seen"]
    del _state["people"]["usr_y"], _friends["usr_y"]
    _KNOBS["auto_adopt_days"] = 0   # 自己チェックで本物のgrowth.jsonに人を書き足さない
    # 減衰: 半減期(既定5.8日)ぶん放置するとちょうど半分
    _state.update(bond=10.0, bond_ts=time.time() - 5.8 * 86400)
    assert abs(bond() - 5.0) < 0.05, bond()
    # なつき度の加算と上限
    _state.update(bond=BOND_CAP - 0.1, bond_ts=time.time())
    bump(named=True)
    assert bond() <= BOND_CAP
    # 実DBで在室復元(VRCXが無ければ休止メッセージが出るだけ)
    init(Path(__file__).parent / "data", "", lambda s: s)
    if not _dead:
        names = sorted(_friends.get(u, "?") for u in _present)
        print("いま在室のフレンド:", names or "(なし)")
    print("ok")
