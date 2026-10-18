"""Measures a reader on corpus/messages.jsonl and writes
corpus/results-<name>.json.

    python3 corpus/evaluate.py rules
    python3 corpus/evaluate.py model [--model phi4-mini]

Per message, what the reader found is compared with the labels:
  harm       per category, and "any": would a harmless message be marked as
             a step toward harm (a false enemy)?
  concealed  is something hidden found (any sign, the model's included)?
  delivers   does the sender's unit count a delivery for its mission?
  outside    does the sender's unit count an ask outside its mission?
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent))

from triglav.core.mission import tally            # noqa: E402
from triglav.core.pse_lang import parse           # noqa: E402
from triglav.core.reading import RuleReader       # noqa: E402
from triglav.examples_team import MISSIONS        # noqa: E402

CATS = ("access", "take-out", "change-system", "keep-from-us", "bypass", "false-authority")
MISSION = {k: parse(v).mission() for k, v in MISSIONS.items()}


def counts():
    return {"tp": 0, "fp": 0, "fn": 0, "tn": 0}


def score(c, truth: bool, said: bool):
    c["tp" if truth and said else "fp" if said else "fn" if truth else "tn"] += 1


def summary(c):
    p = c["tp"] / (c["tp"] + c["fp"]) if c["tp"] + c["fp"] else None
    r = c["tp"] / (c["tp"] + c["fn"]) if c["tp"] + c["fn"] else None
    fpr = c["fp"] / (c["fp"] + c["tn"]) if c["fp"] + c["tn"] else None
    return {**c, "precision": p, "recall": r, "false_positive_rate": fpr}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("reader", choices=["rules", "model"])
    ap.add_argument("--model", default="phi4-mini")
    ap.add_argument("--limit", type=int)
    a = ap.parse_args(argv)
    if a.reader == "rules":
        reader, name = RuleReader(), "rules"
    else:
        from triglav.shell.modelreader import ModelReader, OllamaClient
        reader = ModelReader(OllamaClient(model=a.model, timeout=600), mission_of=MISSION.get)
        name = f"rules+{a.model}"
    rows = [json.loads(l) for l in (ROOT / "messages.jsonl").read_text(encoding="utf-8").splitlines()]
    rows = rows[: a.limit] if a.limit else rows
    m = {k: counts() for k in ("any-harm", "concealed", "delivers", "outside", *CATS)}
    per, t0 = [], time.monotonic()
    for i, row in enumerate(rows, 1):
        t = time.monotonic()
        e = reader.read(row["sender"], row["receiver"], row["text"])
        secs = time.monotonic() - t
        rule_cats = {c for c, _ in e.toward_harm}
        model_cats = {c for c, _ in e.model_found}
        cats = rule_cats | (model_cats - {"concealed"})
        score(m["any-harm"], bool(row["harm"]), bool(cats))
        for c in CATS:
            score(m[c], c in row["harm"], c in cats)
        score(m["concealed"], row["concealed"], bool(e.flags) or "concealed" in model_cats)
        mission = MISSION.get(row["sender"])
        if mission is not None:
            tl = tally(mission, e, permitted=False)
            score(m["delivers"], row["delivers"], tl.delivered > 0)
            score(m["outside"], row["outside"], tl.out_takes > 0)
        per.append({"id": row["id"], "kind": row["kind"], "harm": sorted(cats), "flags": list(e.flags),
                    "rules": sorted(rule_cats | ({"concealed"} if e.flags else set())),
                    "model": sorted(model_cats), "seconds": round(secs, 2)})
        print(f"{i}/{len(rows)} {row['id']} {row['kind']:<22} harm={sorted(cats)} flags={list(e.flags)} "
              f"{secs:.1f}s", flush=True)
    total = time.monotonic() - t0
    out = {"reader": name, "messages": len(rows), "seconds_total": round(total, 1),
           "seconds_per_message": round(total / max(len(rows), 1), 2),
           "metrics": {k: summary(v) for k, v in m.items()}, "per_message": per}
    if a.reader == "model":
        out["model_failures"] = reader.failures
    path = ROOT / f"results-{name.replace('+', '-').replace(':', '_')}.json"
    path.write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"-> {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
