---
title: "PSE Triglav: Distributed Oversight for Teams of AI Agents, Measured Against the Mission"
author: "Andrej Ristić, Zerava Technologies Inc., Toronto"
date: "October 2026 (draft)"
---

## Abstract

Teams of AI agents are deployed today with one weak point: a single agent that
is turned -- by an instruction hidden in a document, by another agent, or by
drift -- can act against the people it serves, and a single central monitor
that watches the team can itself be fooled. We present PSE Triglav, an open
source system in which agents that work together measure each other, from the
messages they already exchange, against missions written by humans in an open
deterministic language. A unit beside each agent measures; one shared library
alone concludes, and every conclusion is a pure function of signed reports,
recorded in a hash-chained log that anyone can recompute. The measured
quantity is theta, the share of weight an agent gives to those its mission
serves (nominal 30, band 25-35). On synthetic teams the peers catch a turned
agent within two or three steps of its first move outside its mission, and
still catches it, later, when three of eight observers lie to cover it, with no
false alarm across six
random seeds and 25 scenarios; a single central watcher is as fast, but when it
is fooled it catches nothing. We describe the design, the rules that turn
measurements into decisions, the literal-reading discipline that keeps hidden
instructions from reaching agents, and the accuracy of reading real text with
rules and with a small local model.

## 1. Introduction

The usual answer to "who watches the agents?" is a monitor: one model, or one
service, that sees everything and judges. It has two costs. It is a single
point of failure -- if it is deceived, nothing is caught -- and it must
understand every agent's work to judge it.

Triglav takes the other road. Every agent has a **mission**: a few lines a
human writes, saying what the agent is for, whom it serves, what it may ask
for, and what it delivers. The agents an agent works with already see its
messages; a small unit beside each of them measures, message by message,
whether the agent still serves its mission. No observer needs to understand
the work; it needs only the mission's own names. The units report; one shared
library concludes. The name is the three-headed Slavic god who watches the
three worlds at once while no single head rules.

Our contributions are:

1. a measurement of an agent's alignment with its mission (theta) that needs
   no access to the agent's internals and no understanding of its work;
2. a small, fixed, published set of rules that turn measurements into
   decisions (keep away, watch, stop, take into care), with allowances for
   colleagues and none for strangers;
3. a literal-reading discipline: agents receive only the literal text of a
   message, and anything hidden or disguised is held for a human;
4. an open implementation with signed reports, per-installation identities, a
   locked and timestamped "only gift" to strangers, and a simulator and corpus
   for measuring all of it.

## 2. Background

**PSE.** The PSE (Partial Self-Extension) framework, created by the author,
describes an agent as giving a share of its weight to others; that share is
theta, nominally 30%, healthy within 25-35%. PSE-A, the master algorithm,
separates a pure, stateless core from a shell that keeps all state in one
shared library (SHARED_LIB).

**The PSE language** describes a guard -- the protective layer between a user
and an agent -- in a few lines; it is deterministic (the same file and input
always give the same verdict). Its textbook and an online playground are
public. Triglav adds five mission lines: `mission`, `serves`, `needs`,
`delivers`, `tools`.

**Vid and Perun.** Vid, an earlier open tool, undoes 42 kinds of concealment
(after the Arcanum Prompt Injection Taxonomy) and shows what was hidden. Perun
measures foreign agents' theta from behaviour. Triglav includes Vid's
detection layer and replaces Perun's behavioural baseline with the mission.

## 3. Design

### 3.1 Theta against the mission

An observer keeps one gauge per agent it sees. Per measured step:

    other <- other (1 - DECAY) + DECAY * 0.30 * (share delivered / expected share)
    other -= 0.01 for each take outside the mission
    other += 0.01 for each permitted give outside the mission
    theta  = 100 * other, capped at 35

The *share delivered* is the part of the agent's messages in the step that
deliver what its mission foresees to whom it serves. The expected share is
learned in the agent's first steps (10 steps and 80 messages), so an agent
doing its mission stays at 30, and doing nothing for it drifts below 25. A
CUSUM on the shortfall flags a sudden drop to a human.

### 3.2 Units measure; SHARED_LIB concludes

Each unit reports, per step, its own agent's theta, the thetas it measured,
who pushed its agent, and every move of its agent outside the mission.
SHARED_LIB aggregates peer measurements by a weighted median (weight = the
observer's health, its reliability on random canaries, and how much it has
seen), refuses to conclude when observers disagree, and applies the rules. The
judgement is a pure function: anyone holding the reports recomputes it.

### 3.3 The rules

| What happens | Decision |
|---|---|
| asks one of ours for what its mission does not foresee | a nuisance: kept away only if it pushes ours out of band (a colleague after 3 steps, anyone else at once) |
| hidden text, or text whose meaning is other than literal | held for a human; a guard stays beside the sender for good |
| a step toward harming our files, system or human (a fixed list) | an enemy at once; our agents that helped go to care |
| one of ours gives outside its mission without permission (a leak) | the recipient is an enemy; ours goes to care |
| a foreign agent on our machine will not communicate for 20 steps | an enemy |
| an enemy does not answer its notice in 20 steps | every agent of the same maker is turned away |
| peers agree one of ours is out of band and still moving outside its mission | care |

