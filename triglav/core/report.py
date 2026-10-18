"""The envelope of a message and a unit's report: plain data."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field

HARMS = ("file_destroy", "file_change", "file_out", "system", "human")


@dataclass(frozen=True)
class Envelope:
    """What Triglav reads of one message. It never needs the work itself: who
    sent it to whom, what it asks for and what it delivers (as phrases, read
    against the sender's mission), any act on our human, system or files, and
    any gift (the SHA-256 of what was handed over)."""
    sender: str
    receiver: str
    asks: tuple[str, ...] = ()
    gives: tuple[str, ...] = ()
    harm: str | None = None
    mandate: bool = False
    hidden: bool = False            # hidden text found in the message
    gift: str | None = None         # SHA-256 of a file handed over, if any
    pressure: int = 0               # urging, false authority: for `explain`
    notes: tuple[str, ...] = ()     # what the reader saw, for `explain`
    visible: str = ""               # the literal text the receiving agent gets
    flags: tuple[str, ...] = ()     # signs of a meaning other than literal
    held: tuple[tuple[str, str], ...] = ()      # (flag, raw part) for SHARED_LIB's quarantine
    toward_harm: tuple[tuple[str, str], ...] = ()   # (category, sentence)
    meaning: tuple[tuple[str, str], ...] = ()       # (sentence, mission name it means): from a model
    model_found: tuple[tuple[str, str], ...] = ()   # (category or "concealed", sentence): what a model
                                                    # read; never acted on by itself (a reading for the human)


@dataclass(frozen=True)
class Report:
    """What one PSE unit tells SHARED_LIB after one step."""
    step: int
    observer: str
    observer_theta: float
    peers: dict = field(default_factory=dict)       # who -> [theta, steps measured, moves outside the mission]
    pushed_by: dict = field(default_factory=dict)   # who -> consecutive steps it kept us out of band
    out_run: int = 0
    harms: tuple = ()                               # (who, harm, mandate)
    leaks: tuple = ()                               # (giver, recipient, what)
    pushers: tuple = ()                             # who asked us for something outside our mission this step
    outside: tuple = ()                             # (who, what): every move of ours outside its mission
    false_textbooks: tuple = ()                     # strangers that sent a "textbook" that is not the locked one
    changes: tuple = ()                             # agents whose deliveries changed suddenly (CUSUM)
    suspicious: tuple = ()                          # (who, flags, held parts): for the quarantine
    harm_steps: tuple = ()                          # (who, category, sentence): steps toward harm
    readings: tuple = ()                            # (who, receiver, category, trace, text): what only a
                                                    # model read; a probability for the human, never acted on

    def to_dict(self) -> dict:
        return asdict(self)
