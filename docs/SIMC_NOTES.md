# Verified SimulationCraft mechanics

Everything here was established **empirically** against an unmodified
SimulationCraft build: branch `midnight`, `1210-01` / `12.1.0.69933`, commit
`d08a1c3`. Line references are to that tree. If you hit one of these and it
behaves differently on a newer build, the source has moved — check the file.

## Injecting tank damage

Use a `damage` raid event:

```
raid_events=/damage,amount=N,cooldown=S,type=physical,player_if=role.tank
```

* `amount` is **per hit**, so the delivered rate is `amount / cooldown`.
  `amount=150000, cooldown=2` is **75k/s**, not 150k/s.
* `type=physical` is reduced by armor; `type=holy` is unmitigated. Use the pair to
  separate armor DR from everything else.
* `player_if=role.tank` targets the tank (`affected_players` in
  `raid_event.cpp`).

### Pitfall 1 — a fight style silently deletes your injector

`sim_t::init_fight_style()` (`sim.cpp`) **clears** `raid_events_str` for
`Patchwerk`. If you set `fight_style=Patchwerk` *and* inject damage, the injector
vanishes and DTPS sits at the dummy baseline. **Do not set a fight style when
injecting damage** (this tool never does).

### Pitfall 2 — the tank dummy auto-injects an external healer

The default enemy is a `tank_dummy` module that adds
`heal,name=tank_heal,amount=...,cooldown=5.0,player_if=role.tank`
(`sc_enemy.cpp::add_tank_heal_raid_event`). That external heal **masks self-sustain**
— exactly what these metrics measure.

* Declaring **`enemy=<name>`** skips the tank-dummy module and removes the heal.
* **`tank_dummy=none` does NOT remove it.**

## Reading the numbers

* **`DTPS` in the text report is per-second and correct.** Use it.
* **`collected_data.dtps.mean` in JSON is NOT per-second** — it is ~`fight_length`
  times too large. Divide by `fight_length.mean`, or just use the text value.
  (`timeline_dmg_taken.mean` is the per-second damage-taken timeline.)
* **The report's `X-Error` is a 95% confidence half-width.** For a 1-sigma error
  divide by `1.959964`. (JSON `hps.mean_std_dev` is already 1 sigma; `dtps` has no
  such field.)
* **DTPS is not exogenous.** Blood Shield absorbs *change* recorded damage taken,
  so an APL that Death Strikes less takes more DTPS on the same raw stream. Compare
  variants on **TTD / selfHPS**, not on DTPS alone.

## Why TTD cannot come from `fight_length`

A tank's health resource is flagged **infinite**
(`player_resources.hpp::is_infinite`; `player_t::resource_loss` skips the
`min(amount, current)` clamp for infinite resources). The death check in
`player_t::do_damage` requires `!resources.is_infinite(RESOURCE_HEALTH)`, so **the
player is never killed** — even at `1e12` damage/s, `deaths` stays `0` and
`fight_length` is not shortened. (Pets have finite health and do die.)

So **TTD is read from the health timeline**: `resource_timelines.health_pct`
(`player.cpp` collects it every tick) as its first crossing of `0`. The curve does
go unboundedly negative. **Skip bin 0** — it is an initialisation sample (health
logged before the first tick, reading `0.0`).

## Authoring APLs

* **`actions=<list>` appended AFTER the player block** is a **full replacement** of
  the default list and skips the module's own sub-lists. This is how you author a
  self-contained rotation.
* **Appended BEFORE the player block**, the same line applies to *every* actor,
  including the enemy — the sim then fails with
  `Enemy 'Fluffy_Pillow': Unable to create action '...'`.
* **`actions.default=` is explicitly rejected** ("Ignoring action list named
  default"). Use bare `actions=`.
* **`/` inside an `actions=` value is the ACTION SEPARATOR.** A condition can never
  contain a division; multiply through instead. (`incoming_damage_5/health.max`
  fails with `Unable to create action 'health.max'`.)
* **`max` / `min` are the infix operators `<?` / `>?`**, not functions.
  `max(a, b)` → `a<?b`; `min(a, b)` → `a>?b`.
* **Death Strike is rune/RP-capped.** DS casts barely move (≈103–105) across
  priority variants, so *adding* a DS line changes nothing — you must **replace** the
  trigger to change behaviour.
* Damage-taken over a window is available as **`incoming_damage_<N>`** (seconds, or
  `_<N>ms`); magic-only via `incoming_magic_damage_<N>`.
  (`compute_incoming_damage`, `player.cpp`.)

## Stat weights

Scale factors work for any metric via **`scale_over=dps|dtps|hps`** (there is no
`scale_metric` option). Because `mu = selfHPS - DTPS`,

```
d(mu)/dstat = d(selfHPS)/dstat - d(DTPS)/dstat
```

`d(DTPS) < 0` means the stat reduces incoming damage. Stat weights need roughly
1500 iterations for signal.
