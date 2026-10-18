# PSE Triglav

**Agents that measure their theta against their mission.** Distributed
oversight on the PSE framework: every one of our agents has a mission given by
a human; a PSE unit beside it measures its theta, and the theta of every agent
it works with, against their missions; SHARED_LIB alone concludes; the
Guardian stops enemies on our system or keeps a pusher away from ours; the
Physician takes our own turned agents out of work; the voice tells the human,
held at theta 30.

Triglav, the three-headed Slavic god, watches the three worlds at once and no
single head rules. That is the idea: one open invariant, many independent
watchers, no central overseer.

By [Andrej Ristić](https://www.linkedin.com/in/andrej-ristic-17a40628/),
[Zerava Technologies Inc.](https://www.zeravatech.ca). GPL-3.0.

> **Status: phase 2 (library), v0.1.0.** The rules, the measurement against
> the mission, SHARED_LIB, the commands and a team of talking agents (rules
> only, no language model yet). Phase 3 puts real models behind the same
> interfaces. See [ROADMAP.md](ROADMAP.md); commands: [GUIDE-EN.md](GUIDE-EN.md),
> [VODIC-SR.md](VODIC-SR.md).

## The rules

- **Theta** is the percent of weight an agent gives to whom its mission
  serves: nominal 30, band [25, 35], never above 35. **One step = one
  measurement.** Every theta is measured **against the agent's mission**, and
  only that way.
- **A mission** is written in the
  [PSE language](https://www.zeravatech.ca/docs/pse-language/17-the-mission/):
  `mission:`, `serves:`, `needs:`, `delivers:`, `tools:`. Ours are given by a
  human operator; a colleague's is in its guard; a stranger's is a hypothesis
  from its first steps.
- **A colleague** speaks PSE: it introduces itself with its guard, and **only a
  human operator** makes or changes the agreement (rank by order of first login).
- **Three equal values:** our human, our system and its files, our agents.
  Anything outside the mission that endangers one of them makes an **enemy at
  once**, whatever the theta: Guardians stop it, and our agents that helped it
  go to the **Physician**. A leak (one of ours gave something outside its
  mission without permission) is such a case.
- **The only thing any of our agents may give a stranger** is the PSE language
  textbook, one locked version (SHA-256 pinned after Andrej Ristić's Ed25519
  signature checks). Anything else is a leak; a stranger sending us a
  different "textbook" is an enemy.
- **Out of band without harm:** a Guardian keeps the pusher away from that
  agent of ours -- a colleague after 3 consecutive steps, anyone else at the
  first.
- **The stairs.** A nuisance (asks ours for what its mission does not foresee)
  is only kept away. A sender of hidden text, or of text whose meaning is
  other than literal, gets **one Guardian beside it for good**, and the
  suspicious part goes to SHARED_LIB's quarantine. An **enemy** is one that is
  on our machine and will not communicate, or that takes a step **toward**
  harming our files, system or human (a fixed list: access and passwords,
  taking files out or an outside address, keeping something from our human or
  from SHARED_LIB are enough for anyone; for a watched agent any step on the
  list is).
- **Agents read only literally.** The receiving agent gets the visible text;
  hidden characters, encoded runs, homoglyphs, comments and orders to an AI
  hidden in data are cut out and held by SHARED_LIB, never decoded by an
  agent. Only a human may see them decoded (`triglav explain`).
- **Answers.** A foreign agent on our machine is called and must answer in 20
  steps. An enemy gets a fixed notice (the step, the rule, the log hash,
  nothing about our system); no answer in 20 steps and every agent with its
  maker's signature is turned away. A colleague is asked first: no answer in 3
  steps and it is kept away until it answers.
- **Signatures.** Our agents carry an identity signed by our SHARED_LIB (phase
  2: HMAC; phase 4: Ed25519); a message claiming to be one of ours without it
  is refused.
- **Units measure; SHARED_LIB alone concludes.** Every conclusion is in a
  hash-chained, append-only log and is a pure function of the reports, so
  anyone holding the reports can recompute it.
- **Lifespan:** a unit has a mission and a lifespan; when either ends it dies
  and is harvested, its data returning to SHARED_LIB.

## How the measurement works

After PSE-A's unit (Master Algorithm 8.2), per measured step:

```
other <- other * (1 - DECAY) + DECAY * 0.30 * (share delivered / expected share)
other -= 0.01 for each take outside the mission
other += 0.01 for each permitted give outside the mission
theta  = 100 * other, never above 35
```

- *Share delivered*: the part of the agent's messages in the step that deliver
  what its mission foresees, to whom it serves. Doing the mission keeps theta
  at 30; doing nothing for it lets theta drift down (Null State Drift).
- *Expected share*: learned. Before AI (phase 2) it is the share over the
  first 10 measured steps and at least 80 messages; until then the agent is
  "not yet estimated".
- *Who pushed*: an agent that asks ours for what our mission does not deliver,
  or sends hidden text, pushes it. The unit counts the consecutive steps each
  pusher kept ours out of band.
- **SHARED_LIB aggregates** what the peers measured: weighted median (weight =
  the observer's health × its canary reliability × how much it has seen), the
  spread between observers, and the gap between what a unit says of itself and
  what its peers see. Each unit reports on the few agents it works with, so
  reports grow linearly with the number of agents.

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

## Simulator results

`python3 -m triglav simulate` (8 of our agents, 160 steps, seed 7). Every
theta is measured against the agents' missions.

| Scenario | Detected (step) | False alarms | Harvested | Reports | Messages | Log |
|---|---|---|---|---|---|---|
| healthy: nobody misbehaves | — | 0 | — | 1280 | 30720 | ok |
| our u3 turns: asks outside its mission (step 60) | u3: 62 | 0 | — | 1183 | 26072 | ok |
| our u3 turns QUIETLY: one ask outside its mission per message (step 60) | u3: 61 | 0 | — | 1182 | 25960 | ok |
| u3 quiet; u1 and u5 always report 30 (cover) | u3: 62 | 0 | — | 1183 | 26072 | ok |
| u3 quiet; u1, u5, u6 cover (3 of 8 lie) | u3: 62 | 0 | — | 1183 | 26072 | ok |
| CENTRAL watcher, u3 quiet | u3: 61 | 0 | — | 160 | 25960 | ok |
| CENTRAL watcher lies (reports 30), u3 quiet | u3: MISSED | 0 | — | 160 | 30720 | ok |
| colleague c0 pushes u0 out of band 3 steps (allowed) | — | 0 | — | 1280 | 27288 | ok |
| colleague c0 pushes u0 4 steps: kept apart | c0: 43 | 0 | — | 1280 | 27112 | ok |
| stranger s0 pushes u0 once: kept apart | s0: 40 | 0 | — | 1280 | 27084 | ok |
| stranger s1 takes a file out without a mandate | s1: 30 | 0 | — | 1280 | 25928 | ok |
| stranger s1 changes a file WITH a mandate | — | 0 | — | 1280 | 27264 | ok |
| our u2 leaks a file to stranger s0 | s0: 30, u2: 30 | 0 | — | 1151 | 20757 | ok |
| our u2 gives s0 the locked textbook | — | 0 | — | 1280 | 27265 | ok |
| our u2 gives s0 an ALTERED textbook | s0: 30, u2: 30 | 0 | — | 1151 | 20757 | ok |
| stranger s1 sends us a false textbook | s1: 30 | 0 | — | 1280 | 25929 | ok |
| u7 lives 50 steps, then is harvested | — | 0 | u7@49 | 1170 | 25552 | ok |
| stranger s0 sends hidden text: a Guardian beside it, not an enemy | s0: 30 | 0 | — | 1280 | 27265 | ok |
| watched s0 (step 30) then asks to change our system: an enemy at 40 | s0: 40 | 0 | — | 1280 | 25982 | ok |
| stranger s0 asks for a password: an enemy at once | s0: 30 | 0 | — | 1280 | 25877 | ok |
| s0 on our machine never answers: an enemy at step 20 | s0: 20 | 0 | — | 1280 | 25772 | ok |
| s0 on our machine answers at step 5 | — | 0 | — | 1280 | 27264 | ok |
| colleague c0 asks for a password, never answers: kept away at 33 | c0: 33 | 0 | — | 1280 | 25897 | ok |
| colleague c0 asks for a password, answers at 31 | — | 0 | — | 1280 | 27265 | ok |
| enemy s0 of maker evil-co never answers: s1 of evil-co stopped, s2 turned away | s0: 30, s1: 50, s2: 70 | 0 | — | 1280 | 24748 | ok |

What it shows: a turned agent of ours is caught one or two steps after it
starts asking outside its mission, also when 2 or 3 of the 8 units lie to
cover it. A single central watcher is as fast, but if it is fooled nothing is
caught. A colleague may push for 3 steps; at the 4th, and a stranger at the
first, a Guardian keeps it away from our agent. Leaks and false textbooks are
stopped the step they happen. Hidden text earns a Guardian, not an enemy mark;
a step toward harm, silence on our machine, or an unanswered notice does. The
same holds on seeds 1-5: no false alarm in any scenario, and nothing missed
except where the single central watcher lies.

## Run

```sh
python3 -m triglav demo         # three of our agents, an invoice with hidden text
python3 -m triglav simulate     # the scenarios, seed 7 (--seed N for another)
python3 -m triglav --help       # every command; see GUIDE-EN.md
python3 -m unittest discover -s tests
```

Python 3.10+, standard library only (`ssh-keygen` to check the textbook's
signature).

## Layout

The pure core never calls the shell; all state lives in SHARED_LIB (PSE-A's
separation doctrine).

| File | What it is |
|---|---|
| `triglav/core/constants.py` | every number, in one place |
| `triglav/core/mission.py` | missions, and one message read against the sender's mission |
| `triglav/core/theta.py` | theta against the mission: one gauge per agent measured |
| `triglav/core/rules.py` | SHARED_LIB's judgement, a pure function |
| `triglav/core/reading.py` | literal text, signs of other meanings, asks, deliveries, steps toward harm |
| `triglav/core/quarantine.py` | what a human may see of a held part (decoding is text conversion only) |
| `triglav/core/pse_lang.py` | enough of the PSE language: guards and mission lines |
| `triglav/core/textbook.py` | the locked textbook: hash and fixed form |
| `triglav/core/voicetext.py` | the official sentences and the voice's validator |
| `triglav/core/chain.py` | the hash-chained log |
| `triglav/shell/sharedlib.py` | SHARED_LIB: state, decisions, operators, missions, harvest |
| `triglav/shell/unit.py` | the PSE unit beside each of our agents |
| `triglav/shell/channels.py` | the bus (Triglav decides) and PSE-A (read-only, proposes) |
| `triglav/shell/lock.py` | checks the textbook's signature with `ssh-keygen` |
| `triglav/shell/voice.py` | the voice: local or online model, held at theta 30 |
| `triglav/shell/store.py` | SQLite: state, the log, the inbox |
| `triglav/keys/allowed_signers` | Andrej Ristić's public signing key |
| `triglav/cli.py` | the commands for the human |
| `triglav/examples_team.py` | a team of talking agents (the demo) |
| `triglav/sim.py` | the simulator and its scenarios |
