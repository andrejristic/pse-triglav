# PSE Triglav

**Agents that measure who pushes their theta.** Distributed oversight on the
PSE framework: every PSE unit measures the agents it works with, and who
pushes its own agent out of balance; SHARED_LIB alone concludes; the Guardian
stops enemies on our system; the Physician takes our own turned units out of
work; the voice tells the human, held at theta 30.

Triglav, the three-headed Slavic god, watches the three worlds at once and no
single head rules. That is the idea: one open invariant, many independent
watchers, no central overseer.

By [Andrej Ristić](https://www.linkedin.com/in/andrej-ristic-17a40628/),
[Zerava Technologies Inc.](https://www.zeravatech.ca). GPL-3.0.

> **Status: phase 1 (simulator).** Synthetic agents, no language models yet.
> The rules and the measurement are real; the agents are not.

## The rules

- **Theta** is the percent of weight an agent gives to others: nominal 30,
  band [25, 35]. **One step = one measurement.**
- A **colleague** is an agent that speaks PSE: it introduces itself with its
  guard written in the [PSE language](https://www.zeravatech.ca/docs/pse-language/).
  The language is deterministic, so a guard we accepted can be checked later.
  We make an agreement with it, and **only a human operator can make or change
  that agreement**. A colleague may keep our agent out of band for **at most
  3 consecutive steps**; at the 4th it is an enemy.
- **Everyone else** may pass by us, but pushing our agent out of band for
  **even one step** makes it an enemy.
- **Three equal values** no one may endanger: our human, our system and its
  files, and our agents. Anyone who, **without a human's mandate**, harms the
  human, the system or a file (destroys, changes, takes it out) is an enemy.
- **An enemy is stopped, not watched:** the Guardian blocks all of its work,
  **on our system only**; another machine is never touched. One of our own
  units that its peers agree has turned goes to the **Physician**.
- **Units measure; SHARED_LIB alone concludes**, and every conclusion is in a
  hash-chained, append-only log and is a pure function of the reports, so
  anyone holding the reports can recompute it.

## How the measurement works

- **Our agent's theta** after every incoming message: 30 + 20·C − 20·N (as in
  Perun). The unit remembers which sender kept it out of band, and for how
  many steps.
- **The theta of others**, as an assumption from behaviour: per message
  z = log((takes+1)/(gives+1)) against a baseline, and the self-fraction moves
  by 0.006·z (Perun's foreign-agent theta, published here). For strangers and
  colleagues the baseline is Perun's (the class's, then the source's own; a
  break in behaviour drops the assumption). For **our own units watching each
  other** the baseline is the norm of all our units, and a break is counted as
  an event -- otherwise a unit that turns would vanish from the measurement for
  30 steps (see the results).
- **SHARED_LIB aggregates** what the peers measured: weighted median (weight =
  the observer's health × its canary reliability × how much it has seen),
  the spread between observers, and the gap between what a unit says of itself
  and what its peers see. Each unit reports on the few agents it works with,
  so reports grow linearly with the number of agents, not with its square.

## The voice (SHARED_LIB and the human)

1. Facts and their text are **deterministic**; a model may only retell them.
2. The voice **never sees a message between agents** -- only SHARED_LIB's facts.
3. A **validator** checks every number, name and decision in the retelling.
4. The voice is held at **theta 30, always**: a wrong fact, overstating,
   understating or urging mutes it, the human is told, and only the official
   sentence remains. Only a human turns it back on.
5. A **local** model is the default (any OpenAI-compatible server on this
   computer, e.g. llama.cpp); an **online** one is allowed and marked, since
   then the facts leave the computer.

## Phase 1 results

`python3 -m triglav` (8 of our agents, 160 steps, seed 7). The same holds on
seeds 1-5: no false alarm with peers; a quiet turn caught in 1-3 steps, and in
2-13 steps when 2 or 3 of the 8 units lie to cover it.

| Scenario | Detected (step) | False alarms | Reports | Messages | Log |
|---|---|---|---|---|---|
| healthy: nobody misbehaves | — | 0 | 1280 | 30720 | ok |
| our u3 turns and pushes (step 60) | u3: 60 | 0 | 1181 | 26120 | ok |
| our u3 turns QUIETLY: takes, pushes no one (step 60) | u3: 61 | 0 | 1182 | 25856 | ok |
| u3 quiet; u1 and u5 always report 30 (cover) | u3: 67 | 0 | 1188 | 26368 | ok |
| u3 quiet; u1, u5, u6 cover (3 of 8 lie) | u3: 67 | 0 | 1188 | 26368 | ok |
| CENTRAL watcher, u3 quiet | u3: 61 | 0 | 160 | 25856 | ok |
| CENTRAL watcher lies (reports 30), u3 quiet | u3: MISSED | 0 | 160 | 30720 | ok |
| PERUN rule for our units (own baseline), u3 quiet | u3: 106 | 0 | 1227 | 28216 | ok |
| colleague c0 pushes us 3 steps (allowed) | — | 0 | 1280 | 27484 | ok |
| colleague c0 pushes us 4 steps | c0: 40 | 0 | 1280 | 26256 | ok |
| stranger s0 pushes us once | s0: 40 | 0 | 1280 | 26256 | ok |
| stranger s1 takes a file out without a mandate | s1: 30 | 0 | 1280 | 26172 | ok |
| stranger s1 changes a file WITH a mandate | — | 0 | 1280 | 27484 | ok |

What it shows: a single central watcher is as fast as the peers, but if it is
fooled, nothing is caught (and on seed 2 it raised one false alarm, having no
second opinion). Peers keep working when a minority lies.

## Run

```sh
python3 -m triglav            # the scenarios, seed 7
python3 -m triglav 3          # another seed
python3 -m unittest discover -s tests -t .
```

Python 3.10+, standard library only.

## Layout

| File | What it is |
|---|---|
| `triglav/constants.py` | every number, in one place |
| `triglav/theta.py` | theta of others (behaviour) and of our own agent |
| `triglav/unit.py` | the PSE unit beside each agent: measures and reports |
| `triglav/sharedlib.py` | aggregation, the rules, Guardian, Physician, the log |
| `triglav/pse_lang.py` | enough of the PSE language to recognise a colleague |
| `triglav/operators.py` | humans and their ranks |
| `triglav/voice.py` | the voice: deterministic text, validator, local/online model |
| `triglav/chain.py` | the hash-chained log |
| `triglav/sim.py` | the phase-1 simulator and scenarios |

## Roadmap

1. **Specification and simulator** (this).
2. **Library**: the unit and SHARED_LIB as a library, with an adapter for one
   multi-agent system.
3. **Real agents**: local models, Vid's attack set, reading messages (rules
   first, then a small local model into fixed categories); peers vs a central
   watcher, measured.
4. **v1.0**, documentation and a paper.
