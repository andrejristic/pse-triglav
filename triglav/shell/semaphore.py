"""The capability semaphore: computed at start and shown to the human at once
(after PSE-A AZ-2: never fail mid-run for a reason knowable at start)."""
from __future__ import annotations


def semaphore(channel, reader=None, transport=None, voice=None) -> list[str]:
    lines = []
    ch = channel.capabilities()
    if ch["channel"] == "bus":
        lines.append(f"channel: bus, {ch['agents']} of our agents -- Triglav DECIDES (Guardian, Physician)")
    else:
        found = "found" if ch.get("found") else "NOT FOUND (nothing to read until it exists)"
        lines.append(f"channel: pse-a, read-only, {ch['path']} {found} -- Triglav only PROPOSES; PSE-A is not changed")
    if reader is not None:
        r = reader.capabilities()
        txt = "free text read" if r.get("free_text") else "free text NOT read (rules only)"
        hid = "hidden text flagged" if r.get("hidden_text") else "hidden text not checked"
        lines.append(f"reader: {r['reader']} -- {txt}; {hid}; structured acts on our values read")
    if transport is not None:
        t = transport.capabilities()
        sep = "separate process" if t["separate_process"] else "same program (separate process comes in phase 4)"
        lines.append(f"SHARED_LIB: {sep}")
    if voice is not None:
        m = getattr(voice, "model", None)
        if m is None:
            lines.append("voice: official text only")
        else:
            where = "ONLINE -- facts leave this computer" if m.leaves_computer else "local -- nothing leaves this computer"
            lines.append(f"voice: retelling by a model, {where}; checked, held at theta 30")
    return lines
