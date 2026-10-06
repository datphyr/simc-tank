"""Tests for the APL authoring helpers."""
from simc_tank import apl


def test_guard_adds_condition_when_absent():
    out = apl.guard(["heart_strike"], "buff.x.up")
    assert out == ["heart_strike,if=buff.x.up"]


def test_guard_ands_existing_condition():
    out = apl.guard(["death_strike,if=runic_power.deficit<20"], "health.pct<80")
    assert out == ["death_strike,if=(health.pct<80)&(runic_power.deficit<20)"]


def test_swap_death_strike_replaces_by_default():
    base = ["auto_attack", "death_strike,if=runic_power.deficit<20", "heart_strike"]
    out = apl.swap_death_strike(base, "death_strike,if=health.pct<80")
    assert "death_strike,if=health.pct<80" in out
    assert "death_strike,if=runic_power.deficit<20" not in out
    assert "heart_strike" in out
    assert "auto_attack" in out


def test_swap_death_strike_keep_fallback():
    base = ["death_strike,if=runic_power.deficit<20", "heart_strike"]
    out = apl.swap_death_strike(base, "death_strike,if=health.pct<80", keep_fallback=True)
    assert out[0] == "death_strike,if=health.pct<80"
    assert "death_strike,if=runic_power.deficit<20" in out


def test_module_condition_has_no_division():
    # '/' is the action separator, so the condition must never contain it.
    assert "/" not in apl.MODULE_DS_CONDITION
    # uses the infix max operator and the 5s damage window
    assert "<?8.5*health.max" in apl.MODULE_DS_CONDITION
    assert "incoming_damage_5" in apl.MODULE_DS_CONDITION


def test_ds_strategy_factories():
    assert apl.DS_STRATEGIES["pure"]() == "death_strike,if=runic_power.deficit<20"
    assert apl.DS_STRATEGIES["health80"]() == "death_strike,if=health.pct<80"
    assert apl.DS_STRATEGIES["module"]().startswith("death_strike,if=")
