# Settings Transfer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a discoverable settings-transfer screen that safely exports selected MuchioLLM settings to JSON and imports selected categories into another installation.

**Architecture:** Keep the existing Python HTTP server and vanilla JavaScript UI. Put category definitions and pure selection/validation/merge logic in a new standard-library-only `settings_transfer.py`, then let `muchio_llm.py` adapt that module to `CFG`, `DEFAULTS`, `CONFIG`, and the existing HTTP handlers. Add a dedicated sidebar section rather than extending the large settings form.

**Tech Stack:** Python 3 standard library, `http.server`, JSON, vanilla HTML/CSS/JavaScript, existing assertion-style Python tests.

## Global Constraints

- The UI must support both JSON export and JSON import.
- Export/import operate on selected categories and leave unselected categories unchanged.
- Existing `config.json` must be backed up before import.
- `peer_supabase_url`, `peer_supabase_key`, and `peer_room` must never be exported or imported.
- Import must validate type, range, length, and restricted enum values.
- Conversation history, diary, voice, and growth data under `data/` are outside this feature.
- No new third-party dependency may be added.
- Preserve existing config save, hot reload, and personality-generation behavior.

---

### Task 1: Add pure category and export-document contracts

**Files:**
- Create: `settings_transfer.py`
- Create: `test_settings_transfer.py`

**Interfaces:**
- `SETTING_CATEGORY_DEFS`: ordered tuples of `(category_id, label, keys)`.
- `SECRET_SETTING_KEYS`: a `frozenset` containing the three peer credential keys.
- `setting_category_payload(defaults, cfg) -> list[dict]`.
- `settings_for_categories(defaults, cfg, categories) -> tuple[list[str], dict]`.
- `build_export_document(defaults, cfg, categories, exported_at) -> dict`.

- [ ] **Step 1: Write the failing tests**

Add tests that construct small `defaults` and `cfg` dictionaries and assert:

```python
def test_personality_categories_and_secrets_are_declared():
    ids = [item[0] for item in SETTING_CATEGORY_DEFS]
    assert {
        "persona-character", "persona-talk", "persona-preferences",
        "persona-free-text", "persona-examples",
    } <= set(ids)
    assert SECRET_SETTING_KEYS == {"peer_supabase_url", "peer_supabase_key", "peer_room"}


def test_export_contains_only_selected_category_keys():
    defaults = {"persona": "default", "examples": "example", "pet_name": "pet",
                "peer_supabase_key": "secret"}
    cfg = {**defaults, "persona": "custom"}
    document = build_export_document(defaults, cfg, ["persona-free-text"], "2026-08-04T00:00:00+0900")
    assert document["format"] == "muchiko-settings"
    assert document["version"] == 1
    assert document["categories"] == ["persona-free-text"]
    assert document["settings"]["persona"] == "custom"
    assert "examples" not in document["settings"]
    assert "peer_supabase_key" not in document["settings"]
```

- [ ] **Step 2: Run the focused test to verify it fails**

Run: `python test_settings_transfer.py`

Expected: FAIL with an import error because `settings_transfer.py` does not exist yet.

- [ ] **Step 3: Implement the minimal pure export module**

Define the ordered category table from the design spec. Make `setting_category_payload` append an `other` category for known keys not explicitly mapped, excluding secret keys. Make `settings_for_categories` validate category IDs, default an empty selection to all non-secret categories, and return only existing non-secret keys. Make `build_export_document` return the exact versioned shape and never include secret keys.

- [ ] **Step 4: Run the focused test to verify it passes**

