# Changelog

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
