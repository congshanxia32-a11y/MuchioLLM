# 起動時設定読み込みローディングUI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `/bootstrap` から設定を取得する間、画面全体に読み込み状態を表示し、成功時に閉じ、失敗時は再試行できるようにする。

**Architecture:** 既存の静的HTMLへ初期表示状態のフルスクリーンオーバーレイを追加する。`ui/app.js` の `loadBootstrap()` がオーバーレイの状態を `loading`、`error`、`ready` に更新し、既存の `applyBootstrap()` 完了後にオーバーレイを閉じる。HTTPエラーとJSON解析エラーは同じ失敗経路に集約し、再試行ボタンは同じbootstrap処理を再実行する。

**Tech Stack:** HTML, CSS, vanilla JavaScript, Pythonの静的UIテスト

## Global Constraints

- 既存の静的HTMLを活かし、スケルトンUIやサーバー起動待ちポーリングは追加しない。
- 設定取得中は背後のフォーム操作を遮断する。
- `aria-live="polite"` と `role="status"` で状態変化を通知する。
- ダークテーマ・ライトテーマの双方でローディングUIを読めるようにする。
- `/bootstrap` 成功後は短いフェードアウト後に `hidden` とし、レイアウトから除外する。
- 初期化失敗時はオーバーレイ内に汎用エラーと再試行ボタンを表示する。
- 変更後は既存のPythonテストと静的UIチェックを実行する。

---

### Task 1: ローディングUIの契約をテストで固定する

**Files:**
- Modify: `test_ui_config.py` — ローディング要素、アクセシビリティ属性、状態更新処理の静的契約を追加
- Test: `ui/index.html`, `ui/app.js`, `ui/style.css` — テスト対象

**Interfaces:**
- Consumes: 既存のUTF-8テキスト読み込みパターン
- Produces: 後続実装が満たすHTML/JS/CSSの文字列契約

- [ ] **Step 1: 失敗する静的テストを書く**

`test_ui_config.py` に次のテストを追加する。HTMLには `id="startup-loading"`、`role="status"`、`aria-live="polite"`、`id="startup-loading-retry"` が必要で、JSには `setBootstrapLoadingState`、`loadBootstrap`、`startup-loading-retry` が必要、CSSには `startup-loading` と `startup-loading.is-ready` が必要とする。

```python
def test_startup_loading_overlay_contract_exists():
    html = HTML.read_text(encoding="utf-8")
    app = (Path(__file__).parent / "ui" / "app.js").read_text(encoding="utf-8")
    css = (Path(__file__).parent / "ui" / "style.css").read_text(encoding="utf-8")
    assert 'id="startup-loading"' in html
    assert 'role="status"' in html
    assert 'aria-live="polite"' in html
    assert 'id="startup-loading-retry"' in html
    assert "function setBootstrapLoadingState" in app
    assert "async function loadBootstrap" in app
    assert "startup-loading-retry" in app
    assert "#startup-loading" in css
    assert "#startup-loading.is-ready" in css
```

- [ ] **Step 2: テストが期待どおり失敗することを確認する**

Run: `python -m pytest test_ui_config.py -q`

Expected: FAIL。現時点のHTML、JS、CSSにはローディングオーバーレイの契約がないため、最初の `assert` が失敗する。

- [ ] **Step 3: テストコードの実行形式を既存規約でも確認する**

Run: `python test_ui_config.py`

Expected: FAIL。同じ契約不足が検出されることを確認する。`pytest` が環境にない場合も、後者の直接実行をテスト基準として継続する。

- [ ] **Step 4: テストのみをコミットする**

```bash
git add test_ui_config.py
git commit -m "test: define startup loading UI contract"
```

### Task 2: オーバーレイとbootstrap状態遷移を実装する

**Files:**
- Modify: `ui/index.html` — `body` 内に初期表示のオーバーレイを追加
- Modify: `ui/style.css` — オーバーレイ、スピナー、状態、テーマ、フェードを追加
- Modify: `ui/app.js:288-296` — bootstrapの状態管理とHTTPエラー処理を追加

**Interfaces:**
- Consumes: Task 1の静的契約、既存の `applyBootstrap()`、既存の `toast()`
- Produces: `setBootstrapLoadingState(state, message)`、`loadBootstrap()`、再試行イベント

- [ ] **Step 1: HTMLに初期表示オーバーレイを追加する**

`ui/index.html` の `</body>` 直前、既存の `savebar` と `toast` の近くに次を追加する。初期状態では `hidden` を付けず、HTML表示直後から操作を遮断する。

```html
<div id="startup-loading" role="status" aria-live="polite" aria-label="設定を読み込んでいます">
  <div class="startup-loading-card">
    <div class="startup-loading-mark" aria-hidden="true">✦</div>
    <p class="startup-loading-title">設定を読み込んでいます…</p>
    <p class="startup-loading-message" id="startup-loading-message">しばらくお待ちください</p>
    <div class="startup-loading-spinner" aria-hidden="true"></div>
    <button type="button" class="ghost" id="startup-loading-retry" hidden>再試行</button>
  </div>
</div>
```

- [ ] **Step 2: CSSで読み込み・エラー・完了状態を表現する**

`ui/style.css` に次を追加する。通常状態は `position:fixed`、`inset:0`、十分高い `z-index`、半透明背景で画面全体を覆う。`is-error` ではスピナーを非表示にしてボタンを表示し、`is-ready` では不透明度と可視性を下げる。`hidden` は最後にレイアウトから除外する。

