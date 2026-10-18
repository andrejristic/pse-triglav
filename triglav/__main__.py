"""python -m triglav  -- run the phase-1 scenarios and print the table."""
from __future__ import annotations

import sys

from .sim import run, scenarios, table


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv if argv is None else argv
    seed = int(argv[1]) if len(argv) > 1 else None
    results = []
    for sc in scenarios():
        if seed is not None:
            sc.seed = seed
        results.append(run(sc))
    print(table(results))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
