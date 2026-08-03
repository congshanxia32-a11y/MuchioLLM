import datetime

from peer_idle import IdlePeerScheduler


def base_config():
    return {
        "peer_enabled": True,
        "peer_idle_enabled": True,
        "peer_idle_initiator": True,
        "peer_idle_after_minutes": 25,
        "peer_idle_interval_minutes": 40,
        "peer_idle_daily_limit": 8,
    }


def test_starts_after_idle_threshold_and_respects_interval():
    scheduler = IdlePeerScheduler()
    now = datetime.datetime(2026, 8, 3, 12, 0, tzinfo=datetime.timezone.utc).timestamp()
    assert not scheduler.should_start(now, now - 24 * 60, now - 60, False, base_config())
    assert scheduler.should_start(now, now - 25 * 60, now - 60, False, base_config())
    assert not scheduler.should_start(now + 10 * 60, now - 35 * 60, now - 10 * 60, False, base_config())
    assert scheduler.should_start(now + 40 * 60, now - 65 * 60, now - 40 * 60, False, base_config())


def test_requires_single_configured_initiator_and_quiet_state():
    scheduler = IdlePeerScheduler()
    now = 1_800_000_000.0
    cfg = base_config()
    cfg["peer_idle_initiator"] = False
    assert not scheduler.should_start(now, now - 30 * 60, now - 30 * 60, False, cfg)
    cfg["peer_idle_initiator"] = True
    assert not scheduler.should_start(now, now - 30 * 60, now - 5, True, cfg)
    assert not scheduler.should_start(now, now - 10 * 60, now - 30 * 60, False, cfg)


def test_daily_limit_resets_on_local_day():
    scheduler = IdlePeerScheduler()
    cfg = base_config()
    cfg["peer_idle_daily_limit"] = 1
    day1 = datetime.datetime(2026, 8, 3, 12, 0).timestamp()
    day2 = day1 + 13 * 60 * 60
    assert scheduler.should_start(day1, day1 - 30 * 60, day1 - 30 * 60, False, cfg)
    assert not scheduler.should_start(day1 + 40 * 60, day1 - 70 * 60, day1 - 40 * 60, False, cfg)
    assert scheduler.should_start(day2, day2 - 30 * 60, day2 - 30 * 60, False, cfg)


if __name__ == "__main__":
    test_starts_after_idle_threshold_and_respects_interval()
    test_requires_single_configured_initiator_and_quiet_state()
    test_daily_limit_resets_on_local_day()
    print("ok")
