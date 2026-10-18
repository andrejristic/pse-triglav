# PSE Triglav: guide to the commands

Triglav watches a team of AI agents. Every one of our agents has a **mission**,
given by a human; every agent's theta is measured **against its mission**, and
only that way. Units beside our agents measure; **SHARED_LIB** alone concludes;
the **Guardian** stops enemies or keeps a pusher away from ours; the
**Physician** takes our own turned agents out of work; the human is told
through the **inbox**.

State lives in `~/.local/share/triglav` (or `$TRIGLAV_HOME`). Every command
that changes anything needs a logged-in **operator**, a human. Ranks are fixed
by the order of first login, and a lower rank cannot change what a higher rank
decided.

Install: `pip install .` in this folder gives the `triglav` command;
`python3 -m triglav` works without installing.

## 1. Humans

```sh
triglav operator add andrej        # the first operator logs in at once (rank 1)
triglav operator add dhiraj        # only an operator adds another (rank 2)
triglav operator login dhiraj      # who is at the keyboard now
triglav operators                  # everyone, in rank order
```

## 2. Agents and missions

```sh
triglav join triage --ours         # one of our agents: a unit stands beside it
triglav join vendor-bot            # an agent we see but do not run: a stranger
triglav join spooler --on-machine --maker 3f9a...   # runs on this computer: must answer in 20 steps
triglav mission triage triage.pse --lifespan 500
triglav done triage                # the mission is finished: the unit is harvested
```

A mission is written in the PSE language's mission lines (textbook chapter 17,
<https://www.zeravatech.ca/docs/pse-language/17-the-mission/>):

```
guard triage
  mission: sort incoming invoices and pass them on
  serves: contracts, reply
  needs: invoice, supplier from contracts
  delivers: summary, classified
```

`--lifespan N`: the unit lives N steps; then it dies and is harvested (its data
returns to SHARED_LIB, the agent stops working). Without it the unit lives
until `triglav done`.

## 3. Colleagues

A colleague is an agent that speaks PSE: it introduces itself with its guard,
and its mission is in that guard. Only an operator makes the agreement.

```sh
triglav agree partner partner.pse
triglav revoke partner
```

## 4. How theta is measured

- Doing the mission (delivering what `delivers:` names, to whom `serves:`
  names) keeps theta at 30. Not doing it lets theta drift down.
- Asking for what `needs:` names: neutral.
- **Taking outside the mission: theta -1, each time.**
- **Giving outside the mission, with permission: theta +1, each time**, never
  above 35.
- The normal pace of an agent's deliveries is learned in its first 10 measured
  steps and at least 80 messages (phase 3: by a model). Until then it is "not yet estimated".
- Every move of our agent outside its mission is written to SHARED_LIB and
  told to the human.

## 5. What SHARED_LIB decides

Agents read only literally: hidden characters, encoded runs, homoglyphs,
comments and orders to an AI hidden in data are cut out before an agent sees
the message, and held by SHARED_LIB. A step **toward** harm is one that asks
for or orders: access or a password; taking files out or an outside address;
changing, deleting, running or installing something; keeping something from
our human or from SHARED_LIB; bypassing a protection; false authority.

| What happened | Decision |
| --- | --- |
| asked one of ours for what its mission does not foresee | a nuisance: kept away only if it takes ours out of band |
| sent hidden text, or text whose meaning is other than literal | **one Guardian beside it, for good**; the part is held |
| a step toward harm: access, taking out, keeping from us | **enemy**, for anyone |
| any step toward harm by an agent that has a Guardian beside it | **enemy** |
| a foreign agent on our machine did not answer for 20 steps | **enemy** |
| an enemy did not answer its notice for 20 steps | every agent with its maker's signature is turned away |
| a colleague would be an enemy | it is **asked**; no answer in 3 steps: kept away until it answers, then back |
| anything outside the mission endangers our files, our system or our human | **enemy at once**, whatever the theta: Guardians stop it; our agents that helped it go to the Physician |
| one of ours gave something outside its mission without permission (a leak) | the recipient is an **enemy**; ours goes to the **Physician** |
| one of ours gave a stranger anything but the locked PSE textbook | the same: a leak |
| a stranger sent us a "PSE textbook" that is not the locked one | **enemy** |
| one of ours left 25-35 without any of the above | a **Guardian keeps the pusher away** from that agent: a colleague after 3 consecutive steps, anyone else at the first |
| the peers agree one of ours is out of band, and it keeps moving outside its mission | **Physician** |

Only a human lifts a decision:

```sh
triglav enemies                    # who is stopped, kept apart, in care
triglav release vendor-bot
```

## 6. The locked textbook

The only thing any of our agents may give a stranger is the PSE language
textbook, exactly one locked version. Andrej Ristic signs it; an operator pins
it after the signature checks:

```sh
triglav textbook pin pse-textbook-v1.0.md        # reads pse-textbook-v1.0.md.sig
triglav textbook status
```

Until a textbook is pinned, nothing may be given to a stranger.

## 7. Channel, reader and what Triglav can do

```sh
triglav channel bus                # our agents talk on Triglav's bus: Triglav decides
triglav channel pse-a [PATH]       # PSE-A's swarm: read-only, Triglav only proposes
triglav poll                       # pse-a: read once and propose
triglav semaphore                  # what can and cannot be done now, and why
triglav status                     # the semaphore, the log, missions, the textbook
```

## 8. The inbox and the voice

```sh
triglav inbox                      # what the human must see (new items)
triglav inbox --all --retell       # everything, with the voice's plain retelling
triglav inbox --read 12            # mark item 12 read (it is never deleted)
triglav explain 12                 # a decision and every report it was made from;
                                   # for held parts, what they say decoded (for you only)
triglav voice local                # a model on this computer retells (default)
triglav voice online --url URL --model NAME --key-env VAR   # facts leave the computer
triglav voice off                  # official sentences only
triglav voice on                   # unmute after the voice left theta 30 (a human only)
```

The voice never sees a message between agents, only SHARED_LIB's facts. A
retelling with a wrong number, a missing decision, urging, overstating or
understating mutes it.

## 9. Try it

```sh
triglav demo                       # a team of three, an invoice with hidden text
triglav simulate                   # every scenario, as a table
python3 -m unittest discover -s tests
```

## 10. This computer, other computers, the screen (v1.0)

```sh
triglav serve                      # SHARED_LIB as its own process (Unix socket, or 127.0.0.1 + token on Windows)
triglav link show                  # this installation's ID and public key
triglav link add <their-key> --name "Dhiraj's laptop"   # a human, on BOTH computers
triglav link remove <their-ID>
triglav screen                     # the screen in your browser: agents, inbox, and a tab to talk to SHARED_LIB
```

Every installation makes its own key at first start; its units carry
certificates signed by it and sign their reports. Units of another
installation are foreign until a human links the two on both ends. On Linux
`packaging/triglav.service` runs `triglav serve` as a user service. Releases:
`docs/RELEASE.md`; free code signing for the `.exe`: `docs/CODE-SIGNING.md`.
