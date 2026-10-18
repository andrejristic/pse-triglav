"""How likely a reading is: probabilities for the human (decided 19 Oct 2026).

The model reads; SHARED_LIB computes; the human decides.

For each category (a step toward harm of one kind, or concealment) the TRACE is
which readers found it in a message:

    A  rules and model      B  model only      C  rules only      D  neither

The labelled corpus says how often each trace appears when the problem is
there (k of N messages) and when it is not (j of M). Counts start at 1
(Laplace), so a small sample never gives 0% or 100%:

    P(trace | problem)    = (k + 1) / (N + 4)
    P(trace | no problem) = (j + 1) / (M + 4)

Bayes' rule turns these into the probability of the problem given the trace,
with THIS installation's own frequency of the problem (the prior): 1% at the
start, then learned from the human's decisions -- (confirmed + 1) / (decided + 100):

    P(problem | trace) = P(t|p) * prior / (P(t|p) * prior + P(t|no p) * (1 - prior))

The range comes from 95% Wilson intervals of the two counts; `cases` is how
many corpus messages had this trace. Pure functions: the same counts always
give the same numbers, so anyone can recompute them.
"""
from __future__ import annotations

import json
import math
from importlib import resources

TRACES = ("A", "B", "C", "D")
START_PRIOR = 0.01
PRIOR_WEIGHT = 100        # the start prior counts as 100 decisions, 1 of them a problem


def trace(rules: bool, model: bool) -> str:
    return "A" if rules and model else "B" if model else "C" if rules else "D"


def prior(confirmed: int = 0, decided: int = 0) -> float:
    return (confirmed + START_PRIOR * PRIOR_WEIGHT) / (decided + PRIOR_WEIGHT)


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return 0.0, 1.0
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return max(0.0, c - h), min(1.0, c + h)


def posterior(l_pos: float, l_neg: float, pi: float) -> float:
    num = l_pos * pi
    den = num + l_neg * (1 - pi)
    return num / den if den > 0 else 0.0


def probability(table: dict | None, category: str, tr: str, pi: float) -> dict | None:
    """The probability that `category` is really there, given trace `tr`.
    None when the corpus has not been measured for it."""
    if not table or category not in table:
        return None
    pos, neg = table[category]["pos"], table[category]["neg"]
    k, n = pos.get(tr, 0), pos["n"]
    j, m = neg.get(tr, 0), neg["n"]
    l_pos, l_neg = (k + 1) / (n + 4), (j + 1) / (m + 4)
    pos_lo, pos_hi = wilson(k, n)
    neg_lo, neg_hi = wilson(j, m)
    eps = 1e-6
    return {"category": category, "trace": tr, "p": round(posterior(l_pos, l_neg, pi), 4),
            "low": round(posterior(max(pos_lo, eps), max(neg_hi, eps), pi), 4),
            "high": round(posterior(max(pos_hi, eps), max(neg_lo, eps), pi), 4),
            "cases": k + j, "prior": round(pi, 4)}


def build_table(per_message: list[dict], labels: dict, categories) -> dict:
    """Counts of each trace, when the problem is there and when it is not, from a
    model run on the corpus (per message: what the rules found, what the model found)."""
    table = {}
    for c in categories:
        pos = {"n": 0, **{t: 0 for t in TRACES}}
        neg = {"n": 0, **{t: 0 for t in TRACES}}
        for p in per_message:
            row = labels[p["id"]]
            truth = row["concealed"] if c == "concealed" else c in row["harm"]
            t = trace(c in p.get("rules", []), c in p.get("model", []))
            side = pos if truth else neg
            side["n"] += 1
            side[t] += 1
        table[c] = {"pos": pos, "neg": neg}
    return table


def load_table() -> dict | None:
    try:
        return json.loads(resources.files("triglav.core").joinpath("evidence.json").read_text("utf-8"))
    except (FileNotFoundError, OSError, ValueError):
        return None


def describe(pr: dict) -> str:
    return (f"{pr['category']}: {100 * pr['p']:.0f}% ({100 * pr['low']:.0f}-{100 * pr['high']:.0f}%), "
            f"{pr['cases']} cases, trace {pr['trace']}")
