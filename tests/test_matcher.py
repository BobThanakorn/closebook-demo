"""Unit tests: the matcher must reproduce the golden labels on synthetic data."""
import filecmp
import json
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import gen_data  # noqa: E402
import matcher  # noqa: E402

DATA_FILES = ["settlement_lines.csv", "payouts.csv", "bank_statement.csv", "golden.json"]
TOL_THB = 1.00


class MatcherTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix="closebook-")
        gen_data.generate(cls.tmp)
        cls.results = {r["batch_id"]: r for r in matcher.match(cls.tmp)}
        with open(os.path.join(cls.tmp, "golden.json"), encoding="utf-8") as f:
            cls.golden = json.load(f)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_every_batch_has_a_result(self):
        self.assertEqual(set(self.results), set(self.golden))

    def test_every_label_equals_golden(self):
        for batch_id, gold in self.golden.items():
            with self.subTest(batch=batch_id):
                self.assertEqual(self.results[batch_id]["label"], gold["label"])

    def test_injected_anomaly_counts(self):
        labels = [g["label"] for g in self.golden.values()]
        for label in ("SHORT_PAYOUT", "DUPLICATE_FEE", "MISSING_DEPOSIT", "REFUND_NOT_NETTED"):
            self.assertEqual(labels.count(label), 2, label)
        self.assertEqual(sum("rounding" in g for g in self.golden.values()), 3)

    def test_rounding_cases_are_never_flagged(self):
        rounding = {b: g for b, g in self.golden.items() if "rounding" in g}
        self.assertEqual(len(rounding), 3)
        for batch_id, gold in rounding.items():
            with self.subTest(batch=batch_id):
                r = self.results[batch_id]
                self.assertLess(abs(gold["rounding"]), TOL_THB)
                self.assertNotEqual(gold["rounding"], 0)
                self.assertEqual(r["label"], "MATCHED")
                self.assertAlmostEqual(r["diff"], gold["rounding"], places=2)

    def test_short_and_duplicate_amounts_are_exact(self):
        for batch_id, gold in self.golden.items():
            if gold["label"] not in ("SHORT_PAYOUT", "DUPLICATE_FEE"):
                continue
            with self.subTest(batch=batch_id):
                detail = self.results[batch_id]["detail"]
                self.assertAlmostEqual(detail["amount"], gold["amount"], places=2)
                if gold["label"] == "DUPLICATE_FEE":
                    self.assertEqual(detail["orders"], gold["orders"])

    def test_no_anomaly_is_wrongly_cleared(self):
        for batch_id, gold in self.golden.items():
            if gold["label"] != "MATCHED":
                with self.subTest(batch=batch_id):
                    self.assertNotEqual(self.results[batch_id]["label"], "MATCHED")

    def test_exceptions_have_thai_text_and_actions(self):
        for r in self.results.values():
            if r["label"] != "MATCHED":
                with self.subTest(batch=r["batch_id"]):
                    self.assertTrue(r["explain_th"])
                    self.assertTrue(2 <= len(r["actions_th"]) <= 3)

    def test_same_seed_produces_identical_data(self):
        other = tempfile.mkdtemp(prefix="closebook-")
        try:
            gen_data.generate(other)
            match, mismatch, errors = filecmp.cmpfiles(self.tmp, other, DATA_FILES, shallow=False)
            self.assertEqual((mismatch, errors), ([], []))
        finally:
            shutil.rmtree(other, ignore_errors=True)

    def test_different_seed_produces_different_data(self):
        other = tempfile.mkdtemp(prefix="closebook-")
        try:
            gen_data.generate(other, seed=gen_data.SEED + 1)
            self.assertFalse(filecmp.cmp(os.path.join(self.tmp, "payouts.csv"),
                                         os.path.join(other, "payouts.csv"), shallow=False))
        finally:
            shutil.rmtree(other, ignore_errors=True)


class ClassifyRuleTest(unittest.TestCase):
    """Small hand-built cases for the rule order in matcher.classify."""

    LINES = [("A", "sale", 100_000), ("A", "commission", -6_000), ("A", "refund", -30_000)]
    EXPECTED = 64_000

    def test_within_tolerance_is_matched(self):
        self.assertEqual(matcher.classify(self.LINES, self.EXPECTED + 99, True)[0], "MATCHED")

    def test_just_over_tolerance_short_is_flagged(self):
        self.assertEqual(matcher.classify(self.LINES, self.EXPECTED - 101, True)[0], "SHORT_PAYOUT")

    def test_overpay_equal_to_refunds_is_refund_not_netted(self):
        self.assertEqual(matcher.classify(self.LINES, self.EXPECTED + 30_000, True)[0], "REFUND_NOT_NETTED")

    def test_other_overpay_is_unknown(self):
        self.assertEqual(matcher.classify(self.LINES, self.EXPECTED + 5_000, True)[0], "OVERPAID_UNKNOWN")

    def test_duplicate_fee_beats_amount_rules(self):
        lines = self.LINES + [("A", "commission", -6_000)]
        label, detail = matcher.classify(lines, self.EXPECTED - 6_000, False)
        self.assertEqual((label, detail), ("DUPLICATE_FEE", {"amount": 6_000, "orders": 1}))

    def test_missing_deposit_when_amount_ok(self):
        self.assertEqual(matcher.classify(self.LINES, self.EXPECTED, False)[0], "MISSING_DEPOSIT")


if __name__ == "__main__":
    unittest.main()
