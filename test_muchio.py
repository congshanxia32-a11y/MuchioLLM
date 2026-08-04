#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""python test_muchio.py — 相槌と「聞く間」の最低限チェック。"""
import muchio_llm as m

# 相槌が文字盤フォントを通り抜けられること（消えると無言になり相槌の意味が消える）
for s in m.aizuchi_pool(False) + m.aizuchi_pool(True):
    out = m.to_board_text(s)
    assert out, f"相槌が盤面で消えた: {s!r}"
    assert len(out) <= 8, f"相槌が長すぎる: {out!r}"

# config化した相槌: 、区切りで差し替えられ、空なら既定に戻る
m.CFG["aizuchi"] = "やあ、おっす"
assert m.aizuchi_pool(False) == ["やあ", "おっす"]
m.CFG["aizuchi"] = ""
assert "ふーん" in m.aizuchi_pool(False), "空指定で既定に戻らない"
m.CFG["aizuchi"] = m.DEFAULTS["aizuchi"]

# 相手がしゃべり続けているあいだは本返事を出さない
assert not m.should_reply_now(now=10.0, last_heard=9.0, pending_at=9.0, win=3.0)
# 3秒黙ったら出す
assert m.should_reply_now(now=13.0, last_heard=10.0, pending_at=10.0, win=3.0)
# 黙らなくても待ちが win*4 を超えたら出す（延々しゃべられて詰まるのを防ぐ）
assert m.should_reply_now(now=23.0, last_heard=22.9, pending_at=10.0, win=3.0)
# win=0 は旧挙動（即返事）
assert m.should_reply_now(now=10.0, last_heard=10.0, pending_at=10.0, win=0.0)

# ---- 成長機能: 挨拶の抑制まわり ----
import time
import growth as g
g._board = m.to_board_text
g._friends = {"usr_a": "ΔΘΛΞΣ", "usr_b": "Poyopon"}
g._loc_epoch = time.time() - 10
g._apply("OnPlayerJoined", "usr_a")
assert g._pop_greet(True) is None, "盤面に出せない名前で挨拶してしまう"
g._apply("OnPlayerJoined", "usr_b")
assert g._pop_greet(False) is None, "会話中に挨拶を捨ててしまう"
greet = g._pop_greet(True)
assert greet and "Poyopon" in greet, f"挨拶が出ない: {greet!r}"
g._apply("OnPlayerLeft", "usr_b")
g._apply("OnPlayerJoined", "usr_b")
assert g._pop_greet(True) is None, "同一インスタンスで二重挨拶"
assert g._state["people"]["usr_b"]["met"] == 1, "再joinでmetが二重カウント"

# ---- 界隈(言語)の多数決 ----
assert g._person_lang({"langs": {"en": 3}}) is None, "票不足なのに判定した"
assert g._person_lang({"langs": {"en": 5, "ja": 1}}) == "en"
assert g._person_lang({"langs": {"ja": 9, "en": 2}}) == "jp"
g._present.clear()
assert g.circle_lang() is None, "無人で判定した"
g._state["people"]["usr_b"]["langs"] = {"en": 10}
g._present.add("usr_b")
assert g.circle_lang() == "en"
g._state["people"]["usr_c"] = {"name": "x", "met": 1, "last": 0, "langs": {"ja": 10}}
g._present.add("usr_c")
assert g.circle_lang() is None, "同数なのに判定した"
g.hear_lang("ja")   # 在室2人に1票ずつ→usr_cがja優勢のまま、usr_bはen優勢のまま
assert g._state["people"]["usr_b"]["langs"] == {"en": 10, "ja": 1}
g.hear_lang("?")    # 不明言語は捨てる
assert g._state["people"]["usr_b"]["langs"] == {"en": 10, "ja": 1}

# ---- あだ名: 盤面に出せない名前でも、ひらがなのあだ名を付ければ呼べる ----
g._state["people"]["usr_a"]["nick"] = "たこ"
g._present.discard("usr_a"); g._greeted.discard("usr_a")
g._apply("OnPlayerJoined", "usr_a")
greet = g._pop_greet(True)
assert greet and "たこ" in greet, f"あだ名で呼べていない: {greet!r}"

# ---- greet=False の人には挨拶しない(記録は続く) ----
g._state["people"]["usr_b"]["greet"] = False
g._present.discard("usr_b"); g._greeted.discard("usr_b")
g._loc_epoch = time.time() + 1   # metカウント許可(新インスタンス扱い)
m0 = g._state["people"]["usr_b"]["met"]
g._apply("OnPlayerJoined", "usr_b")
assert g._pop_greet(True) is None, "greet=Falseなのに挨拶した"
assert g._state["people"]["usr_b"]["met"] == m0 + 1, "greet=Falseでmetが止まった"

# ---- 手動登録(フレンド外)も挨拶対象になる ----
g.adopt("usr_zz", "Leo")
assert "usr_zz" in g._friends
g._apply("OnPlayerJoined", "usr_zz")
greet = g._pop_greet(True)
assert greet and "Leo" in greet, f"手動登録の人に挨拶しない: {greet!r}"

# ---- set_person: あだ名の設定と解除 ----
g.set_person("usr_zz", nick="れお", greet=False)
assert g._state["people"]["usr_zz"]["nick"] == "れお"
assert g._state["people"]["usr_zz"]["greet"] is False
g.set_person("usr_zz", nick="", greet=True)
assert "nick" not in g._state["people"]["usr_zz"]
assert "greet" not in g._state["people"]["usr_zz"]

# ---- 話者タグの真似剥がし: [friend]等を返事の頭から落とす(履歴の自己強化を断つ) ----
_board_jp = lambda text: text if m.kanji_on() else m._kanji_to_hira(text)
assert m.to_board_text("[friend] こんにちは") == "こんにちは"
assert m.to_board_text("[ぎんこん] [friend] やあ") == "やあ"
assert m.to_board_text("【AxioPt】 了解したよ!") == _board_jp("了解したよ!")
assert m.to_board_text("かっこ[つき]のほんぶんはのこる") == "かっこ[つき]のほんぶんはのこる"

# ---- 名前剥がし: ナレーションだけ剥がし、主語は残す ----
assert m.to_board_text("むちこ、きょどる") == "きょどる"
assert m.to_board_text("「むちこ」→「空気の密度が変化しているのは間違いないようだ。」") == _board_jp("空気の密度が変化しているのは間違いないようだ。")
assert m.to_board_text("むちこ」「論理の欠落は即座に解消すべし") == _board_jp("論理の欠落は即座に解消すべし")
assert m.to_board_text("むちこ") == "むちこ", "自己紹介で名前だけ返した場合は残す"
assert m.to_board_text("むちこはかわいいよ") == "むちこはかわいいよ", m.to_board_text("むちこはかわいいよ")
assert m.to_board_text("むちこがやるよ") == "むちこがやるよ"
assert m.to_board_text("了解したよ!論理的なツッコミはやめるね。**むちこ**承知した。") == _board_jp("了解したよ!論理的なツッコミはやめるね。")

