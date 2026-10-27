"""Generate deterministic synthetic marketplace data for the Closebook demo.

Everything written here is synthetic: one imaginary seller, orders placed in
October 2026. Fee rates are ILLUSTRATIVE ONLY and are not real Shopee, Lazada
or TikTok Shop rates.

Money is integer satang internally (1 THB = 100 satang). CSVs show THB with
2 decimals.

Usage: python gen_data.py [out_dir]
"""
import csv
import json
import os
import random
import sys
from datetime import date, timedelta

SEED = 2026

# Illustrative fee rates in basis points (600 bp = 6%). Not real platform rates.
MARKETS = [
    {"market": "Shopee", "prefix": "SHP", "orders": 70,
     "commission_bp": 600, "payment_bp": 300, "bank": "SHOPEE PAYOUT"},
    {"market": "Lazada", "prefix": "LZD", "orders": 45,
     "commission_bp": 500, "payment_bp": 250, "bank": "LAZADA PAYOUT"},
    {"market": "TikTok Shop", "prefix": "TTS", "orders": 45,
     "commission_bp": 400, "payment_bp": 200, "bank": "TIKTOK SHOP PAYOUT"},
]

MONTH_START = date(2026, 10, 1)
MONTH_DAYS = 31
SETTLE_LAG = (3, 5)          # days from order to settlement
FIRST_SETTLE = MONTH_START + timedelta(days=SETTLE_LAG[0])
WINDOW_DAYS = 3              # one payout batch per 3-day settle window
PAYOUT_LAG = 2               # payout date = window end + 2 days
BANK_LAG = (0, 2)            # bank credit lands 0-2 days after payout date

GROSS_THB = (150, 3000)
CAMPAIGN_FEE = 2990          # 29.90 THB
CAMPAIGN_SHARE = 0.25
REFUND_SHARE = 0.04
REFUND_BP = 3000             # partial refund = 30% of gross
FEE_VAT_BP = 700             # 7% VAT on all fees

# Injected anomalies, in the order they are assigned to shuffled batches.
ANOMALY_PLAN = (
    ["SHORT_PAYOUT"] * 2
    + ["DUPLICATE_FEE"] * 2
    + ["MISSING_DEPOSIT"] * 2
    + ["REFUND_NOT_NETTED"] * 2
    + ["ROUNDING"] * 3
)
MIN_ORDERS = 3
SHORT_RANGE = (300_00, 1500_00)

NOISE_DEBITS = [
    ("SUPPLIER PAYMENT - PACKAGING", 4_250_00),
    ("SUPPLIER PAYMENT - STOCK", 38_900_00),
    ("SALARY - PACKING STAFF", 15_000_00),
    ("SALARY - ADMIN", 12_000_00),
    ("ONLINE ADS TOP-UP", 5_000_00),
    ("ONLINE ADS TOP-UP", 3_500_00),
    ("SHOP RENT - NOV", 9_000_00),
    ("COURIER PICKUP FEE", 1_240_00),
    ("ELECTRICITY BILL", 2_317_45),
    ("INTERNET BILL", 799_00),
]


def pct(amount, bp):
    """Round-half-up percentage of a positive satang amount."""
    return (amount * bp + 5000) // 10000


def thb(satang):
    """Format integer satang as a THB string with 2 decimals, no float maths."""
    sign = "-" if satang < 0 else ""
    satang = abs(satang)
    return f"{sign}{satang // 100}.{satang % 100:02d}"


def _fee_vat(lines):
    fees = -sum(a for t, a in lines if t in ("commission", "payment_fee", "campaign_fee"))
    return -pct(fees, FEE_VAT_BP)


def _set_fee_vat(order):
    """Recompute the order's fee_vat line after its base fees change."""
    base = [(t, a) for t, a in order["lines"] if t != "fee_vat"]
    vat = _fee_vat(base)
    order["lines"] = [(t, vat if t == "fee_vat" else a) for t, a in order["lines"]]


