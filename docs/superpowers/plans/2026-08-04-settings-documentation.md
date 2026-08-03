# 設定画面ドキュメント整備 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** MuchioLLMの設定画面を実撮影し、個人情報を黒塗りした注釈付き画像をREADMEとusageガイドへ追加する。

**Architecture:** 起動中のlocalhost設定画面をPlaywright CLIでカテゴリ単位に撮影する。撮影済みPNGへ赤い番号・矢印・説明ラベル・黒塗りを重ね、公開画像だけを `docs/images/settings/` に置く。Markdownは初回設定の順番に沿って画像を参照し、既存の未コミット変更には触れない。

**Tech Stack:** Playwright CLI、既存のブラウザUI、Python標準ライブラリまたはWindows標準の画像処理、Markdown、Git。

## Global Constraints

- 公開用画像には実データを残さない。
- ニックネーム、飼い主名、フレンド名、部屋名、ワールド名、プロンプト内の固有名詞、パス、ID、トークン、ログ識別子を確認する。
- 残った個人情報はモザイクではなく黒塗りの矩形で完全に覆う。
- 画像は `docs/images/settings/` に保存する。
- `README.md` と `docs/usage.md` の設定説明だけを更新し、既存の未コミット変更を上書きしない。
- 最後に `git diff --check` と画像・Markdownリンクの確認を行う。

---

### Task 1: 撮影対象と匿名化箇所を確定する

**Files:**
- Read: `ui/index.html`, `ui/app.js`, `README.md`, `docs/usage.md`
- Create: `output/playwright/` の一時スクリーンショット

**Interfaces:**
- Consumes: `http://localhost:8787` の現在の設定画面
- Produces: 撮影する6カテゴリ、画面状態、黒塗り対象の一覧

- [ ] **Step 1: Playwrightで設定画面を開き、最新snapshotを取得する**

```powershell
npx --yes --package @playwright/cli playwright-cli open http://localhost:8787
npx --yes --package @playwright/cli playwright-cli snapshot
```

- [ ] **Step 2: 各カテゴリを1回ずつ選択し、遷移後にsnapshotを取り直す**

対象は「はじめに」「基本設定」「LLMと人格」「音声と表示」「連携と記憶」「保守とログ」。各クリック後にsnapshotを実行し、対象カードが表示されていることを確認する。

- [ ] **Step 3: 個人情報の表示箇所を台帳化する**

画面上の名前、部屋名、フレンド名、自由テキスト、プロンプト、ログ、パス、IDを確認し、撮影後に黒塗りする矩形またはサンプル値置換として記録する。実値は計画書・README・注釈テキストへ転記しない。

- [ ] **Step 4: 起動中サービスを変更しないことを確認する**

保存ボタン、モデルのダウンロード、更新、削除、音声デバイス変更などの副作用のある操作は行わない。必要な表示状態は読み取り専用の操作で作る。

### Task 2: 匿名化済みのカテゴリ別スクリーンショットを作る

**Files:**
- Create: `docs/images/settings/01-start.png`
- Create: `docs/images/settings/02-basic.png`
- Create: `docs/images/settings/03-llm-personality.png`
- Create: `docs/images/settings/04-audio-display.png`
- Create: `docs/images/settings/05-integrations-memory.png`
- Create: `docs/images/settings/06-maintenance.png`

**Interfaces:**
- Consumes: Task 1のカテゴリ一覧と匿名化台帳
- Produces: 実データを含まない、注釈前のカテゴリ別PNG

- [ ] **Step 1: 各カテゴリを必要な位置までスクロールして撮影する**

画面全体が読めない長さになるカテゴリは、1カテゴリを2枚までに分ける。raw画像は `output/playwright/` に置き、公開用ファイルにはコピーする前に匿名化する。

- [ ] **Step 2: サンプル値で置き換えられる表示を安全な値へ変更する**

設定保存を伴う操作は避け、Playwrightの表示上だけで置換できる場合に限定する。置換できない実データは黒塗り対象にする。

