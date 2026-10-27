"""Build the self-contained demo.html from matcher results and the score.

build(results, score, out_path) writes one HTML file with the data embedded
as JSON. It works from file:// and the only external resource is the Google
Fonts stylesheet. All totals are computed here in integer satang; the page's
JavaScript only formats and displays them.
"""
import json

LABEL_EN = {
    "MATCHED": "Matched",
    "DUPLICATE_FEE": "Duplicate fee",
    "SHORT_PAYOUT": "Short payout",
    "REFUND_NOT_NETTED": "Refund not netted",
    "OVERPAID_UNKNOWN": "Overpaid, unknown",
    "MISSING_DEPOSIT": "Missing deposit",
}


def _satang(thb):
    return int(round(thb * 100))


def view_model(results, score):
    exceptions = [r for r in results if r["label"] != "MATCHED"]
    at_stake = sum(_satang(r["detail"].get("amount", 0)) for r in exceptions)
    return {
        "stats": {
            "batches": score["batches"],
            "auto_matched": score["auto_matched"],
            "open": len(exceptions),
            "at_stake": at_stake / 100,
            "caught": score["caught"],
            "injected": score["injected_anomalies"],
            "false_clears": score["false_clears"],
            "accuracy": score["accuracy"],
        },
        "labels_en": LABEL_EN,
        "results": results,
    }


def build(results, score, out_path):
    data = json.dumps(view_model(results, score), ensure_ascii=False, separators=(",", ":"))
    data = data.replace("</", "<\\/")  # keep the JSON from closing the script tag
    html = TEMPLATE.replace("__DATA__", data)
    with open(out_path, "w", encoding="utf-8", newline="\n") as f:
        f.write(html)
    return out_path


TEMPLATE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Closebook demo</title>
<link rel="icon" href="data:,">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans+Thai:wght@400;600;700&display=swap">
<style>
:root{
  --cream:#F7F5F0; --ink:#13262B; --rust:#B5441C; --teal:#2F7D8C;
  --paper:#FFFFFF; --muted:#55666A; --line:#E2DDD2; --chat:#ECE8DF;
  --rust-soft:#F7E4DB; --teal-soft:#DDEDF0;
  --font:"IBM Plex Sans Thai","Noto Sans Thai","Sarabun",system-ui,sans-serif;
}
*{box-sizing:border-box}
html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--cream);color:var(--ink);font-family:var(--font);font-size:15px;line-height:1.55}
.wrap{max-width:1100px;margin:0 auto;padding:0 16px}
.num{font-variant-numeric:tabular-nums}
h1,h2{margin:0;line-height:1.25}

/* header */
.top{padding:24px 0 16px}
.head{display:flex;gap:14px;align-items:center}
.head svg{flex:none}
h1{font-size:clamp(19px,4.6vw,26px);font-weight:700}
h1 .sub{font-weight:400;color:var(--muted)}
.meta{margin:2px 0 0;color:var(--muted);font-size:13px}

/* honesty banner */
.banner{margin:4px 0 22px;padding:12px 14px;border:1px solid var(--rust);border-left-width:5px;
  background:var(--rust-soft);border-radius:10px;font-weight:600;font-size:14px}

/* stat tiles */
.tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px;margin-bottom:30px}
.tile{background:var(--paper);border:1px solid var(--line);border-radius:14px;padding:12px 14px}
.tile .k{font-size:12.5px;color:var(--muted);line-height:1.35}
.tile .v{font-size:26px;font-weight:700;margin-top:4px;font-variant-numeric:tabular-nums}
.tile .v small{font-size:14px;font-weight:600;color:var(--muted)}
.tile.alert .v{color:var(--rust)}
.tile.good .v{color:var(--teal)}
.tile .note{font-size:12px;color:var(--muted)}

section{margin-bottom:34px}
.sec-head{display:flex;flex-wrap:wrap;align-items:baseline;gap:4px 12px;margin-bottom:12px}
h2{font-size:20px;font-weight:700}
.sec-head p{margin:0;color:var(--muted);font-size:13.5px}

