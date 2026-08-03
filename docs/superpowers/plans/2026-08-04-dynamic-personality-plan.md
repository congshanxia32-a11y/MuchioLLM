# 自動ゆらぎ人格・生成設定 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 人格7項目とLLMのtemperature/top_pを、下限・上限の間で周期的に往復させ、重複再生成時には一時的に多様性を上げる設定とUIを追加する。

**Architecture:** `muchio_llm.py` に時間から現在値を計算する純粋な動的設定関数を追加し、プロンプト生成とOllama payloadの読み取り側だけがそれを使う。設定サーバーはmin/maxと自動ゆらぎ設定を保存し、既存の単一値設定は両端へ移行する。`ui/app.js` と `ui/style.css` は二つのrange入力と現在値マーカーを既存フォームへ組み込む。

**Tech Stack:** Python 3標準ライブラリ、既存のHTTP設定サーバー、Vanilla JavaScript、既存のunittest/pytest互換テスト。

## Global Constraints

- 自動ゆらぎの既定値はOFF。
- 旧設定にmin/maxが無い場合、旧固定値を下限・上限へコピーする。
- 人格値は既存の6段階プロンプト変換を維持する。
- temperatureは0.0〜1.5、top_pは0.1〜1.0の既存範囲を維持する。
- num_predictは自動ゆらぎの対象外。
- 重複・禁止ワード・形式違反の再生成時だけtemperature/top_pを段階的に上げ、新しいseedを使う。

### Task 1: 動的値計算と設定互換のテスト

**Files:**
- Modify: `test_muchio.py`
- Modify: `test_ui_config.py`

**Interfaces:**
- Consumes: planned `dynamic_value(key, static, minimum, maximum, now=None)` and `dynamic_config_value(key, static, lo_key, hi_key, now=None)`.
- Produces: regression tests for runtime interpolation and form persistence.

- [ ] **Step 1: Write failing tests**

  Add tests asserting a disabled/legacy value stays fixed, enabled values stay within bounds, a full period returns to the same endpoint, and UI POST parsing preserves min/max values.

- [ ] **Step 2: Run focused tests to verify failure**

  Run: `python -m pytest test_muchio.py test_ui_config.py -q`

  Expected: FAIL because the dynamic helpers and new config fields do not exist yet.

### Task 2: Python runtime and config persistence

**Files:**
- Modify: `muchio_llm.py`
- Modify: `config.example.json`

**Interfaces:**
- Consumes: Task 1 tests.
- Produces: `dynamic_value`, `dynamic_config_value`, dynamic defaults, backward-compatible `/bootstrap` and `/save` behavior.

- [ ] **Step 1: Implement stable triangle-wave helpers**

  Add a global enable flag, period in minutes, stable per-key phase, and helpers that clamp values and return the static value when disabled or when bounds match.

- [ ] **Step 2: Add defaults and parse/save fields**

  Add `dynamic_enabled`, `dynamic_period_minutes`, `*_min`, `*_max` for the seven traits and `llm_temperature_min/max`, `llm_top_p_min/max`. Preserve old values when new keys are missing and normalize reversed endpoints.

- [ ] **Step 3: Wire current values into prompt and Ollama payload**

  Make `_trait_lines` use the runtime value for each trait and make `ollama_chat` compute runtime temperature/top_p immediately before building `options`. Add `adaptive_sampling(temperature, top_p, diversity)` and pass increasing diversity levels to contract retries and duplicate regeneration.

- [ ] **Step 4: Run focused tests**

  Run: `python -m pytest test_muchio.py test_ui_config.py -q`

  Expected: PASS.

### Task 3: Dual-handle UI and live preview

**Files:**
- Modify: `ui/index.html`
- Modify: `ui/app.js`
- Modify: `ui/style.css`
- Modify: `muchio_llm.py`

**Interfaces:**
- Consumes: Task 2 config keys and bootstrap data.
- Produces: dual range controls for all seven traits and temperature/top_p, animated current markers, and serialized form fields.

- [ ] **Step 1: Add UI metadata and control rendering**

  Extend bootstrap data with dynamic settings metadata and render each item as `*_min` and `*_max` range inputs plus a current-value marker and three numeric labels.

- [ ] **Step 2: Add normalization and preview animation**

  Keep min <= max, update fill/current labels on input, and animate the current marker with the same period/phase calculation used by Python.

- [ ] **Step 3: Add LLM range controls and accessibility labels**

  Add temperature/top_p controls under the LLM card, with explicit labels for lower and upper bounds and no animation when the global toggle is OFF.

- [ ] **Step 4: Verify UI config behavior**

  Run: `python -m pytest test_ui_config.py -q`

  Then start the app and confirm `/bootstrap` includes the new keys and a POST round trip keeps them.

### Task 4: Full verification and documentation

**Files:**
- Modify: `docs/usage.md` or the most relevant existing settings documentation.

- [ ] **Step 1: Run the complete test suite**

  Run: `python -m pytest -q`

- [ ] **Step 2: Run syntax checks**

  Run: `python -m py_compile muchio_llm.py growth.py vrcx_sense.py`

- [ ] **Step 3: Inspect the final diff**

  Run: `git diff --check` and review that only the dynamic settings feature and its tests/docs changed.

- [ ] **Step 4: Update user documentation**

  Document the two endpoints, global period, default OFF behavior, and the fact that personality prompt effects still change at existing six bands.
