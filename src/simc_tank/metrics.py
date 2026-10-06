"""The two metrics: steady-state margin / damage ceiling, and time-to-death.

All functions take a *profile text* (the contents of a ``.simc`` file) and return
plain numbers, so they are testable against a fake runner and reusable in a
library context.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Tuple

from . import simc
from .simc import Options, PlayerMetrics

# --------------------------------------------------------------------------- #
# Damage stream construction
# --------------------------------------------------------------------------- #

#: School of the injected damage. ``physical`` is reduced by armor; ``holy`` is
#: unmitigated -- use the pair to separate armor DR from everything else.
DEFAULT_SCHOOL = "physical"


def steady_events(rate: float, swing: float = 2.0, school: str = DEFAULT_SCHOOL) -> str:
    """A constant damage stream of ``rate`` HP/s, one hit every ``swing`` seconds.

    ``amount`` is per HIT, so ``amount = rate * swing``. With ``cooldown=1`` and
    ``amount=rate`` you get ``rate``/s; keeping the two consistent means the
    injected RATE is independent of the swing timer.
    """
    amount = int(round(rate * swing))
    return (
        f"damage,amount={amount},cooldown={swing:g},type={school},"
        f"player_if=role.tank"
    )


def ramp_events(
    start: float,
    step_pct: float = 1.0,
    swing: float = 2.0,
    upto: float = 400.0,
    school: str = DEFAULT_SCHOOL,
) -> str:
    """A ramping damage stream: one hit per ``swing``, each hit ``step_pct``% harder.

    ``start`` is the initial **damage per second**, so the first hit does
    ``start * swing`` and the very first second of the fight delivers ``start``.
    Implemented as one ``/damage`` raid event per swing with its own ``amount``
    and a ``first``/``last`` window -- stock SimC, exact, no fork.

    Because the ramp is **per hit**, a faster swing escalates faster in wall-clock
    time (more hits/second). That is intended for "each hit does N% more".
    """
    evs: List[str] = []
    t = 0.0
    amount = float(start) * swing
    while t < upto - 1e-9:
        end = min(t + swing, upto)
        evs.append(
            f"damage,amount={int(amount)},cooldown={swing:g},type={school},"
            f"player_if=role.tank,first={t:g},last={end:g}"
        )
        t += swing
        amount *= 1.0 + step_pct / 100.0
    return "/".join(evs)


# --------------------------------------------------------------------------- #
# Metric 1: steady-state margin and damage ceiling
# --------------------------------------------------------------------------- #

@dataclass
class MarginResult:
    rate: float
    metrics: PlayerMetrics

    @property
    def margin(self) -> float:
        return self.metrics.margin


def steady_margin(
    profile: str,
    rate: float,
    school: str = DEFAULT_SCHOOL,
    swing: float = 2.0,
    iterations: int = 1500,
    max_time: int = 300,
    actions: Optional[str] = None,
    simc_path: Optional[str] = None,
) -> MarginResult:
    """Measure ``mu = selfHPS - DTPS`` under a constant ``rate`` HP/s stream.

    No external healer is present (``enemy=`` disables the tank-dummy heal), so
    ``selfHPS`` is the tank's own throughput.

    NOTE: ``mu`` depends on fight length -- the opener inflates ``selfHPS``, so a
    short fight looks more sustainable. Compare rates/variants at a consistent
    (long) ``max_time``; the default 300s is well into steady state.
    """
    opts = Options(
        iterations=iterations,
        max_time=max_time,
        raid_events=steady_events(rate, swing, school),
        actions=actions,
    )
    return MarginResult(rate, simc.run_metrics(profile, opts, simc=simc_path))


def ceiling(
    profile: str,
    lo: float = 10_000,
    hi: float = 500_000,
    tol: float = 2_000,
    school: str = DEFAULT_SCHOOL,
    swing: float = 2.0,
    iterations: int = 800,
    max_time: int = 300,
    actions: Optional[str] = None,
    simc_path: Optional[str] = None,
) -> Tuple[float, MarginResult]:
    """Binary-search the break-even damage rate where ``mu = 0``.

    That rate is the tank's **damage ceiling**: below it the tank sustains
    indefinitely, above it it bleeds. Returns ``(rate, result_at_rate)``.
    """
    def m(rate: float) -> MarginResult:
        return steady_margin(profile, rate, school, swing, iterations, max_time,
                             actions, simc_path)

    a = m(lo)
    if a.margin <= 0:
        return lo, a
    b = m(hi)
    if b.margin > 0:
        return hi, b
    while hi - lo > tol:
        mid = (lo + hi) / 2
        if m(mid).margin > 0:
            lo = mid
        else:
            hi = mid
    mid = (lo + hi) / 2
    return mid, m(mid)


# --------------------------------------------------------------------------- #
# Metric 2: time to death under a ramp
# --------------------------------------------------------------------------- #

def crossing_time(
    health_pct: List[float],
    fight_length: float,
    threshold: float = 0.0,
) -> Optional[float]:
    """First time the health curve falls to ``threshold`` (linear interpolation).

    Returns ``None`` if it never does (survived the window). Bin 0 is an
    initialisation sample (health logged before the first tick, reading 0.0) and
    is skipped so it is not mistaken for a death.
    """
    data = health_pct or []
    if len(data) < 2 or fight_length <= 0:
        return None
    bw = fight_length / len(data)
    prev = data[1]
    for i in range(2, len(data)):
        v = data[i]
        if v <= threshold:
            t0, v0 = (i - 1) * bw, prev
            t1, v1 = i * bw, v
            if v0 == v1:
                return t1
            return t0 + (threshold - v0) * (t1 - t0) / (v1 - v0)
        prev = v
    return None


def time_to_death(
    profile: str,
    start: float = 100_000,
    step_pct: float = 1.0,
    swing: float = 2.0,
    upto: float = 400.0,
    school: str = DEFAULT_SCHOOL,
    iterations: int = 500,
    actions: Optional[str] = None,
    simc_path: Optional[str] = None,
) -> Optional[float]:
    """Seconds survived under a ramping stream (``None`` = survived the window).

    SimC never actually kills a tank (health is flagged infinite), so TTD is read
    from the health timeline's first crossing of 0, not from ``fight_length``.
    See ``docs/SIMC_NOTES.md``.
    """
    opts = Options(
        iterations=iterations,
        max_time=int(upto),
        raid_events=ramp_events(start, step_pct, swing, upto, school),
        actions=actions,
    )
    m = simc.run_metrics(profile, opts, simc=simc_path)
    return crossing_time(m.health_pct, m.fight_length)
