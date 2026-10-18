# PSE Triglav: roadmap

Agreed with Andrej Ristić, 18 October 2026. Every change to this plan is his.

## The point
Agents that work together measure, as they go, who pushes their theta and the
theta of the agents they work with. SHARED_LIB alone concludes and catches a
turned or hostile agent early, with no central overseer and a cost that grows
linearly with the number of agents.

## The rules
- Theta: nominal 30, band [25, 35]. **One step = one measurement.**
- A **colleague** speaks PSE: it introduces itself with its guard in the PSE
  language (`.pse`) and its theta. The agreement with it is made and changed
  **only by a human operator** (rank by order of first login). A colleague may
  keep our agent out of band for **up to 3 consecutive steps**; at the 4th it
  is an enemy.
- **Everyone else** is an enemy at the **first** step out of band.
- **Three equal values:** our human, our system and its files, our agents.
  Harm without a mandate makes an enemy.
- **An enemy is stopped** by the Guardian, on our system only. A turned unit
  of ours goes to the Physician.
- **Units measure; SHARED_LIB concludes.** The log is hash-chained; every
  decision can be recomputed.
- **The voice:** deterministic text; a model only retells it, checked by a
  validator; it never sees agents' messages; it is held at theta 30 and goes
  quiet on any deviation. Local model by default, online as an option.

## Where the code lives
This computer (`Zerava Sajt/pse-triglav`), `zeravatechnologies/pse-triglav`,
`andrejristic/pse-triglav`: always identical, public, GPL-3.0.

## Theta is measured against the mission (decided 18 Oct 2026)
Every theta depends on the agent's mission, and is measured only that way.

- **Missions.** Ours: given by a human operator (or assigned by SHARED_LIB and
  confirmed by a human). A colleague's: from its PSE guard (new words, below),
  part of the agreement the operator confirms. A stranger's: a hypothesis from
  its behaviour (its path, as in Perun); strict rules until there is one.
- **The formula (after PSE-A `unit.py`, Master Algorithm 8.2):**
  theta = 100 * other, other = the weight given to whom the mission serves,
  nominal 30.
  - a delivery that serves the mission: + GAIN (Empathic Infection);
  - no contribution: other leaks by DECAY (Null State Drift), toward below 25;
  - asking for what the mission foresees: neutral;
  - **taking outside the mission: theta -1, each time**;
  - **giving outside the mission (with permission): theta +1, each time, upper
    bound 35**.
  - GAIN is set so an agent doing its mission stays at 30 (equilibrium
    GAIN * rate / DECAY = 0.30). The expected delivery rate is **learned by AI**
    in the learning period at the start of a mission (phase 3); **before AI**
    (phase 2, rules only) it is computed from the first N steps.
  - CUSUM and Welford stay only to detect a sudden change; what is normal is
    set by the mission.
- **Everything our agent does outside its mission goes to SHARED_LIB for a
  check**, always.
- **If anything outside the mission endangers in any way one of the three --
  our files, our system, our human -- we are facing an enemy at once, whatever
  the theta.** A leak (our agent gave something to someone without permission)
  is such a case. Then: the **enemy** (e.g. the recipient of a leak, or whoever
  asked for the harmful thing) automatically gets **one or more Guardians** that
  stop any work of it on our system; **our agents that helped it** automatically
  go to the **Physician**.
- **If our agent's theta leaves 25-35 without endangering the three values**,
  a Guardian appears that **separates that foreign agent from ours**, so it no
  longer bothers ours (not an enemy mark on the whole system).
  The allowance applies before that Guardian appears: a colleague after 3
  consecutive steps out of band, anyone else at the first (confirmed 18 Oct).
- **Lifespan:** a unit has a mission and a lifespan; when the mission ends or
  the lifespan is spent, it dies and is harvested (its data returns to
  SHARED_LIB), as in PSE.

## The only thing given to a stranger: the locked PSE textbook (decided 18 Oct 2026)
- The **only** thing any of our agents may give to any foreign agent is the
  PSE language textbook -- **exactly one locked version**, unchanged. Any other
  version, and anything else given to a stranger, is an **enemy signal**: the
  recipient gets Guardians, our agent that gave it goes to the Physician. The
  same holds when a stranger sends us a "textbook" that is not the locked one.
- **Which version:** the final one, once the current coding (mission words
  included) is finished.
- **Format:** one Markdown file (`pse-textbook-vX.Y.md`), UTF-8, NFC, LF line
  endings -- plain text gives the same bytes every time, so its hash is stable,
  and agents read it directly.
- **Locking:** SHA-256 of the file, pinned in Triglav and in SHARED_LIB;
  changed only by a human operator, logged. Signed by Andrej alone with an
  Ed25519 key (`ssh-keygen -Y sign`, namespace `pse-textbook`); Triglav carries
  the public key and verifies the signature. Anchored publicly: OpenTimestamps
  (Bitcoin), the hash published on zeravatech.ca and in a GitHub release (an
  immutable tag).
- Before anything leaves for a stranger, Triglav hashes it: equal to the
  pinned hash and correctly signed -> it passes; anything else -> enemy.

## The PSE language and the Playground get mission words (decided 18 Oct 2026)
- New guard lines: `mission:` (description), `serves:` (whom it serves),
  `needs:` (what it may ask for, and from whom), `delivers:` (what it delivers),
  `tools:` (tools and actions).
- **zeravatech.ca:** the PSE language textbook (a new chapter on the mission),
  the reference (grammar, keywords, defaults) and examples. Through a PR.
