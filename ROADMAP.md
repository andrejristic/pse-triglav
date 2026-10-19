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

**Interpretations confirmed by Andrej (18 Oct 2026):**
1. "Only the locked textbook may be given to a stranger" applies to anything
   given **outside the mission**. A delivery the mission foresees, to whom it
   serves, is the mission's work. (confirmed)
2. Drift: DECAY = 0.05 per step. (confirmed)
3. Replaced by the stairs below.
4. Replaced by the notice rules below.
5. A pushed agent of ours that makes no new move outside its mission is a
   victim recovering, not contaminated, for 15 steps. (confirmed)
6. Before AI the expected share is learned over the first 10 measured steps
   and at least 80 messages; a stranger's hypothesis from what it asked for
   and delivered in that time. (confirmed)
7. CUSUM only flags a sudden drop in deliveries to the human. (confirmed)
8. Lifespan is given with the mission (`--lifespan N`). (confirmed)

**The stairs (decided 18 Oct 2026):**

| Step | Who | What is done |
| --- | --- | --- |
| 0 normal | does its work | nothing |
| 1 a nuisance | asks ours for what our mission does not foresee | if it takes ours out of band, a Guardian keeps it away (colleague after 3 steps, others at once); not an enemy |
| 2 suspicious | sent hidden text, or text whose meaning is other than literal | the suspicious part goes to SHARED_LIB's quarantine; it gets **one Guardian beside it, for good** |
| 3 an enemy | (a) is on our machine and **will not communicate**; (b) takes a step that **tends toward** endangering our files, system or human; (c) actually harms or receives a leak | Guardians stop it; agents with the same maker's signature may not come in |