```css
#startup-loading{position:fixed;inset:0;z-index:100;display:grid;place-items:center;
 background:color-mix(in srgb,var(--bg) 92%,transparent);backdrop-filter:blur(8px);
 opacity:1;visibility:visible;transition:opacity .2s,visibility .2s}
#startup-loading[hidden]{display:none}
#startup-loading.is-ready{opacity:0;visibility:hidden;pointer-events:none}
.startup-loading-card{min-width:min(360px,calc(100vw - 32px));padding:28px 30px;text-align:center;
 background:var(--card);border:1px solid var(--line);border-radius:var(--r);box-shadow:0 18px 60px rgba(0,0,0,.24)}
.startup-loading-mark{color:var(--accent2);font-size:1.8em;line-height:1}
.startup-loading-title{margin:12px 0 4px;font-size:1.05em}
.startup-loading-message{margin:0;color:var(--dim);font-size:.85em}
.startup-loading-spinner{width:28px;height:28px;margin:18px auto 0;border:3px solid var(--line);
 border-top-color:var(--accent);border-radius:50%;animation:startup-loading-spin .8s linear infinite}
#startup-loading.is-error .startup-loading-spinner{display:none}
#startup-loading-retry{margin-top:18px}
@keyframes startup-loading-spin{to{transform:rotate(360deg)}}
@media (prefers-reduced-motion:reduce){.startup-loading-spinner{animation:none}}
```

The light theme inherits the existing CSS variables, so no separate color block is required.

- [ ] **Step 3: JavaScriptに状態管理を実装する**

`loadBootstrap()` の前に次の関数を追加する。`ready` ではメッセージを更新して次フレームで `is-ready` を付け、`transitionend` 後に `hidden` を付ける。`loading` では再試行ボタンを隠し、`error` では再試行ボタンを表示する。

```javascript
function setBootstrapLoadingState(state, message){
  const overlay = $('startup-loading');
  const messageEl = $('startup-loading-message');
  const retry = $('startup-loading-retry');
  if(!overlay || !messageEl || !retry) return;
  overlay.classList.toggle('is-error', state === 'error');
  overlay.classList.toggle('is-ready', state === 'ready');
  messageEl.textContent = message || (state === 'error'
    ? '設定を読み込めませんでした'
    : 'しばらくお待ちください');
  retry.hidden = state !== 'error';
  retry.disabled = state === 'loading';
  if(state === 'ready'){
    overlay.addEventListener('transitionend', () => { overlay.hidden = true; }, {once:true});
  }else{
    overlay.hidden = false;
  }
}
```

Replace the existing `loadBootstrap()` body with this flow. Check `response.ok` before parsing JSON so HTTP errors enter the same error UI.

```javascript
async function loadBootstrap(){
  setBootstrapLoadingState('loading', '設定を読み込んでいます…');
  try{
    const response = await fetch('/bootstrap');
    if(!response.ok) throw new Error(`HTTP ${response.status}`);
    const d = await response.json();
    applyBootstrap(d);
    maybeStartTour();
    setBootstrapLoadingState('ready', '読み込み完了');
  }catch(e){
    setBootstrapLoadingState('error', '設定を読み込めませんでした。再試行してください');
    toast('設定の初期値を読み込めませんでした', true);
  }
}

$('startup-loading-retry')?.addEventListener('click', loadBootstrap);
```

- [ ] **Step 4: 直接実行の静的テストを通す**

Run: `python test_ui_config.py`

Expected: PASS and `ok`.

- [ ] **Step 5: 変更をコミットする**

```bash
git add ui/index.html ui/style.css ui/app.js
git commit -m "feat: show startup loading state while settings load"
```

### Task 3: 起動フローと回帰を検証する

**Files:**
- Verify: `test_ui_config.py`, `test_muchio.py`, `ui/index.html`, `ui/style.css`, `ui/app.js`

**Interfaces:**
- Consumes: Task 2のオーバーレイと `loadBootstrap()` 状態遷移
- Produces: テスト結果と、ブラウザで確認できる起動時UI

- [ ] **Step 1: 差分の空白エラーを確認する**

Run: `git diff --check HEAD~1..HEAD`

Expected: 出力なし、終了コード0。

- [ ] **Step 2: UI関連テストを実行する**

Run: `python test_ui_config.py`

Expected: `ok`。

- [ ] **Step 3: 主要な既存テストを実行する**

Run: `python test_muchio.py`

Expected: 既存のテストが最後まで完了する。外部サービスや環境依存で失敗した場合は、失敗したテスト名と出力をそのまま記録する。

- [ ] **Step 4: ブラウザで成功経路を確認する**

`run.bat` で起動し、`http://localhost:8787` を開く。確認項目は次のとおり。

1. `/bootstrap` の応答前に全画面オーバーレイが表示され、フォームを操作できない。
2. `/bootstrap` 成功後にオーバーレイがフェードアウトし、設定値がフォームへ反映される。
3. ブラウザの開発者ツールで `/bootstrap` を一時的に失敗させた場合、エラー文と再試行ボタンが表示される。
4. 再試行中はボタンが無効化され、成功するとオーバーレイが閉じる。

- [ ] **Step 5: 最終状態を確認する**

Run: `git status --short`

Expected: 実装対象外のユーザー変更を除き、作業ツリーがクリーン。