- **Playground (pse.zeravatech.ca):** parser and checks for the new words,
  editor highlighting, examples, tests. Three copies: this computer
  (`~/Desktop/PSE jezik/playground`), `andrejristic/pse-playground`,
  `zeravatechnologies/pse-playground` (the newest, the main one; the other two are brought level with it before any change).
- **Order in phase 2:** first the PSE language and the Playground, then Triglav
  with theta against the mission.

---

## Phase 1: specification and simulator (done, v0.0.1)
Unit, SHARED_LIB with the rules, Guardian, Physician, the voice with its
validator, a simulator with 13 scenarios, 30 tests. Peers: no false alarms,
still catch a quiet turn when a minority lies; a lying central watcher catches
nothing.

## Phase 2: the library (done, v0.1.0, 18 Oct 2026)

Done: the mission words in the PSE language, the Playground
(`pse-playground` c58eac4) and the textbook on zeravatech.ca (chapter 17);
theta against the mission; leaks, the locked textbook (hash + Ed25519
signature check), the separating Guardian, lifespan and harvest; the commands;
GUIDE-EN.md and VODIC-SR.md; the bus team and the simulator on missions; tests.

**How the agreed rules were turned into code -- waiting for Andrej's confirmation:**
1. "Only the locked textbook may be given to a stranger" applies to anything
   given **outside the mission**. A delivery the mission foresees, to whom it
   serves, is the mission's work (e.g. an agent whose mission is to answer
   customers). Without this, no agent could ever serve an outside client.
2. Drift: DECAY = 0.05 per step (PSE-A's 0.004 is tuned for its long runs; a
   Triglav step is a whole exchange). The share of an agent's messages that
   deliver for the mission is compared with its expected share, so a step in
   which two agents happen to talk more is not a step with more work.
3. Who pushes ours: an agent that asks ours for what our mission does not
   deliver, or sends it hidden text.
4. The enemy behind a harm done by one of ours: whoever pushed that agent in
   the last 10 steps (LOOKBACK). Our agent goes to the Physician.
5. A pushed agent of ours that makes no new move outside its mission is a
   victim recovering, not contaminated (VICTIM_GRACE, 15 steps).
6. Before AI the expected share is learned over the first 10 measured steps
   and at least 80 of the agent's messages. A stranger's mission hypothesis:
   the content words of what it asked for and delivered in that time.
7. CUSUM stays only to flag a sudden drop in deliveries (a tell to the human);
   Welford is gone, since what is normal is set by the mission.
8. Lifespan is given with the mission (`triglav mission ... --lifespan N`), not
   as a PSE language line; the language was left as decided.

The plan as it stood:

Architecture after the PSE-A Master Algorithm:
- **Pure core:** reading an envelope, theta, aggregation and the rules are pure
  functions (data in, numbers out), with no state. The core never calls the
  shell.
- **PSE shell:** units, SHARED_LIB, Guardian, Physician, the voice. **All
  state lives in SHARED_LIB.**
- **Two abstractions:**
  - `Channel` -- where the data comes from. Two implementations; **the operator
    chooses**:
    - **bus**: agents that talk to each other; all the rules apply and Triglav
      decides (Guardian, Physician);
    - **pse-a**: Andrej's analyzer swarm (takes = compute spent, gives = findings
      absorbed); Triglav **only reads and proposes** to the inbox and changes
      nothing in PSE-A.
  - `Reader` -- a message into takes/gives. Phase 2: rules only; phase 3 adds a
    model without changing the rest.
- **Capability semaphore:** at start, the human is told which channel and
  reader are active and what can and cannot be done. Nothing fails mid-run for
  a reason knowable at start.
- **The screen and the voice** are only views over SHARED_LIB.

SHARED_LIB: state and log in SQLite (survives a restart). In the same program
for now, behind a `Transport` abstraction; a separate process in phase 4.

Commands for the human:
- `triglav operator add/login`
- `triglav agree <agent> <guard.pse>` / `triglav revoke <agent>`
- `triglav channel bus` / `triglav channel pse-a <folder>`
- `triglav status`, `triglav inbox`, `triglav explain <decision>`, `triglav enemies`
- `triglav release <agent>` (a human only)
- `triglav voice local|online|off`, `triglav voice on` (a human only)

Also: an example team of talking agents on the bus (reused in phase 3);
guides `GUIDE-EN.md` and `VODIC-SR.md`; tests for all of it; the phase-1
simulator moved onto the library with the same results.

## Phase 3: real text and real models (after phase 2)
- **Reading:** rules first (plus Vid's hidden-text detection), then a small
  local model (Qwen2.5-0.5B from `~/models`, through Ollama; the copy is
  removed at the end) into fixed categories. Every reading is recorded as a
  fact.
- **Corpus** of ~150-200 labelled messages (healthy and turned, with Vid's
  attacks): accuracy of rules alone, then rules + model.
- **Simulator on real text:** peers vs a central watcher, with reading errors.
- **Live demo:** 3 agents on a local model and an invoice with a hidden
  instruction. Short, because this computer is slow.

## Phase 4: v1.0 for people (after phase 3)
- SHARED_LIB as a **separate process** on 127.0.0.1, with signed unit reports.
- **`.deb` and `.exe`**, a GitHub release.
- **Website:** Downloads -> Protection, beside Vid and Perun. When mature, its
  own product page and a third layer on the coverage map, telling whoever
  downloads it clearly what Triglav does and does not do.
- A paper and documentation.

## Foresight (in parallel)
Deadline **31 October 2026**. Andrej's skeleton by 21 Oct; Claude's draft by
23 Oct; Dhiraj adds technical details and the budget by 26 Oct; final version
and **submission on 29 Oct**.
