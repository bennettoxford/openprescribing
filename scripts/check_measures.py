
import json
import os
import re
import subprocess
from datetime import date, timedelta
from pathlib import Path

LABEL = "review-measure"
TODAY = date.today()
REVIEW_NOTICE_DAYS = 30
DRY_RUN = os.environ.get("DRY_RUN", "false").lower() == "true"
REVIEWERS = ["richiecroker","speed-vm","chrisjwood16","carolineacuda",]
PROJECT_OWNER = "bennettoxford"
PROJECT_NUMBER = 15
PROJECT_STATUS = "OP Measure Review"
REVIEW_DAYS = 14
DEFINITIONS = Path("openprescribing/measures/definitions")


def gh(*args):
    return subprocess.run(
        ["gh", *args], capture_output=True, text=True, check=True
    ).stdout


def project_configuration():
    project = json.loads(
        gh(
            "project",
            "view",
            str(PROJECT_NUMBER),
            "--owner",
            PROJECT_OWNER,
            "--format",
            "json",
        )
    )
    fields = json.loads(
        gh(
            "project",
            "field-list",
            str(PROJECT_NUMBER),
            "--owner",
            PROJECT_OWNER,
            "--format",
            "json",
            "--limit",
            "100",
        )
    )["fields"]

    def field(name, kind):
        found = next(
            (
                item
                for item in fields
                if item["name"] == name and item["dataType"] == kind
            ),
            None,
        )
        if found is None:
            raise ValueError(f"Project field {name!r} ({kind}) not found")
        return found

    status = field("Status", "SINGLE_SELECT")
    option = next(
        (item for item in status["options"] if item["name"] == PROJECT_STATUS), None
    )
    if option is None:
        raise ValueError(f"Project Status option {PROJECT_STATUS!r} not found")
    return (
        project["id"],
        field("Start date", "DATE")["id"],
        field("End date", "DATE")["id"],
        status["id"],
        option["id"],
    )


def add_to_project(issue_url, start, end, configuration, existing_items):
    project_id, start_id, end_id, status_id, option_id = configuration
    item_id = existing_items.get(issue_url)
    if item_id is None:
        item = json.loads(
            gh(
                "project",
                "item-add",
                str(PROJECT_NUMBER),
                "--owner",
                PROJECT_OWNER,
                "--url",
                issue_url,
                "--format",
                "json",
            )
        )
        item_id = item["id"]
        existing_items[issue_url] = item_id
    for field_id, value in ((start_id, start), (end_id, end)):
        gh(
            "project",
            "item-edit",
            "--id",
            item_id,
            "--project-id",
            project_id,
            "--field-id",
            field_id,
            "--date",
            value.isoformat(),
        )
    gh(
        "project",
        "item-edit",
        "--id",
        item_id,
        "--project-id",
        project_id,
        "--field-id",
        status_id,
        "--single-select-option-id",
        option_id,
    )


def main():
    if not DEFINITIONS.is_dir():
        raise FileNotFoundError(f"Definitions directory missing: {DEFINITIONS}")
    repo = os.environ["GITHUB_REPOSITORY"]
    pages = json.loads(
        gh(
            "api",
            "--paginate",
            f"repos/{repo}/issues?state=all&per_page=100",
            "--slurp",
        )
    )
    issues = [issue for page in pages for issue in page if "pull_request" not in issue]
    review_issues = sorted(
        (
            issue
            for issue in issues
            if "<!-- measure-review:" in (issue.get("body") or "")
        ),
        key=lambda issue: issue["number"],
    )
    reviewer_index = 0
    for issue in review_issues:
        match = re.search(r"<!-- review-rotation:(\d+) -->", issue.get("body") or "")
        if match:
            reviewer_index = (int(match.group(1)) + 1) % len(REVIEWERS)

    configuration = None
    existing_items = {}
    if not DRY_RUN:
        configuration = project_configuration()
        items = json.loads(
            gh(
                "project",
                "item-list",
                str(PROJECT_NUMBER),
                "--owner",
                PROJECT_OWNER,
                "--format",
                "json",
                "--limit",
                "10000",
            )
        )["items"]
        existing_items = {
            item["content"]["url"]: item["id"]
            for item in items
            if isinstance(item.get("content"), dict) and item["content"].get("url")
        }
        gh("label", "create", LABEL, "--color", "D93F0B", "--force")

    checked = 0
    created = 0
    for path in sorted(DEFINITIONS.rglob("*.json")):
        with path.open(encoding="utf-8") as handle:
            data = json.load(handle)
        if not isinstance(data, dict) or not data.get("next_review"):
            continue
        checked += 1
        review_date = date.fromisoformat(data["next_review"])
        if review_date > TODAY + timedelta(days=REVIEW_NOTICE_DAYS):
            continue
        marker = f"<!-- measure-review:{path.as_posix()}:{review_date.isoformat()} -->"
        existing = next(
            (issue for issue in review_issues if marker in (issue.get("body") or "")),
            None,
        )
        if existing:
            print(
                f"Already tracked: {path.name} ({review_date}) issue #{existing['number']}"
            )
            # Retry Project setup if issue creation succeeded but Project update failed.
            if not DRY_RUN:
                match = re.search(
                    r"<!-- review-start:(\d{4}-\d{2}-\d{2}) -->",
                    existing.get("body") or "",
                )
                if match and existing["html_url"] not in existing_items:
                    start = date.fromisoformat(match.group(1))
                    add_to_project(
                        existing["html_url"],
                        start,
                        start + timedelta(days=REVIEW_DAYS),
                        configuration,
                        existing_items,
                    )
            continue

        name = data.get("name") or path.stem
        reviewer = REVIEWERS[reviewer_index]
        start = TODAY
        end = start + timedelta(days=REVIEW_DAYS)
        body = (
            f"{marker}\n"
            f"<!-- review-rotation:{reviewer_index} -->\n"
            f"<!-- review-start:{start.isoformat()} -->\n\n"
            f"**Measure:** {name}\n\n"
            f"**Definition:** `{path.as_posix()}`\n\n"
            f"**Review date:** {review_date}\n\n"
            f"**Reviewer:** @{reviewer}\n\n"
            f"**Start date:** {start}\n\n"
            f"**End date:** {end}\n\n"
            "Review the measure, update `next_review`, and close this issue manually."
        )
        if DRY_RUN:
            print(
                f"DRY RUN: Would create {name} ({review_date}) for @{reviewer}, {start} to {end}, Project {PROJECT_NUMBER}, Status {PROJECT_STATUS}"
            )
        else:
            issue_url = gh(
                "issue",
                "create",
                "--title",
                f"Review overdue: {name} ({review_date})",
                "--body",
                body,
                "--label",
                LABEL,
                "--assignee",
                reviewer,
            ).strip()
            print(f"Created issue: {issue_url}")
            add_to_project(issue_url, start, end, configuration, existing_items)
        created += 1
        reviewer_index = (reviewer_index + 1) % len(REVIEWERS)

    print(
        f"Checked {checked} dated definitions; {'would create' if DRY_RUN else 'created'} {created} issues."
    )


if __name__ == "__main__":
    main()