def _make_orders(rng):
    orders, batches = [], {}
    for m in MARKETS:
        drafts = []
        for _ in range(m["orders"]):
            order_date = MONTH_START + timedelta(days=rng.randrange(MONTH_DAYS))
            settle_date = order_date + timedelta(days=rng.randint(*SETTLE_LAG))
            gross = rng.randint(*GROSS_THB) * 100
            has_campaign = rng.random() < CAMPAIGN_SHARE
            has_refund = rng.random() < REFUND_SHARE
            drafts.append((order_date, settle_date, gross, has_campaign, has_refund))
        drafts.sort(key=lambda d: (d[0], d[1], d[2]))

        for n, (order_date, settle_date, gross, has_campaign, has_refund) in enumerate(drafts, 1):
            window = (settle_date - FIRST_SETTLE).days // WINDOW_DAYS
            window_start = FIRST_SETTLE + timedelta(days=window * WINDOW_DAYS)
            batch_id = f"{m['prefix']}-{window_start:%m%d}"
            lines = [
                ("sale", gross),
                ("commission", -pct(gross, m["commission_bp"])),
                ("payment_fee", -pct(gross, m["payment_bp"])),
            ]
            if has_campaign:
                lines.append(("campaign_fee", -CAMPAIGN_FEE))
            lines.append(("fee_vat", _fee_vat(lines)))
            if has_refund:
                lines.append(("refund", -pct(gross, REFUND_BP)))

            order = {
                "order_id": f"{m['prefix']}{order_date:%y%m%d}-{n:03d}",
                "market": m["market"],
                "batch_id": batch_id,
                "settle_date": settle_date,
                "lines": lines,
            }
            orders.append(order)
            batch = batches.setdefault(batch_id, {
                "batch_id": batch_id,
                "market": m["market"],
                "bank": m["bank"],
                "payout_date": window_start + timedelta(days=WINDOW_DAYS - 1 + PAYOUT_LAG),
                "orders": [],
            })
            batch["orders"].append(order)
    return orders, batches


def _expected(batch):
    return sum(a for o in batch["orders"] for _, a in o["lines"])


def _refunds(batch):
    return -sum(a for o in batch["orders"] for t, a in o["lines"] if t == "refund")


def _assign_anomalies(rng, batches):
    """Pick distinct batches (>= MIN_ORDERS orders) for each injected anomaly."""
    pool = sorted(b for b in batches if len(batches[b]["orders"]) >= MIN_ORDERS)
    rng.shuffle(pool)
    assigned = {}
    for label in ANOMALY_PLAN:
        for batch_id in pool:
            if batch_id in assigned:
                continue
            # A short payout must leave a positive payout behind.
            if label == "SHORT_PAYOUT" and _expected(batches[batch_id]) < 2 * SHORT_RANGE[1]:
                continue
            assigned[batch_id] = label
            break
        else:
            raise RuntimeError(f"no eligible batch left for {label}")
    return assigned


def _inject(rng, batch, label):
    """Mutate the batch for its anomaly; return (payout, golden entry, has_deposit)."""
    golden = {"label": "MATCHED" if label == "ROUNDING" else label}

    if label == "DUPLICATE_FEE":
        k = rng.randint(3, min(6, len(batch["orders"])))
        for order in rng.sample(batch["orders"], k):
            if not any(t == "campaign_fee" for t, _ in order["lines"]):
                # Give the order its normal campaign fee first, VAT included.
                order["lines"].insert(3, ("campaign_fee", -CAMPAIGN_FEE))
                _set_fee_vat(order)
            # Then charge the same campaign fee line a second time.
            order["lines"].insert(4, ("campaign_fee", -CAMPAIGN_FEE))
        golden.update(amount=k * CAMPAIGN_FEE, orders=k)
        return _expected(batch), golden, True  # payout reflects both lines

    if label == "REFUND_NOT_NETTED":
        if _refunds(batch) == 0:
            order = rng.choice(batch["orders"])
            gross = order["lines"][0][1]
            order["lines"].append(("refund", -pct(gross, REFUND_BP)))
        refunds = _refunds(batch)
        golden.update(amount=refunds)
        return _expected(batch) + refunds, golden, True

    expected = _expected(batch)
    if label == "SHORT_PAYOUT":
        short = rng.randint(*SHORT_RANGE)
        golden.update(amount=short)
        return expected - short, golden, True
    if label == "MISSING_DEPOSIT":
        golden.update(amount=expected)
        return expected, golden, False
    if label == "ROUNDING":
        delta = rng.choice([-1, 1]) * rng.randint(1, 99)
        golden.update(rounding=delta)
        return expected + delta, golden, True
    return expected, golden, True


