from pathlib import Path

import muchio_llm as m
from settings_transfer import (
    SECRET_SETTING_KEYS,
    SETTING_CATEGORY_DEFS,
    build_export_document,
    merge_import_document,
)


def test_personality_categories_and_secrets_are_declared():
    ids = [item[0] for item in SETTING_CATEGORY_DEFS]
    assert {
        "persona-character", "persona-talk", "persona-preferences",
        "persona-free-text", "persona-examples",
    } <= set(ids)
    assert SECRET_SETTING_KEYS == {"peer_supabase_url", "peer_supabase_key", "peer_room"}


def test_export_contains_only_selected_category_keys():
    defaults = {
        "persona": "default",
        "examples": "example",
        "pet_name": "pet",
        "peer_supabase_key": "secret",
    }
    cfg = {**defaults, "persona": "custom"}
    document = build_export_document(
        defaults, cfg, ["persona-free-text"], "2026-08-04T00:00:00+0900"
    )
    assert document["format"] == "muchiko-settings"
    assert document["version"] == 1
    assert document["categories"] == ["persona-free-text"]
    assert document["settings"]["persona"] == "custom"
    assert "examples" not in document["settings"]
    assert "peer_supabase_key" not in document["settings"]


def test_import_merges_only_selected_categories_and_supports_flat_config():
    defaults = {"persona": "d", "examples": "e", "pet_name": "p", "persona_weight": "mid"}
    cfg = {**defaults, "persona": "old", "examples": "old-example", "pet_name": "keep"}
    merged, imported, ignored = merge_import_document(
        defaults,
        cfg,
        {"persona": "new", "examples": "new-example", "pet_name": "replace"},
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


def test_import_clamps_numbers_and_rejects_boolean_string_mismatch():
    defaults = {"reply_chance": 0.5, "dynamic_enabled": False}
    cfg = dict(defaults)
    merged, imported, _ignored = merge_import_document(
        defaults,
        cfg,
        {"settings": {"reply_chance": 4, "dynamic_enabled": "yes"}},
        ["talk"],
    )
    assert merged["reply_chance"] == 1.0
    assert imported == ["reply_chance"]
    try:
        merge_import_document(
            defaults, cfg, {"settings": {"dynamic_enabled": "yes"}}, ["brain"]
        )
    except ValueError as exc:
        assert "dynamic_enabled" in str(exc)
    else:
        raise AssertionError("boolean/string mismatch was accepted")


def test_bootstrap_and_handler_expose_settings_transfer_contract():
    bootstrap = m._bootstrap_data()
    assert bootstrap["setting_categories"]
    source = Path(m.__file__).read_text(encoding="utf-8")
    assert 'path == "/settings_export"' in source
    assert 'self.path == "/settings_import"' in source
    assert "Content-Disposition" in source
    assert '_backup_path(CONFIG, "import")' in source


if __name__ == "__main__":
    test_personality_categories_and_secrets_are_declared()
    test_export_contains_only_selected_category_keys()
    test_import_merges_only_selected_categories_and_supports_flat_config()
    test_import_rejects_secret_and_invalid_enum()
    test_import_clamps_numbers_and_rejects_boolean_string_mismatch()
    test_bootstrap_and_handler_expose_settings_transfer_contract()
    print("ok")
