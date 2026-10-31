"""
Draws the "Footprints" images for the profile README from GitHub contribution data.

  tide.svg        Headline numbers and a weekly "tide" of contributions over the past year,
                  with a butterfly of light marking the busiest week.
  craft.svg       How I contribute (commits, pull requests, reviews, issues) and
                  where (top repositories, leaving out GitHub's special repos).
  rhythm.svg      Contributions by day of the week, with the busiest day highlighted.

Usage:
    GITHUB_TOKEN=... python footprints.py <username> <output-directory>

Uses only the Python standard library.
"""

import json
import math
import os
import sys
import urllib.request
from datetime import date


# -----------------------------------------------------------------------------
# Data
# -----------------------------------------------------------------------------

QUERY = """
query($login: String!) {
  user(login: $login) {
    contributionsCollection {
      totalCommitContributions
      totalPullRequestContributions
      totalPullRequestReviewContributions
      totalIssueContributions
      commitContributionsByRepository(maxRepositories: 10) {
        repository { name nameWithOwner owner { login } }
        contributions { totalCount }
      }
      contributionCalendar {
        totalContributions
        weeks { contributionDays { date contributionCount } }
      }
    }
  }
}
"""


def fetch_contributions(login: str, token: str) -> dict:
    """Returns the past year's contributions collection from the GitHub GraphQL API."""
    body = json.dumps({"query": QUERY, "variables": {"login": login}}).encode()
    request = urllib.request.Request(
        "https://api.github.com/graphql",
        data=body,
        headers={"Authorization": f"bearer {token}", "Content-Type": "application/json"},
    )

    with urllib.request.urlopen(request, timeout=30) as response:
        payload = json.load(response)

    if "errors" in payload:
        raise RuntimeError(payload["errors"])

    return payload["data"]["user"]["contributionsCollection"]


def is_special_repo(repository: dict) -> bool:
    """GitHub's special repos: a profile README repo (name = owner), `.github`, and `*.github.io` pages."""
    name = repository["name"].lower()
    return (
        name == repository["owner"]["login"].lower()
        or name == ".github"
        or name.endswith(".github.io")
    )


def monthly_totals(calendar: dict) -> list[tuple[str, int]]:
    """(YYYY-MM, contributions) for each month in the calendar, oldest first; drops a partial first month."""
    totals = {}
    for week in calendar["weeks"]:
        for day in week["contributionDays"]:
            month = day["date"][:7]
            totals[month] = totals.get(month, 0) + day["contributionCount"]

    months = sorted(totals.items())
    return months[-12:]


# -----------------------------------------------------------------------------
# Shared drawing pieces
# -----------------------------------------------------------------------------

WIDTH = 1280
FONT = "'DM Sans', -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif"
SERIF = "Literata, Georgia, 'Times New Roman', serif"

GLOW = """<radialGradient id="glow" cx="0.5" cy="0.5" r="0.5">
      <stop offset="0" stop-color="#fff6d8" stop-opacity="0.9"/>
      <stop offset="1" stop-color="#ffd27a" stop-opacity="0"/>
    </radialGradient>"""


def butterfly(x: float, y: float, scale: float, rotate: float = 10) -> str:
    """A single butterfly of light, matching the rest of the profile."""
    return f"""<g transform="translate({x:.1f} {y:.1f}) rotate({rotate}) scale({scale})">
    <circle r="22" fill="url(#glow)" opacity="0.7"/>
    <path d="M0,0 C-3,-10 -14,-15 -16,-8 C-17,-2 -8,1 0,0 Z" fill="#fff4d2"/>
    <path d="M0,0 C3,-10 14,-15 16,-8 C17,-2 8,1 0,0 Z" fill="#fff4d2"/>
    <path d="M0,0 C-6,2 -12,6 -10,10 C-7,13 -2,8 0,0 Z" fill="#ffe0a0"/>
    <path d="M0,0 C6,2 12,6 10,10 C7,13 2,8 0,0 Z" fill="#ffe0a0"/>
  </g>"""


