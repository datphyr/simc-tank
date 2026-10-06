# Metrics

Two metrics answer different questions. **Match the metric to the question** —
they can disagree.

## 1. Steady margin and damage ceiling

Under a **constant** damage stream, measure what the tank takes vs what it heals
itself (no external healer):

```
mu = selfHPS - DTPS
```

* `mu > 0` — self-sustaining; can live indefinitely at this rate.
* `mu <= 0` — net health loss; will die eventually.

The rate where `mu = 0` is the tank's **damage ceiling** (`simc-tank ceiling`
binary-searches it). For Blood this margin degrades *gracefully*: the Death Strike
heal scales with damage taken, so `selfHPS` rises with `DTPS`.

**Answers:** "can I sustain forever at this damage level?"

> **Caveat — `mu` depends on fight length.** The opener inflates `selfHPS`, so a
> short fight looks more sustainable. At a fixed 150k/s on the sample profile,
> `mu` went `+4,138` (60s) → `-202` (90s) → `-10,055` (180s). Always compare rates or
> variants at a consistent, long `max_time`; the tool defaults to 300s.

## 2. Time to death under a ramp

Real fights ramp: each hit does more than the last. With the default stream
(physical, +1% per hit, 2s swing) the metric is **TTD** — seconds until health
crosses 0, read from the health timeline (see `SIMC_NOTES.md` for why SimC itself
never kills a tank).

**Answers:** "how long do I live?" — the question a tank actually cares about.

### They can disagree

The clearest example measured on the sample profile: under a *steady* stream,
gating Vampiric Blood reactively **hurts** `mu` (on-cooldown wins on throughput);
under a *ramp*, the same gating **extends TTD** (saving it for the dangerous part of
the fight). Same knob, opposite verdicts.

## Death Strike: survivability vs pure damage

Death Strike is rune/RP-capped, so you cannot get more of it by adding lines — you
choose *which trigger spends the fixed budget*. Ranking on the sample profile
(`simc-tank variants ...`, default ramp, TTD):

| DS trigger | ordering |
|---|---|
| **module** (5s-window formula) | **best TTD** |
| `health.pct < 80` | ~tied with module |
| `health.pct < 70` | a little worse |
| SimC default (damage-first) | worse |
| `runic_power.deficit < 20` (pure damage) | worst |

**Verdict:** a survivability Death Strike outlives the damage-first default for a
small DPS cost (~2%), and outlives a pure-damage DS by more. It must **replace**
the DS trigger, not be added on top. The module's elaborate 5s-window formula is
essentially tied with a plain `health.pct < 80` threshold. Reproduce with:

```bash
simc-tank variants examples/example_blood.simc --ds module --ds health80 --ds health70 --ds pure
```

## Searching for the best-survivability APL

`tools/search_ttd.py` runs a coordinate-descent search over rotation knobs
(Death Strike trigger, Vampiric Blood trigger, Bone Shield top-up) with TTD as
the objective. On the sample Blood DK profile it converges to:

| action list | TTD (default ramp) | DPS |
|---|---|---|
| stock SimC APL | 132.9 s | 80,800 |
| **best found** (`examples/best_survival.actions`) | **140.7 s (+7.8 s, +5.9%)** | 78,400 (−3.0%) |

The change is a single line: replace the damage-first Death Strike with the
module's **health-reactive 5s-window** condition (keeping Vampiric Blood on
cooldown). It reproduces on a second, steeper ramp (50.9 s → 60.6 s, +9.7 s).

What did **not** help (all measured, none beat the plateau):

* Gating Vampiric Blood to low health — it *hurts* under a per-hit ramp
  (on-cooldown wins: more uptime); the opposite of the result under a coarse
  per-10s ramp. Same knob, ramp-shape-dependent verdict.
* Earlier/deferred Bone Shield top-up (thresholds 6–10) — inert (Bone Shield is
  refreshed by other buttons anyway).
* Reacting to damage spikes, longer DS windows, and a damage-spike trigger.
* Icebound Fortitude — worth ~0.2 s (it is one extra GCD, and does not stack).
* Lichborne — **not implemented (NYI) in SimC**, and it is magic-immunity, useless
  against a physical stream.

The search is cheap (a full run is a few seconds), so the practical recipe is:
fix the ramp shape, then let `tools/search_ttd.py` rank candidates for you.

## Stat priority (survivability)

Combine the two tank-relevant scale-factor sets:

```
d(mu)/dstat = d(selfHPS)/dstat - d(DTPS)/dstat
```

On the sample profile this ranks Haste / Wdps / Mastery at the top — a
survivability ordering that differs from the DPS ordering (where Str/Wdps lead).

## Scope and caveats

* **Steady-state only.** Cooldowns and tank-busters are excluded by design; this is
  the "do I eventually die?" question, not "do I die to this spike?".
* **Numbers move near the ceiling.** Treat outputs as ranges; raise `--iterations`
  when a result matters.
* **`mu` is fight-length dependent** (see above) — use a consistent, long `max_time`.
* The **ramp shape** (per-hit step, swing timer) is a modelling choice; TTD is
  sensitive to it. Use `sweep` to see the sensitivity.