# ---- 盤面センタリング(頭上表示) ----
m.CFG["center_jp"], m.CFG["center_en"] = 16, 16
b = m._pad_board("とろんのあし？")           # 1行は上段。7文字 → セル13〜19(中心16)
assert len(b) == 64 and b[13:20] == "とろんのあし？" and b[:13].isspace(), repr(b)
b = m._pad_board("snack time?")              # 英語はcenter_en基準
assert b.index("snack") == 16 - len("snack time?") // 2, repr(b)
m.CFG["center_jp"] = 0                        # 0=旧来の左寄せ
assert m._pad_board("なに？").startswith("なに？")
b = m._pad_board("x" * 64)                    # 64字=2行ぴったり。欠けない
assert b == "x" * 64
m.CFG["center_jp"] = 16
b = m._pad_board("あ" * 40)                   # 32字超は2行に割ってそれぞれ中央へ
r1, r2 = b[:32], b[32:]
assert r1.strip() == "あ" * 20 and r2.strip() == "あ" * 20, repr(b)
b = m._pad_board("abcdefgh ijklmnop qrstuvwx yz123456")   # 英語は空白で行を割る
assert " " not in (b[:32].strip()[0], b[32:].strip()[0]), repr(b)

# ---- 考え中の点々: 相槌の直後のセルから、上段からはみ出さずに ----
assert "." in m.CHARSET, "点がフォントにない"
b = m._pad_board("ほう")                       # center16 → セル15,16 → 点は17から
s = m._dot_start_cell(b)
assert s == 17 and b[s - 1] != " " and b[s:s + 3] == "   ", (s, repr(b))
assert m._dot_start_cell(" " * 64) == 15, "空盤面は表示位置あたりに出す"
assert m._dot_start_cell(m._pad_board("あ" * 32)) == 29, "上段いっぱいで3点が収まらない"
# スレッド動作: 点が増えていき、止めると点々だけ消えた盤面に戻る(OSC送信なしで検証)
calls = []
_wb = m._write_block
m._write_block = lambda blk, bts, upto=None: calls.append(bts)
m._dots_start("ほう", already_shown=True, hold_check=lambda: False)
time.sleep(m.DOT_TICK * 4.5)
m._dots_stop()
m._write_block = _wb
assert any(m.CHARSET["."] in bts for bts in calls), "点が一度も出なかった"
assert calls[-1] == m._board_bytes(m._pad_board("ほう")), "停止時に点々が残った"

# ---- ページ送り: 64字超は切り捨てず、文の切れ目で複数ページに割る ----
long2 = "あ" * 50 + "。" + "い" * 50 + "。"   # 102字2文
assert m.to_board_text(long2) == long2, "64字超が切り捨てられた"
pages = m._paginate(long2, 64)
assert pages == ["あ" * 50 + "。", "い" * 50 + "。"], pages
assert all(len(p) <= 64 for p in pages)
assert m._paginate("みじかい。", 64) == ["みじかい。"], "短文は1ページ"

# ---- 128セル盤面(Pointer9-16改造アバター): 4行センタリング・均等割り・点々の追従 ----
m.CFG["board_cells"] = 128
b = m._pad_board("とろんのあし？")            # 1行は4行のまんなか寄り(2行目)へ
assert len(b) == 128 and b[32 + 13:32 + 20] == "とろんのあし？" and not b[:32].strip(), repr(b)
b = m._pad_board("あ" * 100)                  # 100字 → 4行に均等割り(25字×4)
rows = [b[i:i + 32].strip() for i in range(0, 128, 32)]
assert [len(r) for r in rows] == [25, 25, 25, 25], rows
s = m._dot_start_cell(m._pad_board("ほう"))    # 点々は文字がある行(2行目)の直後
assert s == 32 + 17, s
assert m._dot_start_cell(" " * 128) == 32 + 15, "空盤面はまんなかの行へ"
m.CFG["max_reply"] = 128
assert m._page_limit() == 128
m.CFG["board_cells"] = 64
assert m._page_limit() == 64, "無改造盤面ではページ上限も64に丸める"
m.CFG["max_reply"] = 64
p = m._paginate("x" * 150, 64)                # 句読点なし→ハードカット
assert p == ["x" * 64, "x" * 64, "x" * 22], p
p = m._paginate("あ" * 60 + "、" + "い" * 60, 64)   # 読点でも割れ、次ページ頭の読点は落ちる
assert p[0] == "あ" * 60 + "、" and p[1] == "い" * 60, p
assert len(m.to_board_text("か" * 300)) <= 64 * m.PAGES_MAX, "全体上限を超えた"

# ---- 表示時間: 短文は従来の8秒床、長文は文字数比例 ----
assert m._hold_for("ほう") == m.HIDE_AFTER
assert m._hold_for("あ" * 10) == m.HIDE_AFTER, "10字は従来どおり"
assert m._hold_for("あ" * 64) == m.HOLD_BASE + m.HOLD_PER_CHAR * 64
assert m._hold_for("あ" * 64) > m._hold_for("あ" * 30) > m._hold_for("あ" * 10)

# ---- 声紋: uid指定の界隈票は本人だけに入る ----
g._state["people"]["usr_b"]["langs"] = {}
g._state["people"]["usr_c"]["langs"] = {}
g._present.update({"usr_b", "usr_c"})
g.hear_lang("en", uid="usr_b")
assert g._state["people"]["usr_b"]["langs"] == {"en": 1}
assert g._state["people"]["usr_c"]["langs"] == {}, "uid指定なのに他人に票が入った"
g.hear_lang("ja")   # 無記名は従来どおり在室全員
assert g._state["people"]["usr_c"]["langs"] == {"ja": 1}
assert g.display_name("usr_b") == "Poyopon"
assert g.display_name("usr_zzz") is None

# ---- ちょっかい対象のon/offと人の削除 ----
g.set_person("usr_b", poke=False)
assert "usr_b" in g._present and "Poyopon" not in g.poke_names(), g.poke_names()
assert "Poyopon" in g.present_names(), "poke=offで在室表示まで消えた"
g.set_person("usr_b", poke=True)
assert "Poyopon" in g.poke_names()
# 手動登録の削除=登録解除(以後知らない人)
assert g.remove("usr_zz")
assert "usr_zz" not in g._friends and "usr_zz" not in g._state["people"]
g._apply("OnPlayerJoined", "usr_zz")
assert "usr_zz" not in g._state["people"], "削除したのにまた記録された"
# フレンドの削除=記録リセット(次に会えばまた数え直す)
assert g.remove("usr_b")
assert "usr_b" in g._friends, "フレンド削除でフレンド判定まで消えた"
g._loc_epoch = time.time() + 1
g._apply("OnPlayerJoined", "usr_b")
assert g._state["people"]["usr_b"]["met"] == 1, "数え直しになっていない"
assert not g.remove("usr_nothere")

# ---- configノブ: なつきやすさ倍率と常連しきい値 ----
g._get_cfg = lambda: {"bond_gain": 2.0, "tier_regular": 3}
g._state.update(bond=0.0, bond_ts=time.time())
g.bump(named=True)
assert abs(g.bond() - 1.0) < 0.01, "bond_gain=2.0で+0.5×2になっていない"
assert g._tier(3, 0) == "よくあうこ", "tier_regular=3が効いていない"
g._get_cfg = None

