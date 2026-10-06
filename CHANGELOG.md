# Changelog

## 0.2.0

- `--actions-file PATH` option to run a full action list from a file.
- `tools/search_ttd.py`: coordinate-descent search for the best-survivability
  APL, with TTD as the objective.
- `examples/best_survival.actions`: the found action list (+7.8 s TTD over the
  stock APL).
- Documented what does *not* help (Vampiric Blood gating under a per-hit ramp,
  Bone Shield top-up, Icebound Fortitude, Lichborne) in `docs/METRICS.md`.

## 0.1.0

Initial release.

- Two tank survivability metrics, computed from an unmodified SimulationCraft
  binary: the **steady margin** `mu = selfHPS - DTPS` (with a binary-searched
  **damage ceiling**), and **time to death (TTD)** under a ramping damage stream.
- `simc-tank` CLI with `margin`, `ceiling`, `ttd`, `sweep`, and `variants`
  commands. Defaults model the base creature: physical damage, +1% per hit, 2s
  swing.
- APL authoring helpers, including the exact SimC translation of the *datbot*
  Blood Death Knight module's health-reactive Death Strike condition.
- Documentation of the empirically-verified SimC mechanics and pitfalls
  (`docs/SIMC_NOTES.md`).
- Pure-logic tests (no SimC binary required) plus a shell smoke test.
