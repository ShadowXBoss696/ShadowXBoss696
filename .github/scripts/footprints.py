"""
Draws the "Footprints" image for the profile README.

Every day with contributions over the past year becomes a butterfly of light
over a summer-dusk sky: busier days are larger and brighter, quiet days stay
as faint specks. The butterflies drift and flap gently via CSS animation.

Usage:
    GITHUB_TOKEN=... python footprints.py <username> <output.svg>

Uses only the Python standard library.
"""

import hashlib
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
        weeks {
          contributionDays { date contributionCount contributionLevel }
        }
      }
    }
  }
}
"""

LEVELS = {
    "NONE": 0,
    "FIRST_QUARTILE": 1,
    "SECOND_QUARTILE": 2,
    "THIRD_QUARTILE": 3,
    "FOURTH_QUARTILE": 4,
}


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


# -----------------------------------------------------------------------------
# Drawing
# -----------------------------------------------------------------------------

WIDTH, HEIGHT = 1280, 320
GRID_X, GRID_Y = 48, 118          # top-left of the first day
PITCH = (WIDTH - 2 * GRID_X) / 53  # space per week column / day row

# Per level: (scale, upper wing colour, lower wing colour, glow opacity)
BUTTERFLY = {
    1: (0.30, "#c9bfe6", "#9a8cc4", 0.25),
    2: (0.38, "#f3c6b0", "#e9a07a", 0.40),
    3: (0.46, "#ffe3a6", "#f2b866", 0.55),
    4: (0.54, "#fff4d2", "#ffd59a", 0.75),
}

STYLE = """
  .float { animation: float 6s ease-in-out infinite; transform-box: fill-box; transform-origin: center; }
  .wing  { animation: flap 1.8s ease-in-out infinite; transform-box: fill-box; transform-origin: center; }
  @keyframes float { 0%, 100% { transform: translateY(0); } 50% { transform: translateY(-3px); } }
  @keyframes flap  { 0%, 100% { transform: scaleX(1); } 50% { transform: scaleX(0.72); } }
"""


def jitter(key: str, spread: float) -> float:
    """Stable pseudo-random offset in [-spread, spread] for a given key (same day → same value)."""
    digest = hashlib.sha1(key.encode()).digest()
    return (digest[0] / 255 * 2 - 1) * spread


def butterfly(x: float, y: float, level: int, key: str) -> str:
    """One butterfly of light at (x, y), sized and coloured by contribution level."""
    scale, upper, lower, glow = BUTTERFLY[level]
    rotate = jitter(key + "r", 18)
    delay = abs(jitter(key + "d", 6))

    return f"""
  <g transform="translate({x:.1f} {y:.1f}) rotate({rotate:.0f}) scale({scale})">
    <g class="float" style="animation-delay:-{delay:.2f}s">
      <circle r="22" fill="url(#glow)" opacity="{glow}"/>
      <g class="wing" style="animation-delay:-{delay / 3:.2f}s">
        <path d="M0,0 C-3,-10 -14,-15 -16,-8 C-17,-2 -8,1 0,0 Z" fill="{upper}"/>
        <path d="M0,0 C3,-10 14,-15 16,-8 C17,-2 8,1 0,0 Z" fill="{upper}"/>
        <path d="M0,0 C-6,2 -12,6 -10,10 C-7,13 -2,8 0,0 Z" fill="{lower}"/>
        <path d="M0,0 C6,2 12,6 10,10 C7,13 2,8 0,0 Z" fill="{lower}"/>
      </g>
    </g>
  </g>"""


def speck(x: float, y: float) -> str:
    """A quiet day: a faint speck in the sky."""
    return f'\n  <circle cx="{x:.1f}" cy="{y:.1f}" r="1.6" fill="#4a5590" opacity="0.7"/>'


def month_labels(weeks: list) -> str:
    """Month names above the first week in which each month starts."""
    labels, last_month = [], None

    for column, week in enumerate(weeks):
        first_day = date.fromisoformat(week["contributionDays"][0]["date"])
        if first_day.month != last_month and first_day.day <= 7:
            x = GRID_X + column * PITCH
            labels.append(f'<text x="{x:.1f}" y="{GRID_Y - 18}">{first_day.strftime("%b")}</text>')
            last_month = first_day.month

    return '\n  <g font-size="11" fill="#8f98c4">' + "".join(labels) + "</g>"


def legend() -> str:
    """'Quiet … busy' scale in the bottom-right corner."""
    x, y = WIDTH - 250, HEIGHT - 28
    parts = [f'<text x="{x}" y="{y + 4}" font-size="11" fill="#8f98c4">quiet</text>', speck(x + 46, y)]
    for i, level in enumerate((1, 2, 3, 4)):
        parts.append(butterfly(x + 72 + i * 28, y, level, f"legend{level}"))
    parts.append(f'<text x="{x + 196}" y="{y + 4}" font-size="11" fill="#8f98c4">busy</text>')
    return "".join(parts)


def render(calendar: dict) -> str:
    """Builds the full SVG for a contribution calendar."""
    weeks = calendar["weeks"]
    total = calendar["totalContributions"]

    days = []
    for column, week in enumerate(weeks):
        for day in week["contributionDays"]:
            row = date.fromisoformat(day["date"]).isoweekday() % 7   # Sunday = 0
            x = GRID_X + column * PITCH + PITCH / 2
            y = GRID_Y + row * PITCH + PITCH / 2
            level = LEVELS.get(day["contributionLevel"], 0)
            days.append(speck(x, y) if level == 0 else butterfly(x, y, level, day["date"]))

    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{HEIGHT}" viewBox="0 0 {WIDTH} {HEIGHT}" font-family="'DM Sans', -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif">
  <title>Footprints this past year: {total} contributions, each busy day drawn as a butterfly of light over a summer dusk.</title>
  <style>{STYLE}</style>
  <defs>
    <linearGradient id="sky" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="#141c3a"/>
      <stop offset="0.7" stop-color="#2c3770"/>
      <stop offset="1" stop-color="#5a4d84"/>
    </linearGradient>
    <radialGradient id="glow" cx="0.5" cy="0.5" r="0.5">
      <stop offset="0" stop-color="#fff6d8" stop-opacity="0.9"/>
      <stop offset="1" stop-color="#ffd27a" stop-opacity="0"/>
    </radialGradient>
  </defs>

  <rect x="0.5" y="0.5" width="{WIDTH - 1}" height="{HEIGHT - 1}" rx="16" fill="url(#sky)" stroke="#2a3360"/>

  <text x="48" y="58" font-family="Literata, Georgia, 'Times New Roman', serif" font-size="26" font-weight="600" fill="#fff6e6">Footprints this past year</text>
  <text x="48" y="84" font-family="Literata, Georgia, 'Times New Roman', serif" font-style="italic" font-size="15" fill="#ffd59a">{total:,} contributions, each one a small summer kept</text>
  {month_labels(weeks)}
  {"".join(days)}
  {legend()}
</svg>
"""


# -----------------------------------------------------------------------------
# Entry point
# -----------------------------------------------------------------------------

if __name__ == "__main__":
    login, output_path = sys.argv[1], sys.argv[2]
    calendar = fetch_calendar(login, os.environ["GITHUB_TOKEN"])

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as file:
        file.write(render(calendar))

    print(f"Wrote {output_path} ({calendar['totalContributions']} contributions)")
