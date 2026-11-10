"""Refresh the profile's pixel cards using public GitHub activity."""

# calculate_rank is adapted from anuraghazra/github-readme-stats, MIT License.
# Copyright (c) 2020 Anurag Hazra. See assets/LICENSE-github-readme-stats.txt.

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from xml.sax.saxutils import escape


ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "assets"
USER = "ZMS-PNG"
INK = "#1c1230"
PANEL = "#281b43"
LINE = "#594079"
CREAM = "#fff1d2"
MUTED = "#c4aedf"
PINK = "#ff86b9"
CYAN = "#7ae7ff"
MINT = "#a4f0c5"
YELLOW = "#ffe28c"
GLYPHS = {
    "0": ["01110", "11011", "11011", "11011", "11011", "11011", "01110"],
    "1": ["00100", "01100", "00100", "00100", "00100", "00100", "01110"],
    "2": ["01110", "10001", "00001", "00010", "00100", "01000", "11111"],
    "3": ["11110", "00001", "00001", "01110", "00001", "00001", "11110"],
    "4": ["00010", "00110", "01010", "10010", "11111", "00010", "00010"],
    "5": ["11111", "10000", "10000", "11110", "00001", "00001", "11110"],
    "6": ["01110", "10000", "10000", "11110", "10001", "10001", "01110"],
    "7": ["11111", "00001", "00010", "00010", "00100", "00100", "00100"],
    "8": ["01110", "10001", "10001", "01110", "10001", "10001", "01110"],
    "9": ["01110", "10001", "10001", "01111", "00001", "00001", "01110"],
    "C": ["01111", "10000", "10000", "10000", "10000", "10000", "01111"],
    "B": ["11110", "10001", "10001", "11110", "10001", "10001", "11110"],
    "A": ["01110", "10001", "10001", "11111", "10001", "10001", "10001"],
    "S": ["01111", "10000", "10000", "01110", "00001", "00001", "11110"],
    "+": ["00000", "00100", "00100", "11111", "00100", "00100", "00000"],
    "-": ["00000", "00000", "00000", "11111", "00000", "00000", "00000"],
}


def api(endpoint, *arguments):
    result = subprocess.run(
        ["gh", "api", endpoint, *arguments],
        check=True,
        capture_output=True,
        encoding="utf-8",
    )
    return json.loads(result.stdout)


def fetch_statistics(now):
    year = now.year
    query = """
    query($user: String!, $from: DateTime!, $to: DateTime!, $prQuery: String!, $issueQuery: String!) {
      user(login: $user) {
        followers { totalCount }
        contributionsCollection(from: $from, to: $to) {
          totalCommitContributions
          totalPullRequestReviewContributions
          restrictedContributionsCount
          contributionCalendar {
            totalContributions
            weeks { contributionDays { date contributionCount contributionLevel } }
          }
        }
      }
      publicPrs: search(query: $prQuery, type: ISSUE) { issueCount }
      publicIssues: search(query: $issueQuery, type: ISSUE) { issueCount }
    }
    """
    response = api(
        "graphql",
        "-f", f"query={query}",
        "-f", f"user={USER}",
        "-f", f"prQuery=author:{USER} is:pr is:public",
        "-f", f"issueQuery=author:{USER} is:issue is:public",
        "-f", f"from={year}-01-01T00:00:00Z",
        "-f", f"to={now.isoformat()}",
    )
    if response.get("errors"):
        raise RuntimeError(response["errors"])
    data = response["data"]
    collection = data["user"]["contributionsCollection"]
    if collection["restrictedContributionsCount"]:
        raise RuntimeError("Use the workflow GITHUB_TOKEN to request public-only statistics.")
    repositories = []
    page = 1
    while True:
        batch = api(f"users/{USER}/repos?type=owner&per_page=100&page={page}")
        repositories.extend(batch)
        if len(batch) < 100:
            break
        page += 1
    owned = [repo for repo in repositories if not repo["fork"]]
    statistics = {
        "user": USER,
        "updatedAt": now.isoformat(),
        "year": year,
        "contributions": collection["contributionCalendar"]["totalContributions"],
        "commits": collection["totalCommitContributions"],
        "publicPullRequests": data["publicPrs"]["issueCount"],
        "publicIssues": data["publicIssues"]["issueCount"],
        "reviews": collection["totalPullRequestReviewContributions"],
        "stars": sum(repo["stargazers_count"] for repo in owned),
        "followers": data["user"]["followers"]["totalCount"],
        "publicRepositories": len(repositories),
        "nonForkRepositories": len(owned),
        "calendar": collection["contributionCalendar"]["weeks"],
        "rankSource": "https://github.com/anuraghazra/github-readme-stats/blob/master/src/calculateRank.js",
        "profileSource": f"https://github.com/{USER}?tab=overview",
    }
    statistics["rank"] = calculate_rank(statistics)
    return statistics


