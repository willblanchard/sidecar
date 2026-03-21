#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from dataclasses import dataclass

EXEMPT_PREFIXES = ("chore:", "docs:", "tooling:", "ci:", "build:", "style:")
EXEMPT_SUBJECT_PREFIXES = ("merge ", "revert ")
WAT_PATTERN = re.compile(r"\bWAT-\d+\b", re.IGNORECASE)


@dataclass(frozen=True)
class CommitMessage:
    sha: str
    subject: str
    body: str


def _is_exempt_subject(subject: str) -> bool:
    normalized = subject.strip().lower()
    if normalized.startswith(EXEMPT_SUBJECT_PREFIXES):
        return True
    return normalized.startswith(EXEMPT_PREFIXES)


def _has_wat_reference(message: str) -> bool:
    return bool(WAT_PATTERN.search(message))


def _format_violation(commit: CommitMessage) -> str:
    return (
        f"{commit.sha[:7]} {commit.subject}\n"
        "  missing WAT-NNN issue reference; use `WAT-NNN: ...` or `... (WAT-NNN)`"
    )


def validate_commit_message(commit: CommitMessage) -> str | None:
    message = commit.body.strip() or commit.subject
    if _is_exempt_subject(commit.subject):
        return None
    if _has_wat_reference(message):
        return None
    return _format_violation(commit)


def _git_lines(*args: str) -> list[str]:
    completed = subprocess.run(
        ["git", *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return [line for line in completed.stdout.splitlines() if line]


def _load_commit(sha: str) -> CommitMessage:
    body = subprocess.run(
        ["git", "show", "-s", "--format=%B", sha],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    subject = body.splitlines()[0] if body.splitlines() else ""
    return CommitMessage(sha=sha, subject=subject, body=body)


def _resolve_commits(rev_range: str | None, rev_list: list[str]) -> list[CommitMessage]:
    if rev_range:
        shas = _git_lines("rev-list", "--reverse", rev_range)
    elif rev_list:
        shas = rev_list
    else:
        raise ValueError("either rev_range or rev_list must be provided")
    return [_load_commit(sha) for sha in shas]


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate git commit messages include a WAT-NNN issue reference.",
    )
    parser.add_argument(
        "--rev-range",
        help="Git revision range to validate, for example origin/main..HEAD",
    )
    parser.add_argument(
        "--rev-list",
        nargs="+",
        help="Explicit commit SHAs to validate.",
    )
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    commits = _resolve_commits(args.rev_range, args.rev_list or [])
    violations = [msg for commit in commits if (msg := validate_commit_message(commit))]
    if not violations:
        print(f"Validated {len(commits)} commit message(s); all required WAT refs present.")
        return 0

    print("Commit message check failed:\n")
    for violation in violations:
        print(violation)
    print(
        "\nAllowed without WAT refs: chore:, docs:, tooling:, ci:, build:, style:, merge commits, and revert commits."
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
