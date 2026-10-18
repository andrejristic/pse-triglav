"""How reports reach SHARED_LIB. Phase 2: in the same program. Phase 4 adds a
separate process on 127.0.0.1 with signed reports, behind the same interface.
"""
from __future__ import annotations

from typing import Protocol

from ..core.report import Report


class Transport(Protocol):
    name: str

    def capabilities(self) -> dict: ...

    def deliver(self, step: int, reports: list[Report]) -> list[dict]: ...


class InProcess:
    name = "in-process"

    def __init__(self, lib):
        self.lib = lib

    def capabilities(self) -> dict:
        return {"transport": "in-process", "separate_process": False, "signed_reports": False}

    def deliver(self, step: int, reports: list[Report]) -> list[dict]:
        return self.lib.receive(step, reports)
