import time

import muchio_relay as relay


def test_settings_validation():
    base = {
        "peer_supabase_url": "https://example.supabase.co",
        "peer_supabase_key": "public-key",
        "peer_room": "room_code_123",
    }
    assert relay.validate_settings(base) is None
    assert relay.validate_settings({**base, "peer_room": "short"})
    assert relay.validate_settings({**base, "peer_supabase_key": "service_role_secret"})
    assert relay.validate_settings({**base, "peer_supabase_url": "http://example.supabase.co"})


def test_message_validation_and_self_filtering():
    message = relay.make_message("こんにちは", "sender-a", "conversation-a", 8)
    assert relay.validate_message(message, "sender-b", 8)["text"] == "こんにちは"
    assert relay.validate_message({"payload": message}, "sender-b", 8)
    assert relay.validate_message(message, "sender-a", 8) is None
    assert relay.validate_message({**message, "version": 2}, "sender-b", 8) is None
    assert relay.validate_message({**message, "turn": 9}, "sender-b", 8) is None
    assert relay.validate_message({**message, "text": "x" * (relay.MAX_TEXT + 1)}, "sender-b", 8) is None


def test_message_payload_does_not_add_social_context_fields():
    message = relay.make_message("Ari is here", "sender-a", "conversation-a", 8)
    assert set(message) == {"type", "version", "message_id", "sender_id", "conversation_id", "text", "turn"}
    assert "friends" not in message and "world" not in message and "owner" not in message


def test_hello_elects_one_leader_without_social_data():
    hello = relay.make_hello("sender-a")
    assert set(hello) == {"type", "version", "sender_id"}
    assert relay.validate_hello(hello, "sender-b")["sender_id"] == "sender-a"
    assert relay.validate_hello(hello, "sender-a") is None
    assert relay.select_leader(("sender-b", "sender-a")) == "sender-a"
    assert relay.select_leader(("sender-a",)) == "sender-a"


def test_turn_limit_simulation():
    current = relay.make_message("start", "sender-a", "conversation-a", 8)
    received = []
    for sender in ("sender-b", "sender-a") * 4:
        current = relay.validate_message(current, sender, 8)
        if current is None:
            break
        received.append(current)
        if current["turn"] <= 1:
            break
        current = relay.make_message("reply", sender, current["conversation_id"], current["turn"] - 1)
    assert received
    assert received[-1]["turn"] == 1
    assert len(received) == 8


def test_disabled_relay_does_not_queue_messages():
    cfg = {
        "peer_enabled": False,
        "peer_supabase_url": "https://example.supabase.co",
        "peer_supabase_key": "public-key",
        "peer_room": "room_code_123",
    }
    r = relay.PeerRelay(lambda: cfg)
    assert not r.publish("hello", "conversation-a", 8)
    assert r.poll() == []
    cfg["peer_enabled"] = True
    assert r.publish("hello", "conversation-a", 8)
    assert r._outgoing.get_nowait()["text"] == "hello"
    r.stop()


def test_fake_realtime_session_sends_without_supabase():
    cfg = {
        "peer_enabled": True,
        "peer_supabase_url": "https://example.supabase.co",
        "peer_supabase_key": "public-key",
        "peer_room": "room_code_123",
        "peer_max_turns": 8,
    }
    sent = []

    class FakeChannel:
        def on_broadcast(self, event, callback):
            self.callback = callback
            return self

        async def subscribe(self):
            return "SUBSCRIBED"

        async def send_broadcast(self, event, payload):
            sent.append((event, payload))

    class FakeClient:
        def __init__(self):
            self.channel_obj = FakeChannel()

        def channel(self, name):
            assert name == "muchio:room_code_123"
            return self.channel_obj

        async def remove_channel(self, channel):
            return None

    fake_client = FakeClient()

    async def fake_create(url, key):
        assert url == cfg["peer_supabase_url"]
        assert key == cfg["peer_supabase_key"]
        return fake_client

    old_create = relay.acreate_client
    relay.acreate_client = fake_create
    try:
        r = relay.PeerRelay(lambda: cfg)
        r.start()
        for _ in range(20):
            if r.status()["state"] == "connected":
                break
            time.sleep(0.05)
        assert r.status()["state"] == "connected"
        assert r.publish("hello", "conversation-a", 8)
        for _ in range(20):
            if any(item[0] == "peer_reply" for item in sent):
                break
            time.sleep(0.05)
        replies = [item for item in sent if item[0] == "peer_reply"]
        assert replies and replies[0][1]["text"] == "hello"
        r.stop()
    finally:
        relay.acreate_client = old_create


if __name__ == "__main__":
    test_settings_validation()
    test_message_validation_and_self_filtering()
    test_hello_elects_one_leader_without_social_data()
    test_turn_limit_simulation()
    test_disabled_relay_does_not_queue_messages()
    test_fake_realtime_session_sends_without_supabase()
    print("ok")
