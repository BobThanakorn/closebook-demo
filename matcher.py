"""Deterministic payout matcher for the Closebook demo.

match(data_dir) reads the CSVs written by gen_data.py and returns one result
per payout batch. Every number is computed here with integer satang
arithmetic. No LLM calculates or changes any number.
"""
import csv
import os
from datetime import date
from decimal import Decimal, ROUND_HALF_UP

TOL = 100                   # 1.00 THB tolerance, in satang
BANK_WINDOW_DAYS = 4        # credit may land 0-4 days after payout date
FEE_TYPES = ("commission", "payment_fee", "campaign_fee")
BANK_KEYWORDS = {"SHOPEE": "Shopee", "LAZADA": "Lazada", "TIKTOK": "TikTok Shop"}

LABEL_TH = {
    "MATCHED": "ตรงกัน",
    "DUPLICATE_FEE": "ค่าธรรมเนียมถูกหักซ้ำ",
    "SHORT_PAYOUT": "ยอดโอนขาด",
    "REFUND_NOT_NETTED": "ยังไม่หักเงินคืนลูกค้า",
    "OVERPAID_UNKNOWN": "ได้รับเงินเกินโดยไม่ทราบสาเหตุ",
    "MISSING_DEPOSIT": "ไม่พบเงินเข้าบัญชี",
}

ACTIONS_TH = {
    "MATCHED": [],
    "DUPLICATE_FEE": ["ยื่นเคลมค่าธรรมเนียมที่ซ้ำ", "บันทึกเป็นค่าธรรมเนียม", "ถามนักบัญชี"],
    "SHORT_PAYOUT": ["ยื่นเคลมยอดที่ขาด", "ถามนักบัญชี"],
    "REFUND_NOT_NETTED": ["กันเงินไว้รอแพลตฟอร์มหักคืน", "ถามนักบัญชี"],
    "OVERPAID_UNKNOWN": ["สอบถามแพลตฟอร์ม", "ถามนักบัญชี"],
    "MISSING_DEPOSIT": ["ติดตามยอดโอนกับแพลตฟอร์ม", "ตรวจบัญชีธนาคารอีกครั้ง", "ถามนักบัญชี"],
}

TH_MONTHS = ["ม.ค.", "ก.พ.", "มี.ค.", "เม.ย.", "พ.ค.", "มิ.ย.",
             "ก.ค.", "ส.ค.", "ก.ย.", "ต.ค.", "พ.ย.", "ธ.ค."]


def to_satang(text):
    return int((Decimal(text.strip()) * 100).to_integral_value(rounding=ROUND_HALF_UP))


def baht(satang):
    """Format satang as '1,234.56' using integer maths only."""
    sign = "-" if satang < 0 else ""
    satang = abs(satang)
    return f"{sign}{satang // 100:,}.{satang % 100:02d}"


def th_date(d):
    return f"{d.day} {TH_MONTHS[d.month - 1]}"


