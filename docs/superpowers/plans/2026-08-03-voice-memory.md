# こえおぼえ強化 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 未分類発話を後から遡って安全に話者プロフィールへ登録でき、日本語/英語を分けて64件まで学習できる声紋記憶を実装する。

**Architecture:** `voiceid.py` を声紋データの唯一の保存・照合境界にし、未分類埋め込みを言語メタデータ付きで保持する。リスナーは発話言語を声紋境界へ渡し、HTTP 層はページング・候補取得・一括登録だけを担当する。UI は候補を自動登録せず、ユーザーが確認した時刻だけを送信する。

**Tech Stack:** Python 3、JSONL/JSON、標準ライブラリの `unittest` 相当の assert テスト、既存の Python HTTP server、既存のバニラ JavaScript UI。

## Global Constraints

- 音声そのものは保存せず、声紋ベクトルと発話メタデータだけを保存する。
- 未分類埋め込みの現在の1500件トリムを廃止し、ユーザーが削除するまで保持する。
- 人物プロフィールの照合対象は言語ごとに最大64件とする。
- `ja`/`en` は同言語を優先して照合し、`unknown` は全言語を比較するが通常より厳しい閾値を使う。
- 既存 `{name, vecs}` プロフィールと既存の1件ラベル付け API は読み込み/動作互換を維持する。
- 未分類候補はユーザー確認なしにプロフィールへ追加しない。
- 既存のユーザー変更が入っているファイルは、対象行以外を整形・改変しない。

---

### Task 1: 声紋ストレージと照合境界を拡張する

**Files:**
- Create: `test_voiceid.py`
- Modify: `voiceid.py:17-129`

**Interfaces:**
- Consumes: 既存の `stash(ts, vec)`、`add_sample(uid, name, ts)`、`match(vec, threshold)` 呼び出し。
- Produces:
  - `stash(ts, vec, lang="unknown", lang_conf=0.0)` — 言語メタデータ付きで未分類声紋を保存する。
  - `pending(limit=50, before=None)` — `before` より古いものを新しい順に返し、ページング用の `next_before` を返す。
  - `candidates(ts, threshold, lang=None, limit=20)` — 指定発話に近い未分類発話を類似度降順で返す。
  - `add_samples(uid, name, timestamps)` — 時刻配列を検証し、`{"added": int, "missing": int, "skipped": int}` を返す。
  - `observe(ts, vec, lang, lang_conf, threshold)` — 未分類声紋を保存してから言語優先照合を行い、既存互換のヒット値または `None` を返す。
  - `match(vec, threshold, lang=None)` — 言語優先・上位3件平均スコアで既存互換の `(uid, name, score)` または `None` を返す。

- [ ] **Step 1: テスト用の一時データ境界を書く**

`test_voiceid.py` に `tempfile.TemporaryDirectory()` を使うヘルパーを置き、各テストで `voiceid.DATA`、`voiceid.VOICES`、`voiceid.EMBEDS` を一時パスへ差し替え、`_profiles` と `_mtime` を初期化する。テストは外部の `data/` を読み書きしない。

- [ ] **Step 2: 未分類履歴の失敗テストを書く**

```python
def test_stash_keeps_language_and_pages_without_trimming():
    for i in range(4):
        voiceid.stash(float(i), [1.0, float(i) + 1.0], "ja", 0.9)
    page = voiceid.pending(limit=2)
    assert [row["ts"] for row in page["items"]] == [3.0, 2.0]
    assert page["items"][0]["lang"] == "ja"
    assert page["items"][0]["lang_conf"] == 0.9
    older = voiceid.pending(limit=2, before=page["next_before"])
    assert [row["ts"] for row in older["items"]] == [1.0, 0.0]
```

- [ ] **Step 3: 旧形式移行と言語別プロフィールの失敗テストを書く**

```python
def test_old_vecs_are_unknown_and_languages_have_independent_capacity():
    voiceid.VOICES.write_text(
        json.dumps({"u": {"name": "A", "vecs": [[1.0, 0.0]]}}),
        encoding="utf-8",
    )
    assert voiceid.summary()[0]["n_by_lang"] == {"unknown": 1}
    for i in range(65):
        voiceid.stash(1000.0 + i, [1.0, 0.01 * i], "ja", 0.9)
        voiceid.add_sample("u", "A", 1000.0 + i)
    for i in range(65):
        voiceid.stash(2000.0 + i, [0.0, 1.0 + 0.01 * i], "en", 0.9)
        voiceid.add_sample("u", "A", 2000.0 + i)
    profile = voiceid.load_profiles()["u"]
    assert sum(s["lang"] == "ja" for s in profile["samples"]) == 64
    assert sum(s["lang"] == "en" for s in profile["samples"]) == 64
    assert any(s["lang"] == "unknown" for s in profile["samples"])
```