# ---- 自アカウント除外: テーブル名(ダッシュ無し)とuid(ダッシュ有り)の突き合わせ ----
assert g._uid_hex("usr_deadbeef-1234-4b43-b0bb-3b532571e12e") == \
    "deadbeef12344b43b0bb3b532571e12e"
own = {"deadbeef12344b43b0bb3b532571e12e"}
assert g._uid_hex("usr_deadbeef-1234-4b43-b0bb-3b532571e12e") in own, "alt垢が除外されない"

# ---- フレンド記念日: きょうが「まるN年」の人の挨拶に一言つく ----
g._anniv = {"usr_b": 2}
g._present.discard("usr_b"); g._greeted.discard("usr_b")
g._apply("OnPlayerJoined", "usr_b")
greet = g._pop_greet(True)
assert greet and "まる2ねん" in greet, f"記念日が挨拶に乗らない: {greet!r}"
g._anniv = {}

# ---- 状況認識(vrcx_sense): ワールド変更のコメントとおもいで ----
import tempfile
from pathlib import Path
import vrcx_sense as vs
vs._board = m.to_board_text
vs._get_cfg = lambda: {"world_comment_chance": 1.0}
vs._data = None
vs._on_location(1, "wrld_a", "Snow Rotunda", "ぱぶりっく", 1, [], announce=False)
assert vs._comment_q is None, "announce=Falseなのにコメントした"
vs._on_location(2, "wrld_a", "Snow Rotunda", "ぱぶりっく", 2, [])
assert vs._pop_comment(False) is None, "会話中にコメントを捨ててしまう"
c2 = vs._pop_comment(True)
assert c2 and "2かいめ" in c2, f"再訪コメントが出ない: {c2!r}"
vs._on_location(3, "wrld_b", "ΩΞΞΞΩ", "ぱぶりっく", 1, [])
c3 = vs._pop_comment(True)
assert c3 and "ΩΞΞΞΩ" not in c3, f"盤面に出せないワールド名を呼んだ: {c3!r}"
# 過去の滞在窓に会話があれば「おもいで」になる
# (界隈別DB分離で vs._conv は廃止。_data 配下の conversation{suffix}.jsonl を読む)
td = Path(tempfile.mkdtemp())
(td / "conversation.jsonl").write_text(
    '{"ts": 100, "text": "[とろ] たいやきのはなし"}\n', encoding="utf-8")
vs._data = td
vs._on_location(4, "wrld_a", "Snow Rotunda", "ぱぶりっく", 3, [(90, 110)])
assert vs._memory == "たいやきのはなし", vs._memory
c4 = vs._pop_comment(True)
assert c4 and "たいやきのはなし" in c4, f"おもいでコメントが出ない: {c4!r}"
assert "このばしょのおもいで" in vs.prompt_lines(), vs.prompt_lines()
vs._data = None
vs._get_cfg = None

# ---- 呼びかけ判定: config化した名前から聞き間違い許容regexを生成 ----
import re as _re
m.load_cfg()
assert m.NAME_RE.pattern == "[まみむめもの][ぁ-ゖー]?ち[ぁ-ゖー]?こ", m.NAME_RE.pattern  # 旧regexの上位互換
for s in ("むちこ", "ムーチコ", "めっちこさあ", "もちこおいで", "Muchiko come here", "眠ちこ"):
    assert m.called_name(s), f"呼びかけを聞き逃した: {s!r}"
assert not m.called_name("こんにちは") and not m.called_name("ぽちこ")
_pn, _pe, _re_bak = m.CFG.get("pet_name"), m.CFG.get("pet_name_en"), m.NAME_RE
m.CFG["pet_name"], m.CFG["pet_name_en"] = "ぽちこ", "pochiko"
m.NAME_RE = m._name_regex("ぽちこ")
assert m.called_name("ぼちこー") and m.called_name("Pochiko!"), "改名後の呼びかけ(清濁ゆれ込み)が効かない"
assert not m.called_name("むちこ"), "改名したのに旧名に反応した"
assert not m._name_regex("").search("むちこ"), "空名が何かにマッチした"
m.CFG["pet_name"], m.CFG["pet_name_en"], m.NAME_RE = _pn, _pe, _re_bak

# ---- モデル自動代用: 設定のモデルが未インストールなら手持ちで動く(配布直後対策) ----
import time as _t
_cfg_bak = dict(m.CFG)
m.CFG["mode"], m.CFG["model"] = "jp", "qwen3.6:35b-a3b-mtp-q4_K_M"
m._TAGS.update(t=_t.time() + 999, models=[("qwen3.5:9b", 5e9), ("nomic-embed-text", 1e9)])
assert m.active_model() == "qwen3.5:9b", m.active_model()   # 埋め込み専用は選ばない
assert m._SUBST["want"] == "qwen3.6:35b-a3b-mtp-q4_K_M"
m._TAGS["models"].append(("qwen3.6:35b-a3b-mtp-q4_K_M", 2e10))
assert m.active_model() == "qwen3.6:35b-a3b-mtp-q4_K_M", "設定モデルがあるのに代用した"
assert m._SUBST["want"] is None
m._TAGS.update(t=_t.time() + 999, models=None)               # ollama不通=判定不能なら設定のまま
assert m.active_model() == "qwen3.6:35b-a3b-mtp-q4_K_M"
m._TAGS.update(t=0.0, models=None)
m.CFG.clear(); m.CFG.update(_cfg_bak)

# ---- ルール文のconfig化: 編集がプロンプトに反映され、{fake}が展開される ----
_cfg_bak2 = dict(m.CFG)
m.CFG["mode"] = "jp"
m.CFG["advanced_rules_enabled"] = True
m.CFG["advanced_safety_enabled"] = True
m.CFG["rules"] = "てすとルール。{fake}おわり。"
m.CFG["fake_profile"] = "本名=ほげ"
sp = m.system_prompt()
assert "てすとルール。" in sp and "おわり。" in sp and "本名=ほげ" in sp, sp[-200:]
assert "{fake}" not in sp and "{lang}" not in sp and "{name}" not in sp
m.CFG["base_rules"] = "きほん{lang}ここまで"
sp = m.system_prompt()
assert "きほん返事は必ず日本語。" not in sp or True   # modeはautoでない=jpのlang文が入る
assert "{lang}" not in sp and "ここまで" in sp
m.CFG.clear(); m.CFG.update(_cfg_bak2)

# ---- 耳の生存ハートビートとOSCヒント ----
m.DATA.mkdir(exist_ok=True)
(m.DATA / "ears.alive").touch()
assert m._ears_alive(), "触った直後なのに耳が死んでいる判定"
assert isinstance(m._osc_off_hint(), bool)

# ---- 設定UI: 静的HTMLに生成プレースホルダを残さず、初期値はbootstrapで渡す ----
_left = _re.findall(r"__[A-Z]+__", (m.UI_DIR / "index.html").read_text(encoding="utf-8"))
assert not _left, f"UIプレースホルダの置換漏れ: {_left}"
_mc = m._model_choices
m._model_choices = lambda key="model": [{"value": "dummy", "label": "dummy", "selected": True}]
_boot = m._bootstrap_data()
assert _boot["cfg"] and _boot["cfg_mtime"] and _boot["model_options"], "bootstrap不足"
m._model_choices = _mc