def generate(out_dir, seed=SEED):
    """Write the four data files to out_dir and return a short summary."""
    rng = random.Random(seed)
    orders, batches = _make_orders(rng)
    anomalies = _assign_anomalies(rng, batches)

    golden, payouts, bank = {}, [], []
    for batch_id in sorted(batches, key=lambda b: (batches[b]["payout_date"], b)):
        batch = batches[batch_id]
        payout, entry, has_deposit = _inject(rng, batch, anomalies.get(batch_id, "MATCHED"))
        golden[batch_id] = entry
        payouts.append((batch_id, batch["market"], batch["payout_date"], payout))
        if has_deposit:
            bank_date = batch["payout_date"] + timedelta(days=rng.randint(*BANK_LAG))
            ref = rng.randint(100000, 999999)
            bank.append((bank_date, f"TRF FROM {batch['bank']} REF{ref}", payout))

    for desc, amount in NOISE_DEBITS:
        when = MONTH_START + timedelta(days=rng.randint(4, 40))
        bank.append((when, desc, -amount))
    bank.sort(key=lambda r: (r[0], r[1]))

    os.makedirs(out_dir, exist_ok=True)
    _write_csv(os.path.join(out_dir, "settlement_lines.csv"),
               ["batch_id", "market", "order_id", "settle_date", "line_type", "amount_thb"],
               [(o["batch_id"], o["market"], o["order_id"], o["settle_date"].isoformat(), t, thb(a))
                for o in sorted(orders, key=lambda o: (o["batch_id"], o["settle_date"], o["order_id"]))
                for t, a in o["lines"]])
    _write_csv(os.path.join(out_dir, "payouts.csv"),
               ["batch_id", "market", "payout_date", "amount_thb"],
               [(b, m, d.isoformat(), thb(a)) for b, m, d, a in payouts])
    _write_csv(os.path.join(out_dir, "bank_statement.csv"),
               ["date", "description", "amount_thb"],
               [(d.isoformat(), desc, thb(a)) for d, desc, a in bank])

    golden_thb = {}
    for batch_id, entry in sorted(golden.items()):
        out = {"label": entry["label"]}
        if "amount" in entry:
            out["amount"] = entry["amount"] / 100
        if "orders" in entry:
            out["orders"] = entry["orders"]
        if "rounding" in entry:
            out["rounding"] = entry["rounding"] / 100
        golden_thb[batch_id] = out
    with open(os.path.join(out_dir, "golden.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(golden_thb, f, indent=2, sort_keys=True)
        f.write("\n")

    return {
        "orders": len(orders),
        "batches": len(batches),
        "settlement_lines": sum(len(o["lines"]) for o in orders),
        "bank_rows": len(bank),
        "anomalies": {b: anomalies[b] for b in sorted(anomalies)},
    }


def _write_csv(path, header, rows):
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f, lineterminator="\n")
        writer.writerow(header)
        writer.writerows(rows)


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
    summary = generate(target)
    print(f"Wrote {target}: {summary['orders']} orders, {summary['batches']} batches, "
          f"{summary['settlement_lines']} settlement lines, {summary['bank_rows']} bank rows")
    for batch_id, label in summary["anomalies"].items():
        print(f"  injected {label:<18} {batch_id}")
