#!/usr/bin/env python3
"""Search for the best-survivability Blood DK APL by TTD.

A small coordinate-descent search over rotation knobs, evaluated with the
``simc-tank`` TTD metric. Knobs:

* ``ds`` -- the Death Strike trigger line
* ``vb`` -- the Vampiric Blood trigger line
* ``bs`` -- Bone Shield top-up threshold

The objective is mean TTD over a repeatable ramp. Run from the repo root:

    python tools/search_ttd.py path/to/tank.simc [--reps 4]
"""
from __future__ import annotations

import argparse
import statistics
import sys
from pathlib import Path
from typing import Callable, Dict, List, Optional, Sequence

# make src/ importable when run from a checkout
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from simc_tank import apl, metrics, simc  # noqa: E402

DATA = Path(__file__).resolve().parents[1] / "src" / "simc_tank" / "data"

DEFAULT_RAMP = dict(start=100_000, step_pct=1.0, swing=2.0, upto=400.0)


def load_base() -> List[str]:
    text = (DATA / "blood_sanlayn.actions").read_text()
    return [l.strip() for l in text.splitlines()
            if l.strip() and not l.strip().startswith("#")]


# --------------------------------------------------------------------------- #
# Knob transforms (each returns a full action list)
# --------------------------------------------------------------------------- #

def set_ds(base: Sequence[str], trigger: str, fallback: bool = False) -> List[str]:
    line = trigger if trigger.startswith("death_strike") else f"death_strike,if={trigger}"
    ds = [a for a in base if a.startswith("death_strike")]
    rest = [a for a in base if not a.startswith("death_strike")]
    return [line] + (ds if fallback else []) + rest


def set_vb(base: Sequence[str], cond: str) -> List[str]:
    return [f"vampiric_blood,if={cond}" if a.startswith("vampiric_blood") else a
            for a in base]


def set_bs(base: Sequence[str], n: int) -> List[str]:
    return [a.replace("buff.bone_shield.stack<6", f"buff.bone_shield.stack<{n}")
            for a in base]


# --------------------------------------------------------------------------- #
# Evaluation
# --------------------------------------------------------------------------- #

def eval_ttd(profile: str, actions: Sequence[str], ramp: Dict, reps: int = 4,
             iterations: int = 500, simc_path: Optional[str] = None) -> Dict:
    ev = metrics.ramp_events(ramp["start"], ramp["step_pct"], ramp["swing"],
                             ramp["upto"], "physical")
    ttys, dps = [], []
    for _ in range(reps):
        opts = simc.Options(iterations=iterations, max_time=int(ramp["upto"]),
                            raid_events=ev, actions="/".join(actions))
        stdout, data = simc.run(profile, opts, simc=simc_path)
        m = simc.player_metrics(stdout, data)
        t = metrics.crossing_time(m.health_pct, m.fight_length)
        ttys.append(t if t is not None else float("inf"))
        dps.append(m.dps)
    return dict(ttd=statistics.fmean(ttys),
                sd=statistics.stdev(ttys) if len(ttys) > 1 else 0.0,
                dps=statistics.fmean(dps))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("profile")
    ap.add_argument("--reps", type=int, default=4)
    ap.add_argument("--iterations", type=int, default=500)
    ap.add_argument("--simc", default=None)
    a = ap.parse_args()

    profile = Path(a.profile).read_text()
    base = load_base()

    def show(label: str, actions: Sequence[str]) -> Dict:
        r = eval_ttd(profile, actions, DEFAULT_RAMP, a.reps, a.iterations, a.simc)
        print(f"  {label:26} TTD={r['ttd']:8.2f} +/-{r['sd']:.2f}  DPS={r['dps']:,.0f}")
        return r

    print("baseline (inlined module APL):")
    b = show("baseline", base)

    print("\nDeath Strike triggers:")
    ds_opts = {
        "module": apl.MODULE_DS_CONDITION,
        "health80": "health.pct<80",
        "health70": "health.pct<70",
        "pure(dmg)": "runic_power.deficit<20",
    }
    best = None
    for name, trig in ds_opts.items():
        r = show(f"DS={name}", set_ds(base, trig))
        if best is None or r["ttd"] > best[1]["ttd"]:
            best = (set_ds(base, trig), r)

    print("\nVampiric Blood triggers (at best DS):")
    for name, cond in {
        "on-CD": "!buff.vampiric_blood.up",
        "health70": "!buff.vampiric_blood.up&health.pct<70",
        "health60": "!buff.vampiric_blood.up&health.pct<60",
    }.items():
        r = show(f"VB={name}", set_vb(best[0], cond))
        if r["ttd"] > best[1]["ttd"]:
            best = (set_vb(best[0], cond), r)

    print(f"\nBEST: TTD={best[1]['ttd']:.2f}s (+{best[1]['ttd']-b['ttd']:.2f}s vs "
          f"baseline) at DPS {best[1]['dps']:,.0f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