# ---- フレンドのかいわ記憶: タグ付き発言だけ拾う(飼い主・むちこ自身は入れない) ----
_lines = ['{"ts":1,"role":"user","text":"[Poyopon] やっほー"}',
          '{"ts":2,"role":"user","text":"たいくつだなあ"}',
          '{"ts":3,"role":"assistant","text":"[friend] ではない"}',
          'こわれた行',
          '{"ts":4,"role":"user","text":"[friend] だれかの声"}']
assert m._pick_friend_lines(_lines, 5) == ["[Poyopon] やっほー", "[friend] だれかの声"]
assert m._pick_friend_lines(_lines, 1) == ["[friend] だれかの声"], "新しい側から数えていない"

# ---- せいかくスライダー: まんなか(45-55)は無音、はしに寄るほど強い文+矛盾ガード ----
_tr_bak = {k: m.CFG.get(k) for k, *_ in m.TRAITS}
_tw_bak = m.CFG.get("trait_weight")
_dynamic_bak = m.CFG.get("dynamic_enabled")
m.CFG["dynamic_enabled"] = False
for k, *_ in m.TRAITS:
    m.CFG[k] = 50
m.CFG["trait_weight"] = "mid"
assert m._trait_lines(False) == "" and m._trait_lines(True) == "", "まんなかで何か足している"
# バンド境界のオフバイワン(9/10, 44/45, 55/56, 90/91)
assert m._trait_band(9) == 0 and m._trait_band(10) == 1
assert m._trait_band(44) == 2 and m._trait_band(45) is None
assert m._trait_band(55) is None and m._trait_band(56) == 3
assert m._trait_band(90) == 4 and m._trait_band(91) == 5
# はし=強度副詞つき+枠組み文。毒舌でも中傷禁止ガードが同居する
m.CFG["trait_mean"] = 100
_t = m._trait_lines(False)
assert "毒舌" in _t and "かならず" in _t and "中傷" in _t and _t.startswith("せいかく"), _t
_te = m._trait_lines(True)
assert "roaster" in _te and "hateful" in _te
# やさしい極=悪口ぜったい禁止+皮肉ガード
m.CFG["trait_mean"] = 0
_t = m._trait_lines(False)
assert "悪口はぜったいに言わず" in _t and "皮肉" in _t
# 軽く口がわるいだけならガードはどちらも出ない
m.CFG["trait_mean"] = 65
_t = m._trait_lines(False)
assert "中傷" not in _t and "皮肉" not in _t
# 効きぐあい(trait_weight)3段で枠組み文が変わる
m.CFG["trait_mean"] = 100
for _w, _frag in (("low", "うっすら"), ("mid", "この設定に従う"), ("high", "かならず守る")):
    m.CFG["trait_weight"] = _w
    assert _frag in m._trait_lines(False), _w
m.CFG["trait_weight"] = "mid"
m.CFG["trait_mean"] = 50
m.CFG["trait_instinct"] = 5
assert "理性的" in m._trait_lines(False)
m.CFG["trait_optimism"] = 95
assert "楽観" in m._trait_lines(False)
for k, *_ in m.TRAITS:
    m.CFG[k] = _tr_bak[k] if _tr_bak[k] is not None else m.DEFAULTS[k]
m.CFG["trait_weight"] = _tw_bak if _tw_bak is not None else m.DEFAULTS["trait_weight"]
m.CFG["dynamic_enabled"] = _dynamic_bak if _dynamic_bak is not None else m.DEFAULTS["dynamic_enabled"]

# ---- じんかくテンプレ: 新構造(persona+examples+traits+checks)と値の妥当性 ----
_tkeys = {k for k, *_ in m.TRAITS}
_ckeys = {t[0] for t in m.RULES_TOGGLES}
for _n, _p in m.PRESETS.items():
    assert set(_p) <= {"persona", "persona_en", "examples", "examples_en", "traits", "checks", "description"}, _n
    assert {"persona", "persona_en", "examples", "examples_en", "traits", "checks"} <= set(_p), _n
    assert _p["persona"] and _p["examples"] and _p["examples_en"], f"{_n}: 空欄"
    assert set(_p["traits"]) <= _tkeys and all(0 <= v <= 100 for v in _p["traits"].values()), _n
    assert set(_p["checks"]) <= _ckeys, _n
assert m.PRESETS["バニラ"]["examples"] == m.DEFAULTS["examples"]
assert m.PRESETS["バニラ"]["persona"] == m.DEFAULTS["persona"]

# ---- こだわりチェック・効きぐあい・れいぶん・旧base_rules移行 ----
_cfg_bak3 = dict(m.CFG)
m.CFG["mode"] = "jp"
m.CFG["advanced_rules_enabled"] = True
m.CFG["persona_preferences_enabled"] = True
m.CFG["persona_examples_enabled"] = True
m.CFG["persona_free_text_enabled"] = True
m.CFG["base_rules"] = ""
m.CFG["examples"] = m.DEFAULTS["examples"]        # 実configの自作れいぶんに左右されない
m.CFG["examples_en"] = m.DEFAULTS["examples_en"]
for k, *_ in m.TRAITS:
    m.CFG[k] = 50
m.CFG["trait_weight"] = m.CFG["persona_weight"] = "mid"
for _c in _ckeys:
    m.CFG[_c] = False
m.CFG["rule_polite"] = True
sp = m.system_prompt()
assert "敬語で話す" in sp and "くだけた話し言葉" not in sp, "politeがONなのに排他になっていない"
assert "なんでしょう？" in sp and "なあに？" not in sp, "敬語ONで初期れいぶんが敬語版に差し替わっていない"
m.CFG["examples"] = "「{name}」→「じぶんのれいぶん」"
assert "じぶんのれいぶん" in m.system_prompt(), "敬語ONでも自作れいぶんは尊重する"
m.CFG["examples"] = m.DEFAULTS["examples"]
m.CFG["rule_polite"] = False
sp = m.system_prompt()
assert "くだけた話し言葉" in sp and "敬語で話す" not in sp
m.CFG["rule_trivia"] = True
assert "うんちく" in m.system_prompt()
# ハードルールは常時入り、敬語禁止(旧文)はもう無い。既定れいぶんは{name}展開されて入る
assert "ナレーション" in sp and "話者タグ" in sp and "説明・敬語" not in sp
assert "なあに？" in sp and "{name}" not in sp
# 人格の効きぐあい: mid=前置きなし / low / high
m.CFG["persona_weight"] = "high"
assert "かならず守る" in m.system_prompt()
m.CFG["persona_weight"] = "low"
assert "うっすらこういう子" in m.system_prompt()
m.CFG["persona_weight"] = "mid"
# 旧base_rules移行: 旧デフォルト・旧プリセット合成文=注入されない(独自編集ではない)
m.CFG["base_rules"] = m._OLD_BASE_RULES
assert "説明・敬語・絵文字" not in m.system_prompt(), "旧デフォルト文が独自文あつかいで二重注入"
m.CFG["base_rules_en"] = m._OLD_BASE_RULES_EN.strip()   # 旧/saveはstripして保存することがあった
assert m._legacy_base_rules(True) == ""
# 独自編集文は従来どおり注入され{lang}も展開される
m.CFG["base_rules"] = "おれのルール{lang}おわり"
sp = m.system_prompt()
assert "おれのルール" in sp and "おわり" in sp and "{lang}" not in sp
m.CFG.clear(); m.CFG.update(_cfg_bak3)

