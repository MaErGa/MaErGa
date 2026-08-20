#!/usr/bin/env python3
"""Regenerate dark_mode.svg / light_mode.svg for the profile README.

Reads config.yaml for the static fields and ascii_art.txt for the portrait,
queries the GitHub GraphQL API for the live stats, and writes both SVGs.

    export ACCESS_TOKEN=<classic PAT with repo + read:user>
    python3 today.py

If the API is unreachable the stats block falls back to whatever is in
cache/stats.json, so a bad token never blanks the profile.

Layout and concept after Andrew Grant (@Andrew6rant); see CREDITS.md.
"""

import hashlib
import json
import os
import sys
from datetime import date
from pathlib import Path

import requests
import yaml

from render import build_svg, justify, section

ROOT = Path(__file__).parent
CACHE = ROOT / "cache"
API = "https://api.github.com/graphql"
TOKEN = os.environ.get("ACCESS_TOKEN", "")


# --------------------------------------------------------------------------
# GraphQL
# --------------------------------------------------------------------------

def query(gql, variables=None):
    r = requests.post(
        API,
        json={"query": gql, "variables": variables or {}},
        headers={"Authorization": f"bearer {TOKEN}"},
        timeout=30,
    )
    r.raise_for_status()
    payload = r.json()
    if "errors" in payload:
        raise RuntimeError(payload["errors"])
    return payload["data"]


VIEWER_Q = """
query {
  viewer {
    id
    login
    followers { totalCount }
    # includeUserRepositories keeps your own repos in the count. Without it
    # this counts only contributions to *other people's* repos, which is 0
    # here and reads as a broken stat next to 900+ commits.
    repositoriesContributedTo(
      contributionTypes: [COMMIT, PULL_REQUEST, REPOSITORY]
      includeUserRepositories: true
    ) { totalCount }
    contributionsCollection {
      totalCommitContributions
      restrictedContributionsCount
    }
  }
}
"""

REPOS_Q = """
query($cursor: String) {
  viewer {
    repositories(first: 100, ownerAffiliations: OWNER, after: $cursor) {
      totalCount
      pageInfo { hasNextPage endCursor }
      nodes {
        nameWithOwner
        stargazerCount
        isFork
        defaultBranchRef { target { ... on Commit { oid } } }
      }
    }
  }
}
"""

HISTORY_Q = """
query($owner: String!, $name: String!, $id: ID!, $cursor: String) {
  repository(owner: $owner, name: $name) {
    defaultBranchRef {
      target {
        ... on Commit {
          history(first: 100, author: {id: $id}, after: $cursor) {
            totalCount
            pageInfo { hasNextPage endCursor }
            nodes { additions deletions }
          }
        }
      }
    }
  }
}
"""


def all_repos():
    nodes, cursor = [], None
    while True:
        data = query(REPOS_Q, {"cursor": cursor})["viewer"]["repositories"]
        nodes.extend(data["nodes"])
        if not data["pageInfo"]["hasNextPage"]:
            return nodes, data["totalCount"]
        cursor = data["pageInfo"]["endCursor"]


def repo_loc(repo, viewer_id):
    """Commits/additions/deletions by the viewer, cached on the head oid."""
    head = (repo.get("defaultBranchRef") or {}).get("target", {}).get("oid")
    if not head:
        return 0, 0, 0

    key = hashlib.sha256(repo["nameWithOwner"].encode()).hexdigest()[:16]
    path = CACHE / f"{key}.json"
    if path.exists():
        cached = json.loads(path.read_text())
        if cached.get("head") == head:
            return cached["commits"], cached["additions"], cached["deletions"]

    owner, name = repo["nameWithOwner"].split("/", 1)
    commits = additions = deletions = 0
    cursor = None
    while True:
        target = query(HISTORY_Q, {"owner": owner, "name": name,
                                   "id": viewer_id, "cursor": cursor})
        hist = ((target["repository"] or {}).get("defaultBranchRef") or {})
        hist = (hist.get("target") or {}).get("history")
        if not hist:
            break
        commits = hist["totalCount"]
        for node in hist["nodes"]:
            additions += node["additions"]
            deletions += node["deletions"]
        if not hist["pageInfo"]["hasNextPage"]:
            break
        cursor = hist["pageInfo"]["endCursor"]

    path.write_text(json.dumps({"head": head, "commits": commits,
                                "additions": additions,
                                "deletions": deletions}))
    return commits, additions, deletions


def fetch_stats(exclude=()):
    viewer = query(VIEWER_Q)["viewer"]
    contributions = viewer["contributionsCollection"]

    repos, repo_total = all_repos()
    stars = sum(r["stargazerCount"] for r in repos)

    commits = additions = deletions = 0
    for repo in repos:
        if repo["isFork"] or repo["nameWithOwner"] in exclude:
            continue
        c, a, d = repo_loc(repo, viewer["id"])
        commits += c
        additions += a
        deletions += d

    return {
        "login": viewer["login"],
        "repos": repo_total,
        "contributed": viewer["repositoriesContributedTo"]["totalCount"],
        "stars": stars,
        "followers": viewer["followers"]["totalCount"],
        "commits": (contributions["totalCommitContributions"]
                    + contributions["restrictedContributionsCount"]),
        "loc_add": additions,
        "loc_del": deletions,
        "loc_net": additions - deletions,
    }