def smooth_path(points: list[tuple[float, float]], floor: float) -> str:
    """Smooth curve through the points (Catmull-Rom as cubic Béziers), never dipping below `floor`."""
    clamp = lambda y: min(y, floor)
    path = f"M{points[0][0]:.1f},{points[0][1]:.1f}"

    for i in range(len(points) - 1):
        p0 = points[i - 1] if i else points[i]
        p1, p2 = points[i], points[i + 1]
        p3 = points[i + 2] if i + 2 < len(points) else p2
        c1 = (p1[0] + (p2[0] - p0[0]) / 6, clamp(p1[1] + (p2[1] - p0[1]) / 6))
        c2 = (p2[0] - (p3[0] - p1[0]) / 6, clamp(p2[1] - (p3[1] - p1[1]) / 6))
        path += f" C{c1[0]:.1f},{c1[1]:.1f} {c2[0]:.1f},{c2[1]:.1f} {p2[0]:.1f},{p2[1]:.1f}"

    return path


# -----------------------------------------------------------------------------
# Footprints: headline numbers + weekly tide
# -----------------------------------------------------------------------------

def render_tide(calendar: dict) -> str:
    height = 320
    left, right, top, bottom = 430, 1220, 92, 246   # chart area

    weeks = calendar["weeks"]
    weekly = [sum(d["contributionCount"] for d in w["contributionDays"]) for w in weeks]
    days = [d for w in weeks for d in w["contributionDays"]]
    active_days = sum(1 for d in days if d["contributionCount"] > 0)

    months = monthly_totals(calendar)
    busiest_month = max(months, key=lambda m: m[1])[0]
    busiest_label = date.fromisoformat(busiest_month + "-01").strftime("%B")

    # Weekly points scaled into the chart area
    peak = max(weekly) or 1
    step = (right - left) / (len(weekly) - 1)
    points = [(left + i * step, bottom - (count / peak) * (bottom - top)) for i, count in enumerate(weekly)]
    line = smooth_path(points, bottom)
    area = line + f" L{right},{bottom} L{left},{bottom} Z"
    peak_x, peak_y = points[weekly.index(peak)]

    # Month names under the first week of each month
    labels, last_month = [], None
    for i, week in enumerate(weeks):
        first_day = date.fromisoformat(week["contributionDays"][0]["date"])
        if first_day.month != last_month and first_day.day <= 7:
            labels.append(f'<text x="{points[i][0]:.1f}" y="{bottom + 22}">{first_day.strftime("%b")}</text>')
            last_month = first_day.month

    gridlines = "".join(
        f'<line x1="{left}" x2="{right}" y1="{top + k * (bottom - top) / 3:.1f}" y2="{top + k * (bottom - top) / 3:.1f}" '
        f'stroke="#4a5590" stroke-opacity="0.35" stroke-dasharray="2 6"/>'
        for k in range(3)
    )

    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{height}" viewBox="0 0 {WIDTH} {height}" font-family="{FONT}">
  <title>Footprints this past year: {calendar['totalContributions']} contributions over {active_days} active days, busiest in {busiest_label}.</title>
  <defs>
    <linearGradient id="sky" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="#141c3a"/><stop offset="0.7" stop-color="#2c3770"/><stop offset="1" stop-color="#5a4d84"/>
    </linearGradient>
    <linearGradient id="tide" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="#ffd59a" stop-opacity="0.55"/><stop offset="1" stop-color="#e9a07a" stop-opacity="0.05"/>
    </linearGradient>
    {GLOW}
  </defs>
  <rect x="0.5" y="0.5" width="{WIDTH - 1}" height="{height - 1}" rx="16" fill="url(#sky)" stroke="#2a3360"/>

  <!-- Headline numbers -->
  <text x="48" y="58" font-family="{SERIF}" font-size="24" font-weight="600" fill="#fff6e6">Footprints this past year</text>
  <text x="48" y="140" font-family="{SERIF}" font-size="56" font-weight="600" fill="#ffd59a">{calendar['totalContributions']:,}</text>
  <text x="48" y="166" font-size="14" fill="#c9cfe8">contributions</text>
  <line x1="48" y1="190" x2="360" y2="190" stroke="#4a5590" stroke-opacity="0.6"/>
  <text x="48" y="226" font-family="{SERIF}" font-size="30" font-weight="600" fill="#fff6e6">{active_days}</text>
  <text x="48" y="248" font-size="13" fill="#c9cfe8">active days</text>
  <text x="200" y="226" font-family="{SERIF}" font-size="30" font-weight="600" fill="#fff6e6">{busiest_label}</text>
  <text x="200" y="248" font-size="13" fill="#c9cfe8">busiest month</text>
  <text x="48" y="290" font-family="{SERIF}" font-style="italic" font-size="14" fill="#ffd59a">each one a small summer kept</text>

  <!-- Weekly tide -->
  {gridlines}
  <path d="{area}" fill="url(#tide)"/>
  <path d="{line}" fill="none" stroke="#ffd59a" stroke-width="2.5" stroke-linejoin="round"/>
  <line x1="{left}" x2="{right}" y1="{bottom}" y2="{bottom}" stroke="#8f98c4" stroke-opacity="0.6"/>
  <g font-size="11" fill="#8f98c4" text-anchor="middle">{"".join(labels)}</g>

  <!-- Busiest week -->
  <circle cx="{peak_x:.1f}" cy="{peak_y:.1f}" r="4" fill="#fff4d2"/>
  {butterfly(peak_x, peak_y - 26, 0.85)}
  <text x="{peak_x:.1f}" y="{peak_y - 52:.1f}" text-anchor="middle" font-size="11" fill="#ffd59a">busiest week · {peak}</text>
