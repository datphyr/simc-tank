"""Low-level SimulationCraft driver: build a profile, run the binary, parse output.

Nothing here knows about tanks or metrics -- it just runs SimC and returns clean
numbers. Keeping this layer dumb makes the metric layer testable without a binary.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence

#: Where to find the simc binary, in order of precedence:
#: explicit argument > $SIMC > PATH lookup > common build location.
DEFAULT_SIMC_PATHS = (
    "/root/simc-build/src/build/simc",
    "/usr/local/bin/simc",
)

#: The report's ``X-Error`` is a 95% confidence half-width; divide by this for 1 sigma.
Z95 = 1.959964


class SimcError(RuntimeError):
    """Raised when the simc binary is missing or a run fails to produce output."""


def find_simc(explicit: Optional[str] = None) -> str:
    """Resolve the simc binary path."""
    if explicit:
        if not os.path.isfile(explicit):
            raise SimcError(f"simc binary not found at {explicit!r}")
        return explicit
    env = os.environ.get("SIMC")
    if env:
        return env
    found = shutil.which("simc")
    if found:
        return found
    for p in DEFAULT_SIMC_PATHS:
        if os.path.isfile(p):
            return p
    raise SimcError(
        "could not find the SimulationCraft binary; pass --simc or set $SIMC"
    )


@dataclass
class Options:
    """SimC options for one run."""

    iterations: int = 300
    max_time: int = 120
    vary_combat_length: float = 0.0
    #: Declaring a plain enemy disables the tank-dummy module, which otherwise
    #: auto-injects an EXTERNAL heal that masks self-sustain. See docs/SIMC_NOTES.md.
    enemy: Optional[str] = "Fluffy_Pillow"
    #: Do NOT set a fight_style when injecting damage: init_fight_style() CLEARS
    #: raid_events for Patchwerk, silently dropping the injector.
    fight_style: Optional[str] = None
    raid_events: Optional[str] = None
    actions: Optional[str] = None
    extra: Sequence[str] = field(default_factory=tuple)

    def as_lines(self) -> List[str]:
        out = [f"iterations={self.iterations}", f"max_time={self.max_time}"]
        # Always pin combat length: a varying fight length makes the ramp window
        # random and adds noise to TTD. 0.0 = deterministic.
        out.append(f"vary_combat_length={self.vary_combat_length:g}")
        if self.fight_style:
            out.append(f"fight_style={self.fight_style}")
        if self.enemy:
            out.append(f"enemy={self.enemy}")
        if self.raid_events:
            out.append(f"raid_events=/{self.raid_events}")
        if self.actions:
            out.append(f"actions={self.actions}")
        out.extend(self.extra)
        return out


@dataclass
class PlayerMetrics:
    """Numbers extracted from one run, for the *player* (first player actor)."""

    dps: float = 0.0
    hps: float = 0.0
    dtps: float = 0.0  # per second, matching the text report
    hps_err: float = 0.0  # 1 sigma
    dtps_err: float = 0.0  # 1 sigma
    fight_length: float = 0.0
    max_health: float = 0.0
    health_pct: List[float] = field(default_factory=list)
    deaths: float = 0.0

    @property
    def margin(self) -> float:
        """Steady-state margin mu = selfHPS - DTPS."""
        return self.hps - self.dtps

    @property
    def margin_err(self) -> float:
        """1 sigma of the margin (HPS and DTPS assumed independent)."""
        return (self.hps_err ** 2 + self.dtps_err ** 2) ** 0.5


def _parse_text_metric(stdout: str, tag: str) -> tuple:
    """Return (value, 1-sigma error) for a metric from the player block."""
    m = re.search(rf"\b{tag}=([0-9.]+) {tag}-Error=([0-9.]+)", stdout)
    if not m:
        return 0.0, 0.0
    return float(m.group(1)), float(m.group(2)) / Z95


def _extract_player(data: dict) -> dict:
    players = data.get("sim", {}).get("players") or []
    if not players:
        raise SimcError("sim output has no player actors")
    return players[0]


def run(
    profile: str,
    options: Optional[Options] = None,
    simc: Optional[str] = None,
    timeout: int = 600,
    want_json: bool = True,
) -> tuple:
    """Run SimC on ``profile`` and return ``(stdout, parsed_json_or_None)``.

    The profile text is appended after the option lines, so per-actor options
    (``actions=``) land inside the player block. Note that ``actions=`` appended
    *after* the player block is a FULL replacement of the default list.
    """
    options = options or Options()
    binary = find_simc(simc)
    with tempfile.TemporaryDirectory() as td:
        json_path = os.path.join(td, "out.json")
        simc_path = os.path.join(td, "run.simc")
        lines = list(options.as_lines())
        if want_json:
            lines.append(f"json={json_path}")
        # An `actions=` override must come AFTER the player block. Placed in the
        # option header (before the profile) it applies to every actor, including
        # the enemy, and the sim fails with "Enemy ... Unable to create action".
        actions_line = None
        header: List[str] = []
        for ln in lines:
            if ln.startswith("actions="):
                actions_line = ln
            else:
                header.append(ln)
        body = "\n".join(header) + "\n" + profile
        if actions_line:
            body += "\n" + actions_line
        with open(simc_path, "w") as fh:
            fh.write(body)
        try:
            proc = subprocess.run(
                [binary, simc_path],
                capture_output=True,
                text=True,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired as exc:  # pragma: no cover - env dependent
            raise SimcError(f"simc timed out after {timeout}s") from exc
        data = None
        if want_json and os.path.exists(json_path):
            with open(json_path) as fh:
                data = json.load(fh)
        stdout = proc.stdout or ""
    return stdout, data


def player_metrics(stdout: str, data: Optional[dict]) -> PlayerMetrics:
    """Pull clean per-player metrics from a run's text + json output."""
    dps, dps_e = _parse_text_metric(stdout, "DPS")
    hps, hps_e = _parse_text_metric(stdout, "HPS")
    dtps, dtps_e = _parse_text_metric(stdout, "DTPS")
    pm = PlayerMetrics(dps=dps, hps=hps, hps_err=hps_e, dtps=dtps, dtps_err=dtps_e)
    if data:
        cd = _extract_player(data)["collected_data"]
        fl = cd.get("fight_length", {}).get("mean", 0.0) or 0.0
        pm.fight_length = fl
        # JSON `dtps.mean` is NOT per-second (it is ~ fight_length too large);
        # dividing by fight_length reproduces the text DTPS exactly.
        if not pm.dtps and isinstance(cd.get("dtps"), dict):
            pm.dtps = cd["dtps"].get("mean", 0.0) / fl if fl else 0.0
        rt = cd.get("resource_timelines", {})
        pm.health_pct = list((rt.get("health_pct") or {}).get("data") or [])
        pm.max_health = (rt.get("health") or {}).get("max", 0.0) or 0.0
        pm.deaths = (cd.get("deaths") or {}).get("mean", 0.0) or 0.0
    return pm


def run_metrics(profile: str, options: Optional[Options] = None,
                simc: Optional[str] = None, timeout: int = 600) -> PlayerMetrics:
    """Convenience: run and return parsed :class:`PlayerMetrics`."""
    stdout, data = run(profile, options, simc=simc, timeout=timeout)
    return player_metrics(stdout, data)
