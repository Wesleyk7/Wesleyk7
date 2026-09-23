from __future__ import annotations

import datetime as dt
import html
import json
import math
import os
import urllib.request
from collections import defaultdict
from pathlib import Path

USERNAME = os.getenv("GITHUB_USERNAME", "Wesleyk7")
TOKEN = os.environ["GITHUB_TOKEN"]
OUT = Path("assets/telemetry.svg")

# Ajuste estes valores se quiser mudar a matriz de foco.
FOCUS = {
    "Suporte": 92,
    "Infra": 88,
    "Dev": 68,
    "Aprendizado": 96,
}


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
        " totalCommitContributions totalIssueContributions totalPullRequestContributions"
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


def points_for_radar(cx, cy, radius, values):
    pts = []
    n = len(values)
    for i, value in enumerate(values):
        angle = -math.pi / 2 + 2 * math.pi * i / n
        r = radius * value / 100.0
        pts.append(f"{cx + math.cos(angle)*r:.1f},{cy + math.sin(angle)*r:.1f}")
    return " ".join(pts)


def radar_grid(cx, cy, radius, count):
    out = []
    for level in (0.25, 0.5, 0.75, 1.0):
        pts = points_for_radar(cx, cy, radius * level, [100] * count)
        out.append(f'<polygon points="{pts}" fill="none" stroke="#1f3855" stroke-width="1"/>')
    for i in range(count):
        angle = -math.pi / 2 + 2 * math.pi * i / count
        x = cx + math.cos(angle) * radius
        y = cy + math.sin(angle) * radius
        out.append(f'<line x1="{cx}" y1="{cy}" x2="{x:.1f}" y2="{y:.1f}" stroke="#172a40" stroke-width="1"/>')
    return "\n".join(out)