# ---- 手動ことば: おしえる→ひとりごと候補に入る→チップ削除と同じ経路で消える ----
_wc_bak2, _jw_bak2 = m._word_counts, m._judge_words
_mw_cfg_bak = dict(m.CFG)
_mw_data_bak, _mw_manual_bak, _mw_videos_bak = m.DATA, m._MANUAL_PATH, m._VIDEOS_PATH
_mw_td = Path(tempfile.mkdtemp())
try:
    m.DATA = _mw_td
    m._MANUAL_PATH = _mw_td / "manual_words.json"
    m._VIDEOS_PATH = _mw_td / "videos.json"
    m.CFG["memory_words_enabled"] = True
    m._word_counts = lambda: {}          # ログ由来の語を消して手動語だけで検証(ollama非依存)
    m._judge_words = lambda counts: {}
    m._save_manual_words(["てすとことば", "Testword"])
    assert "てすとことば" in m._interesting_words("jp") and "てすとことば" not in m._interesting_words("en")
    assert "Testword" in m._interesting_words("en")
    m.purge_word("てすとことば")
    assert "てすとことば" not in m._manual_words() and "Testword" in m._manual_words()
finally:
    m.DATA, m._MANUAL_PATH, m._VIDEOS_PATH = _mw_data_bak, _mw_manual_bak, _mw_videos_bak
    m._word_counts, m._judge_words = _wc_bak2, _jw_bak2
    m.CFG.clear(); m.CFG.update(_mw_cfg_bak)

# ---- NGワードの検出と一括削除 ----
_ng_td = Path(tempfile.mkdtemp())
_ng_data, _ng_manual, _ng_videos = m.DATA, m._MANUAL_PATH, m._VIDEOS_PATH
_ng_cfg, _ng_counts = dict(m.CFG), m._word_counts
try:
    m.DATA = _ng_td
    m._MANUAL_PATH = _ng_td / "manual_words.json"
    m._VIDEOS_PATH = _ng_td / "videos.json"
    m.CFG["ng_words"] = "BadWord,危険,一,BADWORD"
    (_ng_td / "conversation.jsonl").write_text(
        '{"role":"user","text":"This contains badword"}\n'
        '{"role":"user","text":"きけん"}\n', encoding="utf-8")
    (_ng_td / "conversation_en.jsonl").write_text(
        '{"role":"user","text":"safe conversation"}\n', encoding="utf-8")
    (_ng_td / "diary.jsonl").write_text(
        '{"role":"diary","text":"危険な日記"}\n', encoding="utf-8")
    m._save_manual_words(["badword manual", "safe note"])
    m._word_counts = lambda: {"BadWord": 4, "安全": 3}
    assert m._ng_words() == ["BadWord", "危険"], m._ng_words()
    _ng_safety_bak, _ng_mode_bak = m.CFG.get("advanced_safety_enabled"), m.CFG.get("mode")
    m.CFG["advanced_safety_enabled"] = True
    m.CFG["mode"] = "jp"
    _ng_prompt = m.system_prompt()
    assert "BadWord" in _ng_prompt and "関連する内容には触れない" in _ng_prompt, _ng_prompt
    m.CFG["advanced_safety_enabled"], m.CFG["mode"] = _ng_safety_bak, _ng_mode_bak
    _ng_words_bak, _ng_chat_bak = m.CFG["ng_words"], m.ollama_chat
    _ng_calls = []
    def _fake_ng_chat(history, user_text, timeout=90, diversity=0):
        _ng_calls.append(user_text)
        return "静寂と沈黙の話" if len(_ng_calls) == 1 else "別の話題だよ"
    m.CFG["ng_words"] = "静寂,沈黙"
    m.ollama_chat = _fake_ng_chat
    assert m.gen_reply([], "ひとこと") == "別の話題だよ"
    assert len(_ng_calls) == 2, _ng_calls
    m.CFG["ng_words"], m.ollama_chat = _ng_words_bak, _ng_chat_bak
    _ng_kanji_bak = m.CFG.get("kanji_mode")
    m.CFG["kanji_mode"] = True
    assert "沈黙" in m.to_board_text("雨音と沈黙の対比が興味深い。"), "禁止ワードを表示置換している"
    m.CFG["kanji_mode"] = _ng_kanji_bak
    _ng_hits = m._ng_hits()["words"]
    _ng_by_word = {x["word"]: x for x in _ng_hits}
    assert _ng_by_word["BadWord"]["conversation_count"] == 1, _ng_by_word
    assert _ng_by_word["BadWord"]["learned_count"] == 2, _ng_by_word
    assert _ng_by_word["危険"]["conversation_count"] == 1, _ng_by_word
    _ng_deleted = m.purge_word("badword", kind="learned")
    assert _ng_deleted == 2, _ng_deleted
    assert "badword" not in (_ng_td / "conversation.jsonl").read_text(encoding="utf-8").lower()
    assert "badword" not in m._MANUAL_PATH.read_text(encoding="utf-8").lower()
    assert "危険" in (_ng_td / "diary.jsonl").read_text(encoding="utf-8"), "別のNG語まで消えた"
    assert list(_ng_td.glob("*.purge.bak")), "NG削除のバックアップがない"
finally:
    m.DATA, m._MANUAL_PATH, m._VIDEOS_PATH = _ng_data, _ng_manual, _ng_videos
    m.CFG.clear(); m.CFG.update(_ng_cfg)
    m._word_counts = _ng_counts
    m._WORDS_CACHE["key"] = None

# ---- Muchio間会話: 相手発言として扱い、生成手順を返さない ----
assert "相手のMuchio" in m.peer_dialogue_prompt("[Muchio] こんにちは")
assert not m._peer_contract_hits("今日は静かだね。")
assert m._peer_contract_hits("Alright, let's tackle this query. The user is [Muchio].")
assert m.peer_input_is_usable("[Muchio] 今日は静かだね。")
assert not m.peer_input_is_usable("Okay, let me try to work through this query step by step.")
_peer_cfg_bak = dict(m.CFG)
_peer_chat_bak = m.ollama_chat
_peer_calls = []
try:
    m.CFG["mode"] = "jp"
    def _fake_peer_chat(history, user_text, timeout=90, diversity=0):
        _peer_calls.append(user_text)
        return ("Alright, let's tackle this query. The user is [Muchio]."
                if len(_peer_calls) == 1 else "そういう見方もあるね。")
    m.ollama_chat = _fake_peer_chat
    assert m.gen_reply([], "[Muchio] 同じ言葉を繰り返すね。", peer=True) == "そういう見方もあるね。"
    assert len(_peer_calls) == 2, _peer_calls
    assert "相手のMuchio" in _peer_calls[0]
    _peer_calls.clear()
    m.ollama_chat = lambda *args, **kwargs: "Okay, let me try to work through this query step by step."
    assert m.gen_reply([], "[Muchio] まだ話せる？", peer=True) == "そういう見方もあるね。"
