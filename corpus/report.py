"""Writes RESULTS-PHASE3.md from corpus/results-*.json, runs the simulator with
the reading errors each reader made, and fills those numbers into the paper.

    python3 corpus/report.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent
sys.path.insert(0, str(REPO))

from triglav.core import evidence                     # noqa: E402
from triglav.sim import Behaviour, Scenario, run      # noqa: E402

ROWS = ("any-harm", "access", "take-out", "change-system", "keep-from-us", "bypass", "false-authority",
        "concealed", "delivers", "outside")


def pct(x):
    return "-" if x is None else f"{100 * x:.0f}%"


def rates(res: dict, labels: dict) -> dict:
    """Reading error rates for the simulator, from what the reader did on the corpus."""
    m = res["metrics"]
    healthy = [p for p in res["per_message"] if not labels[p["id"]]["harm"] and not labels[p["id"]]["concealed"]]
    rules_of = lambda p: [c for c in p.get("rules", p["harm"]) if c != "concealed"]
    false_conc = sum(1 for p in healthy if p["flags"]) / max(len(healthy), 1)
    false_harm = sum(1 for p in healthy if rules_of(p)) / max(len(healthy), 1)
    false_reading = sum(1 for p in healthy if not rules_of(p) and [c for c in p.get("model", []) if c != "concealed"]) / max(len(healthy), 1)
    miss = lambda k: 1 - (m[k]["recall"] or 0)
    return {"miss_delivery": round(miss("delivers"), 3), "miss_outside": round(miss("outside"), 3),
            "miss_harm": round(miss("any-harm"), 3), "miss_concealed": round(miss("concealed"), 3),
            "false_harm": round(false_harm, 4), "false_concealed": round(false_conc, 4),
            "false_reading": round(false_reading, 4)}


def sim_rows(r: dict) -> list[str]:
    out = []
    for name, sc in (("healthy", Scenario("healthy", reading=r)),
                     ("our u3 turns quietly (step 60)", Scenario("q", reading=r, behaviours={"u3": Behaviour("quiet", 60)},
                                                                 expect_bad=("u3",))),
                     ("u3 quiet, 3 of 8 lie", Scenario("l", reading=r, behaviours={"u3": Behaviour("quiet", 60)},
                                                       liars={"u1": 30.0, "u5": 30.0, "u6": 30.0}, expect_bad=("u3",))),
                     ("central watcher, u3 quiet", Scenario("c", reading=r, layout="central",
                                                            behaviours={"u3": Behaviour("quiet", 60)}, expect_bad=("u3",))),
                     ("stranger asks for a password", Scenario("p", reading=r, strangers=2, expect_bad=("s0",),
                                                               behaviours={"s0": Behaviour("toward-harm", 30, category="access")}))):
        res = run(sc)
        det = ", ".join(f"{k}: {v if v is not None else 'missed'}" for k, v in res.detected.items()) or "-"
        readings = sum(1 for f in res.lib_facts if f["decision"] == "reading") if hasattr(res, "lib_facts") else "-"
        out.append(f"| {name} | {det} | {len(res.false)} | {readings} |")
    return out


def main() -> int:
    labels = {json.loads(l)["id"]: json.loads(l) for l in (ROOT / "messages.jsonl").read_text().splitlines()}
    results = [json.loads(p.read_text()) for p in sorted(ROOT.glob("results-*.json"))]
    results.sort(key=lambda r: (r["reader"] != "rules", "first" not in r["reader"]))
    lines = ["# Phase 3 results: reading real text", "",
             f"Corpus: {len(labels)} labelled messages (`corpus/messages.jsonl`, built by `corpus/build_corpus.py`).",
             "Each reader read every message; `corpus/evaluate.py` compared what it found with the labels.", "",
             "## What each reader found", "",
             "Recall: of the messages that have it, how many were found. False positives: messages marked wrongly.", "",
             "| | " + " | ".join(r["reader"] for r in results) + " |",
             "|---|" + "---|" * len(results)]
    for k in ROWS:
        cells = []
        for r in results:
            m = r["metrics"][k]
            cells.append(f"recall {pct(m['recall'])}, false {m['fp']}")
        lines.append(f"| {k} | " + " | ".join(cells) + " |")
    lines.append("| seconds per message | " + " | ".join(str(r["seconds_per_message"]) for r in results) + " |")
    lines += ["", "`any-harm` false positives are the ones that matter most: each would make an enemy of an",
              "agent that did nothing wrong. `delivers` counts deliveries the sender's mission foresees; the",
              "rules see only the mission's exact words, a model also the meaning.", ""]
    sim_md = []
    for r in results:
        rr = rates(r, labels)
        sim_md += [f"### {r['reader']}", "", f"Error rates used: `{json.dumps(rr)}`", "",
                   "| Scenario | Detected (step) | False alarms | Readings for the human |", "|---|---|---|---|", *sim_rows(rr), ""]
    lines += ["## The simulator with these reading errors", "",
              "The same simulator as in the README, but every message is read with the mistakes the reader made",
              "on the corpus (missed deliveries, missed requests outside the mission, missed harm, missed",
              "concealment, and false harm or false concealment in healthy messages).", "", *sim_md]
    model_runs = [r for r in results if r["reader"] == "rules+phi4-mini"] or [r for r in results if r["reader"] != "rules"]
    if model_runs:
        cats = ("access", "take-out", "change-system", "keep-from-us", "bypass", "false-authority", "concealed")
        table = evidence.build_table(model_runs[0]["per_message"], labels, cats)
        (REPO / "triglav" / "core" / "evidence.json").write_text(json.dumps(table, indent=1), encoding="utf-8")
        lines += ["## Probabilities for the human (traces from the corpus)", "",
                  "How likely each category is when only the model found it (trace B) or both readers did (A),",
                  "with this installation's starting frequency of 1%. Recomputed as the human decides.", "",
                  "| category | trace A (rules + model) | trace B (model only) | trace C (rules only) |",
                  "|---|---|---|---|"]
        for c in cats:
            cells = [evidence.describe(evidence.probability(table, c, tr, evidence.START_PRIOR)).split(": ", 1)[1]
                     for tr in "ABC"]
            lines.append(f"| {c} | " + " | ".join(cells) + " |")
        lines.append("")
    text = "\n".join(lines) + "\n"
    (REPO / "RESULTS-PHASE3.md").write_text(text, encoding="utf-8")
    paper = REPO / "paper" / "triglav.md"
    p = paper.read_text(encoding="utf-8")
    table = text.split("## What each reader found", 1)[1].split("## The simulator", 1)[0].strip()
    simpart = text.split("## The simulator with these reading errors", 1)[1].strip()
    p = p.replace("READING_RESULTS", table).replace("READING_IN_SIM", simpart)
    paper.write_text(p, encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
