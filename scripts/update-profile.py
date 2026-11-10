"""Refresh the profile's pixel cards using public GitHub activity."""

# calculate_rank is adapted from anuraghazra/github-readme-stats, MIT License.
# Copyright (c) 2020 Anurag Hazra. See assets/LICENSE-github-readme-stats.txt.

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from xml.etree import ElementTree
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


def write_svg(filename, width, height, title, content, background=INK, border=LINE):
    frame = (
        f'M10 1H{width - 10}V9H{width - 1}V{height - 10}H{width - 9}'
        f'V{height - 1}H10V{height - 9}H1V10H10Z'
    )
    markup = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" role="img" aria-labelledby="title">\n'
        f'<title id="title">{escape(title)}</title>\n'
        '<style>text{font-family:"Segoe UI","Microsoft YaHei","Noto Sans CJK SC",sans-serif}</style>\n'
        f'<path d="{frame}" fill="{background}" stroke="{border}" stroke-width="2"/>\n'
        + "\n".join(content)
        + "\n</svg>\n"
    )
    (ASSETS / filename).write_text(markup, encoding="utf-8")
    if "<animate" in markup:
        document = ElementTree.fromstring(markup)
        for parent in document.iter():
            for child in list(parent):
                if child.tag.rsplit("}", 1)[-1] in {"animate", "animateTransform", "animateMotion"}:
                    parent.remove(child)
        ElementTree.register_namespace("", "http://www.w3.org/2000/svg")
        static_file = ASSETS / filename.replace(".svg", "-static.svg")
        ElementTree.ElementTree(document).write(static_file, encoding="utf-8", xml_declaration=True)


def pixel_art(x, y, rows, palette, scale=4):
    pixels = []
    for row, cells in enumerate(rows):
        for column, cell in enumerate(cells):
            if cell != ".":
                pixels.append(rect(x + column * scale, y + row * scale, scale, scale, palette[cell]))
    return '<g shape-rendering="crispEdges">' + "".join(pixels) + '</g>'


BOOK = [
    ".bbbbbb..bbbbbb.",
    "bppppppbbppppppb",
    "bpccccpbbpccccpb",
    "bppppppbbppppppb",
    "bpccccpbbpccccpb",
    "bppppppbbppppppb",
    "bpccccpbbpccccpb",
    "bppppppbbppppppb",
    "bppppppbbppppppb",
    ".bbbbbb..bbbbbb.",
    ".......bb.......",
]
BOOK_COLORS = {"b": "#766047", "p": "#fffdf0", "c": "#8cc7c4"}
CAT = [
    "b..........b",
    "bob......bob",
    "booobbbbooob",
    "booooooooobb",
    "boooooooooob",
    "boobooooboob",
    "boobooooboob",
    "boooommoooob",
    "booobbbbooob",
    ".boooooooob.",
    "..bbboobbb..",
    "..bb....bb..",
]
CAT_COLORS = {"b": "#77504c", "o": "#ffcc7f", "m": "#e88191"}


