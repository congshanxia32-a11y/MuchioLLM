from settings_transfer import (
    SECRET_SETTING_KEYS,
    SETTING_CATEGORY_DEFS,
    build_export_document,
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


if __name__ == "__main__":
    test_personality_categories_and_secrets_are_declared()
    test_export_contains_only_selected_category_keys()
    print("ok")
