from __future__ import annotations

import html
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from .core import ScanResult, render_dashboard_rows, scan_result_to_json


def build_dashboard_html(result: ScanResult, limit: int, refresh_seconds: int) -> str:
    warning = f"<div class='banner warning'>{html.escape(result.warning)}</div>" if result.warning else ""
    error = f"<div class='banner error'>{html.escape(result.error)}</div>" if result.error else ""
    empty = "<p>No opportunities matched the current thresholds.</p>" if not result.opportunities and not result.error else ""
    rows = render_dashboard_rows(result.opportunities, limit)
    return f"""
<!doctype html>
<html lang='en'>
<head>
  <meta charset='utf-8'>
  <meta http-equiv='refresh' content='{refresh_seconds}'>
  <meta name='viewport' content='width=device-width, initial-scale=1'>
  <title>Cross Arbitrage Dashboard</title>
  <style>
    body {{ font-family: Arial, sans-serif; margin: 24px; background: #0b1020; color: #ecf0ff; }}
    .banner {{ padding: 12px 16px; border-radius: 8px; margin-bottom: 16px; }}
    .warning {{ background: #4f3d0e; color: #ffd86c; }}
    .error {{ background: #4c1220; color: #ff9db0; }}
    .stats {{ display: flex; gap: 12px; flex-wrap: wrap; margin-bottom: 16px; }}
    .card {{ background: #151c33; padding: 14px 16px; border-radius: 10px; min-width: 180px; }}
    table {{ width: 100%; border-collapse: collapse; background: #151c33; border-radius: 10px; overflow: hidden; }}
    th, td {{ padding: 12px; border-bottom: 1px solid #26304f; text-align: left; vertical-align: top; }}
    th {{ background: #1d2744; }}
    a {{ color: #7fc6ff; }}
    .badge {{ display: inline-block; background: #25345f; padding: 6px 10px; border-radius: 999px; font-size: 0.9rem; }}
  </style>
</head>
<body>
  <h1>Cross Arbitrage Dashboard</h1>
  <p><span class='badge'>Source mode: {html.escape(result.source_mode)}</span></p>
  {warning}
  {error}
  <div class='stats'>
    <div class='card'><strong>Polymarket markets</strong><br>{result.polymarket_count}</div>
    <div class='card'><strong>Kalshi markets</strong><br>{result.kalshi_count}</div>
    <div class='card'><strong>Displayed opportunities</strong><br>{min(limit, len(result.opportunities))}</div>
  </div>
  {empty}
  <table>
    <thead>
      <tr>
        <th>Market</th>
        <th>Strategy</th>
        <th>Edge</th>
        <th>Match score</th>
        <th>Shared tokens</th>
        <th>Polymarket</th>
        <th>Kalshi</th>
      </tr>
    </thead>
    <tbody>
      {rows}
    </tbody>
  </table>
</body>
</html>
""".strip()


def serve_dashboard(result_factory, host: str, port: int, limit: int, refresh_seconds: int) -> None:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            parsed = urlparse(self.path)
            params = parse_qs(parsed.query)
            page_limit = limit
            if "limit" in params:
                try:
                    page_limit = max(1, int(params["limit"][0]))
                except ValueError:
                    page_limit = limit
            result = result_factory()
            if parsed.path == "/api/opportunities":
                payload = scan_result_to_json(result, page_limit).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)
                return

            payload = build_dashboard_html(result, page_limit, refresh_seconds).encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, format, *args):
            return

    server = ThreadingHTTPServer((host, port), Handler)
    print(f"Dashboard available at http://{host}:{port}")
    server.serve_forever()