- [ ] **Step 3: 個人情報を黒塗りして公開用PNGへ出力する**

黒塗りは文字の端が残らないよう、対象領域より上下左右に余白を取る。小さな文字を隠す場合も読める断片を残さない。元画像は `docs/images/settings/` に置かない。

- [ ] **Step 4: 画像を目視確認する**

各PNGを開き、黒塗りの下の文字が読めないこと、画像の端に名前やパスが残っていないこと、文字がつぶれて設定説明を妨げていないことを確認する。

### Task 3: 矢印・番号・短い説明を重ねる

**Files:**
- Modify: `docs/images/settings/01-start.png`
- Modify: `docs/images/settings/02-basic.png`
- Modify: `docs/images/settings/03-llm-personality.png`
- Modify: `docs/images/settings/04-audio-display.png`
- Modify: `docs/images/settings/05-integrations-memory.png`
- Modify: `docs/images/settings/06-maintenance.png`

**Interfaces:**
- Consumes: Task 2の匿名化済みPNG
- Produces: READMEから直接参照できる注釈付きPNG

- [ ] **Step 1: 初心者が最初に見る場所へ番号を付ける**

各画像で番号は最大5個にし、番号の説明は画像内またはMarkdown直下に短く書く。必須項目には「まず」、任意項目には「必要なら」を使う。

- [ ] **Step 2: 重要な入力欄へ矢印を追加する**

矢印は赤色、太さは背景上で読める値、先端は対象ラベルまたは入力欄の余白へ置く。UIの文字を覆わない。長い説明は画像内に詰め込まずMarkdownへ置く。

- [ ] **Step 3: 画像の可読性を確認する**

明暗テーマのどちらでも矢印と番号が見えること、スマートフォン幅に縮小しても番号の順番が追えることを確認する。

### Task 4: READMEとusageガイドを更新する

**Files:**
- Modify: `README.md`
- Modify: `docs/usage.md`

**Interfaces:**
- Consumes: Task 3の6枚の注釈付きPNG
- Produces: 画像付きの初回設定ガイドとカテゴリ別参照リンク

- [ ] **Step 1: READMEの初回設定へ導入画像とリンクを追加する**

`run.bat` 起動後に `http://localhost:8787` を開く流れの直後へ、はじめに・基本設定・LLMの画像を置く。画像には内容を説明する日本語alt textを付ける。

- [ ] **Step 2: docs/usage.mdへカテゴリ別の説明を追加する**

初回設定、LLMと人格、音声と表示、連携と記憶、保守とログの順で、各画像の下に「目的」「最初に触る項目」「保存時の注意」を2〜4文で書く。実在の名前や個人情報は例に使わない。

- [ ] **Step 3: 既存リンクと画像パスを確認する**

READMEからの相対パスは `docs/images/settings/...`、`docs/usage.md`からの相対パスは `images/settings/...` にする。ファイル名の大文字小文字も実ファイルと一致させる。

- [ ] **Step 4: Markdownの個人情報を検索する**

既存の実データに見える名前、部屋名、ID、パス、トークンを追加していないことを確認する。撮影台帳やraw画像をコミット対象に含めない。

### Task 5: 最終検証

**Files:**
- Read: `README.md`, `docs/usage.md`, `docs/images/settings/*.png`

**Interfaces:**
- Consumes: Task 4のドキュメントと画像
- Produces: 完了判定と検証結果

- [ ] **Step 1: Markdownリンクの存在を確認する**

READMEとusageに出てくる `docs/images/settings/` または `images/settings/` の各パスが実在することをPowerShellで確認する。

- [ ] **Step 2: 画像を再確認する**

6枚を順番に開き、個人情報の残存、黒塗り漏れ、矢印の誤指示、番号の重複を確認する。

- [ ] **Step 3: 差分の空白エラーを確認する**

```powershell
git diff --check
```

Expected: no output and exit code 0。

- [ ] **Step 4: 変更範囲を確認する**

```powershell
git status --short
git diff --stat
```

既存の未コミット変更が意図せず含まれていないことを確認する。