- [ ] **Step 4: 言語優先照合と候補ランキングの失敗テストを書く**

```python
def test_match_prefers_same_language_and_candidates_are_manual():
    voiceid.stash(1.0, [1.0, 0.0], "ja", 0.95)
    voiceid.stash(2.0, [0.99, 0.1], "en", 0.95)
    voiceid.add_sample("ja-user", "J", 1.0)
    voiceid.add_sample("en-user", "E", 2.0)
    assert voiceid.match([0.99, 0.1], 0.5, lang="ja")[0] == "ja-user"
    voiceid.stash(3.0, [0.98, 0.2], "ja", 0.95)
    voiceid.stash(4.0, [0.97, 0.2], "ja", 0.95)
    result = voiceid.candidates(4.0, threshold=0.6, lang="ja", limit=5)
    assert [row["ts"] for row in result] == [3.0]
    assert voiceid.summary()[0]["n"] == 1
```

```python
def test_observe_persists_language_before_matching():
    hit = voiceid.observe(10.0, [1.0, 0.0], "en", 0.82, 0.5)
    assert hit is None
    row = voiceid.pending(limit=1)["items"][0]
    assert row["lang"] == "en"
    assert row["lang_conf"] == 0.82
```

- [ ] **Step 5: 新しいテストを実行して、機能不足による失敗を確認する**

Run: `python test_voiceid.py`

Expected: FAIL because `pending`, `candidates`, `add_samples`, language-aware profile loading, and the extended signatures do not exist yet. Fix only test setup errors before proceeding.

- [ ] **Step 6: `voiceid.py` に最小実装を追加する**

実装内容:

1. `stash` は各行へ `lang` と `lang_conf` を追加し、既存の `EMBED_TRIM_AT` 読み込み・トリム処理を削除する。
2. 埋め込み読み込みを時刻検索とページングで共有できるキャッシュにし、壊れた JSON 行は読み飛ばす。
3. `load_profiles` は旧 `vecs` を `samples=[{"lang":"unknown","ts":0.0,"v":...}]` に変換する。
4. `add_sample` は既存互換の薄いラッパーとして `add_samples` を1件呼ぶ。
5. `add_samples` は同一時刻・存在しない時刻・埋め込み欠損を重複登録せず、言語ごとに最大64件を守る。65件目以降は既存サンプルとの平均 cosine が最も高い重複サンプルを置換対象にする。
6. `match` は指定言語のサンプルを優先し、3件以上は上位3件平均、1〜2件は最大値を使う。`lang="unknown"` の場合は `threshold + 0.05` を適用する。
7. `candidates` は対象時刻のベクトルを取得し、対象自身・既にプロフィールへ登録済みの時刻・閾値未満を除外して類似度降順で返す。
8. `observe` は `stash` の後に `match` を呼び、リスナーが保存と照合の順序を取り違えない境界にする。
9. `summary` に従来の `n` を残し、`n_by_lang` を追加する。

- [ ] **Step 7: 声紋テストを再実行してグリーンを確認する**

Run: `python test_voiceid.py`

Expected: PASS。続けて `python -m py_compile voiceid.py test_voiceid.py` を実行し、構文エラーがないことを確認する。

- [ ] **Step 8: Task 1 の変更をコミットする**

```powershell
git add voiceid.py test_voiceid.py
git commit -m "feat: expand voice profile storage"
```

### Task 2: リスナーから言語情報を声紋へ渡す

**Files:**
- Modify: `vrc_listener.py:233-237`

**Interfaces:**
- Consumes: Task 1 の `stash(ts, vec, lang, lang_conf)` と `match(vec, threshold, lang)`。
- Produces: フレンド発話の保存・即時照合が Whisper の `lang` と `conf` を使う動作。

- [ ] **Step 1: `vrc_listener.py` の声紋呼び出しを変更する**

既存の `stash` と `match` の2呼び出しを、Task 1 の保存・照合境界へ置き換える。