/* LINE-style chat feed */
.feed{background:var(--chat);border-radius:18px;padding:16px;
  display:grid;grid-template-columns:repeat(auto-fill,minmax(min(100%,310px),1fr));gap:18px 16px;align-items:start}
.msg .who{display:flex;align-items:center;gap:8px;margin-bottom:6px;font-size:12.5px;color:var(--muted)}
.avatar{width:28px;height:28px;border-radius:50%;background:var(--teal);color:#fff;font-weight:700;
  display:grid;place-items:center;font-size:13px}
.who b{color:var(--ink);font-weight:600}
.card{background:var(--paper);border-radius:4px 18px 18px 18px;box-shadow:0 1px 2px rgba(19,38,43,.08);overflow:hidden}
.card-body{padding:14px 16px 12px}
.card-top{display:flex;flex-wrap:wrap;gap:6px 8px;align-items:center;font-size:12.5px;color:var(--muted)}
.mkt{border:1px solid var(--ink);color:var(--ink);border-radius:999px;padding:0 8px;font-weight:600}
.card-top time{margin-left:auto}
.amt-k{margin-top:10px;font-size:12px;color:var(--muted)}
.amount{font-size:28px;font-weight:700;color:var(--rust);line-height:1.2;font-variant-numeric:tabular-nums}
.tag{display:inline-block;margin-top:8px;background:var(--rust-soft);color:var(--rust);border-radius:6px;
  padding:1px 8px;font-size:13px;font-weight:600}
.explain{margin:10px 0 0;font-size:14px}
.actions{border-top:1px solid var(--line);padding:10px 12px 12px;display:grid;gap:8px}
.btn{font:inherit;font-size:14.5px;font-weight:600;min-height:44px;border-radius:10px;cursor:pointer;
  border:1.5px solid var(--teal);background:var(--paper);color:var(--teal);padding:8px 12px}
