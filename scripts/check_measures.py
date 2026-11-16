import json
import os
import subprocess
from datetime import date
from pathlib import Path

LABEL = "review-overdue"
TODAY = date.today()
DRY_RUN = os.environ.get("DRY_RUN", "false").lower() == "true"

def gh(*args):
    result = subprocess.run(
        ["gh", *args],
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout


def main():
    repo = os.environ["GITHUB_REPOSITORY"]

    # Get all existing issues, including closed ones.
    issues = json.loads(gh(
        "api", "--paginate",
        f"repos/{repo}/issues?state=all&per_page=100",
        "--slurp",
    ))
    issues = [
        issue
        for page in issues
        for issue in page
        if "pull_request" not in issue
    ]

    if not DRY_RUN:
        gh("label", "create", LABEL,
           "--color", "D93F0B", "--force")
    overdue = set()

    for path in sorted(Path(".").rglob("*.json")):
        if any(part.startswith(".") for part in path.parts):
            continue

        with path.open(encoding="utf-8") as f:
            data = json.load(f)

        if not isinstance(data, dict):
            continue

        review_date = data.get("next_review")
        if not review_date:
            continue

        review_date = date.fromisoformat(review_date)
        marker = f"<!-- measure-review:{path.as_posix()} -->"

        existing = next(
            (issue for issue in issues
             if marker in (issue.get("body") or "")),
            None,
        )

        if review_date < TODAY:
            overdue.add(marker)

            if existing:
                if existing["state"] == "closed":
                    if DRY_RUN:
                        print(f"DRY RUN: Would reopen issue #{existing['number']}")
                    else:
                        gh("issue", "reopen", str(existing["number"]))
                continue

            name = data.get("name", path.stem)
            body = (
                f"{marker}\n\n"
                f"Measure: **{name}**\n\n"
                f"File: `{path.as_posix()}`\n\n"
                f"Next review date: **{review_date}**\n\n"
                "Please review this measure and update "
                "`next_review` in its JSON definition."
            )

            if DRY_RUN:
                print(f"DRY RUN: Would create issue: {name} ({review_date})")
            else:
                gh("issue", "create",
                   "--title", f"Review overdue: {name}",
                   "--body", body,
                   "--label", LABEL)
                print(f"Created issue: {name}")

    # Close issues no longer overdue.
    for issue in issues:
        if issue["state"] != "open":
            continue

        body = issue.get("body") or ""
        if (
            "<!-- measure-review:" in body
            and LABEL in [
                label["name"] for label in issue["labels"]
            ]
            and not any(marker in body for marker in overdue)
        ):
            if DRY_RUN:
                print(f"DRY RUN: Would close issue #{issue['number']}")
            else:
                gh("issue", "close", str(issue["number"]),
                   "--comment", "Measure is no longer overdue.")
                print(f"Closed issue #{issue['number']}")


if __name__ == "__main__":
    main()
