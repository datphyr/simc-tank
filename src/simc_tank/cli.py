"""Command-line interface for simc-tank.

    simc-tank margin   PROFILE --rate 150000
    simc-tank ceiling  PROFILE
    simc-tank ttd      PROFILE --start 100000 --step-pct 1 --swing 2
    simc-tank sweep    PROFILE --lo 20000 --hi 400000
    simc-tank variants PROFILE --ds module --ds health80 --ds pure

Every command takes ``--simc`` (else ``$SIMC``, ``PATH``, or the build default)
and a ``PROFILE`` file (a .simc export).
"""
from __future__ import annotations

import argparse
import sys
from typing import List, Optional

from . import apl, metrics, simc


def _read_profile(path: str) -> str:
    with open(path) as fh:
        return fh.read()


def _fmt_ttd(ttd: Optional[float]) -> str:
    return "survived the window" if ttd is None else f"{ttd:.1f} s"


# --------------------------------------------------------------------------- #
# Commands
# --------------------------------------------------------------------------- #

def cmd_margin(args) -> int:
    profile = _read_profile(args.profile)
    r = metrics.steady_margin(
        profile, args.rate, school=args.school, swing=args.swing,
        iterations=args.iterations, max_time=args.max_time,
        actions=_actions_from_args(args), simc_path=args.simc,
    )
    m = r.metrics
    print(f"steady stream: {args.rate:,.0f} {args.school}/s (swing {args.swing:g}s), "
          f"{args.iterations} iters")
    print(f"  DTPS     = {m.dtps:>10,.0f}  (+/-{m.dtps_err:,.0f})")
    print(f"  selfHPS  = {m.hps:>10,.0f}  (+/-{m.hps_err:,.0f})")
    print(f"  margin   = {m.margin:>+10,.0f}  (+/-{m.margin_err:,.0f})   "
          f"{'SUSTAINS' if m.margin > 0 else 'BLEEDS'}")
    return 0


def cmd_ceiling(args) -> int:
    profile = _read_profile(args.profile)
    rate, r = metrics.ceiling(
        profile, lo=args.lo, hi=args.hi, tol=args.tol, school=args.school,
        swing=args.swing, iterations=args.iterations, max_time=args.max_time,
        actions=_actions_from_args(args), simc_path=args.simc,
    )
    print(f"damage ceiling (mu = 0) = ~{rate:,.0f} {args.school}/s")
    print(f"  at that point: DTPS = {r.metrics.dtps:,.0f}, "
          f"selfHPS = {r.metrics.hps:,.0f}")
    return 0


def cmd_ttd(args) -> int:
    profile = _read_profile(args.profile)
    ttd = metrics.time_to_death(
        profile, start=args.start, step_pct=args.step_pct, swing=args.swing,
        upto=args.upto, school=args.school, iterations=args.iterations,
        actions=_actions_from_args(args), simc_path=args.simc,
    )
    print(f"ramp: {args.start:,.0f} {args.school}/s, +{args.step_pct:g}%/hit, "
          f"swing {args.swing:g}s, window {args.upto:g}s")
    print(f"  >>> TTD = {_fmt_ttd(ttd)}")
    return 0


def cmd_sweep(args) -> int:
    profile = _read_profile(args.profile)
    print(f"ramp: {args.start:,.0f} {args.school}/s, +{args.step_pct:g}%/hit, "
          f"swing {args.swing:g}s")
    print(f"{'start dmg/s':>12} {'DTPS':>10} {'selfHPS':>10} {'TTD':>10}")
    start = args.start
    for _ in range(args.steps):
        ttd = metrics.time_to_death(
            profile, start=start, step_pct=args.step_pct, swing=args.swing,
            upto=args.upto, school=args.school, iterations=args.iterations,
            actions=_actions_from_args(args), simc_path=args.simc,
        )
        m = metrics.steady_margin(
            profile, start, school=args.school, swing=args.swing,
            iterations=args.iterations, max_time=int(args.upto),
            actions=_actions_from_args(args), simc_path=args.simc,
        ).metrics
        print(f"{start:>12,.0f} {m.dtps:>10,.0f} {m.hps:>10,.0f} {_fmt_ttd(ttd):>10}")
        start *= args.mult
    return 0


def cmd_variants(args) -> int:
    """Rank Death Strike strategies by TTD (and show the DPS cost)."""
    profile = _read_profile(args.profile)
    base = _read_base(args.base)
    opts_kw = dict(
        iterations=args.iterations,
        max_time=int(args.upto),
        raid_events=metrics.ramp_events(args.start, args.step_pct, args.swing,
                                        args.upto, args.school),
    )
    print(f"Death Strike strategies @ ramp {args.start:,.0f} {args.school}/s, "
          f"+{args.step_pct:g}%/hit, swing {args.swing:g}s")
    print(f"{'strategy':16} {'DPS':>9} {'DS casts':>9} {'TTD':>12}")
    rows = []

    def run_variant(name, variant):
        opts = simc.Options(actions=("/".join(variant) if variant else None), **opts_kw)
        stdout, data = simc.run(profile, opts, simc=args.simc)
        m = simc.player_metrics(stdout, data)
        casts = _ds_casts(stdout)
        ttd = metrics.crossing_time(m.health_pct, m.fight_length)
        rows.append((name, m, ttd))
        print(f"{name:16} {m.dps:>9,.0f} {casts:>9.1f} {_fmt_ttd(ttd):>12}")

    run_variant("baseline", None)
    for name in args.ds:
        factory = apl.DS_STRATEGIES.get(name)
        if factory is None:
            print(f"{name:16} unknown (have: {', '.join(apl.DS_STRATEGIES)})")
            continue
        run_variant(name, apl.swap_death_strike(base, factory()))

    print("\nranked by TTD (longest-lived first):")
    for name, m, ttd in sorted(rows, key=lambda r: -(r[2] if r[2] is not None else 1e9)):
        print(f"  {_fmt_ttd(ttd):>20}  {name:16} DPS {m.dps:>9,.0f}")
    return 0


