"""Pure helpers for moving safe MuchioLLM settings between installations."""

import math


SECRET_SETTING_KEYS = frozenset({
    "peer_supabase_url",
    "peer_supabase_key",
    "peer_room",
})


SETTING_CATEGORY_DEFS = [
    ("profile", "なまえ", ("pet_name", "pet_name_en", "owner_name")),
    ("core", "基本説明", ("core_prompt_enabled", "core_identity", "core_friend_intro",
                             "core_identity_en", "core_friend_intro_en")),
    ("talk", "おしゃべり", ("reply_chance", "friend_reply_chance", "poke_chance",
                               "cooldown", "listen_window", "idle_seconds", "friend_context",
                               "max_reply", "board_cells", "kanji_mode", "osc_proxy",
                               "typing_speed", "center_jp", "center_en")),
    ("brain", "あたま(LLM)", ("mode", "model", "model_en", "think", "dynamic_enabled",
                                "dynamic_period_minutes", "llm_temperature", "llm_temperature_min",
                                "llm_temperature_max", "llm_top_p", "llm_top_p_min",
                                "llm_top_p_max", "llm_num_predict")),
    ("persona-character", "じんかく・せいかく", (
        "persona_character_enabled", "trait_smart", "trait_smart_min", "trait_smart_max",
        "trait_mean", "trait_mean_min", "trait_mean_max", "trait_energy", "trait_energy_min",
        "trait_energy_max", "trait_instinct", "trait_instinct_min", "trait_instinct_max",
        "trait_optimism", "trait_optimism_min", "trait_optimism_max", "trait_weight",
    )),
    ("persona-talk", "じんかく・はなしかた", (
        "persona_talk_enabled", "trait_verbose", "trait_verbose_min", "trait_verbose_max",
        "trait_hard", "trait_hard_min", "trait_hard_max",
    )),
    ("persona-preferences", "じんかく・こだわり", (
        "persona_preferences_enabled", "rule_trivia", "rule_asks", "rule_polite", "rule_names",
    )),
    ("persona-free-text", "じんかく・じゆうテキスト", (
        "persona_free_text_enabled", "persona", "persona_en", "persona_weight",
    )),
    ("persona-examples", "じんかく・れいぶん", (
        "persona_examples_enabled", "examples", "examples_en",
    )),
    ("advanced-rules", "まもりのルール", (
        "advanced_rules_enabled", "base_rules", "base_rules_en", "rules", "rules_en",
    )),
    ("advanced-aizuchi", "あいづち", (
        "advanced_aizuchi_enabled", "aizuchi", "aizuchi_en",
    )),
    ("advanced-safety", "まもり", (
        "advanced_safety_enabled", "fake_profile", "fake_profile_en", "ng_words", "qa_notes",
    )),
    ("advanced-growth", "そだち", (
        "advanced_growth_enabled", "bond_gain", "bond_halflife_days", "tier_regular",
        "absence_days", "auto_adopt_days",
    )),
    ("advanced-sense", "せかい", (
        "advanced_sense_enabled", "world_comment_chance", "song_comment_chance", "care_hours",
        "care_hour", "diary",
    )),
    ("advanced-listener", "耳(リスナー)", (
        "advanced_listener_enabled", "rms_gate", "silence_end", "stt_hint", "stt_hint_en",
        "voice_threshold",
    )),
    ("peer", "Muchio間通信", (
        "peer_enabled", "peer_max_turns", "peer_idle_enabled", "peer_idle_after_minutes",
        "peer_idle_interval_minutes", "peer_idle_daily_limit",
    )),
    ("vrcx", "なかま / VRCX連携", (
        "vrcx_enabled", "greet_friends", "social_context_enabled",
    )),
    ("memory", "記憶", (
        "memory_conversation_enabled", "memory_diary_enabled",
    )),
    ("memory-words", "単語の記憶", ("memory_words_enabled",)),
    ("monologue", "ひとりごと", (
        "monologue_max_continuations", "monologue_topic_cooldown", "monologue_connector_mode",
        "monologue_connectors", "monologue_avoid_words",
    )),
]

_SETTING_CATEGORY_BY_KEY = {
    key: category_id
    for category_id, _label, keys in SETTING_CATEGORY_DEFS
    for key in keys
}


_IMPORT_RANGES = {
    "reply_chance": (0.0, 1.0), "friend_reply_chance": (0.0, 1.0),
    "poke_chance": (0.0, 1.0), "world_comment_chance": (0.0, 1.0),
    "song_comment_chance": (0.0, 1.0), "cooldown": (0.0, 300.0),
    "listen_window": (0.0, 30.0), "idle_seconds": (0.0, 3600.0),
    "friend_context": (0, 50), "max_reply": (10, 128), "board_cells": (64, 128),
    "typing_speed": (0.0, 0.5), "center_jp": (0, 31), "center_en": (0, 31),
    "dynamic_period_minutes": (1.0, 180.0), "llm_temperature": (0.0, 1.5),
    "llm_temperature_min": (0.0, 1.5), "llm_temperature_max": (0.0, 1.5),
    "llm_top_p": (0.1, 1.0), "llm_top_p_min": (0.1, 1.0),
    "llm_top_p_max": (0.1, 1.0), "llm_num_predict": (1, 2048),
    "peer_max_turns": (1, 32), "peer_idle_after_minutes": (5, 120),
    "peer_idle_interval_minutes": (10, 180), "peer_idle_daily_limit": (1, 24),
    "bond_gain": (0.0, 5.0), "bond_halflife_days": (0.5, 60.0),
    "tier_regular": (2, 100), "absence_days": (1, 365), "auto_adopt_days": (0, 100),
    "care_hours": (0.0, 24.0), "care_hour": (0, 23), "rms_gate": (50, 5000),
    "silence_end": (0.2, 3.0), "voice_threshold": (0.3, 0.9),
}
for _trait_key in ("trait_smart", "trait_mean", "trait_energy", "trait_instinct",
                   "trait_optimism", "trait_verbose", "trait_hard"):
    _IMPORT_RANGES[_trait_key] = (0, 100)
    _IMPORT_RANGES[f"{_trait_key}_min"] = (0, 100)
    _IMPORT_RANGES[f"{_trait_key}_max"] = (0, 100)