def render_svg(user, repos, languages, contrib):
    W, H = 1200, 650
    BG = "#08111d"
    PANEL = "#0b1624"
    BORDER = "#17324f"
    TEXT = "#e8eef7"
    MUTED = "#8da1b8"
    BLUE = "#238cff"
    CYAN = "#49c7ff"
    ORANGE = "#ff8a24"
    GREEN = "#42d17d"

    top_langs = sorted(languages.items(), key=lambda x: x[1], reverse=True)[:5]
    lang_total = sum(v for _, v in top_langs) or 1

    calendar = contrib["contributionCalendar"]
    month_totals = defaultdict(int)
    active_days = 0

    for week in calendar["weeks"]:
        for day in week["contributionDays"]:
            count = int(day["contributionCount"])
            date = dt.date.fromisoformat(day["date"])
            month_totals[date.strftime("%Y-%m")] += count
            if count > 0:
                active_days += 1

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
    total_contrib = int(calendar.get("totalContributions", 0))
    total_commits = int(contrib.get("totalCommitContributions", 0))
    public_repos = int(user.get("public_repos", len(repos)))
    followers = int(user.get("followers", 0))

    parts = []
    a = parts.append

    a(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">')
    a(f'<rect width="{W}" height="{H}" rx="22" fill="{BG}"/>')
    a(f'<rect x="1" y="1" width="{W-2}" height="{H-2}" rx="21" fill="none" stroke="{BORDER}"/>')

    a(f'<text x="38" y="48" font-family="Segoe UI,Arial" font-size="28" font-weight="700" fill="{TEXT}">PROFILE TELEMETRY</text>')
    a(f'<text x="38" y="72" font-family="Segoe UI,Arial" font-size="12" fill="{MUTED}">@{esc(USERNAME)} • atualizado automaticamente</text>')

    metrics = [
        ("REPOSITÓRIOS", public_repos, BLUE),
        ("CONTRIBUIÇÕES", total_contrib, ORANGE),
        ("COMMITS", total_commits, CYAN),
        ("DIAS ATIVOS", active_days, GREEN),
    ]

    for i, (label, value, accent) in enumerate(metrics):
        x = 38 + i * 282
        a(f'<rect x="{x}" y="96" width="266" height="92" rx="14" fill="{PANEL}" stroke="{BORDER}"/>')
        a(f'<rect x="{x}" y="96" width="5" height="92" rx="3" fill="{accent}"/>')
        a(f'<text x="{x+20}" y="126" font-family="Segoe UI,Arial" font-size="11" font-weight="600" fill="{MUTED}">{esc(label)}</text>')
        a(f'<text x="{x+20}" y="164" font-family="Segoe UI,Arial" font-size="27" font-weight="800" fill="{TEXT}">{value}</text>')

    # Language telemetry panel
    a(f'<rect x="38" y="214" width="540" height="250" rx="16" fill="{PANEL}" stroke="{BORDER}"/>')
    a(f'<text x="62" y="244" font-family="Segoe UI,Arial" font-size="15" font-weight="700" fill="{TEXT}">LANGUAGE TELEMETRY</text>')
    a(f'<text x="62" y="266" font-family="Segoe UI,Arial" font-size="12" fill="{MUTED}">seus repositórios públicos próprios</text>')

    colors = [BLUE, ORANGE, CYAN, "#7b61ff", GREEN]
    if top_langs:
        for i, (name, amount) in enumerate(top_langs):
            pct = amount / lang_total
            y = 302 + i * 34
            a(f'<text x="62" y="{y}" font-family="Segoe UI,Arial" font-size="14" font-weight="600" fill="{TEXT}">{esc(name)}</text>')
            a(f'<rect x="180" y="{y-13}" width="330" height="12" rx="6" fill="#12263d"/>')
            a(f'<rect x="180" y="{y-13}" width="{330*pct:.1f}" height="12" rx="6" fill="{colors[i]}"/>')
            a(f'<text x="520" y="{y}" text-anchor="end" font-family="Segoe UI,Arial" font-size="12" fill="{MUTED}">{pct*100:.1f}%</text>')
    else:
        a(f'<text x="62" y="320" font-family="Segoe UI,Arial" font-size="12" fill="{MUTED}">Ainda não há linguagens detectáveis.</text>')

    # Focus radar
    a(f'<rect x="596" y="214" width="566" height="250" rx="16" fill="{PANEL}" stroke="{BORDER}"/>')
    a(f'<text x="620" y="244" font-family="Segoe UI,Arial" font-size="15" font-weight="700" fill="{TEXT}">FOCUS MATRIX</text>')
    a(f'<text x="620" y="266" font-family="Segoe UI,Arial" font-size="12" fill="{MUTED}">ênfase atual • editável no script</text>')

    cx, cy, radius = 790, 360, 82
    values = list(FOCUS.values())
    labels = list(FOCUS.keys())
    a(radar_grid(cx, cy, radius, len(values)))
    radar_pts = points_for_radar(cx, cy, radius, values)
    a(f'<polygon points="{radar_pts}" fill="{BLUE}" fill-opacity=".22" stroke="{BLUE}" stroke-width="2"/>')

    for i, label in enumerate(labels):
        angle = -math.pi / 2 + 2 * math.pi * i / len(labels)
        lx = cx + math.cos(angle) * (radius + 30)
        ly = cy + math.sin(angle) * (radius + 30)
        anchor = "middle"
        if math.cos(angle) > 0.3:
            anchor = "start"
        elif math.cos(angle) < -0.3:
            anchor = "end"
        a(f'<text x="{lx:.1f}" y="{ly:.1f}" text-anchor="{anchor}" font-family="Segoe UI,Arial" font-size="11" fill="{MUTED}">{esc(label)}</text>')

    # Activity pulse
    a(f'<rect x="38" y="486" width="1124" height="126" rx="16" fill="{PANEL}" stroke="{BORDER}"/>')
    a(f'<text x="62" y="516" font-family="Segoe UI,Arial" font-size="15" font-weight="700" fill="{TEXT}">ACTIVITY PULSE • 12 MESES</text>')
    a(f'<text x="1140" y="516" text-anchor="end" font-family="Segoe UI,Arial" font-size="12" fill="{MUTED}">{followers} seguidores • {len(languages)} linguagens</text>')

    max_month = max((v for _, _, v in months), default=1) or 1
    chart_x, chart_y, chart_w, chart_h = 62, 542, 690, 48
    gap = 8
    bw = (chart_w - gap * 11) / 12

    for i, (_, label, value) in enumerate(months):
        h = max(3, chart_h * value / max_month)
        x = chart_x + i * (bw + gap)
        y = chart_y + chart_h - h
        color = BLUE if i < 6 else ORANGE
        a(f'<rect x="{x:.1f}" y="{y:.1f}" width="{bw:.1f}" height="{h:.1f}" rx="4" fill="{color}"/>')
        a(f'<text x="{x+bw/2:.1f}" y="606" text-anchor="middle" font-family="Segoe UI,Arial" font-size="10" fill="{MUTED}">{label}</text>')

    # Recent projects
    a(f'<text x="794" y="548" font-family="Segoe UI,Arial" font-size="15" font-weight="700" fill="{TEXT}">RECENT PROJECTS</text>')
    if recent:
        for i, repo in enumerate(recent):
            y = 573 + i * 19
            desc = repo.get("description") or "sem descrição"
            short = (desc[:42] + "…") if len(desc) > 43 else desc
            a(f'<text x="794" y="{y}" font-family="Segoe UI,Arial" font-size="13" font-weight="600" fill="{TEXT}">{esc(repo["name"])}</text>')
            a(f'<text x="930" y="{y}" font-family="Segoe UI,Arial" font-size="11" fill="{MUTED}">{esc(short)}</text>')

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