def render_statistics(statistics, mobile=False):
    width, height = (450, 526) if mobile else (900, 382)
    content = [text(28, 38, f'GitHub 活动档案 / {statistics["year"]}', 23, CREAM, 600)]
    if not mobile:
        content.extend([
            rect(820, 25, 6, 6, CYAN), rect(838, 17, 4, 4, PINK),
            rect(855, 30, 5, 5, YELLOW),
            '<path d="M823 28L840 19L857 32" fill="none" stroke="#594079" stroke-width="2"/>',
        ])
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
        content.append(rect(x, y + 101, 178, 2, LINE))
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
    content.append(text(28, 319 if mobile else 192, "最近半年" if mobile else "今年的贡献足迹", 20, CREAM))
    start_x, start_y = (62, 363) if mobile else (75, 226)
    step = 13 if mobile else min(17, (width - 120) // len(calendar))
    square = 9 if mobile else 12
    colors = {
        "NONE": "#30213f",
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
    footer_y = 492 if mobile else 360
    content.append(text(28, footer_y, f'更新于 {cutoff} · GitHub 公开数据', 18, MUTED))
    filename = "github-stats-mobile.svg" if mobile else "github-stats.svg"
    description = (
        f'{statistics["year"]} 年 {statistics["contributions"]} 次贡献、'
        f'{statistics["commits"]} 次提交，累计 {statistics["publicPullRequests"]} 个公开 PR，'
        f'GitHub Readme Stats 活跃等级 {statistics["rank"]["level"]}。数据更新于 {cutoff}。'
    )
    write_svg(filename, width, height, description, content)


def render_projects():
    ink = "#58442f"
    vaultide = [
        rect(22, 12, 2, 258, "#e6cf9d"),
        text(40, 41, "Vaultide · 知洄", 26, ink, 700),
        text(380, 40, "公开预览", 16, "#806136", anchor="end"),
        rect(40, 60, 342, 124, "#fff9e8"),
        rect(80, 152, 152, 8, "#e9dcbb"),
        '<g><animateTransform attributeName="transform" type="translate" values="0 0;0 -4;0 0" dur="6s" repeatCount="indefinite"/>',
        pixel_art(82, 84, BOOK, BOOK_COLORS, 7),
        '</g>',
        '<path d="M245 96H325V128H290L279 139V128H245Z" fill="#b9e8e3" stroke="#4d8b8b" stroke-width="2"/>',
        rect(261, 108, 7, 7, "#4d8b8b"), rect(280, 108, 7, 7, "#4d8b8b"), rect(299, 108, 7, 7, "#4d8b8b"),
        '<g><animateTransform attributeName="transform" type="translate" values="0 0;0 3;0 0" dur="6s" repeatCount="indefinite"/>',
        rect(302, 143, 48, 30, "#ffb7ca"),
        '<path d="M312 152H339M312 161H332" stroke="#ac5e7d" stroke-width="3"/>',
        '</g>',
        rect(62, 69, 7, 7, "#efb45f"), rect(232, 156, 5, 5, "#dd8ba2"),
        text(40, 214, "把资料变成学习与笔记", 22, ink, 600),
        text(40, 242, "OpenMAIC × Obsidian", 18, "#756044"),
        rect(40, 263, 7, 7, "#338ea6"),
        text(56, 271, "TypeScript", 16, "#2e7284"),
    ]
    for y in [78, 114, 150, 186, 222, 258]:
        vaultide.append(rect(13, y, 17, 4, "#b49a6b"))
    write_svg("project-vaultide.svg", 408, 290, "Vaultide · 知洄。公开预览版学习工作台。书页、提问与笔记轻轻浮动。", vaultide, "#fff2ce", "#c6a770")

    mapes = [
        text(26, 41, "MAPES", 27, "#254c48", 700),
        text(380, 40, "mock 原型", 16, "#326a59", anchor="end"),
        rect(24, 60, 360, 124, "#183d43"),
        '<path d="M112 127H187V110H259" fill="none" stroke="#68b6ad" stroke-width="3" stroke-dasharray="5 6"/>',
        rect(58, 93, 48, 43, "#f3ca84"),
        rect(67, 105, 7, 9, "#31484d"), rect(89, 105, 7, 9, "#31484d"),
        '<path d="M75 123H90" stroke="#b26e66" stroke-width="3"/>',
        rect(50, 140, 64, 8, "#578f88"),
        '<path d="M122 74H190V98H149L139 108V98H122Z" fill="#b4dcd3"/>',
        rect(136, 84, 5, 5, "#517c77"), rect(150, 84, 5, 5, "#517c77"), rect(164, 84, 5, 5, "#517c77"),
        '<g><rect x="169" y="122" width="8" height="8" fill="#ffe28c"/><animateTransform attributeName="transform" type="translate" values="0 0;0 0;18 -16;90 -16;90 -16;0 0" keyTimes="0;.2;.4;.65;.85;1" dur="6s" repeatCount="indefinite"/><animate attributeName="opacity" values="0;1;1;0;0" keyTimes="0;.2;.65;.8;1" dur="6s" repeatCount="indefinite"/></g>',
        rect(272, 78, 75, 85, "#e2f2e8"),
        rect(282, 88, 42, 5, "#386b67"),
        text(26, 214, "多 Agent 角色表现评测", 22, "#254c48", 600),
        text(26, 242, "CLI、模拟评审与六维报告", 18, "#41685f"),
        rect(26, 263, 7, 7, "#448974"),
        text(42, 271, "Python", 16, "#367460"),
    ]
    for row in range(6):
        mapes.extend([rect(282, 103 + row * 8, 4, 4, "#72a796"), rect(293, 103 + row * 8, 42, 3, "#9ec5b5")])
    write_svg("project-mapes.svg", 408, 290, "MAPES。mock 评测原型。角色的示意消息沿路径进入六维报告。", mapes, "#e1f3e9", "#79aa97")


def render_practice(mobile=False):
    width, height = (450, 450) if mobile else (900, 280)
    sprout = [
        ".......gg.......", "....ll.gg.ll....", "...llllggllll...", "....lllgglll....",
        ".......gg.......", "..llll.gg.llll..", ".llllllggllllll.", "..lllllgglllll..",
        ".......gg.......", ".......gg.......", "....bbbbbbbb....", ".....pppppp.....",
        ".....pppppp.....", "......pppp......", "......bbbb......",
    ]
    film = [
        "..bbwwbbwwbbww..", ".bbwwbbwwbbwwb..", ".bbbbbbbbbbbbbb.", ".bppppppppppppb.",
        ".bppppwpppppppb.", ".bppppwwppppppb.", ".bppppwwwpppppb.", ".bppppwwwwppppb.",
        ".bppppwwwpppppb.", ".bppppwwppppppb.", ".bppppwpppppppb.", ".bppppppppppppb.",
        ".bbbbbbbbbbbbbb.",
    ]
    vision = [
        ".bbbbbbbbbbbbbb.", ".bppppppppppppb.", ".bpppppmmpppppb.", ".bpppppmmpppppb.",
        ".bpppppgpgppppb.", ".bppppggggppppb.", ".bpppgpggpgpppb.",
        ".bpppppggpppppb.", ".bppppgppgppppb.", ".bpppgppppgpppb.", ".bppppppppppppb.",
        ".bbbbbbbbbbbbbb.", ".......bb.......", ".....bbbbbb.....",
    ]
    tasks = [
        ("教学训练", "课程、练习与评价", BOOK, BOOK_COLORS),
        ("农业 Agent", "任务交接与人员确认", sprout, {"g": "#4c8063", "l": "#88bc84", "b": "#9e7859", "p": "#c69a73"}),
        ("创作工具", "脚本、分镜与素材", film, {"b": "#555571", "w": "#fff0bf", "p": "#d895b4"}),
        ("视觉原型", "关键点与跌倒识别", vision, {"b": "#497285", "p": "#cce4e9", "m": "#538985", "g": "#538985"}),
    ]
    trail = "M28 145H430V345H111" if mobile else "M28 152H112V163H336V152H560V163H870"
    content = [
        rect(10, height - 20, width - 20, 10, "#dfeddf"),
        f'<path d="{trail}" fill="none" stroke="#c3b397" stroke-width="4" stroke-dasharray="5 8"/>',
        rect(39, 34, 33, 7, "#d1e5ec"), rect(51, 27, 20, 7, "#d1e5ec"),
        rect(width - 96, 36, 42, 7, "#d1e5ec"), rect(width - 82, 29, 20, 7, "#d1e5ec"),
        '<g><animateTransform attributeName="transform" type="translate" values="0 0;0 0;30 -2;60 0;90 -2;90 0;60 -2;30 0;0 0" keyTimes="0;.15;.25;.35;.45;.6;.7;.8;1" dur="10s" repeatCount="indefinite"/>',
        pixel_art(18, 118, CAT, CAT_COLORS, 2), '</g>',
    ]
    for index, (title, description, sprite, palette) in enumerate(tasks):
        column = index % 2 if mobile else index
        row = index // 2 if mobile else 0
        x, y = 112 + column * 224, 72 + row * 200
        content.append(rect(x - 39, y + 58, 78, 5, "#d5e4de"))
        content.append(pixel_art(x - 32, y, sprite, palette, 4))
        content.append(text(x, y + 108 if mobile else 215, title, 22, "#334f60", 600, "middle"))
        content.append(text(x, y + 136 if mobile else 245, description, 18, "#526c77", anchor="middle"))
    filename = "practice-mobile.svg" if mobile else "practice.svg"
    write_svg(filename, width, height, "近期实践地图。书页、植物、场记板与人体关键点代表四个探索方向，小橘猫在路边轻轻探头。", content, "#eef7fa", "#c0d8e0")


def main():
    statistics = fetch_statistics(datetime.now(timezone.utc).replace(microsecond=0))
    render_statistics(statistics)
    render_statistics(statistics, mobile=True)
    render_projects()
    render_practice()
    render_practice(mobile=True)
    (ASSETS / "github-stats.json").write_text(json.dumps(statistics, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f'Refreshed {USER}: {statistics["contributions"]} contributions, {statistics["commits"]} commits, rank {statistics["rank"]["level"]}.')


if __name__ == "__main__":
    main()
