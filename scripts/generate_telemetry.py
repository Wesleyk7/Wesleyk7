from __future__ import annotations

import datetime as dt
import html
import json
import os
import urllib.request
from collections import defaultdict
from pathlib import Path

USERNAME = os.getenv("GITHUB_USERNAME", "Wesleyk7")
TOKEN = os.environ["GITHUB_TOKEN"]
OUT = Path("assets/telemetry.svg")

# Só coisas que você já está estudando/praticando.
CURRENT_SKILLS = [
    ("HTML", "estudando"),
    ("CSS", "estudando"),
    ("Python", "básico"),
    ("Git & GitHub", "praticando"),
]

# Áreas de interesse, sem fingir que já domina.
INTERESTS = [
    "Suporte Técnico",
    "Infraestrutura",
]


def request_json(url: str, method: str = "GET", body: dict | None = None):
    headers = {
        "Authorization": f"Bearer {TOKEN}",
        "Accept": "application/vnd.github+json",
        "User-Agent": "profile-telemetry-action",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    data = None
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"

    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def esc(value) -> str:
    return html.escape(str(value), quote=True)


def fetch_user():
    return request_json(f"https://api.github.com/users/{USERNAME}")


def fetch_repos():
    repos = []
    page = 1
    while True:
        batch = request_json(
            f"https://api.github.com/users/{USERNAME}/repos"
            f"?per_page=100&page={page}&type=owner&sort=updated"
        )
        if not batch:
            break
        repos.extend(batch)
        if len(batch) < 100:
            break
        page += 1
    return [r for r in repos if not r.get("fork") and not r.get("archived")]


def fetch_language_totals(repos):
    totals = defaultdict(int)
    for repo in repos:
        try:
            langs = request_json(repo["languages_url"])
        except Exception:
            continue
        for language, amount in langs.items():
            totals[language] += int(amount)
    return dict(totals)


def fetch_contributions():
    now = dt.datetime.now(dt.timezone.utc)
    start = now - dt.timedelta(days=365)

    query = (
        "query($login: String!, $from: DateTime!, $to: DateTime!) {"
        " user(login: $login) {"
        " contributionsCollection(from: $from, to: $to) {"
        " contributionCalendar { totalContributions weeks { contributionDays { date contributionCount } } }"
        " }"
        " }"
        " }"
    )

    payload = {
        "query": query,
        "variables": {
            "login": USERNAME,
            "from": start.isoformat().replace("+00:00", "Z"),
            "to": now.isoformat().replace("+00:00", "Z"),
        },
    }

    response = request_json(
        "https://api.github.com/graphql",
        method="POST",
        body=payload,
    )
    if response.get("errors"):
        raise RuntimeError(response["errors"])
    return response["data"]["user"]["contributionsCollection"]


def render_svg(user, repos, languages, contrib):
    W, H = 1200, 650

    BG = "#08111d"
    PANEL = "#0b1624"
    PANEL_2 = "#0d1a2a"
    BORDER = "#17324f"
    TEXT = "#e8eef7"
    MUTED = "#8da1b8"
    BLUE = "#238cff"
    CYAN = "#49c7ff"
    ORANGE = "#ff8a24"
    GREEN = "#42d17d"
    PURPLE = "#8a63ff"

    top_langs = sorted(languages.items(), key=lambda x: x[1], reverse=True)[:5]
    lang_total = sum(v for _, v in top_langs) or 1

    calendar = contrib["contributionCalendar"]
    month_totals = defaultdict(int)

    for week in calendar["weeks"]:
        for day in week["contributionDays"]:
            count = int(day["contributionCount"])
            date = dt.date.fromisoformat(day["date"])
            month_totals[date.strftime("%Y-%m")] += count

    now = dt.datetime.now(dt.timezone.utc)
    months = []
    for delta in range(11, -1, -1):
        year = now.year
        month = now.month - delta
        while month <= 0:
            month += 12
            year -= 1
        key = f"{year:04d}-{month:02d}"
        label = dt.date(year, month, 1).strftime("%b")
        months.append((key, label, month_totals.get(key, 0)))

    recent = repos[:3]

    parts = []
    a = parts.append

    a(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">')
    a(f'<rect width="{W}" height="{H}" rx="22" fill="{BG}"/>')
    a(f'<rect x="1" y="1" width="{W-2}" height="{H-2}" rx="21" fill="none" stroke="{BORDER}"/>')

    # Header
    a(f'<text x="38" y="48" font-family="Segoe UI,Arial" font-size="28" font-weight="700" fill="{TEXT}">PROFILE TELEMETRY</text>')
    a(f'<text x="38" y="72" font-family="Segoe UI,Arial" font-size="12" fill="{MUTED}">@{esc(USERNAME)}</text>')
    # Top section: no cards, just a clean current-learning strip
    a(f'<rect x="38" y="96" width="1124" height="112" rx="16" fill="{PANEL}" stroke="{BORDER}"/>')
    a(f'<text x="62" y="128" font-family="Segoe UI,Arial" font-size="15" font-weight="700" fill="{TEXT}">ESTUDANDO AGORA</text>')
    skill_colors = [ORANGE, CYAN, GREEN, BLUE]
    x = 62
    for i, (name, status) in enumerate(CURRENT_SKILLS):
        w = 220 if name != "Git & GitHub" else 250
        a(f'<rect x="{x}" y="165" width="{w}" height="30" rx="15" fill="{PANEL_2}" stroke="{skill_colors[i]}" stroke-opacity=".8"/>')
        a(f'<circle cx="{x+16}" cy="180" r="4" fill="{skill_colors[i]}"/>')
        a(f'<text x="{x+30}" y="184" font-family="Segoe UI,Arial" font-size="12" font-weight="600" fill="{TEXT}">{esc(name)}</text>')
        a(f'<text x="{x+w-16}" y="184" text-anchor="end" font-family="Segoe UI,Arial" font-size="11" fill="{MUTED}">{esc(status)}</text>')
        x += w + 12

    # Left panel: language bars
    a(f'<rect x="38" y="232" width="540" height="252" rx="16" fill="{PANEL}" stroke="{BORDER}"/>')
    a(f'<text x="62" y="264" font-family="Segoe UI,Arial" font-size="15" font-weight="700" fill="{TEXT}">LANGUAGE TELEMETRY</text>')
    colors = [BLUE, ORANGE, CYAN, PURPLE, GREEN]
    if top_langs:
        for i, (name, amount) in enumerate(top_langs):
            pct = amount / lang_total
            y = 324 + i * 34
            a(f'<text x="62" y="{y}" font-family="Segoe UI,Arial" font-size="14" font-weight="600" fill="{TEXT}">{esc(name)}</text>')
            a(f'<rect x="180" y="{y-13}" width="330" height="12" rx="6" fill="#12263d"/>')
            a(f'<rect x="180" y="{y-13}" width="{330*pct:.1f}" height="12" rx="6" fill="{colors[i]}"/>')
            a(f'<text x="520" y="{y}" text-anchor="end" font-family="Segoe UI,Arial" font-size="12" fill="{MUTED}">{pct*100:.1f}%</text>')
    else:
        a(f'<text x="62" y="340" font-family="Segoe UI,Arial" font-size="12" fill="{MUTED}">Ainda não há linguagens detectáveis.</text>')

    # Right panel: what you know + interests
    a(f'<rect x="596" y="232" width="566" height="252" rx="16" fill="{PANEL}" stroke="{BORDER}"/>')
    a(f'<text x="620" y="264" font-family="Segoe UI,Arial" font-size="15" font-weight="700" fill="{TEXT}">MEU MOMENTO</text>')
    a(f'<text x="620" y="322" font-family="Segoe UI,Arial" font-size="12" font-weight="700" fill="{CYAN}">CONHECIMENTOS ATUAIS</text>')
    y = 348
    for name, status in CURRENT_SKILLS:
        a(f'<circle cx="628" cy="{y-4}" r="4" fill="{GREEN}"/>')
        a(f'<text x="642" y="{y}" font-family="Segoe UI,Arial" font-size="13" fill="{TEXT}">{esc(name)}</text>')
        a(f'<text x="840" y="{y}" font-family="Segoe UI,Arial" font-size="11" fill="{MUTED}">{esc(status)}</text>')
        y += 28

    a(f'<text x="905" y="322" font-family="Segoe UI,Arial" font-size="12" font-weight="700" fill="{ORANGE}">INTERESSES</text>')
    y2 = 350
    for interest in INTERESTS:
        a(f'<rect x="905" y="{y2-18}" width="210" height="30" rx="15" fill="{PANEL_2}" stroke="{ORANGE}" stroke-opacity=".7"/>')
        a(f'<text x="1010" y="{y2+2}" text-anchor="middle" font-family="Segoe UI,Arial" font-size="12" font-weight="600" fill="{TEXT}">{esc(interest)}</text>')
        y2 += 44

    # Bottom panel: monthly activity + recent projects
    a(f'<rect x="38" y="510" width="1124" height="112" rx="16" fill="{PANEL}" stroke="{BORDER}"/>')
    a(f'<text x="62" y="540" font-family="Segoe UI,Arial" font-size="15" font-weight="700" fill="{TEXT}">ACTIVITY PULSE • 12 MESES</text>')

    max_month = max((v for _, _, v in months), default=1) or 1
    chart_x, chart_y, chart_w, chart_h = 62, 558, 670, 44
    gap = 8
    bw = (chart_w - gap * 11) / 12

    for i, (_, label, value) in enumerate(months):
        h = max(3, chart_h * value / max_month)
        x = chart_x + i * (bw + gap)
        y = chart_y + chart_h - h
        color = BLUE if i < 8 else ORANGE
        a(f'<rect x="{x:.1f}" y="{y:.1f}" width="{bw:.1f}" height="{h:.1f}" rx="4" fill="{color}"/>')
        a(f'<text x="{x+bw/2:.1f}" y="616" text-anchor="middle" font-family="Segoe UI,Arial" font-size="10" fill="{MUTED}">{label}</text>')

    a(f'<text x="790" y="540" font-family="Segoe UI,Arial" font-size="15" font-weight="700" fill="{TEXT}">RECENT PROJECTS</text>')
    if recent:
        for i, repo in enumerate(recent):
            y = 566 + i * 18
            desc = repo.get("description") or ""
            short = (desc[:34] + "…") if len(desc) > 35 else desc
            a(f'<text x="790" y="{y}" font-family="Segoe UI,Arial" font-size="12" font-weight="600" fill="{TEXT}">{esc(repo["name"])}</text>')
            a(f'<text x="920" y="{y}" font-family="Segoe UI,Arial" font-size="10" fill="{MUTED}">{esc(short)}</text>')

    a("</svg>")
    return "\n".join(parts)


def main():
    OUT.parent.mkdir(parents=True, exist_ok=True)
    user = fetch_user()
    repos = fetch_repos()
    languages = fetch_language_totals(repos)
    contributions = fetch_contributions()
    OUT.write_text(render_svg(user, repos, languages, contributions), encoding="utf-8")
    print(f"Generated {OUT}")


if __name__ == "__main__":
    main()
