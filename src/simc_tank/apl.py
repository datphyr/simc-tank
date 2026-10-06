"""Authoring APL variants in SimulationCraft.

Two things live here:

1. Small, verified primitives for manipulating action lists
   (:func:`guard`, :func:`replace_lines`).
2. The **survivability Death Strike** strategies, including the exact translation
   of the *datbot* module's health-reactive condition into SimC syntax.

SimC APL gotchas encoded here (all empirically verified -- see docs/SIMC_NOTES.md):

* ``actions=<list>`` appended AFTER the profile fully REPLACES the default list
  and skips the module's own sub-lists. Appended BEFORE the profile it applies to
  every actor, including the enemy, and the sim fails.
* Within an ``actions=`` value, ``/`` is the ACTION SEPARATOR -- so a condition can
  never contain a division. Multiply through instead.
* ``max``/``min`` are the infix operators ``<?`` / ``>?``, not functions.
"""
from __future__ import annotations

from typing import Iterable, List, Optional, Sequence

# --------------------------------------------------------------------------- #
# Verified APL primitives
# --------------------------------------------------------------------------- #

def guard(lines: Sequence[str], cond: str) -> List[str]:
    """AND ``cond`` onto every line's existing ``if=`` (or add one)."""
    out: List[str] = []
    for a in lines:
        if "if=" in a:
            i = a.index("if=")
            out.append(a[:i] + f"if=({cond})&(" + a[i + 3:] + ")")
        else:
            sep = "" if a.endswith(",") else ","
            out.append(a + f"{sep}if={cond}")
    return out


def replace_lines(
    lines: Sequence[str],
    prefix: str,
    replacements: Sequence[str],
) -> List[str]:
    """Drop every line starting with ``prefix`` and put ``replacements`` in front."""
    kept = [a for a in lines if not a.startswith(prefix)]
    return list(replacements) + kept


# --------------------------------------------------------------------------- #
# The datbot-module survivability Death Strike, translated
# --------------------------------------------------------------------------- #

#: The module's condition:
#:
#:     heal = max(0.2415 * damage_taken_5s_fraction, 0.085)
#:     DS if health_fraction <= 1 - 2*heal
#:
#: translated to SimC. Division is removed by multiplying through by
#: ``health.max`` (``/`` would be parsed as the action separator), and ``max``
#: becomes the infix ``<?``. ``incoming_damage_5`` is the 5s damage-taken window.
MODULE_DS_CONDITION = (
    "health.pct*health.max<=100*health.max"
    "-2*(24.15*incoming_damage_5<?8.5*health.max)"
)


def ds_pure(threshold: int = 20) -> str:
    """Damage-first Death Strike: fire on Runic Power deficit (the module default)."""
    return f"death_strike,if=runic_power.deficit<{threshold}"


def ds_health(pct: float) -> str:
    """Simple survivability Death Strike: heal below ``pct`` health."""
    return f"death_strike,if=health.pct<{pct:g}"


def ds_module() -> str:
    """The datbot module's health-reactive Death Strike (translated exactly)."""
    return f"death_strike,if={MODULE_DS_CONDITION}"


#: Named Death Strike strategies for head-to-head comparison, best-TTD first
#: (see docs/METRICS.md for the measured results).
DS_STRATEGIES = {
    "module": ds_module,
    "health80": lambda: ds_health(80),
    "health70": lambda: ds_health(70),
    "pure": ds_pure,
}


def swap_death_strike(
    base: Sequence[str],
    ds_line: str,
    keep_fallback: bool = False,
) -> List[str]:
    """Return ``base`` with its Death Strike lines replaced by ``ds_line``.

    Death Strike is rune/RP-capped, so ADDING a line does nothing -- a variant must
    REPLACE the trigger to change behaviour. With ``keep_fallback`` the original
    DS lines are kept *below* the new one.
    """
    ds_lines = [a for a in base if a.startswith("death_strike")]
    kept = [a for a in base if not a.startswith("death_strike")]
    new = [ds_line] + (ds_lines if keep_fallback else [])
    return new + kept
