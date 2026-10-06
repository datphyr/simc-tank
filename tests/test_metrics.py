"""Pure-logic tests: damage-stream construction and the TTD crossing detector."""
from simc_tank import metrics


def test_steady_events_rate_is_swing_independent():
    # amount is per HIT, so amount*swings/sec == rate regardless of swing length.
    for swing in (1, 2, 3):
        ev = metrics.steady_events(100_000, swing=swing)
        assert f"amount={int(100_000 * swing)}" in ev
        assert f"cooldown={swing:g}" in ev
        assert "type=physical" in ev
        assert "player_if=role.tank" in ev


def test_ramp_events_first_hit_and_growth():
    ev = metrics.ramp_events(100_000, step_pct=1, swing=2, upto=6)
    parts = ev.split("/")
    assert len(parts) == 3
    # first hit = start * swing
    assert "amount=200000" in parts[0]
    # each hit 1% harder
    assert "amount=202000" in parts[1]
    assert "amount=204020" in parts[2]
    # windows tile
    assert "first=0,last=2" in parts[0]
    assert "first=2,last=4" in parts[1]


def test_ramp_events_default_school_physical():
    assert "type=physical" in metrics.ramp_events(100_000)


def test_crossing_time_interpolates_and_skips_bin0():
    # bin 0 is an init sample (0.0) and must be skipped. Values 50 at t=2 and
    # -50 at t=3 cross zero midway -> t = 2.5 (not t=0).
    hp = [0.0, 100.0, 50.0, -50.0]
    t = metrics.crossing_time(hp, fight_length=4.0)
    assert t is not None
    assert abs(t - 2.5) < 1e-9


def test_crossing_time_hits_exact_zero_sample():
    # a sample that is exactly 0 counts as the crossing at that sample's time
    hp = [0.0, 100.0, 50.0, 0.0, -50.0]
    assert metrics.crossing_time(hp, fight_length=5.0) == 3.0


def test_crossing_time_returns_none_if_survived():
    hp = [0.0, 100.0, 90.0, 80.0, 95.0]
    assert metrics.crossing_time(hp, fight_length=5.0) is None


def test_crossing_time_handles_short_and_empty():
    assert metrics.crossing_time([], 10.0) is None
    assert metrics.crossing_time([100.0], 10.0) is None
    assert metrics.crossing_time([0.0, 100.0], 0.0) is None


def test_crossing_time_already_dead_after_init():
    # dips straight through zero at the first scanned bin -> linear interp from bin 1
    hp = [0.0, 10.0, -10.0]
    t = metrics.crossing_time(hp, fight_length=3.0)
    assert t is not None and 1.0 <= t <= 2.0
