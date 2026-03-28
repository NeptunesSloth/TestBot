from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from money_printer_lite.storage import SQLiteStorage


def _render_html(storage: SQLiteStorage) -> str:
    metrics = storage.dashboard_metrics()
    opportunities = storage.latest_opportunities(60)
    paper_trades = storage.trades("paper", 50)
    live_trades = storage.trades("live", 50)
    best = metrics["best_setup"]
    best_setup = "n/a" if not best else f"{best['setup_type']} ({best['pnl']:.2f})"

    opp_rows = "".join(
        f"<tr><td>{o['detected_at']}</td><td>{o['asset']}</td><td>{o['relationship_type']}</td>"
        f"<td>{o['opportunity_class']}</td><td>{o['net_edge']:.4f}</td><td>{o['confidence_score']:.2f}</td><td>{o['description']}</td></tr>"
        for o in opportunities
    )
    paper_rows = "".join(
        f"<tr><td>{t['closed_at']}</td><td>{t['asset']}</td><td>{t['setup_type']}</td><td>{t['stake']:.2f}</td>"
        f"<td>{t['expected_edge']:.4f}</td><td>{t['realized_pnl']:.4f}</td></tr>"
        for t in paper_trades
    )
    live_rows = "".join(
        f"<tr><td>{t['closed_at']}</td><td>{t['asset']}</td><td>{t['setup_type']}</td><td>{t['stake']:.2f}</td>"
        f"<td>{t['expected_edge']:.4f}</td><td>{t['realized_pnl']:.4f}</td></tr>"
        for t in live_trades
    )

    return f"""
<!doctype html>
<html>
<head>
  <meta charset="utf-8"/>
  <meta http-equiv="refresh" content="15"/>
  <title>Polymarket Money Printer Lite</title>
  <style>
    body {{ font-family: Arial; margin: 20px; background:#0f172a; color:#e2e8f0; }}
    .grid {{ display:grid; grid-template-columns: repeat(4, minmax(180px,1fr)); gap: 10px; }}
    .card {{ background:#1e293b; padding:10px; border-radius:8px; }}
    table {{ width:100%; border-collapse: collapse; margin-top:14px; }}
    th, td {{ border-bottom:1px solid #334155; padding:8px; text-align:left; }}
    th {{ background:#1e293b; }}
  </style>
</head>
<body>
  <h1>Polymarket Money Printer Lite</h1>
  <div class="grid">
    <div class="card"><b>Total Hypothetical P&L</b><br>{metrics['total_hypothetical_pnl']}</div>
    <div class="card"><b>Realized P&L</b><br>{metrics['realized_pnl']}</div>
    <div class="card"><b>Open Exposure</b><br>{metrics['open_exposure']}</div>
    <div class="card"><b>Opportunities Today</b><br>{metrics['opportunities_today']}</div>
    <div class="card"><b>Trades Today</b><br>{metrics['trades_today']}</div>
    <div class="card"><b>Average Net Edge</b><br>{metrics['average_net_edge']}</div>
    <div class="card"><b>Wins / Losses</b><br>{metrics['win_count']} / {metrics['loss_count']}</div>
    <div class="card"><b>Best Setup</b><br>{best_setup}</div>
  </div>

  <h2>Active opportunities</h2>
  <table><thead><tr><th>Time</th><th>Asset</th><th>Type</th><th>Class</th><th>Net Edge</th><th>Confidence</th><th>Description</th></tr></thead><tbody>{opp_rows}</tbody></table>

  <h2>Paper trade history</h2>
  <table><thead><tr><th>Time</th><th>Asset</th><th>Setup</th><th>Stake</th><th>Expected Edge</th><th>Realized P&L</th></tr></thead><tbody>{paper_rows}</tbody></table>

  <h2>Live trade history</h2>
  <table><thead><tr><th>Time</th><th>Asset</th><th>Setup</th><th>Stake</th><th>Expected Edge</th><th>Realized P&L</th></tr></thead><tbody>{live_rows}</tbody></table>
</body>
</html>
"""


def serve_dashboard(storage: SQLiteStorage, host: str, port: int) -> None:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == "/api/overview":
                payload = json.dumps(storage.dashboard_metrics()).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)
                return
            if self.path == "/api/opportunities":
                payload = json.dumps(storage.latest_opportunities(100)).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)
                return

            html = _render_html(storage).encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(html)))
            self.end_headers()
            self.wfile.write(html)

        def log_message(self, format, *args):
            return

    server = ThreadingHTTPServer((host, port), Handler)
    print(f"Dashboard at http://{host}:{port}")
    server.serve_forever()
