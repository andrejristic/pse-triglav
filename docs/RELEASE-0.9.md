# PSE Triglav 0.9.0 (preview)

*A preview for people who want to try Triglav and for reviewers. Not 1.0: see "What does not work yet".*

## What works

- **Missions and theta measured against them.** Every agent's mission is written in the open PSE language; the agents it works with measure, from the messages they exchange, whether it still serves that mission.
- **One shared library concludes.** Units sign their reports; SHARED_LIB applies fixed, published rules and records every decision in a hash-chained log that anyone can recompute.
- **The stairs.** A nuisance is kept away; a sender of hidden text gets a guard beside it for good; a step toward harming your files, your system or you makes an enemy at once, on your system only; one of yours that turns goes to the Physician after its peers agree for three steps.
- **Agents read only literally.** Vid's 42 concealment detectors are built in, plus shape filters for legitimate forms (emoji, Arabic or Hebrew text, hashes, attachments); anything hidden is held for you and shown to you alone.
- **An optional reader with a local model** (phi4-mini through Ollama). It only reads: what only the model finds becomes a reading with a probability measured on a labelled corpus, shown to you when it is at least 20%; you decide.
- **Each installation is its own world.** Its own Ed25519 key, unit certificates, signed reports; computers linked only by a human, on both ends.
- **`triglav serve`** (SHARED_LIB as its own process), **`triglav screen`** (a browser screen with a tab for talking to SHARED_LIB), the commands, and guides in English and Serbian.
- **Measured:** 109 automated tests; a simulator with 25 scenarios and no false alarm on six seeds; on a labelled corpus of 160 messages, rules plus model find 92% of the steps toward harm with no false one. See `RESULTS-PHASE3.md`.

## What does not work yet

- **The adapters are missing.** Triglav cannot yet sit beside agents you already run: their tool calls (MCP), their model calls (OpenAI-compatible APIs) and their talk with other agents (A2A) do not pass through it. Today it protects agents written for its own bus (in one program, or through `triglav serve`), and runs the simulator and the demos.
- **Windows builds are not code-signed yet** (Windows will warn about an unknown publisher). Check the SHA-256 sums and their signature below.
- **Figures for real deployments are still to be established.**

**When the adapters are added, Triglav will watch the agents you already run as well.** That is the next step (see the roadmap).

## Files

- `pse-triglav_0.9.0_all.deb`: Ubuntu and Debian (needs Python 3.10+ and python3-cryptography)
- `triglav.exe`: Windows (console program)
- `SHA256SUMS` and `SHA256SUMS.sig`: the sums, signed by Andrej Ristić

## Check a download

```sh
sha256sum -c SHA256SUMS
ssh-keygen -Y verify -f allowed_signers -I andrej-ristic -n zerava-release -s SHA256SUMS.sig < SHA256SUMS
```

`allowed_signers` is in the repository at `triglav/keys/allowed_signers` (key fingerprint SHA256:2AE7b4r/6+XoObrRT41SlNSC+4YXdtvZG51Vf/PXml4).

GPL-3.0. By Andrej Ristić, Zerava Technologies Inc.
