
import json
import os
import re
import subprocess
from datetime import date, timedelta
from pathlib import Path

LABEL = "review-overdue"
TODAY = date.today()
DRY_RUN = os.environ.get("DRY_RUN", "false").lower() == "true"

# Replace with actual GitHub usernames, in rotation order.
REVIEWERS = [
    "richiecroker",
    "speed-vm",
    "chrisjwood16",
    "carolineacuda",
]

REVIEW_DAYS = 14


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

    # Retrieve all issues, including closed issues.
    issues = json.loads(
        gh(
            "api",
            "--paginate",
            f"repos/{repo}/issues?state=all&per_page=100",
            "--slurp",
        )
    )

    issues = [issue for page in issues for issue in page if "pull_request" not in issue]

    # Find previously created measure-review issues.
    review_issues = [
        issue
        for issue in issues
        if "<!-- measure-review:" in (issue.get("body") or "")
    ]

    # Sort by issue number to reconstruct assignment order.
    review_issues.sort(key=lambda issue: issue["number"])

    # Determine the next reviewer from the stored rotation marker.
    reviewer_index = 0

    for issue in review_issues:
        body = issue.get("body") or ""
        match = re.search(r"<!-- review-rotation:(\d+) -->", body)

        if match:
            previous_index = int(match.group(1))
            reviewer_index = (previous_index + 1) % len(REVIEWERS)

    if not DRY_RUN:
        gh("label", "create", LABEL, "--color", "D93F0B", "--force")

    overdue = set()
    checked = 0
    new_issues = 0

    # Search only the measure definitions.
    for path in sorted(Path("openprescribing/measures/definitions").rglob("*.json")):
        checked += 1

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
            (issue for issue in review_issues if marker in (issue.get("body") or "")),
            None,
        )

        if review_date < TODAY:
            overdue.add(marker)

            # Existing issues are not reassigned.
            if existing:
                if existing["state"] == "closed":
                    if DRY_RUN:
                        print(f"DRY RUN: Would reopen issue #{existing['number']}")
                    else:
                        gh("issue", "reopen", str(existing["number"]))
                continue

            name = data.get("name", path.stem)
            reviewer = REVIEWERS[reviewer_index]
            due_date = TODAY + timedelta(days=REVIEW_DAYS)

            rotation_marker = f"<!-- review-rotation:{reviewer_index} -->"

            body = (
                f"{marker}\n"
                f"{rotation_marker}\n\n"
                f"## Measure review required\n\n"
                f"**Measure:** {name}\n\n"
                f"**Definition:** `{path.as_posix()}`\n\n"
                f"**Next review date:** {review_date:%Y-%m-%d}\n\n"
                f"**Assigned reviewer:** @{reviewer}\n\n"
                f"**Review deadline:** {due_date:%Y-%m-%d}\n\n"
                "Please review the measure definition and "
                "update `next_review` when the review is complete."
            )

            if DRY_RUN:
                print(
                    f"DRY RUN: Would create issue: {name} "
                    f"({review_date}) assigned to @{reviewer}, "
                    f"due {due_date}"
                )
            else:
                gh(
                    "issue",
                    "create",
                    "--title",
                    f"Review overdue: {name}",
                    "--body",
                    body,
                    "--label",
                    LABEL,
                    "--assignee",
                    reviewer,
                )
                print(
                    f"Created issue: {name}, "
                    f"assigned to @{reviewer}, due {due_date}"
                )

            new_issues += 1
            reviewer_index = (reviewer_index + 1) % len(REVIEWERS)

    # Close issues whose measures are no longer overdue.
    for issue in review_issues:
        if issue["state"] != "open":
            continue

        body = issue.get("body") or ""

        if (
            LABEL in [label["name"] for label in issue["labels"]]
            and not any(marker in body for marker in overdue)
        ):
            if DRY_RUN:
                print(f"DRY RUN: Would close issue #{issue['number']}")
            else:
                gh(
                    "issue",
                    "close",
                    str(issue["number"]),
                    "--comment",
                    "Measure is no longer overdue.",
                )
                print(f"Closed issue #{issue['number']}")

    print(f"\nChecked {checked} JSON files.")
    print(f"{new_issues} new review issues {'identified' if DRY_RUN else 'created'}.")

    if DRY_RUN:
        print("DRY RUN complete. No GitHub issues were modified.")


if __name__ == "__main__":
    main()