def _ds_casts(stdout: str) -> float:
    import re

    m = re.search(r"^\s*death_strike\s+Count=\s*([0-9.]+)", stdout, re.M)
    return float(m.group(1)) if m else 0.0


# --------------------------------------------------------------------------- #
# Parser
# --------------------------------------------------------------------------- #

def _add_common(p: argparse.ArgumentParser) -> None:
    p.add_argument("profile", help="path to a .simc profile export")
    p.add_argument("--simc", default=None, help="path to the simc binary")
    p.add_argument("--school", default=metrics.DEFAULT_SCHOOL,
                   choices=["physical", "holy"], help="injected damage school")
    p.add_argument("--swing", type=float, default=2.0, help="creature swing timer (s)")
    p.add_argument("--iterations", type=int, default=500)
    p.add_argument("--actions", default=None,
                   help="override the default action list (colon-separated)")
    p.add_argument("--actions-file", default=None, metavar="PATH",
                   help="override with an action list from a file (one per line)")


def _actions_from_args(args) -> Optional[str]:
    """Resolve the effective actions override from --actions / --actions-file."""
    if getattr(args, "actions_file", None):
        return "/".join(_read_base(args.actions_file))
    return getattr(args, "actions", None)


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="simc-tank",
        description="Survivability metrics for SimulationCraft tanks.",
    )
    sub = ap.add_subparsers(dest="cmd", required=True)

    m = sub.add_parser("margin", help="steady mu = selfHPS - DTPS at a fixed rate")
    _add_common(m)
    m.add_argument("--rate", type=float, required=True, help="damage per second")
    m.add_argument("--max-time", type=int, default=300)
    m.set_defaults(func=cmd_margin, iterations=1500)

    c = sub.add_parser("ceiling", help="binary-search the mu = 0 damage rate")
    _add_common(c)
    c.add_argument("--lo", type=float, default=10_000)
    c.add_argument("--hi", type=float, default=500_000)
    c.add_argument("--tol", type=float, default=2_000)
    c.add_argument("--max-time", type=int, default=300)
    c.set_defaults(func=cmd_ceiling, iterations=800)

    t = sub.add_parser("ttd", help="time to death under a ramping stream")
    _add_common(t)
    t.add_argument("--start", type=float, default=100_000, help="initial damage/s")
    t.add_argument("--step-pct", type=float, default=1.0, help="%% harder per hit")
    t.add_argument("--upto", type=float, default=400.0, help="fight window (s)")
    t.set_defaults(func=cmd_ttd)

    s = sub.add_parser("sweep", help="TTD across a range of start damage")
    _add_common(s)
    s.add_argument("--start", type=float, default=100_000)
    s.add_argument("--step-pct", type=float, default=1.0)
    s.add_argument("--steps", type=int, default=4)
    s.add_argument("--mult", type=float, default=1.6, help="start multiplier per row")
    s.add_argument("--upto", type=float, default=400.0)
    s.set_defaults(func=cmd_sweep)

    v = sub.add_parser("variants", help="rank Death Strike strategies by TTD")
    v.add_argument("profile")
    v.add_argument("--simc", default=None)
    v.add_argument("--school", default=metrics.DEFAULT_SCHOOL, choices=["physical", "holy"])
    v.add_argument("--swing", type=float, default=2.0)
    v.add_argument("--start", type=float, default=100_000)
    v.add_argument("--step-pct", type=float, default=1.0)
    v.add_argument("--upto", type=float, default=400.0)
    v.add_argument("--iterations", type=int, default=400)
    v.add_argument("--base", default="module",
                   help="base action list: 'module' (SimC default) or a .simc path")
    v.add_argument("--ds", action="append", default=None,
                   help="strategy name (repeatable); default: all")
    v.set_defaults(func=cmd_variants)
    return ap


def _read_base(base: str) -> List[str]:
    """A base action list for variant authoring.

    ``module`` loads the bundled inline of the spec's built-in APL (see
    ``simc_tank/data/blood_sanlayn.actions``); anything else is a path to a file
    with one action per line (``#`` comments allowed).
    """
    if base == "module":
        from importlib.resources import files

        text = files("simc_tank.data").joinpath("blood_sanlayn.actions").read_text()
    else:
        with open(base) as fh:
            text = fh.read()
    return [
        ln.strip()
        for ln in text.splitlines()
        if ln.strip() and not ln.strip().startswith("#")
    ]


def main(argv: Optional[List[str]] = None) -> int:
    ap = build_parser()
    args = ap.parse_args(argv)
    if args.cmd == "variants" and not args.ds:
        args.ds = list(apl.DS_STRATEGIES)
    try:
        return args.func(args)
    except simc.SimcError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
