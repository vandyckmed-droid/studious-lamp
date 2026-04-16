import os
from flask import Flask, render_template_string, jsonify
import pandas as pd
import yfinance as yf

app = Flask(__name__)

_cache = {}


def get_universe():
    """Pull S&P MidCap 400 constituents (MDY) from Wikipedia."""
    if "universe" in _cache:
        return _cache["universe"]

    url = "https://en.wikipedia.org/wiki/List_of_S%26P_400_companies"
    tables = pd.read_html(url)
    df = tables[0][["Symbol", "Security", "GICS Sector"]].copy()
    # yfinance uses dashes instead of dots in tickers
    df["Symbol"] = df["Symbol"].str.replace(".", "-", regex=False)
    df = df.sort_values("Symbol").reset_index(drop=True)
    _cache["universe"] = df
    return df


@app.route("/")
def index():
    try:
        universe = get_universe()
        tickers = universe.to_dict(orient="records")
        count = len(tickers)
        error = None
    except Exception as e:
        tickers = []
        count = 0
        error = str(e)

    return render_template_string(PAGE_TEMPLATE, tickers=tickers, count=count, error=error)


@app.route("/api/prices")
def api_prices():
    """Download 1 month of closing prices for the full universe."""
    universe = get_universe()
    symbols = universe["Symbol"].tolist()

    data = yf.download(symbols, period="1mo", threads=True)
    close = data["Close"]

    last_close = close.iloc[-1]
    first_close = close.iloc[0]
    change_pct = ((last_close - first_close) / first_close * 100).round(2)

    result = {}
    for sym in symbols:
        try:
            lc = last_close.get(sym)
            cp = change_pct.get(sym)
            result[sym] = {
                "last_close": round(float(lc), 2) if pd.notna(lc) else None,
                "change_1m": round(float(cp), 2) if pd.notna(cp) else None,
            }
        except Exception:
            result[sym] = {"last_close": None, "change_1m": None}

    return jsonify(result)


@app.route("/health")
def health():
    return jsonify({"status": "ok"})