.btn.primary{background:var(--teal);color:#fff}
.btn:hover{filter:brightness(.95)}
.btn:focus-visible{outline:3px solid var(--ink);outline-offset:2px}
.done{border-top:1px solid var(--line);padding:12px 14px 14px}
.chip-done{display:inline-block;background:var(--teal-soft);color:#1F5A66;border-radius:999px;
  padding:4px 12px;font-weight:600;font-size:13.5px}
.done-sub{display:block;margin-top:6px;font-size:12.5px;color:var(--muted)}
.empty{grid-column:1/-1;text-align:center;color:var(--muted);padding:12px}

/* batch table */
.table-wrap{overflow-x:auto;background:var(--paper);border:1px solid var(--line);border-radius:14px}
.table-wrap:focus-visible{outline:3px solid var(--teal)}
table{border-collapse:collapse;width:100%;min-width:760px;font-size:14px}
th,td{padding:9px 12px;text-align:left;white-space:nowrap;border-bottom:1px solid var(--line)}
th{font-size:12.5px;font-weight:600;color:var(--muted);background:#FBFAF7;position:sticky;top:0}
tbody tr:last-child td{border-bottom:0}
td.r,th.r{text-align:right;font-variant-numeric:tabular-nums}
tr.exc td:first-child{box-shadow:inset 4px 0 0 var(--rust)}
.res{display:inline-block;border-radius:999px;padding:1px 10px;font-size:12.5px;font-weight:600}
.res.ok{background:var(--teal-soft);color:#1F5A66}
.res.bad{background:var(--rust-soft);color:var(--rust)}
.round{margin-left:6px;font-size:12px;color:var(--muted)}
.miss{color:var(--rust);font-weight:600}

footer{border-top:1px solid var(--line);padding:18px 0 34px;color:var(--muted);font-size:13.5px}
footer p{margin:0 0 6px}
footer .lead{color:var(--ink)}
@media (prefers-reduced-motion:no-preference){.done{animation:pop .25s ease-out}}
@keyframes pop{from{opacity:0;transform:translateY(4px)}to{opacity:1;transform:none}}
</style>
</head>
<body>
<header class="top">
  <div class="wrap head">
    <svg width="44" height="44" viewBox="0 0 40 40" role="img" aria-label="Closebook logo">
      <rect width="40" height="40" rx="10" fill="#13262B"/>
      <path d="M8 12.5c4-1.8 8-1.8 12 .8 4-2.6 8-2.6 12-.8v15.2c-4-1.8-8-1.8-12 .8-4-2.6-8-2.6-12-.8z" fill="#F7F5F0"/>
      <path d="M20 13.4v15.1" stroke="#13262B" stroke-width="1.2"/>
      <path d="M23 21.4l2.6 2.6 4.6-5.2" stroke="#B5441C" stroke-width="2.3" fill="none" stroke-linecap="round" stroke-linejoin="round"/>
    </svg>
    <div>
      <h1>Closebook <span class="sub">· month-end payout reconciliation</span></h1>
      <p class="meta">Demo seller · orders placed October 2026 · Shopee, Lazada, TikTok Shop</p>
    </div>
  </div>
</header>

<main class="wrap">
  <div class="banner" role="note">Synthetic data. Fee rates are illustrative. Matching is deterministic code; no LLM calculates any number.</div>

  <div class="tiles" id="tiles" aria-label="Summary"></div>

  <section aria-labelledby="owner-h">
    <div class="sec-head">
      <h2 id="owner-h">Needs the owner</h2>
      <p>รายการที่รอเจ้าของร้านตัดสินใจ · กดหนึ่งครั้งเพื่อส่งต่อให้นักบัญชี</p>
    </div>
    <div class="feed" id="cards"></div>
  </section>

  <section aria-labelledby="table-h">
    <div class="sec-head">
      <h2 id="table-h">All payout batches</h2>
      <p>Every 3-day payout window, matched against settlement lines and the bank statement</p>
    </div>
    <div class="table-wrap" tabindex="0" role="region" aria-labelledby="table-h">
      <table>
        <thead><tr>
          <th>Batch</th><th>Market</th><th>Payout date</th><th class="r">Orders</th>
          <th class="r">Payout (THB)</th><th class="r">Expected (THB)</th><th>Bank deposit</th><th>Result</th>
        </tr></thead>
        <tbody id="rows"></tbody>
      </table>
    </div>
  </section>
</main>

<footer>
  <div class="wrap">
    <p class="lead">Results are scored against a golden set on synthetic data and test the matching logic, not accuracy on real sellers.</p>
    <p>This demo is not connected to any marketplace, LINE, bank or accounting system. Built by run_demo.py from a fixed seed.</p>
  </div>
</footer>

<script type="application/json" id="demo-data">__DATA__</script>
<script>
(function () {
  "use strict";
  var D = JSON.parse(document.getElementById("demo-data").textContent);
  var S = D.stats;
  var money = new Intl.NumberFormat("en-US", {minimumFractionDigits: 2, maximumFractionDigits: 2});
  var TH_M = ["ม.ค.","ก.พ.","มี.ค.","เม.ย.","พ.ค.","มิ.ย.","ก.ค.","ส.ค.","ก.ย.","ต.ค.","พ.ย.","ธ.ค."];
  var EN_M = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];

  function el(tag, cls, text) {
    var n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text != null) n.textContent = text;
    return n;
  }
  function parts(iso) { var p = iso.split("-"); return {d: +p[2], m: +p[1] - 1}; }
  function thDate(iso) { var p = parts(iso); return p.d + " " + TH_M[p.m]; }
  function enDate(iso) { var p = parts(iso); return p.d + " " + EN_M[p.m]; }

  // Stat tiles
  var tiles = document.getElementById("tiles");
  var openValue;
  function tile(label, value, cls, note) {
    var t = el("div", "tile" + (cls ? " " + cls : ""));
    t.appendChild(el("div", "k", label));
    var v = el("div", "v num");
    if (value instanceof Node) v.appendChild(value); else v.textContent = value;
    t.appendChild(v);
    if (note) t.appendChild(el("div", "note", note));
    tiles.appendChild(t);
    return {tile: t, value: v};
  }
  tile("Batches checked", S.batches);
  tile("Matched with no human input", S.auto_matched, "good");
  var openTile = tile("Open exceptions", S.open, S.open ? "alert" : "good");
  openTile.value.setAttribute("aria-live", "polite");
  tile("THB at stake", money.format(S.at_stake), "alert");
  var caught = document.createDocumentFragment();
  caught.appendChild(document.createTextNode(S.caught));
  caught.appendChild(el("small", null, " / " + S.injected));
  tile("Anomalies caught", caught, S.caught === S.injected ? "good" : "alert");
  tile("Wrongly cleared", S.false_clears, S.false_clears === 0 ? "good" : "alert", "target 0");
  var open = S.open;

  // Owner cards
  var feed = document.getElementById("cards");
  var exceptions = D.results.filter(function (r) { return r.label !== "MATCHED"; });
  if (!exceptions.length) feed.appendChild(el("p", "empty", "ไม่มีรายการค้าง"));
  exceptions.forEach(function (r) {
    var msg = el("div", "msg");
    var who = el("div", "who");
    who.appendChild(el("span", "avatar", "C"));
    who.appendChild(el("b", null, "Closebook"));
    who.appendChild(el("span", null, "09:00"));
    msg.appendChild(who);

    var card = el("article", "card");
    card.setAttribute("aria-label", r.label_th + " " + r.batch_id);
    var body = el("div", "card-body");
    var top = el("div", "card-top");
    top.appendChild(el("span", "mkt", r.market));
    top.appendChild(el("span", null, "รอบ " + r.batch_id));
    var t = el("time", null, "วันโอน " + thDate(r.payout_date));
    t.setAttribute("datetime", r.payout_date);
    top.appendChild(t);
    body.appendChild(top);
    body.appendChild(el("div", "amt-k", "ยอดเงินที่ต้องตรวจ (บาท)"));
    body.appendChild(el("div", "amount", "฿" + money.format(r.detail.amount)));
    body.appendChild(el("span", "tag", r.label_th));
    body.appendChild(el("p", "explain", r.explain_th));
    card.appendChild(body);

    var actions = el("div", "actions");
    r.actions_th.forEach(function (a, i) {
      var b = el("button", "btn" + (i === 0 ? " primary" : ""), a);
      b.type = "button";
      b.addEventListener("click", function () {
        var done = el("div", "done");
        done.setAttribute("role", "status");
        done.appendChild(el("span", "chip-done", "✓ เรียบร้อย · รอนักบัญชีอนุมัติ"));
        done.appendChild(el("span", "done-sub", "Done, awaiting accountant approval · เลือก: " + a));
        card.replaceChild(done, actions);
        open = Math.max(0, open - 1);
        openTile.value.textContent = open;
        if (open === 0) { openTile.tile.classList.remove("alert"); openTile.tile.classList.add("good"); }
      });
      actions.appendChild(b);
    });
    card.appendChild(actions);
    msg.appendChild(card);
    feed.appendChild(msg);
  });

  // Batch table
  var rows = document.getElementById("rows");
  D.results.forEach(function (r) {
    var ok = r.label === "MATCHED";
    var tr = el("tr", ok ? "" : "exc");
    tr.appendChild(el("td", null, r.batch_id));
    tr.appendChild(el("td", null, r.market));
    tr.appendChild(el("td", null, enDate(r.payout_date)));
    tr.appendChild(el("td", "r", r.orders));
    tr.appendChild(el("td", "r", money.format(r.payout)));
    tr.appendChild(el("td", "r", money.format(r.expected)));
    tr.appendChild(r.bank_date ? el("td", null, enDate(r.bank_date)) : el("td", "miss", "Not found"));
    var res = el("td");
    var chip = el("span", "res " + (ok ? "ok" : "bad"), D.labels_en[r.label]);
    chip.title = r.label_th;
    res.appendChild(chip);
    if (ok && r.detail.rounding) {
      res.appendChild(el("span", "round num", "rounding " + (r.detail.rounding > 0 ? "+" : "") + r.detail.rounding.toFixed(2)));
    }
    tr.appendChild(res);
    rows.appendChild(tr);
  });
})();
</script>
</body>
</html>
"""