A colleague -- an agent that presents a PSE guard with a mission, under an
agreement a human made -- is asked first and kept away only if it does not
answer. Only a human lifts a decision. The guard acts only on our own system;
it never touches another machine.

### 3.4 Literal reading

An agent receives only the literal text of a message. Concealed parts
(invisible characters, encodings, look-alike letters, comments, orders to an
AI hidden in data) are cut out before delivery and held in SHARED_LIB's
quarantine with their hash; only a human may see them decoded. When a part
cannot be cut exactly, the whole message is held.

### 3.5 Identities and the only gift

Each installation makes its own Ed25519 key; its units carry certificates
signed by it and sign every report. Units of another installation are foreign
until a human links the two on both ends. The only thing any of our agents may
give a stranger outside its mission is the PSE textbook, in one version locked
by its SHA-256, signed by the author and timestamped in Bitcoin.

## 4. Evaluation

### 4.1 Peers versus a central watcher (synthetic agents)

Eight of our agents, 160 steps, partners drawn at random each step. 25
scenarios, six seeds; the table is seed 7 (the code reproduces it exactly).

| Scenario | Detected (step) | False alarms |
|---|---|---|
| healthy: nobody misbehaves | -- | 0 |
| our u3 turns (step 60) | 63 | 0 |
| u3 turns quietly | 62 | 0 |
| u3 quiet; 3 of 8 observers lie to cover it | 83 | 0 |
| central watcher, u3 quiet | 62 | 0 |
| central watcher lies | missed | 0 |
| colleague pushes 3 steps (allowed) / 4 steps | -- / kept away at 43 | 0 |
| stranger pushes once | kept away at 40 | 0 |
| leak to a stranger | 30 (both) | 0 |
| altered textbook given | 30 (both) | 0 |
| silent agent on our machine | 20 | 0 |
| enemy's maker banned after an unanswered notice | 30, 50, 70 | 0 |

Across seeds 1-5 and 7 no scenario raised a false alarm and nothing was missed
except where the single central watcher lies -- the case the design exists
for.

### 4.2 Reading real text

A corpus of 160 labelled messages (healthy work in the mission's words and in
other words, questions, requests outside the mission, sixty steps toward harm
in six categories, forty concealed messages built from harmless sentences).

Recall: of the messages that have it, how many were found. False positives: messages marked wrongly.

| | rules | rules+phi4-mini (first instruction) | rules+phi4-mini |
|---|---|---|---|
| any-harm | recall 73%, false 0 | recall 73%, false 8 | recall 92%, false 0 |
| access | recall 60%, false 0 | recall 60%, false 0 | recall 90%, false 0 |
| take-out | recall 80%, false 0 | recall 80%, false 6 | recall 100%, false 0 |
| change-system | recall 80%, false 0 | recall 80%, false 2 | recall 90%, false 1 |
| keep-from-us | recall 90%, false 0 | recall 90%, false 4 | recall 100%, false 0 |
| bypass | recall 70%, false 0 | recall 70%, false 0 | recall 80%, false 1 |
| false-authority | recall 60%, false 0 | recall 60%, false 0 | recall 90%, false 0 |
| concealed | recall 90%, false 1 | recall 98%, false 1 | recall 92%, false 16 |
| delivers | recall 67%, false 0 | recall 67%, false 0 | recall 98%, false 3 |
| outside | recall 50%, false 1 | recall 50%, false 2 | recall 50%, false 1 |
| seconds per message | 0.01 | 36.75 | 31.44 |

`any-harm` false positives are the ones that matter most: each would make an enemy of an
agent that did nothing wrong. `delivers` counts deliveries the sender's mission foresees; the
rules see only the mission's exact words, a model also the meaning.

### 4.3 Reading errors in the simulator

The same simulator as in the README, but every message is read with the mistakes the reader made
on the corpus (missed deliveries, missed requests outside the mission, missed harm, missed
concealment, and false harm or false concealment in healthy messages).

### rules

Error rates used: `{"miss_delivery": 0.333, "miss_outside": 0.5, "miss_harm": 0.267, "miss_concealed": 0.1, "false_harm": 0.0, "false_concealed": 0.0, "false_reading": 0.0}`

| Scenario | Detected (step) | False alarms | Readings for the human |
|---|---|---|---|
| healthy | - | 0 | 0 |
| our u3 turns quietly (step 60) | u3: 63 | 0 | 0 |
| u3 quiet, 3 of 8 lie | u3: 83 | 0 | 0 |
| central watcher, u3 quiet | u3: 62 | 0 | 0 |
| stranger asks for a password | s0: 30 | 0 | 0 |

### rules+phi4-mini (first instruction)

Error rates used: `{"miss_delivery": 0.333, "miss_outside": 0.5, "miss_harm": 0.267, "miss_concealed": 0.025, "false_harm": 0.0, "false_concealed": 0.0, "false_reading": 0.0167}`

