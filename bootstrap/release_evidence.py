"""Read-only publication preflight: bind successful CI to the exact release SHA."""

import argparse
import json
import re
import subprocess
import sys
from urllib.parse import urlencode


WORKFLOW = "bootstrap-consumer-tests.yml"
BRANCH = "release/v1.25"
REQUIRED_JOBS = {"Bootstrap (ubuntu-latest)", "Bootstrap (windows-latest)"}


class EvidenceError(RuntimeError):
    pass


def api(endpoint):
    try:
        result = subprocess.run(
            ["gh", "api", endpoint], capture_output=True, text=True, check=False
        )
    except FileNotFoundError as error:
        raise EvidenceError("GitHub CLI is required.") from error
    if result.returncode:
        raise EvidenceError(
            "GitHub API failed; check gh authentication, organization SSO and repository access."
        )
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as error:
        raise EvidenceError("GitHub API returned invalid JSON.") from error
    if not isinstance(payload, dict):
        raise EvidenceError("GitHub API returned an unexpected response.")
    return payload


def find_evidence(repository, sha):
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository):
        raise EvidenceError("Repository must be owner/name, not a URL or credentials.")
    if not re.fullmatch(r"[0-9a-f]{40}", sha):
        raise EvidenceError("Supply the full 40-character release commit SHA.")
    query = urlencode({
        "branch": BRANCH, "event": "push", "head_sha": sha,
        "status": "success", "per_page": 100,
    })
    runs = api(
        f"repos/{repository}/actions/workflows/{WORKFLOW}/runs?{query}"
    ).get("workflow_runs")
    if not isinstance(runs, list):
        raise EvidenceError("GitHub API did not return workflow runs.")
    for run in runs:
        if not isinstance(run, dict):
            raise EvidenceError("GitHub API returned a malformed workflow run.")
        # Exact SHA is essential here: a different commit's CI cannot authorize a release.
        if (
            run.get("head_sha") != sha
            or run.get("head_branch") != BRANCH
            or run.get("event") != "push"
            or run.get("status") != "completed"
            or run.get("conclusion") != "success"
            or run.get("path") != f".github/workflows/{WORKFLOW}"
        ):
            continue
        run_id = run.get("id")
        if not isinstance(run_id, int):
            raise EvidenceError("GitHub API returned a workflow without a run ID.")
        jobs = api(f"repos/{repository}/actions/runs/{run_id}/jobs?per_page=100").get("jobs")
        if not isinstance(jobs, list) or not all(isinstance(job, dict) for job in jobs):
            raise EvidenceError("GitHub API returned malformed job evidence.")
        successful = {
            job.get("name") for job in jobs if job.get("conclusion") == "success"
        }
        if REQUIRED_JOBS <= successful:
            return {
                "repository": repository, "headSha": sha, "branch": BRANCH,
                "runId": run_id, "url": run.get("html_url"),
                "jobs": sorted(REQUIRED_JOBS),
            }
    raise EvidenceError(
        "No completed successful push run with both platforms for this exact release SHA. "
        "Do not tag or publish yet."
    )


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", required=True, help="GitHub owner/repository")
    parser.add_argument("--sha", required=True, help="Exact BLUE commit, not a branch or tag")
    args = parser.parse_args(argv)
    try:
        evidence = find_evidence(args.repo, args.sha)
    except EvidenceError as error:
        print(f"Release blocked: {error}", file=sys.stderr)
        return 1
    print(json.dumps(evidence, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
