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

# Conhecimentos que você está estudando/praticando.
CURRENT_SKILLS = [
    ("HTML", "estudando"),
    ("CSS", "estudando"),
    ("Python", "básico"),
    ("Git & GitHub", "praticando"),
]

# Áreas que você tem interesse em aprender/explorar.
INTERESTS = [
    "Suporte Técnico",
    "Infraestrutura",
    "Desenvolvimento Web",
    "Full Stack",
    "Inteligência Artificial e Dados",
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

    req = urllib.request.Request(
        url,
        data=data,
        headers=headers,
        method=method,
    )

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

    return [
        repo
        for repo in repos
        if not repo.get("fork") and not repo.get("archived")
    ]


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
        " contributionCalendar {"
        " totalContributions"
        " weeks {"
        " contributionDays {"
        " date"
        " contributionCount"
        " }"
        " }"
        " }"
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

    top_langs = sorted(
        languages.items(),
        key=lambda item: item[1],
        reverse=True,
    )[:5]

    lang_total = sum(value for _, value in top_langs) or 1

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

        months.append(
            (
                key,
                label,
                month_totals.get(key, 0),
            )
        )

    recent = repos[:3]

    parts = []
    a = parts.append

    # Base do SVG
    a(
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'width="{W}" height="{H}" viewBox="0 0 {W} {H}">'
    )
    a(f'<rect width="{W}" height="{H}" rx="22" fill="{BG}"/>')
    a(
        f'<rect x="1" y="1" width="{W - 2}" height="{H - 2}" '
        f'rx="21" fill="none" stroke="{BORDER}"/>'
    )

    # Cabeçalho
    a(
        f'<text x="38" y="48" font-family="Segoe UI,Arial" '
        f'font-size="28" font-weight="700" fill="{TEXT}">'
        f'PROFILE TELEMETRY</text>'
    )
    a(
        f'<text x="38" y="72" font-family="Segoe UI,Arial" '
        f'font-size="12" fill="{MUTED}">@{esc(USERNAME)}</text>'
    )

    # ESTUDANDO AGORA
    a(
        f'<rect x="38" y="96" width="1124" height="112" '
        f'rx="16" fill="{PANEL}" stroke="{BORDER}"/>'
    )
    a(
        f'<text x="62" y="128" font-family="Segoe UI,Arial" '
        f'font-size="15" font-weight="700" fill="{TEXT}">'
        f'ESTUDANDO AGORA</text>'
    )

    skill_colors = [ORANGE, CYAN, GREEN, BLUE]
    x = 62

    for i, (name, status) in enumerate(CURRENT_SKILLS):
        width = 220 if name != "Git & GitHub" else 250

        a(
            f'<rect x="{x}" y="165" width="{width}" height="30" '
            f'rx="15" fill="{PANEL_2}" '
            f'stroke="{skill_colors[i]}" stroke-opacity=".8"/>'
        )
        a(
            f'<circle cx="{x + 16}" cy="180" r="4" '
            f'fill="{skill_colors[i]}"/>'
        )
        a(
            f'<text x="{x + 30}" y="184" '
            f'font-family="Segoe UI,Arial" font-size="12" '
            f'font-weight="600" fill="{TEXT}">{esc(name)}</text>'
        )
        a(
            f'<text x="{x + width - 16}" y="184" '
            f'text-anchor="end" font-family="Segoe UI,Arial" '
            f'font-size="11" fill="{MUTED}">{esc(status)}</text>'
        )

        x += width + 12

    # LANGUAGE TELEMETRY
    a(
        f'<rect x="38" y="232" width="540" height="252" '
        f'rx="16" fill="{PANEL}" stroke="{BORDER}"/>'
    )
    a(
        f'<text x="62" y="264" font-family="Segoe UI,Arial" '
        f'font-size="15" font-weight="700" fill="{TEXT}">'
        f'LANGUAGE TELEMETRY</text>'
    )

    colors = [BLUE, ORANGE, CYAN, PURPLE, GREEN]

    if top_langs:
        for i, (name, amount) in enumerate(top_langs):
            pct = amount / lang_total
            y_lang = 324 + i * 34

            a(
                f'<text x="62" y="{y_lang}" '
                f'font-family="Segoe UI,Arial" font-size="14" '
                f'font-weight="600" fill="{TEXT}">{esc(name)}</text>'
            )
            a(
                f'<rect x="180" y="{y_lang - 13}" '
                f'width="330" height="12" rx="6" fill="#12263d"/>'
            )
            a(
                f'<rect x="180" y="{y_lang - 13}" '
                f'width="{330 * pct:.1f}" height="12" rx="6" '
                f'fill="{colors[i]}"/>'
            )
            a(
                f'<text x="520" y="{y_lang}" text-anchor="end" '
                f'font-family="Segoe UI,Arial" font-size="12" '
                f'fill="{MUTED}">{pct * 100:.1f}%</text>'
            )

    else:
        a(
            f'<text x="62" y="340" font-family="Segoe UI,Arial" '
            f'font-size="12" fill="{MUTED}">'
            f'Ainda não há linguagens detectáveis.</text>'
        )

    # MEU MOMENTO
    a(
        f'<rect x="596" y="232" width="566" height="252" '
        f'rx="16" fill="{PANEL}" stroke="{BORDER}"/>'
    )
    a(
        f'<text x="620" y="264" font-family="Segoe UI,Arial" '
        f'font-size="15" font-weight="700" fill="{TEXT}">'
        f'MEU MOMENTO</text>'
    )

    # Conhecimentos atuais
    a(
        f'<text x="620" y="306" font-family="Segoe UI,Arial" '
        f'font-size="12" font-weight="700" fill="{CYAN}">'
        f'CONHECIMENTOS ATUAIS</text>'
    )

    y_skill = 338

    for name, status in CURRENT_SKILLS:
        a(
            f'<circle cx="628" cy="{y_skill - 4}" r="4" '
            f'fill="{GREEN}"/>'
        )
        a(
            f'<text x="642" y="{y_skill}" '
            f'font-family="Segoe UI,Arial" font-size="13" '
            f'fill="{TEXT}">{esc(name)}</text>'
        )
        a(
            f'<text x="815" y="{y_skill}" text-anchor="end" '
            f'font-family="Segoe UI,Arial" font-size="11" '
            f'fill="{MUTED}">{esc(status)}</text>'
        )

        y_skill += 28

    # Interesses
    a(
        f'<text x="875" y="306" font-family="Segoe UI,Arial" '
        f'font-size="12" font-weight="700" fill="{ORANGE}">'
        f'INTERESSES</text>'
    )

    for i, interest in enumerate(INTERESTS):
        if i < 4:
            col = i % 2
            row = i // 2

            x_interest = 875 + (col * 132)
            y_interest = 322 + (row * 42)

            a(
                f'<rect x="{x_interest}" y="{y_interest}" '
                f'width="124" height="30" rx="15" '
                f'fill="{PANEL_2}" stroke="{ORANGE}" '
                f'stroke-opacity=".7"/>'
            )
            a(
                f'<text x="{x_interest + 62}" '
                f'y="{y_interest + 20}" text-anchor="middle" '
                f'font-family="Segoe UI,Arial" font-size="9" '
                f'font-weight="600" fill="{TEXT}">'
                f'{esc(interest)}</text>'
            )

        else:
            # IA e Dados ocupa uma linha inteira
            x_interest = 875
            y_interest = 406

            a(
                f'<rect x="{x_interest}" y="{y_interest}" '
                f'width="256" height="30" rx="15" '
                f'fill="{PANEL_2}" stroke="{ORANGE}" '
                f'stroke-opacity=".7"/>'
            )
            a(
                f'<text x="{x_interest + 128}" '
                f'y="{y_interest + 20}" text-anchor="middle" '
                f'font-family="Segoe UI,Arial" font-size="9" '
                f'font-weight="600" fill="{TEXT}">'
                f'{esc(interest)}</text>'
            )

    # ACTIVITY PULSE + RECENT PROJECTS
    a(
        f'<rect x="38" y="510" width="1124" height="112" '
        f'rx="16" fill="{PANEL}" stroke="{BORDER}"/>'
    )
    a(
        f'<text x="62" y="540" font-family="Segoe UI,Arial" '
        f'font-size="15" font-weight="700" fill="{TEXT}">'
        f'ACTIVITY PULSE • 12 MESES</text>'
    )

    max_month = max(
        (value for _, _, value in months),
        default=1,
    ) or 1

    chart_x = 62
    chart_y = 558
    chart_w = 670
    chart_h = 44
    gap = 8
    bar_width = (chart_w - gap * 11) / 12

    for i, (_, label, value) in enumerate(months):
        height = max(
            3,
            chart_h * value / max_month,
        )

        x_bar = chart_x + i * (bar_width + gap)
        y_bar = chart_y + chart_h - height

        color = BLUE if i < 8 else ORANGE

        a(
            f'<rect x="{x_bar:.1f}" y="{y_bar:.1f}" '
            f'width="{bar_width:.1f}" height="{height:.1f}" '
            f'rx="4" fill="{color}"/>'
        )
        a(
            f'<text x="{x_bar + bar_width / 2:.1f}" y="616" '
            f'text-anchor="middle" font-family="Segoe UI,Arial" '
            f'font-size="10" fill="{MUTED}">{label}</text>'
        )

    # Projetos recentes — somente nomes
    a(
        f'<text x="790" y="540" font-family="Segoe UI,Arial" '
        f'font-size="15" font-weight="700" fill="{TEXT}">'
        f'RECENT PROJECTS</text>'
    )

    if recent:
        for i, repo in enumerate(recent):
            y_repo = 566 + i * 18

            a(
                f'<text x="790" y="{y_repo}" '
                f'font-family="Segoe UI,Arial" font-size="12" '
                f'font-weight="600" fill="{TEXT}">'
                f'{esc(repo["name"])}</text>'
            )

    a("</svg>")

    return "\n".join(parts)


def main():
    OUT.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    user = fetch_user()
    repos = fetch_repos()
    languages = fetch_language_totals(repos)
    contributions = fetch_contributions()

    svg = render_svg(
        user,
        repos,
        languages,
        contributions,
    )

    OUT.write_text(
        svg,
        encoding="utf-8",
    )

    print(f"Generated {OUT}")


if __name__ == "__main__":
    main()

