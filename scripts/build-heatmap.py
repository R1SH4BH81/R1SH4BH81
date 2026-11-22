#!/usr/bin/env python3
"""Regenerate contributions.svg — a GitHub-style contributions heatmap —
from the live contributions calendar. Stdlib only.

Levels come from the public calendar endpoint (no auth); the total comes
from the GraphQL API using GH_TOKEN (the workflow passes GITHUB_TOKEN).
If the total fetch fails, the previous SVG's total is reused.
"""
import json
import os
import re
import urllib.request
from datetime import date, timedelta
from pathlib import Path

USER = os.environ.get("HEATMAP_USER", "R1SH4BH81")
OUT = Path(__file__).resolve().parent.parent / "contributions.svg"
UA = {"User-Agent": "heatmap-generator/1.0 (+https://github.com/R1SH4BH81)"}

COLORS = ["#161b22", "#0e4429", "#006d32", "#26a641", "#39d353"]  # dark greens
CELL, GAP = 10, 3
PITCH = CELL + GAP
TOP, LEFT, TITLE_H = 22, 28, 24
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
          "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def fetch(url, headers=None, data=None):
    req = urllib.request.Request(url, data=data, headers={**UA, **(headers or {})})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8")


def get_total():
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if token:
        try:
            q = {"query": '{ user(login: "%s") { contributionsCollection { '
                           'contributionCalendar { totalContributions } } } }' % USER}
            res = json.loads(fetch(
                "https://api.github.com/graphql",
                {"Authorization": "Bearer " + token, "Content-Type": "application/json"},
                data=json.dumps(q).encode()))
            return res["data"]["user"]["contributionsCollection"][
                "contributionCalendar"]["totalContributions"]
        except Exception as e:
            print(f"GraphQL total failed ({e}); falling back to previous SVG")
    if OUT.exists():
        m = re.search(r"([\d,]+) contributions in the last year", OUT.read_text())
        if m:
            return int(m.group(1).replace(",", ""))
    raise SystemExit("no total available: GraphQL failed and no previous SVG")


def main():
    html = fetch(f"https://github.com/users/{USER}/contributions")
    days = re.findall(r'<td[^>]*?data-date="(\d{4}-\d{2}-\d{2})"[^>]*?data-level="(\d)"', html)
    days = sorted((date.fromisoformat(d), int(l)) for d, l in days)
    if len(days) < 300:
        raise SystemExit(f"only {len(days)} days parsed; refusing to write a partial grid")
    total = get_total()
    print(f"days: {len(days)}  total: {total}  range: {days[0][0]}..{days[-1][0]}")

    first, last = days[0][0], days[-1][0]
    start_sunday = first - timedelta(days=(first.weekday() + 1) % 7)
    n_weeks = ((last - start_sunday).days // 7) + 1
    by_date = dict(days)
    W = LEFT + n_weeks * PITCH
    H = TITLE_H + TOP + 7 * PITCH + 18

    p = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">']
    p.append('<style>text{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,Arial,sans-serif;fill:#7d8590;font-size:9px}</style>')
    p.append(f'<text x="{LEFT}" y="14" style="font-size:12px;fill:#e6edf3">{total} contributions in the last year</text>')

    seen_month = None
    for w in range(n_weeks):
        col_date = start_sunday + timedelta(days=w * 7)
        if col_date.month != seen_month:
            seen_month = col_date.month
            p.append(f'<text x="{LEFT + w * PITCH}" y="{TITLE_H + 12}">{MONTHS[col_date.month - 1]}</text>')

    for row, label in ((1, "Mon"), (3, "Wed"), (5, "Fri")):
        p.append(f'<text x="0" y="{TITLE_H + TOP + row * PITCH + 9}">{label}</text>')

    for w in range(n_weeks):
        for row in range(7):
            d = start_sunday + timedelta(days=w * 7 + row)
            if d < first or d > last:
                continue
            x, y = LEFT + w * PITCH, TITLE_H + TOP + row * PITCH
            p.append(f'<rect x="{x}" y="{y}" width="{CELL}" height="{CELL}" rx="2" '
                     f'fill="{COLORS[by_date.get(d, 0)]}"><title>{d.isoformat()}</title></rect>')

    lx, ly = W - 110, H - 4
    p.append(f'<text x="{lx}" y="{ly}">Less</text>')
    for i, c in enumerate(COLORS):
        p.append(f'<rect x="{lx + 28 + i * PITCH}" y="{ly - 9}" width="{CELL}" height="{CELL}" rx="2" fill="{c}"/>')
    p.append(f'<text x="{lx + 28 + 5 * PITCH + 3}" y="{ly}">More</text>')
    p.append("</svg>")

    OUT.write_text("\n".join(p) + "\n")
    print(f"wrote {OUT} ({W}x{H})")


if __name__ == "__main__":
    main()
