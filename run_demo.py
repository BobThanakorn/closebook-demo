"""Run the Closebook demo: generate -> match -> score -> report.

Exit code 0 only if no anomaly is wrongly cleared and accuracy >= 0.95.
Scores come from a golden set on synthetic data. They test the matching
logic, not accuracy on real sellers.
"""
import json
import os
import platform
import sys
from datetime import datetime, timezone

import gen_data
import matcher

ROOT = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(ROOT, "data")
OUT_DIR = os.path.join(ROOT, "output")
MIN_ACCURACY = 0.95
AMOUNT_TOL_THB = 1.00


def score(results, golden):
    by_batch = {r["batch_id"]: r for r in results}
    anomalies = [b for b, g in golden.items() if g["label"] != "MATCHED"]
    correct = sum(by_batch[b]["label"] == g["label"] for b, g in golden.items())

    amount_checks = []
    for batch_id, gold in sorted(golden.items()):
        if gold["label"] not in ("SHORT_PAYOUT", "DUPLICATE_FEE"):
            continue
        detail = by_batch[batch_id]["detail"]
        ok = abs(detail.get("amount", 0) - gold["amount"]) <= AMOUNT_TOL_THB
        if gold["label"] == "DUPLICATE_FEE":
            ok = ok and detail.get("orders") == gold["orders"]
        amount_checks.append({"batch_id": batch_id, "label": gold["label"],
                              "golden": gold["amount"], "found": detail.get("amount"), "exact": ok})

    s = {
        "batches": len(golden),
        "correct": correct,
        "accuracy": round(correct / len(golden), 4),
        "injected_anomalies": len(anomalies),
        "caught": sum(by_batch[b]["label"] == golden[b]["label"] for b in anomalies),
        "false_clears": sum(by_batch[b]["label"] == "MATCHED" for b in anomalies),
        "false_alarms": sum(by_batch[b]["label"] != "MATCHED"
                            for b, g in golden.items() if g["label"] == "MATCHED"),
        "auto_matched": sum(r["label"] == "MATCHED" for r in results),
        "rounding_cases_cleared": sum(by_batch[b]["label"] == "MATCHED"
                                      for b, g in golden.items() if "rounding" in g),
        "amounts_exact": all(c["exact"] for c in amount_checks),
        "amount_checks": amount_checks,
    }
    s["passed"] = s["false_clears"] == 0 and s["accuracy"] >= MIN_ACCURACY
    return s


def report(s, summary):
    caught_line = f"{s['caught']}/{s['injected_anomalies']}"
    rows = [
        ("Data", f"{summary['orders']} synthetic orders, seed {gen_data.SEED}"),
        ("Batches checked", s["batches"]),
        ("Correct labels", s["correct"]),
        ("Accuracy", f"{s['accuracy']:.2%}"),
        ("Injected anomalies", s["injected_anomalies"]),
        ("Caught", caught_line),
        ("False clears (target 0)", s["false_clears"]),
        ("False alarms", s["false_alarms"]),
        ("Auto-matched", s["auto_matched"]),
        ("Rounding cases cleared", f"{s['rounding_cases_cleared']}/3"),
        ("Amounts exact (+-1 THB)", "yes" if s["amounts_exact"] else "NO"),
    ]
    lines = ["Closebook demo - scoring against golden set (synthetic data)", "-" * 60]
    lines += [f"{k:<26} {v}" for k, v in rows]
    for c in s["amount_checks"]:
        lines.append(f"  {c['label']:<14} {c['batch_id']:<10} golden {c['golden']:>9.2f}  "
                     f"found {c['found']:>9.2f}  {'ok' if c['exact'] else 'MISMATCH'}")
    lines.append("-" * 60)
    lines.append("PASS" if s["passed"] else
                 f"FAIL (need false clears = 0 and accuracy >= {MIN_ACCURACY:.0%})")
    lines.append("Scored on synthetic data: tests the logic, not real-world accuracy.")
    return "\n".join(lines)


def main():
    summary = gen_data.generate(DATA_DIR)
    results = matcher.match(DATA_DIR)
    with open(os.path.join(DATA_DIR, "golden.json"), encoding="utf-8") as f:
        golden = json.load(f)
    s = score(results, golden)

    os.makedirs(OUT_DIR, exist_ok=True)
    with open(os.path.join(OUT_DIR, "results.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump({"score": s, "results": results}, f, ensure_ascii=False, indent=2)
        f.write("\n")

    text = report(s, summary)
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    with open(os.path.join(OUT_DIR, "run_log.txt"), "w", encoding="utf-8", newline="\n") as f:
        f.write(f"Run at {stamp} with Python {platform.python_version()}\n{text}\n")
    print(text)
    return 0 if s["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