Run: `python test_settings_transfer.py`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add settings_transfer.py test_settings_transfer.py
git commit -m "feat: add settings transfer export contract"
```

### Task 2: Add validated import merge behavior

**Files:**
- Modify: `settings_transfer.py`
- Modify: `test_settings_transfer.py`

**Interfaces:**
- `sanitize_import_value(key, value, current, defaults) -> object`.
- `merge_import_document(defaults, cfg, document, categories) -> tuple[dict, list[str], list[str]]`.

- [ ] **Step 1: Write the failing tests**

Add tests for selected-category merging, legacy flat `config.json` input, secret rejection, enum validation, numeric clamping, and invalid types:

```python
def test_import_merges_only_selected_categories_and_supports_flat_config():
    defaults = {"persona": "d", "examples": "e", "pet_name": "p", "persona_weight": "mid"}
    cfg = {**defaults, "persona": "old", "examples": "old-example", "pet_name": "keep"}
    merged, imported, ignored = merge_import_document(
        defaults, cfg, {"persona": "new", "examples": "new-example", "pet_name": "replace"},
        ["persona-free-text"],
    )
    assert merged["persona"] == "new"
    assert merged["examples"] == "old-example"
    assert merged["pet_name"] == "keep"
    assert imported == ["persona"]
    assert "examples" in ignored and "pet_name" in ignored


def test_import_rejects_secret_and_invalid_enum():
    defaults = {"persona": "d", "persona_weight": "mid", "peer_supabase_key": ""}
    cfg = dict(defaults)
    document = {"settings": {"persona_weight": "unsafe", "peer_supabase_key": "leak"}}
    try:
        merge_import_document(defaults, cfg, document, ["persona-free-text"])
    except ValueError as exc:
        assert "persona_weight" in str(exc)
    else:
        raise AssertionError("invalid enum was accepted")
```

Also assert that a numeric value outside its configured range is clamped and a boolean/string mismatch raises `ValueError`.

- [ ] **Step 2: Run the focused test to verify it fails**

Run: `python test_settings_transfer.py`

Expected: FAIL because the import functions do not exist.

- [ ] **Step 3: Implement the minimal import logic**

Accept either a versioned document with a `settings` object or a flat config dictionary. Resolve the selected category IDs through the same category table used by export. Ignore keys outside the selected categories, unknown keys, and secret keys. Validate booleans, numbers, strings, `mode`, `trait_weight`, and `persona_weight`; clamp the documented numeric ranges and enforce existing maximum string lengths. Return the merged dictionary plus sorted imported and ignored key lists.

- [ ] **Step 4: Run the focused test to verify it passes**

Run: `python test_settings_transfer.py`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add settings_transfer.py test_settings_transfer.py
git commit -m "feat: validate settings transfer imports"
```

### Task 3: Wire the Python server and config backups

**Files:**
- Modify: `muchio_llm.py:137-280`, `muchio_llm.py:_bootstrap_data`, `muchio_llm.py:_UIHandler`
- Modify: `test_settings_transfer.py`

**Interfaces:**
- `GET /settings_export?categories=<comma-separated-ids>` returns a JSON attachment named `muchiko-settings.json`.
- `POST /settings_import` accepts `{document, categories, cfg_mtime}` and returns `{ok, mtime, categories, imported, ignored}`.
- `_backup_path(CONFIG, "import")` remains the backup naming mechanism.

- [ ] **Step 1: Write failing server-contract tests**

Add source-contract tests that assert `_bootstrap_data()` exposes `setting_categories`, that the handler source contains both routes and `Content-Disposition`, and that importing calls the existing backup helper before writing `CONFIG`. Add a direct test of the pure document returned for the current `CFG` so this is not only a string-presence check.

- [ ] **Step 2: Run the focused tests to verify failure**

Run: `python test_settings_transfer.py`

Expected: FAIL because the current bootstrap and handler have no transfer routes.

- [ ] **Step 3: Implement the server wiring**

Import the pure helpers. Add `setting_categories` to `_bootstrap_data()`. Add a small `_send_download_json` method to the handler. In `do_GET`, parse `categories`, build the export document, and send it as UTF-8 JSON with `Content-Disposition: attachment; filename="muchiko-settings.json"`. In `do_POST`, parse the JSON body, reject stale `cfg_mtime` with 409, merge through the pure helper, copy `CONFIG` to `_backup_path(CONFIG, "import")`, write the merged config, call `load_cfg()`, and return the result. Return 400 for JSON, type, format, or value errors.

- [ ] **Step 4: Run focused and existing tests**