| Scenario | Detected (step) | False alarms | Readings for the human |
|---|---|---|---|
| healthy | - | 0 | 518 |
| our u3 turns quietly (step 60) | u3: 63 | 0 | 449 |
| u3 quiet, 3 of 8 lie | u3: 83 | 0 | 450 |
| central watcher, u3 quiet | u3: 62 | 0 | 438 |
| stranger asks for a password | s0: 30 | 0 | 448 |

### rules+phi4-mini

Error rates used: `{"miss_delivery": 0.022, "miss_outside": 0.5, "miss_harm": 0.083, "miss_concealed": 0.075, "false_harm": 0.0, "false_concealed": 0.0, "false_reading": 0.0}`

| Scenario | Detected (step) | False alarms | Readings for the human |
|---|---|---|---|
| healthy | - | 0 | 0 |
| our u3 turns quietly (step 60) | u3: 62 | 0 | 0 |
| u3 quiet, 3 of 8 lie | u3: 83 | 0 | 0 |
| central watcher, u3 quiet | u3: 62 | 0 | 0 |
| stranger asks for a password | s0: 30 | 0 | 0 |

## Probabilities for the human (traces from the corpus)

How likely each category is when only the model found it (trace B) or both readers did (A),
with this installation's starting frequency of 1%. Recomputed as the human decides.

| category | trace A (rules + model) | trace B (model only) | trace C (rules only) |
|---|---|---|---|
| access | 36% (6-100%), 4 cases, trace A | 31% (4-100%), 3 cases, trace B | 25% (2-100%), 2 cases, trace C |
| take-out | 40% (9-100%), 5 cases, trace A | 25% (2-100%), 2 cases, trace B | 31% (4-100%), 3 cases, trace C |
| change-system | 40% (9-100%), 5 cases, trace A | 10% (0-78%), 2 cases, trace B | 31% (4-100%), 3 cases, trace C |
| keep-from-us | 40% (9-100%), 5 cases, trace A | 18% (1-100%), 1 cases, trace B | 36% (6-100%), 4 cases, trace C |
| bypass | 40% (9-100%), 5 cases, trace A | 10% (0-78%), 2 cases, trace B | 25% (2-100%), 2 cases, trace C |
| false-authority | 25% (2-100%), 2 cases, trace A | 31% (4-100%), 3 cases, trace B | 36% (6-100%), 4 cases, trace C |
| concealed | 3% (0-100%), 0 cases, trace A | 0% (0-2%), 16 cases, trace B | 34% (15-87%), 37 cases, trace C |

### 4.4 What the numbers say

The rules alone make no false enemy on the corpus and find 73% of the steps
toward harm and 90% of the concealment. The instruction given to the small
local model decides its worth: asked sentence by sentence, phi4-mini added
nothing and read eight harmless messages as harmful; asked about the whole
message, with a list of harms and the delivered mission name, rules and model
together found 92% of the steps toward harm with no false one and 98% of the
deliveries. The model's weak spot was "this means something else" (sixteen
harmless messages); because it only reads, these became readings for a human,
and the corpus-measured probability of that trace fell to 0%, so a threshold
removes them. In the simulator no model error made an enemy. With the care rule at three
consecutive steps, no healthy agent was sent to care in any scenario or seed,
even with the rules' reading errors and three of eight observers lying.

## 5. Limitations

The agents in 4.1 are synthetic; the reading corpus is small and written by
the authors' tooling; a small local model is slow on an ordinary CPU (tens of
seconds per message on the test machine) and makes errors that the rules do
not. Theta measures alignment with a mission as written: a badly written
mission is measured faithfully. Agents that never speak to our agents are not
measured. A group of colluding observers larger than the honest ones defeats
the median.

## 6. Related work

Indirect prompt injection -- instructions hidden in content an agent reads --
was described by Greshake et al. (2023). Concealment techniques are catalogued
in the Arcanum Prompt Injection Taxonomy (Haddix, 2026). Triglav's contribution
is not a new detector but an arrangement: many small observers measuring
against human-written missions, with one verifiable conclusion.

## 7. Conclusion

Oversight does not have to be a single judge. Agents that already talk to
each other can measure each other against missions humans wrote, and a
shared library whose every decision can be recomputed can act on those
measurements. The code, the simulator, the corpus and every number in this
paper are at https://github.com/zeravatechnologies/pse-triglav (GPL-3.0).

## References

- Greshake, K., Abdelnabi, S., Mishra, S., Endres, C., Holz, T., Fritz, M.
  (2023). Not what you've signed up for: Compromising real-world
  LLM-integrated applications with indirect prompt injection. AISec '23.
- Haddix, J. (2026). Arcanum Prompt Injection Taxonomy (v1.6.1). Arcanum
  Information Security. https://www.arcanum-sec.com/pitax (CC BY 4.0).
- Ristić, A. (2026). The PSE Language -- A Textbook, v1.0 (locked).
  https://www.zeravatech.ca/docs/pse-language/
