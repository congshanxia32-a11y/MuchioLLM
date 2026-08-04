"""Pure helpers for moving safe MuchioLLM settings between installations."""


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