def calculate_rank(statistics):
    """GitHub Readme Stats formula, adapted under its MIT License."""
    weighted_score = (
        2 * (1 - 2 ** (-statistics["commits"] / 250))
        + 3 * (1 - 2 ** (-statistics["publicPullRequests"] / 50))
        + (1 - 2 ** (-statistics["publicIssues"] / 25))
        + (1 - 2 ** (-statistics["reviews"] / 2))
        + 4 * statistics["stars"] / (statistics["stars"] + 50)
        + statistics["followers"] / (statistics["followers"] + 10)
    )
    percentile = 100 * (1 - weighted_score / 12)
    thresholds = [1, 12.5, 25, 37.5, 50, 62.5, 75, 87.5, 100]
    levels = ["S", "A+", "A", "A-", "B+", "B", "B-", "C+", "C"]
    level = next(level for level, threshold in zip(levels, thresholds) if percentile <= threshold)
    return {"level": level, "percentile": round(percentile, 4)}


def rect(x, y, width, height, color, **attributes):
    extra = " ".join(f'{key}="{value}"' for key, value in attributes.items())
    return f'<rect x="{x}" y="{y}" width="{width}" height="{height}" fill="{color}" {extra}/>'


def text(x, y, value, size=20, color=CREAM, weight=400, anchor="start"):
    return (
        f'<text x="{x}" y="{y}" font-size="{size}" fill="{color}" '
        f'font-weight="{weight}" text-anchor="{anchor}">{escape(str(value))}</text>'
    )


def pixel_text(x, y, value, color, scale=6):
    pixels = []
    for index, character in enumerate(str(value)):
        for row, cells in enumerate(GLYPHS[character]):
            for column, cell in enumerate(cells):
                if cell == "1":
                    pixels.append(rect(x + (index * 6 + column) * scale, y + row * scale, scale, scale, color))
    return "".join(pixels)


def write_svg(filename, width, height, title, content):
    frame = (
        f'M10 1H{width - 10}V9H{width - 1}V{height - 10}H{width - 9}'
        f'V{height - 1}H10V{height - 9}H1V10H10Z'
    )
    markup = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" role="img" aria-labelledby="title">\n'
        f'<title id="title">{escape(title)}</title>\n'
        '<style>text{font-family:"Segoe UI","Microsoft YaHei","Noto Sans CJK SC",sans-serif}</style>\n'
        f'<path d="{frame}" fill="{INK}" stroke="{LINE}" stroke-width="2"/>\n'
        + "\n".join(content)
        + "\n</svg>\n"
    )
    (ASSETS / filename).write_text(markup, encoding="utf-8")


