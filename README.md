# simc-tank

Survivability metrics for **SimulationCraft** tanks, computed from an
**unmodified** SimC binary.

SimC tells you how much a tank *heals* and *takes*. It does not tell you whether
the tank **survives**, or **for how long**. This package adds two metrics that do:

| metric | question it answers |
|---|---|
| **steady margin** `mu = selfHPS - DTPS` | "can I sustain forever at this damage rate?" — and the rate where `mu = 0` is your **damage ceiling** |
| **time to death (TTD)** | "how long do I live?" under a *ramping* damage stream (each hit harder than the last) |

Both are read from SimC's own output; the tool only drives the binary and parses
it. See [`docs/METRICS.md`](docs/METRICS.md) for definitions and results, and
[`docs/SIMC_NOTES.md`](docs/SIMC_NOTES.md) for the empirically-verified SimC
mechanics (there are several sharp edges).

## Install

```bash
pip install -e .
```

Requires a SimulationCraft binary built from the `midnight` branch (the tool is
tested against `1210-01` / `12.1.0.69933`). Point the tool at it with `--simc`,
the `SIMC` environment variable, `PATH`, or a common build path (see
`simc_tank/simc.py`).

## Quickstart

```bash
simc-tank ttd      examples/example_blood.simc            # time to death under a ramp
simc-tank ceiling  examples/example_blood.simc            # the mu = 0 damage rate
simc-tank margin   examples/example_blood.simc --rate 150000
simc-tank sweep    examples/example_blood.simc --start 100000 --steps 4
simc-tank variants examples/example_blood.simc --ds module --ds health80 --ds pure

# run a full action list from a file, and compare two of them
simc-tank ttd examples/example_blood.simc --actions-file examples/best_survival.actions
```

`examples/best_survival.actions` is a Blood DK action list found by
[`tools/search_ttd.py`](tools/search_ttd.py) to maximise TTD (+7.8 s over the
stock APL — see [`docs/METRICS.md`](docs/METRICS.md#searching-for-the-best-survivability-apl)).

`examples/example_blood.simc` is a synthetic Blood DK profile; substitute any
SimC gear export.

## Commands

| command | description |
|---|---|
| `margin` | steady `mu = selfHPS - DTPS` at a fixed damage rate |
| `ceiling` | binary-search the break-even rate where `mu = 0` |
| `ttd` | seconds survived under a ramping stream |
| `sweep` | TTD across a range of starting damage |
| `variants` | rank Death Strike strategies by TTD (and show the DPS cost) |

Common options: `--school physical|holy`, `--swing <s>`, `--iterations N`,
`--simc PATH`, and `--actions-file PATH` (run a full action list read from a
file). Defaults model the base creature: **physical** damage, **+1% per hit**,
**2s swing timer**.

```bash
simc-tank --help
simc-tank ttd --help
```

## Library use

```python
from simc_tank import metrics, apl

profile = open("my_tank.simc").read()
rate, r = metrics.ceiling(profile)
print("damage ceiling:", rate, "mu at ceiling:", r.margin)

ttd = metrics.time_to_death(profile, start=100_000, step_pct=1, swing=2)
```

## Death Strike: survivability vs damage

Death Strike is rune/RP-capped, so you choose *which trigger* spends the budget.
A health-reactive trigger outlives the damage-first default for a small DPS cost —
and the *datbot* module's 5s-window formula is provided, translated exactly
([`docs/METRICS.md`](docs/METRICS.md#death-strike-survivability-vs-pure-damage)):

```python
from simc_tank import apl
base = [...]                                   # your action list
apl.swap_death_strike(base, apl.ds_module())   # or apl.ds_health(80), apl.ds_pure()
```

## Development

```bash
pip install -e '.[dev]'
pytest
```

Tests are pure-logic and use a fake `simc` executable, so they need no SimC binary.

## License

MIT