Run: `python test_settings_transfer.py` and `python test_ui_config.py`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add muchio_llm.py test_settings_transfer.py
git commit -m "feat: add settings transfer endpoints"
```

### Task 4: Build the independent transfer screen

**Files:**
- Modify: `ui/index.html:16-22`, `ui/index.html` near the main section close
- Modify: `ui/app.js:191-220`, `ui/app.js` navigation helpers
- Modify: `ui/style.css` transfer and responsive rules
- Modify: `test_ui_config.py`

**Interfaces:**
- Sidebar button uses `data-section="transfer"`.
- Main section uses `id="settings-transfer"` and `data-section="transfer"`.
- Category checkboxes use `data-transfer-category` and `data-transfer-group`.
- Buttons use `id="settings-export"`, `id="settings-import"`, and file input `id="settings-import-file"`.

- [ ] **Step 1: Write failing UI contract tests**

Add assertions that the sidebar contains the transfer section, the page has separate export/import panels, the file input accepts JSON, and `ui/app.js` contains download and import calls for `/settings_export` and `/settings_import`. Assert the copy mentions that secrets are excluded and import creates a backup.

- [ ] **Step 2: Run the focused UI test to verify it fails**

Run: `python test_ui_config.py`

Expected: FAIL because the current HTML and JavaScript do not contain the transfer screen.

- [ ] **Step 3: Implement the UI with intentional hierarchy**

Add the new sidebar item and section. Use a calm two-panel layout with a short explanation, a category summary, explicit select-all/select-none controls, and strong action buttons. Render category checkboxes from `/bootstrap` data so labels stay in sync with the server. Keep the existing dark/light theme variables, keyboard focus styles, mobile one-column layout, and reduced-motion behavior.

- [ ] **Step 4: Implement the browser interactions**

Call `renderSettingsTransfer(d.setting_categories || [])` from `applyBootstrap`. Bind selection helpers once. For export, require at least one category, fetch the endpoint, create a blob URL, trigger `muchiko-settings.json`, revoke the URL, and show a success/error toast. For import, require a file and category, parse JSON, confirm the backup, POST the document and current mtime, refresh bootstrap and prompt state after success, and show imported item count. Handle 409 and server errors with concrete messages.

- [ ] **Step 5: Run the UI contract tests**

Run: `python test_ui_config.py`

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add ui/index.html ui/app.js ui/style.css test_ui_config.py
git commit -m "feat: add settings transfer screen"
```

### Task 5: Verify end-to-end behavior and polish

**Files:**
- Modify: `test_settings_transfer.py` if an integration regression is found
- Modify: `ui/index.html`, `ui/app.js`, or `ui/style.css` only for verified issues

- [ ] **Step 1: Run all repository tests**

Run: `python test_settings_transfer.py; python test_ui_config.py; python test_muchio.py; python test_peer_idle.py; python test_social_context.py; python test_muchio_relay.py; python test_voiceid.py`

Expected: all scripts exit successfully.

- [ ] **Step 2: Start the existing UI server without saving settings**

Run: `python muchio_llm.py` in a separate process and open `http://localhost:8787`. Do not click the existing Save, model download, update, reset, purge, or destructive memory controls.

- [ ] **Step 3: Verify the transfer screen visually and functionally**

Confirm the sidebar opens the transfer screen, all categories are readable, the layout collapses to one column at narrow width, keyboard focus is visible, export downloads `muchiko-settings.json`, and the exported JSON does not contain the three peer secret keys. Use a copy of the exported file for import so the live config is not changed unexpectedly.

- [ ] **Step 4: Check the final diff and repository state**

Run: `git diff HEAD~4 --check` and `git status --short`.

Expected: no whitespace errors; only the settings-transfer implementation and its tests/docs are changed; no generated JSON or runtime data is added.

- [ ] **Step 5: Commit any verified polish**

```bash
git add settings_transfer.py muchio_llm.py ui/index.html ui/app.js ui/style.css test_settings_transfer.py test_ui_config.py
git commit -m "test: verify settings transfer workflow"
```
