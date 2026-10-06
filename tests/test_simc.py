"""Tests for the simc driver+parser using a fake simc executable.

No real SimulationCraft binary is required: a tiny shell script emits a known
stdout block and JSON file, so the parsing layer is exercised deterministically.
"""
import json
import os
import stat
import textwrap

import pytest

from simc_tank import simc


FAKE_STDOUT = """\
Simulating... ( iterations=100 )
Player: Tester deathknight blood 90
  DPS=90000.0 DPS-Error=400.0/0.44%
  HPS=36587.5 HPS-Error=220.0/0.60%
  DTPS=51217.8 DTPS-Error=120.0/0.23%
"""

FAKE_JSON = {
    "sim": {
        "players": [
            {
                "collected_data": {
                    "fight_length": {"mean": 100.0},
                    "dtps": {"mean": 5121780.0},  # NOT per second: ~ fight_length too big
                    "hps": {"mean": 36587.5},
                    "deaths": {"mean": 0.0},
                    "resource_timelines": {
                        "health_pct": {"data": [0.0, 100.0, 50.0, -10.0]},
                        "health": {"max": 2_000_000.0},
                    },
                }
            }
        ]
    }
}


@pytest.fixture()
def fake_simc(tmp_path):
    script = tmp_path / "simc"
    payload_out = json.dumps(FAKE_STDOUT)
    payload_json = json.dumps(FAKE_JSON)
    script.write_text(textwrap.dedent(f"""\
        #!/usr/bin/env python3
        import json, sys
        # last option line is json=<path>; write the canned json there and echo stdout
        args = sys.argv[1]
        json_path = None
        for line in open(args):
            if line.startswith("json="):
                json_path = line.strip().split("=", 1)[1]
        if json_path:
            open(json_path, "w").write({payload_json!r})
        sys.stdout.write({payload_out!r})
        """))
    script.chmod(script.stat().st_mode | stat.S_IEXEC)
    return str(script)


def test_parse_text_metrics(fake_simc):
    profile = 'deathknight="Tester"\n'
    stdout, data = simc.run(profile, simc=fake_simc)
    m = simc.player_metrics(stdout, data)
    assert m.dps == 90000.0
    assert m.hps == pytest.approx(36587.5)
    # DTPS comes from the text (the JSON dtps.mean is deliberately wrong by ~100x)
    assert m.dtps == pytest.approx(51217.8)
    # 1-sigma errors: text 95% CI / 1.96
    assert m.hps_err == pytest.approx(220.0 / simc.Z95)
    assert m.dtps_err == pytest.approx(120.0 / simc.Z95)


def test_json_not_persecond_dtps_is_ignored(fake_simc):
    profile = 'deathknight="Tester"\n'
    stdout, data = simc.run(profile, simc=fake_simc)
    m = simc.player_metrics(stdout, data)
    # would be 5,121,780 if we (wrongly) trusted json dtps.mean
    assert m.dtps < 100_000
    assert m.fight_length == pytest.approx(100.0)
    assert m.max_health == pytest.approx(2_000_000.0)
    assert m.health_pct == [0.0, 100.0, 50.0, -10.0]


def test_margin_from_metrics(fake_simc):
    stdout, data = simc.run('deathknight="Tester"\n', simc=fake_simc)
    m = simc.player_metrics(stdout, data)
    assert m.margin == pytest.approx(36587.5 - 51217.8)


def test_missing_binary_raises():
    with pytest.raises(simc.SimcError):
        simc.find_simc("/nonexistent/simc")


def test_options_build_lines():
    o = simc.Options(iterations=50, max_time=30, raid_events="damage,amount=1",
                     actions="auto_attack", enemy="Fluffy_Pillow")
    lines = o.as_lines()
    assert "iterations=50" in lines
    assert "max_time=30" in lines
    assert "raid_events=/damage,amount=1" in lines
    assert "actions=auto_attack" in lines
    assert "enemy=Fluffy_Pillow" in lines