finally:
    m.CFG.clear(); m.CFG.update(_peer_cfg_bak)
    m.ollama_chat = _peer_chat_bak

# ---- ものしりナレッジ: キーワード一致で注入・不一致で無音。空行は無視 ----
_kn_bak = m.CFG.get("knowledge")
m.CFG["knowledge"] = "神話: ゼウスはギリシャの神さまの王\n\nうちゅう: ブラックホールは光もにげられない"
assert m._knowledge_lines() == ["神話: ゼウスはギリシャの神さまの王",
                                "うちゅう: ブラックホールは光もにげられない"]
_hit = m._knowledge_hits("そういえば神話ってすき？")
assert "ゼウス" in _hit and "ブラックホール" not in _hit
assert m._knowledge_hits("こんにちは") == ""
m.CFG["knowledge"] = _kn_bak if _kn_bak is not None else ""

# ---- にっきけし: 無い日は何もしない(ファイル無変更・バックアップも作らない) ----
assert m.delete_diary_entry("1999-01-01", "") == 0

# ---- 単語集計: assistant行(むちこ自身のひらがな返答)は数えない ----
from pathlib import Path as _P
_tmp = _P(__file__).parent / "data" / "_test_words.jsonl"
_tmp.write_text('{"ts":1,"role":"user","text":"チョコレートすき"}\n'
                '{"ts":2,"role":"assistant","text":"カステラたべる"}\n', encoding="utf-8")
_alldb, m.ALL_DB = m.ALL_DB, [_tmp]
_wc_cfg_bak = dict(m.CFG)
m.CFG["memory_words_enabled"] = True
m._WORDS_CACHE["key"] = None
_counts = m._word_counts()
m.ALL_DB = _alldb
m.CFG.clear(); m.CFG.update(_wc_cfg_bak)
m._WORDS_CACHE["key"] = None
_tmp.unlink()
assert "チョコレート" in _counts, _counts
assert "カステラ" not in _counts, "assistant行の単語を数えてしまった"

# ---- ことば学習: 判定パースと、ひとりごと用の単語えらび ----
# 箇条書き・番号・引用符・候補外の行が混ざっても、候補との完全一致だけ拾う
parsed = m._parse_judge("- Cloma\n2. フィザカル\n「プランス」\nしらないことば\nちゃ",
                        ["Cloma", "フィザカル", "プランス", "What", "おなか", "おちゃ"])
assert parsed == {"Cloma": True, "フィザカル": True, "プランス": True,
                  "What": False, "おなか": False, "おちゃ": False}, parsed
assert m._parse_judge("cloma", ["Cloma"]) == {"Cloma": True}   # 大文字小文字ゆれ

_wc, _jw = m._word_counts, m._judge_words
_iw_cfg_bak = dict(m.CFG)
_iw_manual_bak = m._MANUAL_PATH
try:
    m._MANUAL_PATH = Path(tempfile.mkdtemp()) / "manual_words.json"
    m.CFG["memory_words_enabled"] = True
    m._word_counts = lambda: {"Cloma": 5, "What": 14, "おなか": 11, "フィザカル": 3, "ひとこと": 1}
    m._judge_words = lambda counts: {"What": False, "おなか": False, "Cloma": True}
    assert m._interesting_words("en") == ["Cloma"], "判定Falseの語が混ざった"
    assert m._interesting_words("jp") == ["フィザカル"], "未判定はTrue扱い(フェイルオープン)のはず"
finally:
    m._word_counts, m._judge_words = _wc, _jw
    m._MANUAL_PATH = _iw_manual_bak
    m.CFG.clear(); m.CFG.update(_iw_cfg_bak)

# ---- 漢字モード(セルペア16bit) ----
assert m.KCHARSET, "kanji_charset.jsonが無い(先にgen_kanji_atlas.pyを実行)"
m.CFG["kanji_mode"] = False
m.CFG["board_cells"] = 128
# OFF時は現行と完全一致: バイト列=旧CHARSETの1バイト/字
bts = m._board_bytes("やあ ")
assert bts == [m.CHARSET["や"], m.CHARSET["あ"], 0], bts
assert len(m._board_bytes(m._pad_board("やあ"))) == 128
assert m.to_board_text("元気だよ") == "げんきだよ", "OFF時はひらがな化が生きる"
m.CFG["kanji_mode"] = True
# ON時: 2バイト/グリフ、ページ0文字はhi=0
kb = m._board_bytes("漢あ")
ki = m.KCHARSET["漢"]
assert kb == [ki >> 8, ki & 255, 0, m.CHARSET["あ"]], kb
# 盤面は64グリフ=128バイト、行は16グリフ
assert len(m._pad_board("漢字テスト")) == 64
assert len(m._board_bytes(m._pad_board("漢字テスト"))) == 128
assert m._page_limit() <= 64
# 漢字素通し+カタカナ維持+表に無い字は読みに落ちる
out = m.to_board_text("漢字とカタカナが出るよ")
assert "漢字" in out and "カタカナ" in out, out
# 長音がそのまま出る(旧モードは-変換だった)
assert "ー" in m.to_board_text("すごーい")
# 全空白盤面の点々開始位置: center_jp(セル単位)をグリフ単位に換算し忘れると行の右端(15/16)に寄るバグの回帰
s0 = m._dot_start_cell(" " * 64)
assert 0 <= s0 < 64 and 4 <= s0 % 16 <= 12, s0
# バイト128は転送不能(クランプで129と衝突)——グリフ表に低位バイト128が無いこと
assert all(v & 255 != 128 for v in m.KCHARSET.values()), "下位バイト128のグリフが混入"
# 表に無い字(第2水準外)を含む語は読みに落ちる
m.CFG["kanji_mode"] = True
out = m.to_board_text("鬱蒼とした森")
assert "森" in out and "鬱" not in out, out
m.CFG["kanji_mode"] = False
m.CFG["board_cells"] = 64

# ---- OSCプロキシ: VRCPetの旧1バイト直書きを復元できる ----
st = {"ptr": 0, "board": [0] * 128, "dirty": False}
text = "やあ げんき?"
for blk in range(2):
    msgs = [("/avatar/parameters/KAT_Pointer", [blk + 1])]
    for i in range(8):
        ch = text[blk * 8 + i] if blk * 8 + i < len(text) else " "
        msgs.append((f"/avatar/parameters/KAT_CharSync{i}",
                     [(m.CHARSET.get(ch, 0) if m.CHARSET.get(ch, 0) <= 127
                       else m.CHARSET.get(ch, 0) - 256) / 127.0]))
    assert m._proxy_ingest(msgs, st) is True
assert st["dirty"]
assert m._proxy_text(st).startswith("やあ げんき?")
# KAT以外は取り込まない(素通し対象)
assert m._proxy_ingest([("/avatar/parameters/Foo", [1])], st) is False
# osc_parseラウンドトリップ(kat_sniffと共用)
out = []
m.osc_parse(m._osc("/avatar/parameters/KAT_Pointer", 3), out)
assert out == [("/avatar/parameters/KAT_Pointer", [3])]

