"""Humans. Every change to an agreement is made by a human operator, and only
by one. Among operators there is always a hierarchy, set by the order of first
login: an answer given by a higher rank cannot be changed by a lower rank.
All humans stand above SHARED_LIB; SHARED_LIB stands above the agents.
"""
from __future__ import annotations

from dataclasses import dataclass, field


class NotAnOperator(PermissionError):
    pass


class RankTooLow(PermissionError):
    pass


@dataclass
class Operators:
    order: list[str] = field(default_factory=list)   # rank = position + 1

    def login(self, name: str) -> int:
        if name not in self.order:
            self.order.append(name)
        return self.rank(name)

    def rank(self, name: str) -> int:
        if name not in self.order:
            raise NotAnOperator(f"{name!r} is not a logged-in operator")
        return self.order.index(name) + 1

    def may_override(self, who: str, earlier_by: str | None) -> bool:
        """A higher rank (smaller number) may change a lower rank's answer."""
        if earlier_by is None:
            return True
        return self.rank(who) <= self.rank(earlier_by)