# --------------------------------------------------------------------------
# Panel content
# --------------------------------------------------------------------------

def uptime(birth):
    """Calendar-accurate years/months/days, pluralised."""
    today = date.today()
    years = today.year - birth.year
    months = today.month - birth.month
    days = today.day - birth.day
    if days < 0:
        months -= 1
        prev = (today.replace(day=1) - date.resolution)
        days += prev.day
    if months < 0:
        years -= 1
        months += 12

    parts = []
    for value, unit in ((years, "year"), (months, "month"), (days, "day")):
        if value or unit == "day":
            parts.append(f"{value} {unit}{'' if value == 1 else 's'}")
    return ", ".join(parts)


# Top-level config keys that are settings rather than panel content.
RESERVED = {"username", "name", "birth_date", "layout", "stats"}

# Every block gets a `- Title ------` rule. The title is derived from the
# config key, so a new block in the YAML is headed automatically; list a key
# here only when title-casing gets the wording wrong.
HEADER_LABELS = {"languages": "Languages & Tools"}


def header_for(key):
    return HEADER_LABELS.get(key, key.replace("_", " ").title())

BLANK = [("", "value")]


def build_rows(cfg, stats):
    """Every dict in config.yaml becomes a block, in the order written.

    Add, remove or rename a block in the YAML and it shows up here - nothing
    in this file names the individual sections.
    """
    w = cfg["layout"]["panel_cols"]
    header = f"{cfg['username']}@github "
    rows = [[(header, "title"), ("-" * max(w - len(header), 1), "rule")]]
    rows.append(BLANK)
    rows.append(justify("Uptime", uptime(_birth(cfg)), w))

    for key, block in cfg.items():
        if key in RESERVED or not isinstance(block, dict) or not block:
            continue
        rows.append(BLANK)
        rows.append(section(header_for(key), w))
        for label, value in block.items():
            rows.append(justify(label, str(value), w))

    rows.append(BLANK)
    rows.append(section("GitHub Stats", w))
    rows.extend(stat_rows(stats, w))
    return rows


def _pad(left, right, w):
    """Dot-leader row where the two halves are pre-coloured token lists."""
    used = sum(len(t) for t, _ in left) + sum(len(t) for t, _ in right)
    dots = "." * max(w - used - 2, 1)
    return left + [(f" {dots} ", "dots")] + right


def stat_rows(s, w):
    rows = []
    rows.append(_pad(
        [("- Repos:", "key")],
        [(f"{s['repos']:,}", "num"), (" {Contributed: ", "value"),
         (f"{s['contributed']:,}", "add"), ("} | Stars: ", "value"),
         (f"{s['stars']:,}", "add")],
        w))
    rows.append(_pad(
        [("- Commits:", "key")],
        [(f"{s['commits']:,}", "num"), (" | Followers: ", "value"),
         (f"{s['followers']:,}", "add")],
        w))
    rows.append(_pad(
        [("- Lines of Code on GitHub:", "key")],
        [(f"{s['loc_net']:,}", "num"), (" (", "value"),
         (f"{s['loc_add']:,}++", "add"), (", ", "value"),
         (f"{s['loc_del']:,}--", "del"), (")", "value")],
        w))
    return rows


def _birth(cfg):
    return date.fromisoformat(str(cfg["birth_date"]))


# --------------------------------------------------------------------------

FALLBACK = {"login": "", "repos": 0, "contributed": 0, "stars": 0,
            "followers": 0, "commits": 0, "loc_add": 0, "loc_del": 0,
            "loc_net": 0}


def load_stats(cfg):
    snapshot = CACHE / "stats.json"
    if not TOKEN:
        print("ACCESS_TOKEN not set - using cached stats", file=sys.stderr)
    else:
        try:
            exclude = set((cfg.get("stats") or {}).get("exclude_repos") or [])
            stats = fetch_stats(exclude)
            snapshot.write_text(json.dumps(stats, indent=2))
            return stats
        except Exception as exc:               # noqa: BLE001 - never blank the profile
            print(f"stats fetch failed ({exc}) - using cached stats",
                  file=sys.stderr)
    if snapshot.exists():
        return json.loads(snapshot.read_text())
    return FALLBACK


def main():
    CACHE.mkdir(exist_ok=True)
    cfg = yaml.safe_load((ROOT / "config.yaml").read_text())

    art_file = cfg["layout"].get("ascii_file", "ascii_art.txt")
    art_path = ROOT / art_file
    if not art_path.exists():
        sys.exit(f"{art_file} missing - run: python3 ascii_art.py photo.png")
    ascii_lines = art_path.read_text().rstrip("\n").split("\n")

    rows = build_rows(cfg, load_stats(cfg))
    cols = cfg["layout"]["ascii_cols"]
    panel = cfg["layout"]["panel_cols"]

    for theme, filename in (("dark", "dark_mode.svg"), ("light", "light_mode.svg")):
        (ROOT / filename).write_text(
            build_svg(ascii_lines, rows, theme, cols, panel))
        print(f"wrote {filename}")


if __name__ == "__main__":
    main()
