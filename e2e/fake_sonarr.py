#!/usr/bin/env python3
"""Minimal Sonarr v3 API stand-in with a demo library (stdlib only).

Used for screenshots and the Playwright smoke test. Airing dates are relative
to "now", so the demo looks the same whenever it runs. API key: "demo-key".

  python3 e2e/fake_sonarr.py [port]
  POST /_control/files {"series": 1, "season": 3, "files": [1, 2, 3]}  # change files
"""

import json
import sys
from datetime import UTC, datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

API_KEY = "demo-key"
NOW = datetime.now(UTC).replace(minute=0, second=0, microsecond=0)


def series(sid, title, year, stype, seasons, slug=None):
    return {
        "id": sid, "title": title, "sortTitle": title.lower(), "titleSlug": slug or title.lower().replace(" ", "-"),
        "year": year, "tvdbId": 300000 + sid, "seriesType": stype, "status": "continuing", "monitored": True,
        "images": [], "seasons": [{"seasonNumber": n, "monitored": True} for n in seasons],
    }


def episodes(sid, season, count, first_air, interval_days, files, finale=None, start_id=0):
    out = []
    for n in range(1, count + 1):
        air = first_air + timedelta(days=interval_days * (n - 1))
        out.append({
            "id": sid * 10000 + season * 100 + n + start_id, "seriesId": sid, "seasonNumber": season,
            "episodeNumber": n, "title": f"Episode {n}", "airDateUtc": air.isoformat().replace("+00:00", "Z"),
            "monitored": True, "hasFile": n in files, **({"finaleType": "season"} if n == finale else {}),
        })
    return out


SERIES = [
    series(1, "That Time I Got Reincarnated as a Slime", 2018, "anime", [1, 2, 3]),
    series(2, "Mushoku Tensei", 2021, "anime", [1, 2]),
    series(3, "Severance", 2022, "standard", [1, 2]),
    series(4, "Andor", 2022, "standard", [1, 2]),
    series(5, "Frieren", 2023, "anime", [1, 2]),
    series(6, "The Bear", 2022, "standard", [1, 2, 3]),
]
EPISODES = {
    1: episodes(1, 3, 24, NOW - timedelta(days=7 * 20), 7, set(range(1, 19)), finale=24)
    + episodes(1, 2, 24, NOW - timedelta(days=900), 7, set(range(1, 25)), finale=24),
    2: episodes(2, 2, 12, NOW - timedelta(days=120), 7, set(range(1, 13))),
    3: episodes(3, 2, 10, NOW - timedelta(days=100), 7, set(range(1, 11)), finale=10),
    4: episodes(4, 2, 12, NOW - timedelta(days=30), 0, set(range(1, 4))),
    5: episodes(5, 2, 12, NOW + timedelta(days=60), 7, set()),
    6: episodes(6, 3, 10, NOW - timedelta(days=300), 0, set(range(1, 11))),
}


class Handler(BaseHTTPRequestHandler):
    def _send(self, status, body):
        data = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):  # noqa: N802
        if self.headers.get("X-Api-Key") != API_KEY:
            return self._send(401, {"message": "Unauthorized"})
        url = urlsplit(self.path)
        if url.path == "/api/v3/system/status":
            return self._send(200, {"appName": "Sonarr", "version": "4.0.99-fake"})
        if url.path == "/api/v3/series":
            return self._send(200, SERIES)
        if url.path.startswith("/api/v3/series/"):
            sid = int(url.path.rsplit("/", 1)[1])
            return self._send(200, next(s for s in SERIES if s["id"] == sid))
        if url.path == "/api/v3/episode":
            sid = int(parse_qs(url.query)["seriesId"][0])
            return self._send(200, EPISODES.get(sid, []))
        return self._send(404, {"message": "Not found"})

    def do_POST(self):  # noqa: N802
        if self.path != "/_control/files":
            return self._send(404, {})
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        for ep in EPISODES[body["series"]]:
            if ep["seasonNumber"] == body["season"]:
                ep["hasFile"] = ep["episodeNumber"] in body["files"]
        return self._send(200, {"ok": True})

    def log_message(self, *_args):
        pass


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 18989
    ThreadingHTTPServer(("0.0.0.0", port), Handler).serve_forever()  # noqa: S104 - test server