_IMPORT_MAX_LENGTHS = {
    "pet_name": 16, "pet_name_en": 32, "owner_name": 32,
    "core_identity": 500, "core_friend_intro": 500, "core_identity_en": 500,
    "core_friend_intro_en": 500, "persona": 500, "persona_en": 500,
    "ng_words": 500, "qa_notes": 1500, "fake_profile": 500, "fake_profile_en": 500,
    "rules": 1500, "rules_en": 1500, "examples": 600, "examples_en": 600,
    "aizuchi": 300, "aizuchi_en": 300, "stt_hint": 200, "stt_hint_en": 200,
    "model": 120, "model_en": 120, "base_rules": 1500, "base_rules_en": 1500,
    "monologue_connectors": 2000, "monologue_avoid_words": 500,
}

_IMPORT_ENUMS = {
    "mode": {"auto", "jp", "en"},
    "trait_weight": {"low", "mid", "high"},
    "persona_weight": {"low", "mid", "high"},
    "monologue_connector_mode": {"always", "random", "off"},
}


def setting_category_payload(defaults, cfg):
    """Return UI-ready category definitions, including newly added keys."""
    known = set(defaults) | set(cfg)
    extras = sorted(known - set(_SETTING_CATEGORY_BY_KEY) - SECRET_SETTING_KEYS)
    definitions = list(SETTING_CATEGORY_DEFS)
    if extras:
        definitions.append(("other", "その他", tuple(extras)))
    return [
        {"id": category_id, "label": label, "keys": list(keys)}
        for category_id, label, keys in definitions
    ]


def settings_for_categories(defaults, cfg, categories):
    """Return valid selected category IDs and safe current settings."""
    payload = setting_category_payload(defaults, cfg)
    valid = {item["id"] for item in payload}
    selected = [category_id for category_id in categories if category_id in valid]
    if not selected:
        selected = [item["id"] for item in payload]
    keys = {
        key
        for item in payload
        if item["id"] in selected
        for key in item["keys"]
        if key not in SECRET_SETTING_KEYS
    }
    return selected, {key: cfg[key] for key in sorted(keys) if key in cfg}


def build_export_document(defaults, cfg, categories, exported_at):
    selected, settings = settings_for_categories(defaults, cfg, categories)
    return {
        "format": "muchiko-settings",
        "version": 1,
        "exported_at": exported_at,
        "categories": selected,
        "settings": settings,
    }


def sanitize_import_value(key, value, current, defaults):
    """Validate and normalize one imported value using the current config type."""
    reference = current[key] if key in current else defaults.get(key)
    if isinstance(reference, bool):
        if not isinstance(value, bool):
            raise ValueError(f"{key} は真偽値ではありません")
        return value
    if isinstance(reference, (int, float)) and not isinstance(reference, bool):
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            raise ValueError(f"{key} は数値ではありません")
        if not math.isfinite(float(value)):
            raise ValueError(f"{key} は有限の数値ではありません")
        lo, hi = _IMPORT_RANGES.get(key, (None, None))
        if lo is not None:
            value = min(hi, max(lo, value))
        return int(round(value)) if isinstance(reference, int) else float(value)
    if isinstance(reference, str):
        if not isinstance(value, str):
            raise ValueError(f"{key} は文字列ではありません")
        choices = _IMPORT_ENUMS.get(key)
        if choices is not None and value not in choices:
            raise ValueError(f"{key} の値が不正です")
        return value[:_IMPORT_MAX_LENGTHS.get(key, 4000)]
    raise ValueError(f"{key} の型を判定できません")


def merge_import_document(defaults, cfg, document, categories):
    """Merge safe values from a versioned or legacy config document."""
    if not isinstance(document, dict):
        raise ValueError("読み込みデータの形式が不正です")
    if document.get("format") not in (None, "muchiko-settings"):
        raise ValueError("むちこの設定ファイルではありません")
    settings = document.get("settings", document)
    if not isinstance(settings, dict):
        raise ValueError("設定値の形式が不正です")

    selected, _ = settings_for_categories(defaults, cfg, categories)
    payload = setting_category_payload(defaults, cfg)
    allowed = {
        key
        for item in payload
        if item["id"] in selected
        for key in item["keys"]
    }
    merged = dict(cfg)
    imported = []
    ignored = []
    for key, value in settings.items():
        if key in SECRET_SETTING_KEYS or key not in allowed:
            ignored.append(key)
            continue
        if key not in cfg and key not in defaults:
            ignored.append(key)
            continue
        merged[key] = sanitize_import_value(key, value, cfg, defaults)
        imported.append(key)
    return merged, sorted(imported), sorted(ignored)
