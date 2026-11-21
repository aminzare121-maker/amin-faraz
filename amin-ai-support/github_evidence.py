"""Read-only GitHub issue/PR provenance for a project within a shared repository.

Issue/PR records are UNVERIFIED and indexed for developers only, never customers.
No GitHub token is required for public repositories. If supplied, the token is used
only as an authorization header and never recorded in indexed passages.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen


def repository_slug(git_url: str) -> str:
    parsed = urlparse(git_url)
    if (parsed.scheme != "https" or parsed.hostname != "github.com" or
        parsed.port is not None or parsed.username is not None or
        parsed.password is not None or parsed.query or parsed.fragment):
        raise ValueError("GitHub HTTPS repository is required")
    path = parsed.path.strip("/")
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+\.git", path):
        raise ValueError("Unexpected repository URL")
    return path.removesuffix(".git")


def relevant(item: dict, markers: list[str]) -> bool:
    """Explicit title/label classification avoids cross-project PR body leakage."""
    if not markers:
        return False
    title = item.get("title") or ""
    labels = " ".join(x.get("name", "") for x in item.get("labels", []) if isinstance(x, dict))
    haystack = (title + " " + labels).casefold().replace("ي", "ی").replace("ك", "ک")
    return any(
        bool(re.search(r"(?<![a-z0-9])" + re.escape(marker.casefold()) + r"(?![a-z0-9])",
                       haystack))
        if marker.isascii() else marker.casefold().replace("ي", "ی").replace("ك", "ک") in haystack
        for marker in markers if isinstance(marker, str) and len(marker.strip()) >= 2
    )


def collect_issues(project: dict, api_fetch=None) -> list[dict]:
    """Fetch max 100 recently updated issues/PRs; relevance must be explicit."""
    slug = repository_slug(project["git_url"])
    markers = project.get("provenance_terms", [])
    if not markers:
        return []
    if api_fetch is None:
        def api_fetch(url):
            headers = {"Accept": "application/vnd.github+json",
                       "User-Agent": "amin-ai-support-hub/0.2"}
            token = os.environ.get("AMIN_GITHUB_TOKEN", "").strip()
            if token:
                headers["Authorization"] = "Bearer " + token
            with urlopen(Request(url, headers=headers), timeout=18) as response:
                return json.load(response)
    records = api_fetch(
        f"https://api.github.com/repos/{slug}/issues?state=all&sort=updated&per_page=100")
    if not isinstance(records, list):
        raise ValueError("GitHub issues endpoint did not return a list")
    return [x for x in records if isinstance(x, dict) and relevant(x, markers)][:60]


def index_issues(project: dict, knowledge, issues: list[dict], scrub):
    """Atomically replace existing issue evidence, without touching source docs."""
    rows = []
    for issue in issues:
        number = issue.get("number")
        if not isinstance(number, int) or number <= 0:
            continue
        kind = "pulls" if "pull_request" in issue else "issues"
        source = f"__github__/{kind}/{number}"
        body = (issue.get("body") or "")[:5000]
        title = (issue.get("title") or "")[:500]
        url = (issue.get("html_url") or "")[:300]
        state = (issue.get("state") or "")[:30]
        updated = (issue.get("updated_at") or "")[:50]
        text = scrub(
            f"UNVERIFIED GITHUB {kind.upper()} SOURCE — not an approved solution.\n"
            f"Title: {title}\nURL: {url}\nState: {state}\nUpdated: {updated}\n"
            f"Unverified description:\n{body}")
        for i in range(0, len(text), 1200):
            chunk = text[i:i + 1200]
            rows.append((project["id"], source, i // 1200, "developer",
                         chunk, hashlib.sha256(chunk.encode()).hexdigest()))
    with knowledge.connect() as db:
        db.execute("BEGIN IMMEDIATE")
        db.execute(
            "DELETE FROM passages WHERE project_id=? AND "
            "(path LIKE '__github__/issues/%' OR path LIKE '__github__/pulls/%')",
            (project["id"],))
        db.executemany("INSERT INTO passages VALUES (?,?,?,?,?,?)", rows)
    return {"issues_and_prs": len(issues), "developer_passages": len(rows)}


def update_provenance(project: dict, knowledge, scrub, api_fetch=None) -> dict:
    issues = collect_issues(project, api_fetch=api_fetch)
    return index_issues(project, knowledge, issues, scrub)