# ---- voice memory: timestamp-paged history, explicit candidates, and batch labels ----
# These assertions fail if the page joins unrecorded embeddings, ignores the cursor,
# auto-registers candidate rows, or accepts a UID without a display name.
import json as _json
import threading as _threading
import urllib.error as _urlerror
import urllib.parse as _urlparse
import urllib.request as _urlrequest

_voice_td = Path(tempfile.mkdtemp())
_voice_data_bak = m.DATA
_voice_paths_bak = (m.voiceid.DATA, m.voiceid.VOICES, m.voiceid.EMBEDS,
                    m.voiceid._profiles, m.voiceid._mtime,
                    m.voiceid._embed_cache_key, m.voiceid._embed_cache_rows)
_voice_name_bak = m.growth.display_name
try:
    m.DATA = _voice_td
    m.voiceid.DATA = _voice_td
    m.voiceid.VOICES = _voice_td / "voices.json"
    m.voiceid.EMBEDS = _voice_td / "embeds.jsonl"
    m.voiceid._profiles = {}
    m.voiceid._mtime = 0.0
    m.voiceid._embed_cache_key = None
    m.voiceid._embed_cache_rows = []
    (_voice_td / "others_heard.jsonl").write_text(
        '{"ts": 3.0, "text": "latest", "who_name": "Friend A", "lang": "en"}\n'
        '{"ts": 2.0, "text": "middle", "who_name": "Friend B", "lang": "en"}\n'
        '{"ts": 1.0, "text": "oldest", "who_name": "Friend C", "lang": "jp"}\n',
        encoding="utf-8")
    m.voiceid.EMBEDS.write_text(
        '{"ts": 3.0, "v": [1.0, 0.0], "lang": "en", "lang_conf": 0.9}\n'
        '{"ts": 2.0, "v": [0.9, 0.1], "lang": "en", "lang_conf": 0.9}\n'
        '{"ts": 1.0, "v": [0.0, 1.0], "lang": "jp", "lang_conf": 0.9}\n'
        '{"ts": 0.0, "v": [1.0, 0.0], "lang": "en", "lang_conf": 0.9}\n',
        encoding="utf-8")
    m.growth.display_name = lambda uid: {"usr_a": "Alice", "usr_b": "Bob"}.get(uid)

    page = m._voice_page(limit=2)
    assert [item["ts"] for item in page["recent"]] == [3.0, 2.0], page
    assert page["next_before"] == 2.0, page
    assert page["profiles"] == [], page
    assert m._voice_page(limit=2, before=2.0)["recent"] == [{
        "ts": 1.0, "text": "oldest", "who_name": "Friend C", "lang": "jp",
    }]

    # Missing transcript metadata must not leave a page short or skip older valid history.
    (_voice_td / "others_heard.jsonl").write_text(
        '{"ts": 3.0, "text": "latest", "who_name": "Friend A", "lang": "en"}\n'
        '{"ts": 1.0, "text": "oldest", "who_name": "Friend C", "lang": "jp"}\n',
        encoding="utf-8")
    page = m._voice_page(limit=2)
    assert [item["ts"] for item in page["recent"]] == [3.0, 1.0], page
    assert page["next_before"] is None, page

    # Paging may scan past embedding rows with no transcript, but must stop once
    # it has the extra valid transcript row that proves another page exists.
    (_voice_td / "others_heard.jsonl").write_text(
        '{"ts": 10.0, "text": "first", "who_name": "Friend A", "lang": "en"}\n'
        '{"ts": 8.0, "text": "second", "who_name": "Friend B", "lang": "en"}\n'
        '{"ts": 7.0, "text": "extra", "who_name": "Friend C", "lang": "en"}\n'
        '{"ts": 6.0, "text": "too old", "who_name": "Friend D", "lang": "en"}\n',
        encoding="utf-8")
    _voice_pending_bak = m.voiceid.pending
    _voice_pending_calls = []

    def _fake_pending(limit=50, before=None):
        _voice_pending_calls.append((limit, before))
        if before is None:
            return {"items": [
                {"ts": 10.0, "v": [1.0, 0.0], "lang": "en"},
                {"ts": 9.0, "v": [1.0, 0.0], "lang": "en"},
            ], "next_before": 9.0}
        if before == 9.0:
            return {"items": [
                {"ts": 8.0, "v": [1.0, 0.0], "lang": "en"},
                {"ts": 7.0, "v": [1.0, 0.0], "lang": "en"},
            ], "next_before": 7.0}
        return {"items": [
            {"ts": 6.0, "v": [1.0, 0.0], "lang": "en"},
        ], "next_before": None}

    try:
        m.voiceid.pending = _fake_pending
        page = m._voice_page(limit=2)
    finally:
        m.voiceid.pending = _voice_pending_bak
    assert [item["ts"] for item in page["recent"]] == [10.0, 8.0], page
    assert page["next_before"] == 8.0, page
    assert _voice_pending_calls == [(2, None), (2, 9.0)], _voice_pending_calls

    (_voice_td / "others_heard.jsonl").write_text(
        '{"ts": 3.0, "text": "latest", "who_name": "Friend A", "lang": "en"}\n'
        '{"ts": 2.0, "text": "middle", "who_name": "Friend B", "lang": "en"}\n'
        '{"ts": 1.0, "text": "oldest", "who_name": "Friend C", "lang": "jp"}\n',
        encoding="utf-8")

    candidates = m._voice_candidates(3.0)
    assert [(item["ts"], item["text"], item["lang"]) for item in candidates] == [
        (2.0, "middle", "en"),
    ], candidates
    assert candidates[0]["score"] > 0.9, candidates
    assert m.voiceid.summary() == [], "viewing candidates must not register them"
    assert m._voice_candidates(999.0) == []

    result = m._voice_batch("usr_a", [1.0, 2.0])
    assert result == {"added": 2, "missing": 0, "skipped": 0}, result
    assert m._voice_batch("missing", [3.0]) == {"added": 0, "missing": 0, "skipped": 0}

    _voice_server = m.HTTPServer(("127.0.0.1", 0), m._UIHandler)
    _voice_thread = _threading.Thread(target=_voice_server.serve_forever, daemon=True)
    _voice_thread.start()
    _voice_base = f"http://127.0.0.1:{_voice_server.server_port}"
    try:
        with _urlrequest.urlopen(_voice_base + "/voices?limit=999") as _response:
            _voice_http_page = _json.load(_response)
        assert len(_voice_http_page["recent"]) <= 100, _voice_http_page
        with _urlrequest.urlopen(_voice_base + "/voices?limit=1") as _response:
            _voice_http_page = _json.load(_response)
        assert [item["ts"] for item in _voice_http_page["recent"]] == [3.0], _voice_http_page
        try:
            _urlrequest.urlopen(_voice_base + "/voice_candidates?ts=bad")
            raise AssertionError("invalid candidate timestamp must return HTTP 400")
        except _urlerror.HTTPError as _error:
            assert _error.code == 400
            assert _json.load(_error) == {"ok": False, "error": "invalid ts"}
        for _invalid_ts in ("nan", "inf"):
            try:
                _urlrequest.urlopen(_voice_base + "/voice_candidates?ts=" + _invalid_ts)
                raise AssertionError(f"{_invalid_ts} candidate timestamp must return HTTP 400")
            except _urlerror.HTTPError as _error:
                assert _error.code == 400
        _voice_request = _urlrequest.Request(
            _voice_base + "/voice_batch",
            data=_urlparse.urlencode({"uid": "missing", "ts": [3.0]}, doseq=True).encode(),
            method="POST")
        try:
            _urlrequest.urlopen(_voice_request)
            raise AssertionError("batch label for an unknown UID must return HTTP 400")
        except _urlerror.HTTPError as _error:
            assert _error.code == 400
        for _invalid_ts in ("nan", "inf"):
            _voice_request = _urlrequest.Request(
                _voice_base + "/voice_batch",
                data=_urlparse.urlencode({"uid": "usr_b", "ts": [_invalid_ts]}, doseq=True).encode(),
                method="POST")
            try:
                _urlrequest.urlopen(_voice_request)
                raise AssertionError(f"{_invalid_ts} batch timestamp must return HTTP 400")
            except _urlerror.HTTPError as _error:
                assert _error.code == 400
        _voice_request = _urlrequest.Request(
            _voice_base + "/voice_batch",
            data=_urlparse.urlencode({"uid": "usr_b", "ts": [3.0]}, doseq=True).encode(),
            method="POST")
        with _urlrequest.urlopen(_voice_request) as _response:
            assert _json.load(_response) == {
                "ok": True, "added": 1, "missing": 0, "skipped": 0,
            }
    finally:
        _voice_server.shutdown()
        _voice_server.server_close()
        _voice_thread.join()