PAGE_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>MDY Universe</title>
  <style>
    * { margin: 0; padding: 0; box-sizing: border-box; }
    body {
      font-family: 'SF Mono', 'Fira Code', 'Consolas', monospace;
      background: #0a0a0a;
      color: #d0d0d0;
      padding: 1.5rem;
      font-size: 14px;
    }
    h1 { color: #fff; margin-bottom: 0.25rem; font-size: 1.4rem; }
    .subtitle { color: #666; margin-bottom: 1rem; font-size: 0.85rem; }
    .status-bar {
      display: flex; gap: 1.5rem; align-items: center;
      margin-bottom: 1rem; flex-wrap: wrap;
    }
    .badge {
      padding: 0.3rem 0.8rem;
      border-radius: 4px;
      font-size: 0.8rem;
    }
    .badge-count { background: #1a1a2e; color: #667eea; border: 1px solid #2a2a4e; }
    .badge-loading { background: #1a1a1a; color: #f59e0b; border: 1px solid #333; }
    .badge-done { background: #0a1a0a; color: #4ade80; border: 1px solid #1a3a1a; }
    .badge-error { background: #1a0a0a; color: #f87171; border: 1px solid #3a1a1a; }
    .error { color: #f87171; margin-bottom: 1rem; }
    table {
      width: 100%;
      border-collapse: collapse;
      table-layout: fixed;
    }
    th, td {
      text-align: left;
      padding: 0.5rem 0.75rem;
      border-bottom: 1px solid #1a1a1a;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }
    th {
      background: #111;
      color: #888;
      font-weight: 600;
      text-transform: uppercase;
      font-size: 0.7rem;
      letter-spacing: 0.05em;
      position: sticky;
      top: 0;
      cursor: pointer;
      user-select: none;
    }
    th:hover { color: #bbb; }
    th.sorted-asc::after { content: " ▲"; }
    th.sorted-desc::after { content: " ▼"; }
    tr:hover { background: #111; }
    .col-num { width: 50px; text-align: right; color: #444; }
    .col-ticker { width: 90px; font-weight: 600; color: #667eea; }
    .col-name { width: auto; }
    .col-sector { width: 180px; color: #888; }
    .col-price { width: 100px; text-align: right; font-variant-numeric: tabular-nums; }
    .col-change { width: 100px; text-align: right; font-variant-numeric: tabular-nums; }
    .pos { color: #4ade80; }
    .neg { color: #f87171; }
    .loading-cell { color: #444; }
    @media (max-width: 700px) {
      .col-sector { display: none; }
      th:nth-child(4), td:nth-child(4) { display: none; }
    }
  </style>
</head>
<body>
  <h1>MDY Universe — S&P MidCap 400</h1>
  <p class="subtitle">Step 1: Tickers + closing prices</p>

  <div class="status-bar">
    <span class="badge badge-count">{{ count }} stocks</span>
    <span class="badge badge-loading" id="price-status">Prices loading...</span>
  </div>

  {% if error %}
  <p class="error">Error loading universe: {{ error }}</p>
  {% endif %}

  <table>
    <thead>
      <tr>
        <th class="col-num" data-col="0" data-type="num">#</th>
        <th class="col-ticker" data-col="1" data-type="str">Ticker</th>
        <th class="col-name" data-col="2" data-type="str">Company</th>
        <th class="col-sector" data-col="3" data-type="str">Sector</th>
        <th class="col-price" data-col="4" data-type="num">Last Close</th>
        <th class="col-change" data-col="5" data-type="num">1M Chg %</th>
      </tr>
    </thead>
    <tbody id="table-body">
      {% for t in tickers %}
      <tr data-sym="{{ t.Symbol }}">
        <td class="col-num">{{ loop.index }}</td>
        <td class="col-ticker">{{ t.Symbol }}</td>
        <td class="col-name">{{ t.Security }}</td>
        <td class="col-sector">{{ t['GICS Sector'] }}</td>
        <td class="col-price loading-cell" id="price-{{ t.Symbol }}">—</td>
        <td class="col-change loading-cell" id="chg-{{ t.Symbol }}">—</td>
      </tr>
      {% endfor %}
    </tbody>
  </table>

  <script>
    // Fetch prices in background so the page loads instantly
    fetch("/api/prices")
      .then(r => r.json())
      .then(data => {
        for (const [sym, vals] of Object.entries(data)) {
          const priceEl = document.getElementById("price-" + sym);
          const chgEl = document.getElementById("chg-" + sym);
          if (!priceEl) continue;

          if (vals.last_close !== null) {
            priceEl.textContent = "$" + vals.last_close.toFixed(2);
            priceEl.classList.remove("loading-cell");
          }
          if (vals.change_1m !== null) {
            const sign = vals.change_1m >= 0 ? "+" : "";
            chgEl.textContent = sign + vals.change_1m.toFixed(2) + "%";
            chgEl.classList.remove("loading-cell");
            chgEl.classList.add(vals.change_1m >= 0 ? "pos" : "neg");
          }
        }
        const badge = document.getElementById("price-status");
        badge.textContent = "Prices loaded";
        badge.className = "badge badge-done";
      })
      .catch(err => {
        const badge = document.getElementById("price-status");
        badge.textContent = "Price load failed";
        badge.className = "badge badge-error";
      });

    // Simple column sorting
    document.querySelectorAll("th").forEach(th => {
      th.addEventListener("click", () => {
        const col = parseInt(th.dataset.col);
        const type = th.dataset.type;
        const tbody = document.getElementById("table-body");
        const rows = Array.from(tbody.querySelectorAll("tr"));
        const asc = !th.classList.contains("sorted-asc");

        document.querySelectorAll("th").forEach(h => {
          h.classList.remove("sorted-asc", "sorted-desc");
        });
        th.classList.add(asc ? "sorted-asc" : "sorted-desc");

        rows.sort((a, b) => {
          let va = a.children[col].textContent.replace(/[$%+,]/g, "").trim();
          let vb = b.children[col].textContent.replace(/[$%+,]/g, "").trim();
          if (va === "—") va = asc ? "999999" : "-999999";
          if (vb === "—") vb = asc ? "999999" : "-999999";
          if (type === "num") {
            va = parseFloat(va) || 0;
            vb = parseFloat(vb) || 0;
            return asc ? va - vb : vb - va;
          }
          return asc ? va.localeCompare(vb) : vb.localeCompare(va);
        });
        rows.forEach(r => tbody.appendChild(r));
      });
    });
  </script>
</body>
</html>
"""


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 3000))
    app.run(host="0.0.0.0", port=port)