</svg>
"""


# -----------------------------------------------------------------------------
# Craft: how I contribute, and where
# -----------------------------------------------------------------------------

KINDS = [  # (field, label, colour)
    ("totalCommitContributions",            "Commits",       "#ffd59a"),
    ("totalPullRequestContributions",       "Pull requests", "#e9a07a"),
    ("totalPullRequestReviewContributions", "Code reviews",  "#b8a9e6"),
    ("totalIssueContributions",             "Issues",        "#8fc4ef"),
]


def arc(cx: float, cy: float, r: float, start: float, end: float) -> str:
    """SVG arc from angle `start` to `end` (radians, 0 = 12 o'clock, clockwise)."""
    x1, y1 = cx + r * math.sin(start), cy - r * math.cos(start)
    x2, y2 = cx + r * math.sin(end), cy - r * math.cos(end)
    large = 1 if end - start > math.pi else 0
    return f"M{x1:.1f},{y1:.1f} A{r},{r} 0 {large} 1 {x2:.1f},{y2:.1f}"


def render_craft(collection: dict) -> str:
    height = 320

    # How I contribute: a ring split by kind of contribution
    counts = [(label, colour, collection[field]) for field, label, colour in KINDS]
    total = sum(count for _, _, count in counts) or 1
    cx, cy, r, gap = 150, 186, 70, 0.04

    angle, ring, legend = 0.0, [], []
    for i, (label, colour, count) in enumerate(counts):
        sweep = 2 * math.pi * count / total
        if count:
            ring.append(f'<path d="{arc(cx, cy, r, angle + gap / 2, angle + sweep - gap / 2)}" fill="none" stroke="{colour}" stroke-width="18" stroke-linecap="round"/>')
        angle += sweep

        y = 128 + i * 34
        legend.append(f"""
  <circle cx="262" cy="{y - 4}" r="6" fill="{colour}"/>
  <text x="276" y="{y}" font-size="14" fill="#e3e6f3">{label}</text>
  <text x="490" y="{y}" font-size="14" fill="#fff6e6" text-anchor="end" font-weight="700">{count:,}</text>
  <text x="530" y="{y}" font-size="12" fill="#8f98c4" text-anchor="end">{round(100 * count / total)}%</text>""")

    # Where my footprints led: top repositories, special repos left out
    repos = [r for r in collection["commitContributionsByRepository"] if not is_special_repo(r["repository"])][:5]
    top = max((r["contributions"]["totalCount"] for r in repos), default=1)
    bx, bw = 640, 470

    bars = []
    for i, repo in enumerate(repos):
        y = 124 + i * 36
        count = repo["contributions"]["totalCount"]
        width = max(8, bw * count / top)
        bars.append(f"""
  <text x="{bx}" y="{y - 8}" font-size="13" fill="#e3e6f3">{repo["repository"]["nameWithOwner"]}</text>
  <rect x="{bx}" y="{y - 2}" width="{bw}" height="8" rx="4" fill="#4a5590" opacity="0.35"/>
  <rect x="{bx}" y="{y - 2}" width="{width:.1f}" height="8" rx="4" fill="url(#bar)"/>
  <circle cx="{bx + width:.1f}" cy="{y + 2}" r="7" fill="url(#dot)"/>
  <text x="{bx + bw + 20}" y="{y + 6}" font-size="14" font-weight="700" fill="#fff6e6">{count:,}</text>""")

    if not repos:
        bars.append(f'<text x="{bx}" y="140" font-size="13" fill="#8f98c4">No public repositories yet this year.</text>')

    summary = ", ".join(f"{count:,} {label.lower()}" for label, _, count in counts)
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{height}" viewBox="0 0 {WIDTH} {height}" font-family="{FONT}">
  <title>How I contribute: {summary}. Where: {", ".join(r["repository"]["nameWithOwner"] for r in repos) or "no public repositories yet"}.</title>
  <defs>
    <linearGradient id="sky" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="#141c3a"/><stop offset="0.7" stop-color="#2c3770"/><stop offset="1" stop-color="#5a4d84"/>
    </linearGradient>
    <linearGradient id="bar" x1="0" y1="0" x2="1" y2="0">
      <stop offset="0" stop-color="#e9a07a"/><stop offset="1" stop-color="#ffd59a"/>
    </linearGradient>
    <radialGradient id="dot" cx="0.5" cy="0.5" r="0.5">
      <stop offset="0" stop-color="#fff6d8"/><stop offset="0.4" stop-color="#ffd59a" stop-opacity="0.8"/><stop offset="1" stop-color="#ffd27a" stop-opacity="0"/>
    </radialGradient>
  </defs>
  <rect x="0.5" y="0.5" width="{WIDTH - 1}" height="{height - 1}" rx="16" fill="url(#sky)" stroke="#2a3360"/>

  <!-- How I contribute -->
  <text x="48" y="58" font-family="{SERIF}" font-size="24" font-weight="600" fill="#fff6e6">How I contribute</text>
  <text x="48" y="82" font-family="{SERIF}" font-style="italic" font-size="14" fill="#ffd59a">not only writing, but reviewing and asking too</text>
  <circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="#4a5590" stroke-opacity="0.3" stroke-width="18"/>
  {"".join(ring)}
  <text x="{cx}" y="{cy + 2}" text-anchor="middle" font-family="{SERIF}" font-size="28" font-weight="600" fill="#fff6e6">{total:,}</text>
  <text x="{cx}" y="{cy + 22}" text-anchor="middle" font-size="11" fill="#c9cfe8">this year</text>
  {"".join(legend)}

  <line x1="590" y1="48" x2="590" y2="{height - 40}" stroke="#4a5590" stroke-opacity="0.5"/>

  <!-- Where my footprints led -->
  <text x="{bx}" y="58" font-family="{SERIF}" font-size="24" font-weight="600" fill="#fff6e6">Where my footprints led</text>
  <text x="{bx}" y="82" font-family="{SERIF}" font-style="italic" font-size="14" fill="#ffd59a">the shores I kept returning to, by commits</text>
  {"".join(bars)}
</svg>
"""


# -----------------------------------------------------------------------------
# Rhythm: contributions by day of the week
# -----------------------------------------------------------------------------

DAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]
DAYS_PLURAL = ["Sundays", "Mondays", "Tuesdays", "Wednesdays", "Thursdays", "Fridays", "Saturdays"]


def render_rhythm(calendar: dict) -> str:
    height = 280

    totals = [0] * 7
    for week in calendar["weeks"]:
        for day in week["contributionDays"]:
            totals[date.fromisoformat(day["date"]).isoweekday() % 7] += day["contributionCount"]

    total = sum(totals) or 1
    peak = max(totals) or 1
    busiest = totals.index(peak)
    weekend = round(100 * (totals[0] + totals[6]) / total)

    # One pillar of light per weekday; the busiest glows gold
    left, gap, bw, base, tall = 560, 92, 40, 232, 150
    pillars = []
    for i, count in enumerate(totals):
        x = left + i * gap
        h = max(6, tall * count / peak)
        is_peak = i == busiest
        pillars.append(f"""
  <rect x="{x}" y="{base - tall}" width="{bw}" height="{tall}" rx="20" fill="#4a5590" opacity="0.22"/>
  <rect x="{x}" y="{base - h:.1f}" width="{bw}" height="{h:.1f}" rx="20" fill="url({'#peak' if is_peak else '#pillar'})"/>
  <text x="{x + bw / 2}" y="{base - h - 10:.1f}" text-anchor="middle" font-size="12" font-weight="700" fill="{'#fff6e6' if is_peak else '#c9cfe8'}">{count}</text>
  <text x="{x + bw / 2}" y="{base + 22}" text-anchor="middle" font-size="12" fill="{'#ffd59a' if is_peak else '#8f98c4'}">{DAYS[i]}</text>""")

    peak_x = left + busiest * gap + bw / 2
    peak_y = base - tall - 40

    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{height}" viewBox="0 0 {WIDTH} {height}" font-family="{FONT}">
  <title>My rhythm: contributions by day of the week over the past year. Most active on {DAYS_PLURAL[busiest]}; {weekend}% on weekends.</title>
  <defs>
    <linearGradient id="sky" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="#141c3a"/><stop offset="0.7" stop-color="#2c3770"/><stop offset="1" stop-color="#5a4d84"/>
    </linearGradient>
    <linearGradient id="pillar" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="#b8a9e6"/><stop offset="1" stop-color="#6d5a92"/>
    </linearGradient>
    <linearGradient id="peak" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="#ffd59a"/><stop offset="1" stop-color="#e9a07a"/>
    </linearGradient>
    {GLOW}
  </defs>
  <rect x="0.5" y="0.5" width="{WIDTH - 1}" height="{height - 1}" rx="16" fill="url(#sky)" stroke="#2a3360"/>

  <text x="48" y="58" font-family="{SERIF}" font-size="24" font-weight="600" fill="#fff6e6">My rhythm</text>
  <text x="48" y="82" font-family="{SERIF}" font-style="italic" font-size="14" fill="#ffd59a">every week has its own tide</text>

  <text x="48" y="150" font-family="{SERIF}" font-size="40" font-weight="600" fill="#ffd59a">{DAYS_PLURAL[busiest]}</text>
  <text x="48" y="174" font-size="14" fill="#c9cfe8">when I'm most at work</text>
  <line x1="48" y1="196" x2="420" y2="196" stroke="#4a5590" stroke-opacity="0.6"/>
  <text x="48" y="232" font-family="{SERIF}" font-size="28" font-weight="600" fill="#fff6e6">{100 - weekend}% · {weekend}%</text>
  <text x="48" y="254" font-size="13" fill="#c9cfe8">weekdays · weekends</text>

  {"".join(pillars)}
  {butterfly(peak_x, peak_y, 0.75)}
</svg>
"""


# -----------------------------------------------------------------------------
# Entry point
# -----------------------------------------------------------------------------

if __name__ == "__main__":
    login, output_dir = sys.argv[1], sys.argv[2]
    collection = fetch_contributions(login, os.environ["GITHUB_TOKEN"])
    calendar = collection["contributionCalendar"]

    images = {
        "tide.svg": render_tide(calendar),
        "craft.svg": render_craft(collection),
        "rhythm.svg": render_rhythm(calendar),
    }

    os.makedirs(output_dir, exist_ok=True)
    for name, svg in images.items():
        with open(os.path.join(output_dir, name), "w", encoding="utf-8") as file:
            file.write(svg)

    print(f"Wrote {', '.join(images)} ({calendar['totalContributions']} contributions)")