def render_statistics(statistics, mobile=False):
    width, height = (450, 548) if mobile else (900, 400)
    content = [text(28, 38, f'GitHub 活动档案 / {statistics["year"]}', 23, CREAM, 600)]
    metrics = [
        (statistics["contributions"], "年度贡献", PINK),
        (statistics["commits"], "年度提交", CYAN),
        (statistics["publicPullRequests"], "累计公开 PR", MINT),
        (statistics["rank"]["level"], "GRS 活跃等级", YELLOW),
    ]
    for index, (value, label, color) in enumerate(metrics):
        column = index % 2 if mobile else index
        row = index // 2 if mobile else 0
        x = 28 + column * (210 if mobile else 218)
        y = 66 + row * 122
        content.append(rect(x, y, 190 if mobile else 198, 104, PANEL))
        content.append(rect(x, y, 5, 104, color))
        scale = min(6, 162 // (6 * len(str(value))))
        content.append(pixel_text(x + 20, y + 15, value, color, scale))
        content.append(text(x + 20, y + 86, label, 19, MUTED))

    calendar = []
    cutoff = statistics["updatedAt"][:10]
    first_day = f'{statistics["year"]}-01-01'
    for week in statistics["calendar"]:
        days = [day for day in week["contributionDays"] if first_day <= day["date"] <= cutoff]
        if days:
            calendar.append(days)
    if mobile:
        calendar = calendar[-26:]
    content.append(text(28, 331 if mobile else 206, "最近半年" if mobile else "今年的贡献足迹", 20, CREAM))
    start_x, start_y = (62, 375) if mobile else (75, 248)
    step = 13 if mobile else 17
    square = 9 if mobile else 12
    colors = {
        "NONE": "#34244b",
        "FIRST_QUARTILE": "#744278",
        "SECOND_QUARTILE": "#aa548e",
        "THIRD_QUARTILE": "#df74a8",
        "FOURTH_QUARTILE": PINK,
    }
    previous_month = None
    for column, days in enumerate(calendar):
        month = days[0]["date"][5:7]
        if month != previous_month:
            content.append(text(start_x + column * step, start_y - 14, f'{int(month)}月', 18 if mobile else 15, MUTED))
            previous_month = month
        for day in days:
            weekday = (datetime.fromisoformat(day["date"]).weekday() + 1) % 7
            content.append(rect(start_x + column * step, start_y + weekday * step, square, square, colors[day["contributionLevel"]]))
    for weekday, label in [(1, "一"), (3, "三"), (5, "五")]:
        content.append(text(28, start_y + weekday * step + square, label, 18 if mobile else 15, MUTED))
    footer_y = 506 if mobile else 382
    content.append(text(28, footer_y, f'更新于 {cutoff} · GitHub 公开数据', 18, MUTED))
    filename = "github-stats-mobile.svg" if mobile else "github-stats.svg"
    description = (
        f'{statistics["year"]} 年 {statistics["contributions"]} 次贡献、'
        f'{statistics["commits"]} 次提交，累计 {statistics["publicPullRequests"]} 个公开 PR，'
        f'GitHub Readme Stats 活跃等级 {statistics["rank"]["level"]}。数据更新于 {cutoff}。'
    )
    write_svg(filename, width, height, description, content)


def render_project(filename, title, status, description, detail, language, color, icon):
    content = [rect(10, 10, 388, 32, PANEL)]
    for index, dot_color in enumerate([PINK, YELLOW, CYAN]):
        content.append(rect(24 + 14 * index, 23, 6, 6, dot_color))
    content.append(text(383, 32, status, 16, color, anchor="end"))
    content.append(rect(24, 61, 33, 33, color))
    content.append(text(40, 85, icon, 24, INK, 700, "middle"))
    content.append(text(72, 86, title, 27, CREAM, 600))
    content.append(text(24, 122, description, 19, MUTED))
    content.append(text(24, 149, detail, 19, MUTED))
    content.append(rect(24, 170, 7, 7, color))
    content.append(text(40, 178, language, 16, color))
    write_svg(filename, 408, 198, f'{title}，{status}。{description}。{detail}。', content)


def render_practice(mobile=False):
    width, height = (450, 260) if mobile else (900, 142)
    tasks = [
        ("教学训练", "课程、练习与评价", PINK, "▤"),
        ("农业 Agent", "任务交接与人员确认", MINT, "+"),
        ("创作工具", "脚本、分镜与素材", YELLOW, "▸"),
        ("视觉原型", "关键点与跌倒识别", CYAN, "◇"),
    ]
    content = []
    for index, (title, description, color, icon) in enumerate(tasks):
        column = index % 2 if mobile else index
        row = index // 2 if mobile else 0
        x, y = 24 + column * 222, 30 + row * 118
        content.append(rect(x, y, 24, 24, color))
        content.append(text(x + 12, y + 18, icon, 19, INK, 600, "middle"))
        content.append(text(x, y + 54, title, 22, CREAM, 600))
        content.append(text(x, y + 84, description, 18, MUTED))
    filename = "practice-mobile.svg" if mobile else "practice.svg"
    write_svg(filename, width, height, "近期实践。教学训练、农业多智能体、创作工具和跌倒识别原型。", content)


def main():
    statistics = fetch_statistics(datetime.now(timezone.utc).replace(microsecond=0))
    render_statistics(statistics)
    render_statistics(statistics, mobile=True)
    render_project("project-vaultide.svg", "Vaultide · 知洄", "公开预览", "资料、互动学习、练习与笔记", "OpenMAIC × Obsidian", "TypeScript", CYAN, "≡")
    render_project("project-mapes.svg", "MAPES", "mock 原型", "多 Agent 角色表现评测", "CLI · 模拟评审 · 六维报告", "Python", MINT, ">")
    render_practice()
    render_practice(mobile=True)
    (ASSETS / "github-stats.json").write_text(json.dumps(statistics, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f'Refreshed {USER}: {statistics["contributions"]} contributions, {statistics["commits"]} commits, rank {statistics["rank"]["level"]}.')


if __name__ == "__main__":
    main()
