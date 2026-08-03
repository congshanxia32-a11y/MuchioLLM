import time

import growth
import muchio_llm as muchio
import vrcx_sense


def test_growth_social_context_uses_current_nicknames_and_filters_names():
    old_state = growth._state
    old_present = growth._present
    old_owner = growth._owner
    old_board = growth._board
    try:
        growth._state = {
            "bond": 30.0,
            "bond_ts": time.time(),
            "people": {
                "u1": {"name": "Alice", "nick": "Ari", "met": 4},
                "u2": {"name": "TooLong" * 20, "met": 2},
                "u3": {"name": "Bad\x00Name", "met": 2},
                "u4": {"name": "Hidden", "met": 2},
            },
        }
        growth._present = {"u1", "u2", "u3", "u4"}
        growth._owner = "Owner"
        growth._board = lambda text: "" if text == "Hidden" else text

        context = growth.social_context()

        assert "主人：Owner" in context
        assert "Ari" in context
        assert "Hidden" not in context
        assert "Bad" not in context
        assert "TooLong" not in context
        assert "かなり親しい" in context
    finally:
        growth._state = old_state
        growth._present = old_present
        growth._owner = old_owner
        growth._board = old_board


def test_vrcx_world_context_returns_current_world_only():
    old_world = vrcx_sense._world
    try:
        vrcx_sense._world = {"name": "Japan Shrine", "visits": 3, "itype": "public"}
        assert vrcx_sense.world_context() == "いまのワールド：Japan Shrine"
        vrcx_sense._world = None
        assert vrcx_sense.world_context() == ""
    finally:
        vrcx_sense._world = old_world


def test_vrcx_failure_clears_social_context():
    old_growth_dead = growth._dead
    old_vrcx_dead = vrcx_sense._dead
    old_owner = growth._owner
    old_world = vrcx_sense._world
    old_cfg = dict(muchio.CFG)
    try:
        muchio.CFG["social_context_enabled"] = True
        muchio.CFG["vrcx_enabled"] = True
        growth._dead = True
        vrcx_sense._dead = True
        growth._owner = "Owner"
        vrcx_sense._world = {"name": "Japan Shrine"}
        assert growth.social_context() == ""
        assert vrcx_sense.world_context() == ""
        assert muchio.social_context_prompt() == ""
    finally:
        growth._dead = old_growth_dead
        vrcx_sense._dead = old_vrcx_dead
        growth._owner = old_owner
        vrcx_sense._world = old_world
        muchio.CFG.clear()
        muchio.CFG.update(old_cfg)


def test_social_context_prompt_is_available_for_compact_models_and_can_turn_off():
    old_cfg = dict(muchio.CFG)
    old_growth = growth.social_context
    old_world = vrcx_sense.world_context
    try:
        muchio.CFG["social_context_enabled"] = True
        muchio.CFG["vrcx_enabled"] = True
        growth.social_context = lambda en=False: "主人：Owner。いま近くにいる友達：Ari。"
        vrcx_sense.world_context = lambda en=False: "いまのワールド：Japan Shrine"

        prompt = muchio.social_context_prompt()
        assert "Owner" in prompt
        assert "Ari" in prompt
        assert "Japan Shrine" in prompt

        muchio.CFG["social_context_enabled"] = False
        assert muchio.social_context_prompt() == ""
    finally:
        muchio.CFG.clear()
        muchio.CFG.update(old_cfg)
        growth.social_context = old_growth
        vrcx_sense.world_context = old_world


def test_system_prompt_includes_social_context_for_compact_model():
    old_cfg = dict(muchio.CFG)
    old_profile = muchio.model_prompt_profile
    old_mode = muchio.effective_mode
    old_growth = growth.social_context
    old_world = vrcx_sense.world_context
    try:
        muchio.CFG["social_context_enabled"] = True
        muchio.CFG["vrcx_enabled"] = True
        muchio.CFG["mode"] = "jp"
        muchio.model_prompt_profile = lambda: "compact"
        muchio.effective_mode = lambda: "jp"
        growth.social_context = lambda en=False: "Owner: Owner. Friend: Ari."
        vrcx_sense.world_context = lambda en=False: "World: Japan Shrine"
        prompt = muchio.system_prompt()
        assert "Owner" in prompt and "Ari" in prompt and "Japan Shrine" in prompt
    finally:
        muchio.CFG.clear()
        muchio.CFG.update(old_cfg)
        muchio.model_prompt_profile = old_profile
        muchio.effective_mode = old_mode
        growth.social_context = old_growth
        vrcx_sense.world_context = old_world


if __name__ == "__main__":
    test_growth_social_context_uses_current_nicknames_and_filters_names()
    test_vrcx_world_context_returns_current_world_only()
    test_vrcx_failure_clears_social_context()
    test_social_context_prompt_is_available_for_compact_models_and_can_turn_off()
    test_system_prompt_includes_social_context_for_compact_model()
    print("ok")
