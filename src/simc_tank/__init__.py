"""simc-tank: survivability metrics for SimulationCraft tanks.

Two metrics, one goal -- answer "will the tank die, and when?":

* **steady margin** ``mu = selfHPS - DTPS`` -- positive means self-sustaining
  forever; the damage rate at ``mu = 0`` is the tank's **damage ceiling**.
* **time to death (TTD)** -- seconds survived under a *ramping* damage stream
  (each hit does more than the last), read from the health timeline.

Both are computed from an unmodified SimulationCraft binary; see
``docs/SIMC_NOTES.md`` for the empirically-verified mechanics and pitfalls.
"""

__version__ = "0.1.0"

from .apl import MODULE_DS_CONDITION, guard, replace_lines  # noqa: F401
from .metrics import (  # noqa: F401
    ceiling,
    crossing_time,
    ramp_events,
    steady_margin,
    time_to_death,
)

__all__ = [
    "__version__",
    "ceiling",
    "crossing_time",
    "ramp_events",
    "steady_margin",
    "time_to_death",
    "guard",
    "replace_lines",
    "MODULE_DS_CONDITION",
]
