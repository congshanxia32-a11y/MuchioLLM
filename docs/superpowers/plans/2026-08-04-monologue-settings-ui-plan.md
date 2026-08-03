# ひとりごと連作設定UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** ひとりごとの連作回数、主題クールダウン、接続句、避ける話題語を設定UIから変更できるようにする。

**Architecture:** `muchio_llm.py` に設定の既定値と保存時の数値補正を追加し、既存の `/bootstrap` と `/save` の流れで値を受け渡す。`ui/index.html` にLLM設定カードを追加し、既存の `ui/app.js` のbootstrap反映・変更検知・保存を利用する。連作ロジックは既存の設定キーを読むため、UI追加では動作経路を増やさない。

**Tech Stack:** Python標準HTTP設定サーバー、HTML、CSS、Vanilla JavaScript、既存の軽量アサーションテスト。

## Global Constraints

- 既存の保存ボタンと設定再読込を使い、別の保存経路を作らない。
- 連作最大回数は0〜10、主題クールダウンは0〜10に補正する。
- 接続句と避ける話題語はテキストとして保存し、接続句は1行1候補、話題語はカンマ区切りで扱う。
- 既存設定がない環境でも現在の動作と同じ初期値になる。
- UIは現在の暗色テーマ、キーボードフォーカス、モバイル幅のレイアウトを維持する。

---

### Task 1: 設定契約のテスト

**Files:**
- Modify: `test_muchio.py`
- Modify: `test_ui_config.py`

- [ ] 失敗するテストを書く: 新しい設定キーとUIフィールドの存在、数値範囲、textareaのform参加を検証する。
- [ ] `python .\\test_muchio.py` と `python .\\test_ui_config.py` を実行し、未実装キーまたは未実装UIで失敗することを確認する。

### Task 2: バックエンド設定の追加

**Files:**
- Modify: `muchio_llm.py`
- Modify: `config.example.json`

- [ ] `monologue_max_continuations`、`monologue_topic_cooldown`、`monologue_connector_mode`、`monologue_connectors`、`monologue_avoid_words` を既定値へ追加する。
- [ ] `/save` の設定抽出へ追加し、数値を範囲内へ補正する。
- [ ] `/bootstrap` が既定値を含むことを既存のCFG経由で確認する。

### Task 3: 設定カードのHTML

**Files:**
- Modify: `ui/index.html`

- [ ] `LLMと人格` セクションに、最大回数・クールダウン回数・接続句モード・接続句候補・避ける話題語のフィールドを追加する。
- [ ] すべてのフィールドを `cfg` フォームへ参加させる。

### Task 4: bootstrap反映・変更検知・スタイル

**Files:**
- Modify: `ui/app.js`
- Modify: `ui/style.css`

- [ ] checkbox/select/number/textareaを既存のbootstrap反映処理で復元できるようにする。
- [ ] textareaとselectの変更で保存バーを表示する。
- [ ] 候補入力と数値フィールドを既存カードの密度に合わせ、モバイルで1列へ落とす。

### Task 5: 検証

**Files:**
- Test: `test_muchio.py`
- Test: `test_ui_config.py`

- [ ] 2つのテストスクリプト、`python -m py_compile .\\muchio_llm.py`、`git diff --check` を実行する。
- [ ] 失敗があれば実装を修正して再実行し、結果を報告する。