def _read(path):
    with open(path, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def load(data_dir):
    lines = {}
    for row in _read(os.path.join(data_dir, "settlement_lines.csv")):
        lines.setdefault(row["batch_id"], []).append(
            (row["order_id"], row["line_type"], to_satang(row["amount_thb"])))

    payouts = [{
        "batch_id": row["batch_id"],
        "market": row["market"],
        "payout_date": date.fromisoformat(row["payout_date"]),
        "amount": to_satang(row["amount_thb"]),
    } for row in _read(os.path.join(data_dir, "payouts.csv"))]

    credits = []
    for row in _read(os.path.join(data_dir, "bank_statement.csv")):
        amount = to_satang(row["amount_thb"])
        desc = row["description"].upper()
        market = next((m for k, m in BANK_KEYWORDS.items() if k in desc), None)
        if amount > 0 and market:
            credits.append({"date": date.fromisoformat(row["date"]), "market": market, "amount": amount})
    return lines, payouts, credits


def match_bank(payouts, credits):
    """Assign each payout at most one unused bank credit.

    Payouts are taken in payout-date order. A candidate credit has the same
    market, an amount within TOL and a date 0-4 days after the payout date.
    The earliest such credit wins, then the closest amount.
    """
    used, found = set(), {}
    for p in sorted(payouts, key=lambda p: (p["payout_date"], p["batch_id"])):
        candidates = [
            (c["date"], abs(c["amount"] - p["amount"]), i)
            for i, c in enumerate(credits)
            if i not in used
            and c["market"] == p["market"]
            and abs(c["amount"] - p["amount"]) <= TOL
            and 0 <= (c["date"] - p["payout_date"]).days <= BANK_WINDOW_DAYS
        ]
        if candidates:
            bank_date, _, i = min(candidates)
            used.add(i)
            found[p["batch_id"]] = bank_date
    return found


def classify(lines, payout, has_deposit):
    """Apply the spec rules in order. Returns (label, detail) in satang."""
    expected = sum(a for _, _, a in lines)
    diff = payout - expected
    refunds = -sum(a for _, t, a in lines if t == "refund")

    seen, extra, dup_orders = set(), 0, set()
    for order_id, line_type, amount in lines:
        if line_type not in FEE_TYPES:
            continue
        key = (order_id, line_type)
        if key in seen:
            extra += -amount
            dup_orders.add(order_id)
        seen.add(key)

    if dup_orders:
        return "DUPLICATE_FEE", {"amount": extra, "orders": len(dup_orders)}
    if diff < -TOL:
        return "SHORT_PAYOUT", {"amount": -diff}
    if diff > TOL:
        if abs(diff - refunds) <= TOL:
            return "REFUND_NOT_NETTED", {"amount": diff, "refunds": refunds}
        return "OVERPAID_UNKNOWN", {"amount": diff}
    if not has_deposit:
        return "MISSING_DEPOSIT", {"amount": payout}
    detail = {"amount": 0}
    if diff:
        detail["rounding"] = diff
    return "MATCHED", detail


def explain_th(label, r, d):
    """Thai explanation from a fixed template, filled with computed amounts."""
    m, b, pd = r["market"], r["batch_id"], th_date(r["payout_date"])
    pay, exp_ = baht(r["payout"]), baht(r["expected"])
    amt = baht(d.get("amount", 0))
    if label == "DUPLICATE_FEE":
        return (f"{m} รอบ {b} หักค่าแคมเปญซ้ำ {d['orders']} คำสั่งซื้อ รวม {amt} บาท "
                f"ยอดโอน {pay} บาท ตรงกับรายการ แต่รายการมีค่าธรรมเนียมเดียวกันสองครั้ง")
    if label == "SHORT_PAYOUT":
        return (f"{m} โอนรอบ {b} มา {pay} บาท แต่ตามรายการชำระเงินควรได้ {exp_} บาท "
                f"ขาดไป {amt} บาท")
    if label == "REFUND_NOT_NETTED":
        return (f"{m} โอนรอบ {b} มา {pay} บาท มากกว่าที่ควรได้ {amt} บาท "
                f"ซึ่งเท่ากับยอดคืนเงินลูกค้าในรอบนี้ แพลตฟอร์มอาจหักคืนในรอบถัดไป")
    if label == "OVERPAID_UNKNOWN":
        return (f"{m} โอนรอบ {b} มา {pay} บาท มากกว่าที่ควรได้ {amt} บาท "
                f"และไม่ตรงกับยอดคืนเงิน ต้องตรวจสอบสาเหตุ")
    if label == "MISSING_DEPOSIT":
        return (f"{m} แจ้งโอนรอบ {b} จำนวน {pay} บาท วันที่ {pd} "
                f"แต่ยังไม่พบเงินเข้าบัญชีธนาคารภายใน {BANK_WINDOW_DAYS} วัน")
    if "rounding" in d:
        return (f"ยอดโอน {pay} บาท ต่างจากรายการ {baht(d['rounding'])} บาท "
                f"อยู่ในเกณฑ์ปัดเศษ และพบเงินเข้าบัญชีแล้ว")
    return f"ยอดโอน {pay} บาท ตรงกับรายการ และพบเงินเข้าบัญชีแล้ว"


def rewrite_explanation(result):
    """LLM HOOK: not used in this demo.

    A later version may let an LLM rephrase `explain_th` in friendlier Thai.
    The LLM would only reword text. Every number must come from this module,
    and a check would reject any rewrite whose numbers differ from the
    template's numbers. Today this returns the template unchanged.
    """
    return result["explain_th"]


def _thb(satang):
    return round(satang / 100, 2)


def match(data_dir):
    """Return one result dict per payout batch, ordered by payout date."""
    lines, payouts, credits = load(data_dir)
    deposits = match_bank(payouts, credits)

    results = []
    for p in sorted(payouts, key=lambda p: (p["payout_date"], p["batch_id"])):
        batch_lines = lines.get(p["batch_id"], [])
        label, detail = classify(batch_lines, p["amount"], p["batch_id"] in deposits)
        expected = sum(a for _, _, a in batch_lines)
        raw = {**p, "payout": p["amount"], "expected": expected}
        result = {
            "batch_id": p["batch_id"],
            "market": p["market"],
            "payout_date": p["payout_date"].isoformat(),
            "payout": _thb(p["amount"]),
            "expected": _thb(expected),
            "diff": _thb(p["amount"] - expected),
            "orders": len({o for o, _, _ in batch_lines}),
            "label": label,
            "label_th": LABEL_TH[label],
            "detail": {k: (v if k == "orders" else _thb(v)) for k, v in detail.items()},
            "bank_date": deposits[p["batch_id"]].isoformat() if p["batch_id"] in deposits else None,
            "explain_th": explain_th(label, raw, detail),
            "actions_th": ACTIONS_TH[label],
        }
        result["explain_th"] = rewrite_explanation(result)
        results.append(result)
    return results


if __name__ == "__main__":
    import sys
    here = os.path.dirname(os.path.abspath(__file__))
    for r in match(sys.argv[1] if len(sys.argv) > 1 else os.path.join(here, "data")):
        print(f"{r['batch_id']:<10} {r['market']:<12} {r['payout']:>10.2f} {r['diff']:>9.2f}  {r['label']}")
