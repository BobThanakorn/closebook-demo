# Closebook demo

Closebook is an AI agent idea that closes the month for Thai online sellers on
Shopee, Lazada and TikTok Shop. This repo is a small, runnable demo of one
loop, on **synthetic data**:

1. Match each marketplace payout to its settlement lines and to a bank deposit.
2. Flag only the exceptions.
3. Show each exception to the owner as a one-tap approval card in Thai.

> Synthetic data. Fee rates are illustrative. Matching is deterministic code;
> no LLM calculates any number.

**Try it:** [live demo](https://bobthanakorn.github.io/closebook-demo/demo.html)
(opens in the browser, nothing to install; best viewed on a phone-width screen too).
Landing page for the prototype: [closebook-site](https://github.com/BobThanakorn/closebook-site).

## What it shows

Running the demo generates one imaginary seller's October 2026 orders
(160 orders: Shopee 70, Lazada 45, TikTok Shop 45), injects known anomalies,
matches every payout batch, scores the result against a golden answer key and
builds `demo.html`.

Latest run (see `output/run_log.txt`):

| Measure | Result |
|---|---|
| Payout batches checked | 33 |
| Correct labels | 33 (100%) |
| Injected anomalies caught | 8 / 8 |
| Wrongly cleared (anomaly labelled MATCHED) | 0 |
| False alarms | 0 |
| Matched with no human input | 25 |
| Rounding cases (< 1 THB) left unflagged | 3 / 3 |
| Short-payout and duplicate-fee amounts exact | yes |

**These numbers test the matching logic on synthetic data that the same repo
generated. They are not accuracy on real sellers and not customer results.**

`demo.html` opens from disk and is written Thai-first (the title, banner and
footer sentence stay in English). It shows:

- the honesty banner and a progress panel ("8 items need you", with a bar for
  auto-matched / handed to the accountant / waiting on you);
- six summary tiles, including anomalies caught and wrongly cleared (target 0);
- a "Needs the owner" feed of LINE-style cards. Each card shows paid vs
  expected vs the finding, a Thai explanation and 2 to 3 action buttons.
  Tapping one replaces the buttons with "done, awaiting accountant approval"
  and lowers the open count; "เลิกทำ" (undo) brings the buttons back;
- a table of every batch with filters (all / needs checking, by marketplace).
  Tapping a batch ID jumps to its card. On a phone the table becomes stacked cards.

Layout was checked with headless Edge at 320 to 1280 px wide (no horizontal
scroll, tap targets at least 44 px). It has not been tested on a physical phone.
The buttons only change the page; nothing is sent to an accountant.

## How to run

Python 3.9 or newer, standard library only. No installs.

```sh
python3 run_demo.py                          # generate -> match -> score -> build
python3 -m unittest discover -s tests -v     # unit tests
```

On Windows use `py` (or `python`) instead of `python3`.

`run_demo.py` exits with code 0 only if no anomaly is wrongly cleared and
accuracy is at least 95%; otherwise it exits 1. It writes:

- `data/` - `settlement_lines.csv`, `payouts.csv`, `bank_statement.csv`, `golden.json`
- `output/results.json` - every batch result plus the score
- `output/run_log.txt` - the printed report with a timestamp
- `demo.html` - the self-contained demo page

## How it works

| File | Role |
|---|---|
| `gen_data.py` | Seeded generator (seed 2026). Same seed gives byte-identical files. |
| `matcher.py` | `match(data_dir)`: deterministic rules, integer satang maths. |
| `run_demo.py` | Runs the pipeline, scores against `golden.json`, sets the exit code. |
| `build_demo.py` | `build(results, score, out_path)`: writes `demo.html`. |
| `tests/test_matcher.py` | Golden-label, rounding, exact-amount, no-false-clear and seed tests. |

**Data.** Money is integer satang inside the code; CSVs show THB with two
decimals. Each order has a sale line and negative fee lines (commission,
payment fee, a 29.90 THB campaign fee on about 25% of orders, 7% VAT on fees)
and about 4% have a 30% partial refund. Fee rates (Shopee 6% + 3%,
Lazada 5% + 2.5%, TikTok Shop 4% + 2%) are **illustrative, not real platform
rates**. Payouts are grouped into 3-day settle windows per marketplace and paid
two days after the window ends; bank credits land 0 to 2 days later, mixed with
10 unrelated debits.

**Injected anomalies** (each on a different batch with at least 3 orders):
2 short payouts, 2 duplicate campaign fees, 2 missing bank deposits, 2 refunds
not netted, and 3 sub-1-THB rounding differences that must stay MATCHED.

**Matcher rules**, per batch, in order (tolerance 1.00 THB):

1. Same fee type charged twice on one order -> `DUPLICATE_FEE`
2. Payout more than 1 THB below expected -> `SHORT_PAYOUT`
3. Payout more than 1 THB above expected -> `REFUND_NOT_NETTED` if the gap equals the batch's refunds, else `OVERPAID_UNKNOWN`
4. No matching bank credit -> `MISSING_DEPOSIT`
5. Otherwise -> `MATCHED`

Bank matching uses each credit once: same marketplace, amount within 1 THB,
dated 0 to 4 days after the payout date, earliest first, then closest amount.

Thai explanations and suggested actions come from fixed templates filled with
the computed amounts. `matcher.rewrite_explanation()` is a marked hook where a
later version could let an LLM reword the Thai text; it would not be allowed
to change any number.

**A note on batch count.** The brief expected about 27 to 30 batches. Orders
placed 1-31 October settle 3-5 days later, so settle dates span 33 days, which
is 11 three-day windows for each of 3 marketplaces: 33 batches. The demo keeps
the brief's rules rather than forcing the count.

## What it does not do

- No real marketplace, bank, LINE or accounting connection. Nothing calls a network.
- No real seller data. Every number is generated.
- No auth, database or deployment.
- No ledger posting (FlowAccount, PEAK) and no PP.30 VAT pack.
- The card buttons only change the page; nothing is sent to an accountant.
- The golden set checks the rules against anomalies the generator itself
  injected. Real payout files will have formats and failure modes this demo
  does not cover.

## Planned next steps

1. **Marketplace APIs.** Read settlement and payout data from Shopee, Lazada
   and TikTok Shop seller APIs instead of synthetic CSVs.
2. **LINE Official Account.** Send exception cards to the owner in LINE, using
   reply messages when the owner messages the account.
3. **Ledger export.** Export approved entries in a format accounting software
   such as FlowAccount or PEAK can import.
4. **PP.30 working paper.** Prepare a VAT working paper (output VAT on sales,
   input VAT on platform fees) for the accountant to review before filing.