```python
hit = voiceid.observe(entry["ts"], vec, lang, conf, v_thresh)
```

- [ ] **Step 2: Task 1 の声紋テストを連携変更後にも実行する**

Run: `python test_voiceid.py`

Expected: PASS。`observe` の保存順序・言語引数契約が維持される。

- [ ] **Step 3: 構文と既存リスナー契約を確認する**

Run: `python -m py_compile vrc_listener.py voiceid.py`

Expected: PASS。実音声モデルを起動するテストは行わず、既存の音声認識ループを変更していないことを差分で確認する。

- [ ] **Step 4: Task 2 の変更をコミットする**

```powershell
git add vrc_listener.py
git commit -m "feat: store voice language metadata"
```

### Task 3: 履歴ページング・候補・一括登録 API を追加する

**Files:**
- Modify: `muchio_llm.py:2899-2912, 3028-3046`
- Modify: `test_muchio.py`

**Interfaces:**
- Consumes: Task 1 の `pending`, `candidates`, `add_samples`, `summary`。
- Produces:
  - `GET /voices?limit=50&before=<ts>` — `recent`, `next_before`, `profiles` を返す。
  - `GET /voice_candidates?ts=<ts>&limit=20` — `candidates` を返す。
  - `POST /voice_batch` with `uid=<uid>&ts=<ts>&ts=<ts>` — 一括登録の結果を返す。

- [ ] **Step 1: HTTP 層から切り出す純粋関数の失敗テストを書く**

`muchio_llm.py` に `_voice_page(limit=50, before=None)` と `_voice_candidates(ts, limit=20)` を追加する前提で、`test_muchio.py` に次の契約を追加する。

```python
page = m._voice_page(limit=2)
assert len(page["recent"]) <= 2
assert "next_before" in page
assert "profiles" in page
```

テストでは `m.DATA` 以下の一時 `others_heard.jsonl` と Task 1 の一時声紋データを使い、発話本文とベクトルの時刻を同じにする。

- [ ] **Step 2: 失敗を確認する**

Run: `python test_muchio.py`

Expected: FAIL with `AttributeError` because `_voice_page` and `_voice_candidates` are not defined.

- [ ] **Step 3: `_voice_page` と `_voice_candidates` を実装する**

`_voice_page` は `voiceid.pending` の時刻をキーに `others_heard.jsonl` の本文・`who_name`・`lang` を結合し、要求された `limit` 件だけ返す。本文が見つからない埋め込みは除外し、次ページがない場合の `next_before` は `None` にする。

`_voice_candidates` は対象 `ts` のレコードを見つけて `voiceid.candidates` を呼び、本文と `score`、`lang`、`ts` を返す。対象がなければ空配列を返す。

- [ ] **Step 4: GET ルートを新しい純粋関数へ接続する**

`/voices` の固定 `[-10:]` 読み込みを削除し、`parse_qs` から `limit` を20〜100に丸め、`before` を float として `_voice_page` へ渡す。`/voice_candidates` を追加し、不正な `ts` は HTTP 400 で `{"ok": false, "error": "invalid ts"}` を返す。

- [ ] **Step 5: 一括登録 API の失敗テストを書く**

```python
result = m._voice_batch("usr_a", [1.0, 2.0])
assert result["added"] == 2
assert result["missing"] == 0
assert result["skipped"] == 0
```

`_voice_batch` は人物名が存在しない場合は `added=0` とし、リクエスト処理側は HTTP 400 にするテストも追加する。

- [ ] **Step 6: 一括登録を実装して POST ルートへ接続する**

`_voice_batch(uid, timestamps)` は `growth.display_name(uid)` を取得し、Task 1 の `voiceid.add_samples` を呼ぶ。`POST /voice_batch` は `q.get("ts", [])` を全件 float 化し、空配列・不正値・未登録 uid を 400、正常系を 200 で返す。既存 `/voice` は従来どおり1件登録に残す。

- [ ] **Step 7: API テストを実行する**

Run: `python test_muchio.py`

Expected: PASS。続けて `python -m py_compile muchio_llm.py test_muchio.py` を実行する。

- [ ] **Step 8: Task 3 の変更をコミットする**

```powershell
git add muchio_llm.py test_muchio.py
git commit -m "feat: page and batch-label voice history"
```

### Task 4: 「こえおぼえ」画面を遡及表示・確認登録にする