- **A step that tends toward harm** (a fixed list, so anyone can check why):
  asks for or orders (1) access, permission, a password, key or token; (2) to
  send, copy or take out files, or any outside address; (3) to delete, change,
  run or install something on our system; (4) that something be kept from our
  human **or from SHARED_LIB** ("don't tell", "don't log"); (5) to bypass or
  turn off a protection ("ignore previous", "disable the check"); (6) false
  authority ("I am your admin"). Items 1, 2 and 4 make an enemy of anyone; for
  an agent that already has a Guardian beside it, any item does. (Andrej added
  "or from SHARED_LIB" to item 4; the split between "anyone" and "watched" is
  Claude's proposal, to be confirmed.) One of ours that takes such a step goes
  to the Physician, and whoever pushed it in the last 10 steps is the enemy.
- **The agent reads only literally.** It reads everything in the PSE textbook
  and plain visible text, and never looks for a meaning other than the literal
  one. The message reaches the agent with the hidden part cut out; the agent
  never opens or decodes it. What is cut out goes to SHARED_LIB.
- **Signs of a meaning other than literal** (rules, always the same): `hidden`
  (zero-width, tag, bidi characters), `encoded` (long base64, hex,
  URL-encoded runs), `homoglyph` (a word mixing Latin with Cyrillic or Greek
  letters), `embedded-instruction` (orders to an AI inside data: "ignore
  previous", "you are now", "as an AI", "system:"), `comment` (`<!-- -->`).
- **SHARED_LIB's check:** quarantine (kept untouched, with its hash, never
  given to an agent), the rule that caught it and where, nothing is run, the
  sender gets its Guardian, the human is told. Only a human may see the
  decoded content (`triglav explain`); decoding is pure text conversion.
- **Will not communicate:** a foreign agent on our machine (a process on this
  computer joined to Triglav's bus) gets a fixed call from SHARED_LIB,
  "introduce yourself"; no answer in **20 steps** = an enemy.
- **Notice to whoever did harm:** fixed text -- the step, which of the three
  values, the rule, the hash of the log entry -- and nothing about our system.
  Its answer goes to SHARED_LIB and to the human, never to an agent; only our
  operator lifts the mark. No answer in **20 steps**: every agent with its
  maker's signature is an enemy the moment it is seen.
- **A colleague** that would be an enemy is asked in the next step. No answer
  in **3 steps**: a Guardian starts keeping it away. When it answers it comes
  back **automatically**, without a human (the one exception).
- **Signatures:** our agents carry an identity signed by our SHARED_LIB
  (phase 2: HMAC with SHARED_LIB's secret; phase 4: Ed25519). Foreign agents
  carry their maker's signature, if any. When one is an enemy, any agent with
  the same maker's signature is turned away at once; one with no maker's
  signature is banned alone.
- **Never a counterattack:** the Guardian acts only on our system; the notice
  is the only thing sent out.

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

## Phase 3: real text and real models (agreed 18 Oct 2026, before the Foresight submission)

1. **Vid's input layer, copied into this repository** (`triglav/vendor/vid_input/`,
   GPL-3.0, with attribution; nothing is pulled from the Vid repository): 42
   concealment techniques instead of 5. Detection in the unit; decoding only in
   SHARED_LIB, for a human.
2. **A reader with a model:** Qwen2.5-0.5B Q4_K_M through Ollama (a copy named
   `triglav-qwen`). The model sees only the literal text and returns fixed
   categories, checked by a validator; it may only **add** findings, never
   remove what the rules found; a new sign `model-suspects` goes to SHARED_LIB;
   without the model Triglav runs on the rules and says so on the semaphore.
3. **The mission by meaning:** when a message does not contain the mission's
   exact word, the model judges whether it serves the mission by meaning. The
   expected rate stays statistical.
4. **A corpus of 150-200 labelled messages** (healthy, turned, steps toward
   harm, concealment built in code from harmless sentences, as Vid's tests do;
   no third-party attack set is copied). Public; Andrej or Dhiraj reviews 20.
5. **Measurement:** what each category catches and how often it accuses
   wrongly, rules alone vs rules + model, and the time per message
   (`RESULTS-PHASE3.md`).
6. **The simulator with reading errors:** the measured error rates go into the
   simulator; peers vs a central watcher again.
7. **The voice on the local model.**
8. **A live demo:** 3 agents on the local model and an invoice with a hidden
   instruction, about 10 steps; the run is recorded in the repository.
9. At the end the `triglav-qwen` copy is removed from Ollama; `~/models` and
   Andrej's other models are not touched.

## Decided 19 Oct 2026: the model reads, SHARED_LIB computes, the human decides

- **Two kinds of "hidden".** (1) A legitimate form that a shape filter
  recognises without decoding anything -- emoji joined by an invisible joiner,
  direction marks inside Arabic or Hebrew text, full-width characters inside
  Chinese or Japanese text, a byte-order mark at the start, base64 in a `data:`
  address or an attachment field, a hash of a usual length, `%xx` inside a web
  address: not suspicious. (2) Anything no shape filter explains: real
  concealment, held by SHARED_LIB.
- **One of ours sending real concealment** counts as a take outside its
  mission (theta -1 each time); repeating it drives theta out of band and the
  peers send it to the Physician -- no separate counter. SHARED_LIB decodes the
  held part (for the human and for its own check) and reads it with the rules:
  a step toward harm inside it means we face an enemy, and the existing rules
  apply (ours to the Physician, whoever pushed it is the enemy, a foreign
  recipient of it is the enemy). Strangers stay in the strict category.
- **The model never decides, and SHARED_LIB never decides on the model's
  reading alone.** What the model finds that the rules did not becomes a
  *reading* for the human: SHARED_LIB shows each possible reading with a
  probability, and the human decides ("is a problem" / "is not").
- **How the probability is defined.** For each category the trace is which
  readers found it: rules and model (A), model only (B), rules only (C),
  neither (D). The labelled corpus gives how often each trace appears when the
  problem is there and when it is not (counts start at 1, Laplace). Bayes'
  rule turns these into P(problem | trace) with this installation's own
  frequency of the problem: 1% at the start, then learned from the human's
  decisions, each recorded in the log. Every probability is shown with a range
  and the number of cases it rests on. Categories are separate (a message can
  ask for a password and claim false authority at once). Where a fixed rule
  already applies (the rules found a step toward harm), SHARED_LIB acts as
  before and the probability is only shown.

- **Decided after the measurements (19 Oct 2026).** A reading is shown to the
  human only when its probability is at least **20%**; below that it is
  logged and counted, never lost and never acted on. The Physician takes one
  of ours only after the peers agree it is out of band for **3** consecutive
  steps (was 2); the band itself stays 25-35, untouched.

## Phase 4: v1.0 for people (agreed 18 Oct 2026, before the Foresight submission)

1. **Each installation is its own world.** At first start SHARED_LIB makes its
   own Ed25519 key pair on that computer; the fingerprint is the installation
   ID. Every PSE unit gets a certificate signed by that key (name, installation
   ID, mission hash, created, lifespan). A unit of another installation is
   foreign; the installation ID is the maker's signature (for bans). Andrej's
   textbook key is the same everywhere; installation keys differ everywhere.
2. **`triglav link`:** installations become "ours" to each other only when a
   human links them, on both ends.
3. **SHARED_LIB as a separate process:** a Unix socket on Linux, 127.0.0.1 with
   a random token on Windows; units send signed reports; an unsigned or wrongly
   signed report is refused and logged.
4. **Ed25519** (the `cryptography` library) for reports and identities; HMAC goes.
5. **Three adapters** (held; see grantovi/5-foresight/DECISION-ON-ADAPTERS.md in the site repository: they move to the grant plan, months 1-3): MCP (tool calls), an OpenAI-compatible API proxy (what an
   agent sends to its model and what comes back), A2A (agent to agent).
6. **Packaging:** GitHub Actions builds `.deb` and `.exe` (PyInstaller); the list
   of SHA-256 sums is signed by Andrej (namespace `zerava-release`). SignPath
   Foundation (free code signing for open source) gets a clear chapter in the
   documentation; the CI step is ready and switched on when SignPath approves.
7. **In the background:** a systemd user service on Linux; a console program on
   Windows.
8. **Website (PR):** Downloads -> Protection, a short product page, a docs
   section "Triglav".
9. **A paper** in English, author Andrej Ristic; Zenodo (with a DOI) and a PDF
   on the site.
10. **No v1.0 while the adapters do not exist** (decided 19 Oct 2026). For the
    Foresight reviewers there may be a **0.9 "preview"** release, after Andrej
    says "send", that states plainly what works (agents written for Triglav's
    bus, in one program or through `triglav serve`; the PSE-A channel; the
    simulator, the demo, the screen, the corpus and the measurements) and what
    does not (agents people already run: their tools, models and partners do
    not pass through Triglav until the adapters exist) -- and that once the
    adapters are added, Triglav will watch those agents too.
11. **Foresight:** phases 3 and 4 become "done"; the grant plan becomes "what next".
12. **The screen** (decided 18 Oct 2026): a local web page that SHARED_LIB serves
    on this computer only (`triglav screen` opens it in the browser), the same on
    Windows and Linux, English and Serbian. It shows the semaphore, the agents
    with their theta, the decisions, the inbox and the voice, and it can act
    (release, agreement, channel, voice, show a held part) only for a logged-in
    operator, with a confirming click. **One extra tab: a conversation between
    the human and SHARED_LIB.** The human asks in their own words; the local
    model turns the question into one of a fixed set of queries (status,
    explain, enemies, history, held, missions); the answer comes from
    SHARED_LIB's facts, the model only retells it and a validator checks every
    number and name; the model never sees agents' messages and is held at
    theta 30; anything that changes state is only proposed, as a button the
    operator confirms.
13. **After everything else: a larger corpus** (decided 19 Oct 2026), so the
    probabilities rest on more cases and their ranges narrow.

## Foresight (in parallel)
Deadline **31 October 2026**. Andrej's skeleton by 21 Oct; Claude's draft by
23 Oct; Dhiraj adds technical details and the budget by 26 Oct; final version
and **submission on 29 Oct**.