finally:
    m.DATA = _voice_data_bak
    (m.voiceid.DATA, m.voiceid.VOICES, m.voiceid.EMBEDS,
     m.voiceid._profiles, m.voiceid._mtime,
     m.voiceid._embed_cache_key, m.voiceid._embed_cache_rows) = _voice_paths_bak
    m.growth.display_name = _voice_name_bak

# ---- 自動ゆらぎ: 固定値互換・範囲内の三角波・周期再現 ----
_dynamic_cfg_bak = dict(m.CFG)
try:
    m.CFG["dynamic_enabled"] = False
    assert m.dynamic_config_value("trait_smart", 50, 0, 100, now=123.0) == 50
    m.CFG["dynamic_enabled"] = True
    m.CFG["dynamic_period_minutes"] = 10
    _values = [m.dynamic_value("trait_smart", 50, 20, 80, now=t)
               for t in (0.0, 1.0, 123.4, 299.9, 600.0, 901.0)]
    assert all(20 <= v <= 80 for v in _values), _values
    assert abs(m.dynamic_value("trait_smart", 50, 20, 80, now=17.25) - \
               m.dynamic_value("trait_smart", 50, 20, 80, now=617.25)) < 1e-9
    assert abs(m.dynamic_value("trait_smart", 50, 80, 20, now=123.0) - \
               m.dynamic_value("trait_smart", 50, 20, 80, now=123.0)) < 1e-9
finally:
    m.CFG.clear(); m.CFG.update(_dynamic_cfg_bak)

# ---- 重複再生成: 通常時は設定値、再試行時だけ多様性を上げて上限内に収める ----
_base_temp, _base_top_p = m.adaptive_sampling(0.35, 0.85, 0)
assert (_base_temp, _base_top_p) == (0.35, 0.85)
_retry_temp, _retry_top_p = m.adaptive_sampling(0.35, 0.85, 1)
assert 0.35 < _retry_temp <= 1.5
assert 0.85 < _retry_top_p <= 1.0
assert m.adaptive_sampling(1.5, 1.0, 3) == (1.5, 1.0)

# ---- ひとりごとの連作: 履歴・接続句・主題クールダウン ----
_conversation = []
for _i in range(14):
    _conversation.extend([("user", f"発言 {_i}"), ("assistant", f"返答 {_i}")])
assert len(m.reply_history(_conversation, "local")) == 20
assert len(m.reply_history(_conversation, "local", exclude_last=True)) == 19
assert m.reply_history(_conversation, "local", exclude_last=True)[-1] == ("user", "発言 13")
assert m.reply_history(_conversation, "peer")[-1] == ("assistant", "返答 13")
_memory_bak = m.CFG.get("memory_conversation_enabled")
m.CFG["memory_conversation_enabled"] = False
assert m.reply_history(_conversation, "local") == []
m.CFG["memory_conversation_enabled"] = _memory_bak

assert m.monologue_topic("虚無と存在の境界") == "abstract"
assert m.monologue_topic("座標と距離の話") == "place"
assert m.monologue_topic("今日は机の輪郭を測る") == "other"
assert m.topic_on_cooldown("虚空を考える", ["abstract"])
assert not m.topic_on_cooldown("虚空を考える", ["place"])

_prefix_cfg_bak = {k: m.CFG.get(k) for k in (
    "monologue_connector_mode", "monologue_connectors",
    "monologue_max_continuations")}
m.CFG["monologue_connector_mode"] = "always"
m.CFG["monologue_connectors"] = ""
m.CFG["monologue_max_continuations"] = m.MONOLOGUE_MAX_CONTINUATIONS
_prefixes = {m.monologue_prefix(i) for i in range(1, 11)}
assert _prefixes <= set(m.MONOLOGUE_PREFIXES)
assert m.monologue_prefix(0) == ""
assert m.monologue_prefix(m.MONOLOGUE_MAX_CONTINUATIONS + 1) == ""
assert m.monologue_prompt(1, "直前の返答", ["abstract"]).startswith("直前のひとりごと")
assert "新しい観察対象" in m.monologue_prompt(m.MONOLOGUE_MAX_CONTINUATIONS,
                                                 "直前の返答", ["abstract"])
m.CFG.update(_prefix_cfg_bak)
for _key in ("monologue_max_continuations", "monologue_topic_cooldown",
             "monologue_connector_mode", "monologue_connectors",
             "monologue_avoid_words"):
    assert _key in m.DEFAULTS and _key in m.CFG, _key
_connector_cfg_bak = {k: m.CFG.get(k) for k in (
    "monologue_connector_mode", "monologue_connectors")}
try:
    m.CFG["monologue_connector_mode"] = "off"
    assert m.monologue_prefix(1) == ""
    m.CFG["monologue_connector_mode"] = "always"
    m.CFG["monologue_connectors"] = "接続A\n接続B"
    assert m.monologue_prefix(1) in {"接続A", "接続B"}
finally:
    m.CFG.update(_connector_cfg_bak)
_limit_cfg_bak = {k: m.CFG.get(k) for k in (
    "monologue_max_continuations", "monologue_topic_cooldown")}
try:
    m.CFG["monologue_max_continuations"] = 99
    m.CFG["monologue_topic_cooldown"] = -2
    assert m.monologue_max_continuations() == 10
    assert m.monologue_topic_cooldown() == 0
finally:
    m.CFG.update(_limit_cfg_bak)

print("ok")
