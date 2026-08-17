#!/usr/bin/env python3
"""Build a per-language commit-count chart for the profile README.

Unlike github-readme-stats' top-langs card (which ranks by byte count of
files currently in each repo), this counts how many of the user's own
commits touched each language, across all of their non-fork repos.
"""

import json
import os
import re
import subprocess
import sys
import tempfile
import urllib.request

USERNAME = os.environ.get("GH_USERNAME", "battletech45")
AUTHOR_NAMES = os.environ.get("AUTHOR_NAMES", "Altay Taneri,battletech45").split(",")
TOKEN = os.environ.get("GITHUB_TOKEN", "")
OUT_PATH = os.environ.get("OUT_PATH", "dist/commit-lang-stats.svg")

EXT_TO_LANG = {
    "dart": "Dart",
    "js": "JavaScript",
    "jsx": "JavaScript",
    "mjs": "JavaScript",
    "cjs": "JavaScript",
    "ts": "TypeScript",
    "tsx": "TypeScript",
    "java": "Java",
    "py": "Python",
    "rb": "Ruby",
    "swift": "Swift",
    "kt": "Kotlin",
    "kts": "Kotlin",
    "m": "Objective-C",
    "html": "HTML",
    "css": "CSS",
    "scss": "CSS",
    "mdx": "MDX",
}

LANG_COLORS = {
    "Dart": "#00B4AB",
    "JavaScript": "#f1e05a",
    "TypeScript": "#3178c6",
    "Java": "#b07219",
    "Python": "#3572A5",
    "Ruby": "#701516",
    "Swift": "#F05138",
    "Kotlin": "#A97BFF",
    "Objective-C": "#438eff",
    "HTML": "#e34c26",
    "CSS": "#563d7c",
    "MDX": "#fcb32c",
}


def gh_api(path):
    req = urllib.request.Request(f"https://api.github.com{path}")
    req.add_header("Accept", "application/vnd.github+json")
    if TOKEN:
        req.add_header("Authorization", f"Bearer {TOKEN}")
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read())


def list_repos():
    repos, page = [], 1
    while True:
        batch = gh_api(f"/users/{USERNAME}/repos?per_page=100&page={page}")
        if not batch:
            break
        repos.extend(r["name"] for r in batch if not r["fork"])
        page += 1
    return repos


def ext_of(path):
    base = os.path.basename(path).lower()
    if base == "dockerfile":
        return "dockerfile"
    if "." not in base:
        return None
    return base.rsplit(".", 1)[-1]


def count_langs_for_repo(repo, workdir):
    clone_dir = os.path.join(workdir, repo)
    url = f"https://github.com/{USERNAME}/{repo}.git"
    subprocess.run(
        ["git", "clone", "--quiet", "--filter=blob:none", url, clone_dir],
        check=False,
    )
    if not os.path.isdir(clone_dir):
        return {}

    author_args = []
    for name in AUTHOR_NAMES:
        author_args += ["--author", name]

    log = subprocess.run(
        ["git", "-C", clone_dir, "log", "-i", *author_args, "--pretty=format:%H"],
        capture_output=True,
        text=True,
        check=False,
    ).stdout.splitlines()

    counts = {}
    for sha in log:
        show = subprocess.run(
            ["git", "-C", clone_dir, "show", "--name-only", "--pretty=format:", sha],
            capture_output=True,
            text=True,
            check=False,
        ).stdout
        langs_in_commit = set()
        for path in show.splitlines():
            path = path.strip()
            if not path:
                continue
            ext = ext_of(path)
            lang = EXT_TO_LANG.get(ext)
            if lang:
                langs_in_commit.add(lang)
        for lang in langs_in_commit:
            counts[lang] = counts.get(lang, 0) + 1
    return counts


def render_svg(counts, top_n=6):
    total = sum(counts.values()) or 1
    items = sorted(counts.items(), key=lambda kv: kv[1], reverse=True)[:top_n]

    width, row_h, pad_top = 300, 28, 55
    height = pad_top + row_h * len(items) + 15

    bar_segments = []
    x = 0
    for lang, n in items:
        w = (n / total) * (width - 20)
        color = LANG_COLORS.get(lang, "#8b8b8b")
        bar_segments.append(
            f'<rect x="{x:.2f}" y="0" width="{w:.2f}" height="8" fill="{color}" />'
        )
        x += w

    rows = []
    for i, (lang, n) in enumerate(items):
        pct = 100 * n / total
        y = pad_top + i * row_h
        color = LANG_COLORS.get(lang, "#8b8b8b")
        rows.append(f'''
      <circle cx="16" cy="{y - 5}" r="5" fill="{color}" />
      <text x="30" y="{y}" class="lang">{lang}</text>
      <text x="{width - 20}" y="{y}" text-anchor="end" class="pct">{pct:.1f}% ({n})</text>''')

    svg = f'''<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg" font-family="'Segoe UI', Ubuntu, Sans-Serif">
  <style>
    .title {{ fill: #58a6ff; font-size: 16px; font-weight: 600; }}
    .lang {{ fill: #c9d1d9; font-size: 13px; }}
    .pct {{ fill: #8b949e; font-size: 12px; }}
  </style>
  <rect width="{width}" height="{height}" rx="6" fill="#0d1117" />
  <text x="20" y="26" class="title">Most Committed Languages</text>
  <g transform="translate(10, 36)">{''.join(bar_segments)}</g>
  <g>{''.join(rows)}</g>
</svg>'''
    return svg


def main():
    repos = list_repos()
    print(f"Repos: {repos}", file=sys.stderr)

    total_counts = {}
    with tempfile.TemporaryDirectory() as workdir:
        for repo in repos:
            counts = count_langs_for_repo(repo, workdir)
            print(f"{repo}: {counts}", file=sys.stderr)
            for lang, n in counts.items():
                total_counts[lang] = total_counts.get(lang, 0) + n

    print(f"Totals: {total_counts}", file=sys.stderr)

    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w") as f:
        f.write(render_svg(total_counts))


if __name__ == "__main__":
    main()
