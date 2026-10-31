"""
Draws the "Footprints" images for the profile README from the GitHub contribution calendar.

  tide.svg        Headline numbers and a weekly "tide" of contributions over the past year,
                  with a butterfly of light marking the busiest week.
  lanterns.svg    The last twelve months as paper lanterns floating over the sea at night:
                  busier months float higher and glow brighter.

Usage:
    GITHUB_TOKEN=... python footprints.py <username> <output-directory>

Uses only the Python standard library.
"""

import json
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
      contributionCalendar {
        totalContributions
        weeks { contributionDays { date contributionCount } }
      }
    }
  }
}
"""


def fetch_calendar(login: str, token: str) -> dict:
    """Returns the contribution calendar for the past year from the GitHub GraphQL API."""
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

    return payload["data"]["user"]["contributionsCollection"]["contributionCalendar"]


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
# Lanterns: one per month, floating over the sea
# -----------------------------------------------------------------------------

def lantern(x: float, y: float, glow: float, month: str, count: int, sea: float) -> str:
    """A paper lantern at (x, y) with a string down to the water, its reflection, and labels."""
    return f"""
  <!-- {month} -->
  <line x1="{x:.1f}" y1="{y + 30:.1f}" x2="{x:.1f}" y2="{sea:.1f}" stroke="#ffd59a" stroke-opacity="{0.15 + glow * 0.25:.2f}" stroke-dasharray="1 4"/>
  <circle cx="{x:.1f}" cy="{y:.1f}" r="{34 + glow * 26:.0f}" fill="url(#lanternglow)" opacity="{0.25 + glow * 0.65:.2f}"/>
  <rect x="{x - 11:.1f}" y="{y - 30:.1f}" width="22" height="5" rx="2" fill="#5a3b2a"/>
  <rect x="{x - 17:.1f}" y="{y - 26:.1f}" width="34" height="50" rx="14" fill="url(#paper)" opacity="{0.55 + glow * 0.45:.2f}"/>
  <g stroke="#c9733f" stroke-opacity="0.35">
    <line x1="{x - 14:.1f}" x2="{x + 14:.1f}" y1="{y - 12:.1f}" y2="{y - 12:.1f}"/>
    <line x1="{x - 16:.1f}" x2="{x + 16:.1f}" y1="{y:.1f}" y2="{y:.1f}"/>
    <line x1="{x - 14:.1f}" x2="{x + 14:.1f}" y1="{y + 12:.1f}" y2="{y + 12:.1f}"/>
  </g>
  <rect x="{x - 11:.1f}" y="{y + 24:.1f}" width="22" height="5" rx="2" fill="#5a3b2a"/>
  <text x="{x:.1f}" y="{y + 5:.1f}" text-anchor="middle" font-size="12" font-weight="700" fill="#6b3a1e">{count}</text>
  <ellipse cx="{x:.1f}" cy="{sea + 18:.1f}" rx="{8 + glow * 10:.1f}" ry="3" fill="#ffd59a" opacity="{0.15 + glow * 0.4:.2f}"/>
  <text x="{x:.1f}" y="{sea + 44:.1f}" text-anchor="middle" font-size="12" fill="#c9cfe8">{month}</text>"""


def render_lanterns(calendar: dict) -> str:
    height = 340
    sea = 250                     # waterline
    highest, lowest = 116, 200     # lantern centre for the busiest / quietest month

    months = monthly_totals(calendar)
    peak = max(count for _, count in months) or 1
    gap = (WIDTH - 2 * 80) / (len(months) - 1)

    lanterns = []
    for i, (month, count) in enumerate(months):
        glow = count / peak
        x = 80 + i * gap
        y = lowest - glow * (lowest - highest)
        label = date.fromisoformat(month + "-01").strftime("%b")
        lanterns.append(lantern(x, y, glow, label, count, sea))

    busiest = max(months, key=lambda m: m[1])
    busiest_label = date.fromisoformat(busiest[0] + "-01").strftime("%B %Y")

    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{height}" viewBox="0 0 {WIDTH} {height}" font-family="{FONT}">
  <title>The last twelve months as lanterns floating over the sea; busier months float higher and glow brighter. Brightest: {busiest_label}.</title>
  <defs>
    <linearGradient id="night" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="#0d1330"/><stop offset="1" stop-color="#2d3a6e"/>
    </linearGradient>
    <linearGradient id="sea" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="#1f2b58"/><stop offset="1" stop-color="#0e1430"/>
    </linearGradient>
    <linearGradient id="paper" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="#fff1d6"/><stop offset="0.6" stop-color="#ffc98a"/><stop offset="1" stop-color="#f29a5a"/>
    </linearGradient>
    <radialGradient id="lanternglow" cx="0.5" cy="0.5" r="0.5">
      <stop offset="0" stop-color="#ffcf8a" stop-opacity="0.8"/><stop offset="1" stop-color="#ff9f5a" stop-opacity="0"/>
    </radialGradient>
    <clipPath id="frame"><rect width="{WIDTH}" height="{height}" rx="16"/></clipPath>
  </defs>

  <g clip-path="url(#frame)">
    <rect width="{WIDTH}" height="{sea}" fill="url(#night)"/>
    <rect y="{sea}" width="{WIDTH}" height="{height - sea}" fill="url(#sea)"/>
    <g fill="#ffffff">
      <circle cx="420" cy="44" r="1.2" opacity="0.6"/><circle cx="520" cy="28" r="1" opacity="0.5"/>
      <circle cx="760" cy="52" r="1.3" opacity="0.6"/><circle cx="1010" cy="34" r="1" opacity="0.5"/>
      <circle cx="1180" cy="60" r="1.1" opacity="0.5"/>
    </g>
  </g>

  <text x="48" y="54" font-family="{SERIF}" font-size="24" font-weight="600" fill="#fff6e6">A year of lanterns</text>
  <text x="48" y="78" font-family="{SERIF}" font-style="italic" font-size="14" fill="#ffd59a">one for each month; the brighter it glows, the more it held</text>
  {"".join(lanterns)}

  <rect x="0.5" y="0.5" width="{WIDTH - 1}" height="{height - 1}" rx="16" fill="none" stroke="#2a3360"/>
</svg>
"""


# -----------------------------------------------------------------------------
# Entry point
# -----------------------------------------------------------------------------

if __name__ == "__main__":
    login, output_dir = sys.argv[1], sys.argv[2]
    calendar = fetch_calendar(login, os.environ["GITHUB_TOKEN"])

    os.makedirs(output_dir, exist_ok=True)
    for name, svg in (("tide.svg", render_tide(calendar)), ("lanterns.svg", render_lanterns(calendar))):
        with open(os.path.join(output_dir, name), "w", encoding="utf-8") as file:
            file.write(svg)

    print(f"Wrote tide.svg and lanterns.svg ({calendar['totalContributions']} contributions)")