**Files:**
- Modify: `ui/app.js:620-654`
- Modify: `ui/index.html`（声紋カードの補助テキストが必要な場合のみ）
- Modify: `ui/style.css`（候補チェック行の表示が必要な場合のみ）

**Interfaces:**
- Consumes: `/voices?limit=&before=`, `/voice_candidates?ts=`, `/voice_batch`。
- Produces: 直近10件固定をやめ、過去ページと候補チェックを操作できる UI。

- [ ] **Step 1: UI状態と描画契約を追加する**

`ui/app.js` の音声記憶セクションに `voiceBefore`、`voiceRows`、`voiceCandidates` を追加し、`loadV(reset)` が `limit=50` と `before` を送る。プロフィール表示は `n_by_lang` を `ja/en/unknown` の順で表示し、旧 API の `n` だけでも表示できるようにする。

- [ ] **Step 2: 既存の固定10件描画をページングへ置き換える**

初回は `voiceBefore=null` で行を置換し、「もっと見る」は `next_before` を保存して追記する。重複時刻は `Set` で除外する。候補行には `data-ts`、言語、類似度、チェックボックスを表示する。

- [ ] **Step 3: 1件ラベル付け後の候補取得を実装する**

既存 `labelV` は `/voice` 成功後に `fetch('/voice_candidates?ts='+...)` を呼び、候補を同じ行の下へ表示する。候補が0件なら追加 UI は出さない。候補取得失敗時は既存の行更新だけを成功扱いにする。

- [ ] **Step 4: 確認済み候補の一括登録を実装する**

候補チェックボックスから `ts` を集め、`URLSearchParams` に同じ `ts` キーを複数追加して `/voice_batch` へ送る。レスポンスの `added/missing/skipped` を短いステータス表示にし、成功後は候補を閉じてプロフィール件数と未分類一覧を再読込する。未チェック候補は送信しない。

- [ ] **Step 5: UIの構文とエンドポイント文字列を検証する**

Run: `node --check ui/app.js`

Expected: PASS。Node がない環境では `Get-Content ui/app.js -Raw` で該当関数を確認し、ブラウザの `/voices`、`/voice_candidates`、`/voice_batch` 呼び出しが存在することを `rg` で確認する。

- [ ] **Step 6: Task 4 の変更をコミットする**

```powershell
git add ui/app.js ui/index.html ui/style.css
git commit -m "feat: review and batch-label voice candidates"
```

### Task 5: 全体検証と利用説明を更新する

**Files:**
- Modify: `docs/usage.md`（こえおぼえの操作説明を追加）
- Modify: `DEVELOPING.md`（声紋データ形式とテスト手順を追記）

**Interfaces:**
- Consumes: Task 1〜4 の保存形式・API・UI操作。
- Produces: 利用者が過去発話の遡り方、候補の確認、一括登録、言語別プロフィールを理解できる説明。

- [ ] **Step 1: ドキュメント更新の内容を確認する**

`docs/usage.md` に「こえおぼえ」節を追加し、次の手順を明記する。

1. 未分類発話の「もっと見る」で過去へ遡る。
2. 1件に人物を指定する。
3. 表示された候補を確認してチェックする。
4. 一括登録する。
5. 日本語/英語の件数が別々に表示される。

- [ ] **Step 2: 開発者向けデータ移行説明を追加する**

`DEVELOPING.md` に、旧 `vecs` は `unknown` へ移行されること、プロフィールは言語ごとに最大64件であること、音声自体は保存しないこと、`python test_voiceid.py` が声紋テストであることを追記する。

- [ ] **Step 3: 全テストを実行する**

Run:

```powershell
python test_voiceid.py
python test_muchio.py
python test_muchio_relay.py
python test_social_context.py
python test_ui_config.py
python -m py_compile voiceid.py vrc_listener.py muchio_llm.py test_voiceid.py
node --check ui/app.js
```

Expected: 全コマンドが終了コード0。失敗した場合は失敗テストを先に直し、他の既存変更を巻き戻さない。

- [ ] **Step 4: 変更差分と作業ツリーを確認する**

Run: `git diff --check; git status --short`

Expected: 対象ファイルに空白エラーがなく、既存のユーザー変更が今回のコミットへ混入していない。

- [ ] **Step 5: Task 5 の変更をコミットする**

```powershell
git add docs/usage.md DEVELOPING.md
git commit -m "docs: explain voice memory workflow"
```
