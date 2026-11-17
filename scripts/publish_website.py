"""Propose an allowlisted static mark update through git/gh; never merge/deploy."""
import argparse
import base64
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import urllib.parse

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.export_website import FILES, load_export

SOURCE = "gloghry/icon"
WEBSITE = "gloghry/gloghry.github.io"
WEBSITE_ISSUE = 86
PRIORITY_FIELD = 49933722
MARKER = "<!-- gl-static-export-v1 -->"
PREFIX = "icon-update/"
CHANGE_TYPES = {"bug", "enhancement", "documentation", "maintenance"}


class APIError(RuntimeError):
    def __init__(self, status):
        self.status = status
        super().__init__("GitHub request failed (HTTP " + str(status) + ")")


class API:
    def __init__(self, token):
        if not token:
            raise ValueError("Missing publishing/read credential")
        self.token = token

    def request(self, method, path, data=None):
        # Fixed host and non-verbose subprocesses keep credentials/response bodies out of logs.
        command = ["gh", "api", "--hostname", "github.com", "--method", method,
                   "-H", "X-GitHub-Api-Version: 2026-03-10", path]
        if data is not None:
            command += ["--input", "-"]
        result = subprocess.run(command, input=None if data is None else json.dumps(data),
                                env={**os.environ, "GH_TOKEN": self.token, "GH_DEBUG": ""},
                                text=True, capture_output=True, timeout=60)
        if result.returncode:
            match = re.search(r"HTTP (\d{3})", result.stderr)
            raise APIError(int(match[1]) if match else 0)
        return json.loads(result.stdout) if result.stdout.strip() else None


def blob_sha(data):
    import hashlib
    return hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()


def current(source_api, sha):
    return source_api.request("GET", "/repos/" + SOURCE + "/git/ref/heads/master")["object"]["sha"] == sha


def file_sha(api, name, ref):
    path = "/repos/" + WEBSITE + "/contents/" + name + "?ref=" + urllib.parse.quote(ref, safe="")
    try:
        result = api.request("GET", path)
    except APIError as error:
        if error.status == 404:
            return None
        raise
    if result.get("type") != "file":
        raise ValueError("Unexpected website file type")
    return result["sha"]


def pulls(api, state="open", branch=None):
    result = []
    page = 1
    while True:
        query = {"state": state, "per_page": 100, "page": page}
        if branch:
            query["head"] = "gloghry:" + branch
        batch = api.request("GET", "/repos/" + WEBSITE + "/pulls?" + urllib.parse.urlencode(query))
        result.extend(batch)
        if len(batch) < 100:
            return result
        page += 1


def owned(pr):
    head = pr.get("head") or {}
    return ((pr.get("body") or "").startswith(MARKER)
            and head.get("ref", "").startswith(PREFIX)
            and (head.get("repo") or {}).get("full_name") == WEBSITE)


def verify_branch(api, branch, desired):
    if any(file_sha(api, name, branch) != sha for name, sha in desired.items()):
        raise ValueError("Publication branch differs from export")
    result = api.request("GET", "/repos/" + WEBSITE + "/compare/main..." + branch)
    # GitHub limits comparison file lists to 300. Never accept a truncated comparison.
    if len(result["files"]) >= 300 or any(f["filename"] not in FILES
            or f.get("previous_filename", f["filename"]) not in FILES for f in result["files"]):
        raise ValueError("Publication branch contains unrelated changes")


def supersede(api, keep=None):
    for pr in pulls(api):
        if pr["number"] != keep and owned(pr):
            api.request("PATCH", "/repos/" + WEBSITE + "/pulls/" + str(pr["number"]), {"state": "closed"})


def linked_priority(api):
    issue = api.request("GET", "/repos/" + WEBSITE + "/issues/" + str(WEBSITE_ISSUE))
    if issue.get("pull_request"):
        raise ValueError("Website tracking reference must be an issue")
    values = [v["single_select_option"]["name"] for v in issue.get("issue_field_values", [])
              if v["issue_field_id"] == PRIORITY_FIELD and v.get("single_select_option")]
    if len(values) != 1 or values[0] not in {"Urgent", "High", "Medium", "Low"}:
        raise ValueError("Website tracking issue needs an unambiguous native Priority")
    return values[0]


def finalize(api, pr, priority):
    route = "/repos/" + WEBSITE + "/issues/" + str(pr["number"])
    labels = api.request("GET", route + "/labels")
    for label in labels:
        name = label["name"]
        if name in CHANGE_TYPES - {"enhancement"} or name.startswith("priority:"):
            api.request("DELETE", route + "/labels/" + urllib.parse.quote(name, safe=""))
    applied = api.request("POST", route + "/labels", {"labels": ["enhancement"]})
    if {x["name"] for x in applied} & CHANGE_TYPES != {"enhancement"}:
        raise ValueError("Website PR change-type labels need review")
    api.request("POST", route + "/issue-field-values", {
        "issue_field_values": [{"field_id": PRIORITY_FIELD, "value": priority}]})
    fields = api.request("GET", route).get("issue_field_values", [])
    if not any(v["issue_field_id"] == PRIORITY_FIELD
               and v.get("single_select_option", {}).get("name") == priority for v in fields):
        raise ValueError("Website PR native Priority was not applied")
    supersede(api, pr["number"])


def push_candidate(token, base, branch, files):
    """Create one atomic commit through git, with no force push or source history."""
    auth = base64.b64encode(("x-access-token:" + token).encode()).decode()
    env = {**os.environ, "GIT_TERMINAL_PROMPT": "0", "GIT_CONFIG_NOSYSTEM": "1",
           "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_COUNT": "2",
           "GIT_CONFIG_KEY_0": "http.https://github.com/.extraheader",
           "GIT_CONFIG_VALUE_0": "AUTHORIZATION: basic " + auth,
           "GIT_CONFIG_KEY_1": "credential.helper", "GIT_CONFIG_VALUE_1": ""}
    # Prevent inherited tracing from printing authentication headers.
    for name in list(env):
        if name.startswith("GIT_TRACE") or name == "GIT_CURL_VERBOSE":
            del env[name]
    with tempfile.TemporaryDirectory(prefix="gl-website-") as temporary:
        def git(*args):
            result = subprocess.run(["git", *args], cwd=temporary, env=env,
                                    capture_output=True, timeout=120)
            if result.returncode:
                raise RuntimeError("Website git operation failed; no default branch write attempted")
        git("init", "--quiet")
        git("remote", "add", "origin", "https://github.com/" + WEBSITE + ".git")
        git("fetch", "--quiet", "--depth", "1", "origin", base)
        git("checkout", "--quiet", "--detach", "FETCH_HEAD")
        for name, data in files.items():
            path = Path(temporary) / name
            # Do not follow a symlink introduced in the destination repository.
            if any(p.is_symlink() for p in (path, *path.parents)):
                raise ValueError("Website destination contains symlink")
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        git("add", "--", *FILES)
        git("diff", "--cached", "--check")
        git("-c", "user.name=GL asset publisher", "-c",
            "user.email=41898282+github-actions[bot]@users.noreply.github.com",
            "-c", "commit.gpgsign=false", "commit", "--quiet", "-m", "Update the static GL header mark")
        git("push", "--quiet", "origin", "HEAD:refs/heads/" + branch)


def publish(api, source_api, folder, sha, push=None):
    if not re.fullmatch(r"[0-9a-f]{40}", sha):
        raise ValueError("Invalid source revision")
    files, digest = load_export(folder)
    if not current(source_api, sha):
        return {"status": "skipped-stale"}
    repo = api.request("GET", "/repos/" + WEBSITE)
    if repo["default_branch"] != "main" or repo["private"]:
        raise ValueError("Website configuration changed; review required")
    base = api.request("GET", "/repos/" + WEBSITE + "/git/ref/heads/main")["object"]["sha"]
    desired = {n: blob_sha(v) for n, v in files.items()}
    if all(file_sha(api, n, base) == value for n, value in desired.items()):
        if not current(source_api, sha):
            return {"status": "skipped-stale"}
        supersede(api)
        return {"status": "unchanged"}
    priority = linked_priority(api)
    branch = PREFIX + digest[:24]
    candidates = pulls(api, "all", branch)
    if candidates:
        pr = candidates[0]
        if not owned(pr):
            raise ValueError("Publication branch is not publisher-owned")
        if pr["state"] == "open":
            verify_branch(api, branch, desired)
            if not current(source_api, sha):
                return {"status": "skipped-stale"}
            finalize(api, pr, priority)
        return {"status": "existing-" + pr["state"], "number": pr["number"]}
    try:
        api.request("GET", "/repos/" + WEBSITE + "/git/ref/heads/" + branch)
        branch_exists = True
    except APIError as error:
        if error.status != 404:
            raise
        branch_exists = False
    if branch_exists:
        verify_branch(api, branch, desired)
    else:
        if not current(source_api, sha):
            return {"status": "skipped-stale"}
        if push is None:
            push = lambda b, br, f: push_candidate(api.token, b, br, f)
        push(base, branch, files)
        verify_branch(api, branch, desired)
    if not current(source_api, sha):
        return {"status": "skipped-stale"}
    account = api.request("GET", "/user")["login"]
    body = MARKER + """
Update the prebuilt GL header PNG/WebP, simplified favicon and public provenance.
Review the exact asset diff, desktop/mobile light/dark previews and website CI
before merging. This publisher never merges or deploys. Historical screenshots
in docs/gl-mark-review are not refreshed by this proposal.

Related to #86. Keep the tracking issue open for future imports.

Design and camera selection: Garett Loghry.

**AI assistance:** Codex implemented the static asset publisher; this automated
PR was opened using the configured publishing account: `""" + account + "`.\n"
    pr = api.request("POST", "/repos/" + WEBSITE + "/pulls", {
        "title": "Update the static GL header mark", "head": branch, "base": "main", "body": body})
    finalize(api, pr, priority)
    return {"status": "opened", "number": pr["number"]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--export", type=Path, required=True)
    parser.add_argument("--source-sha", required=True)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    if args.dry_run:
        files, digest = load_export(args.export)
        result = {"status": "dry-run", "files": list(files), "export_digest": digest}
    else:
        result = publish(API(os.environ["WEBSITE_TOKEN"]), API(os.environ["SOURCE_TOKEN"]), args.export, args.source_sha)
    print(json.dumps(result))
    if os.getenv("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a") as output:
            output.write("Static GL publisher: **" + result["status"] + "**.\n")


if __name__ == "__main__":
    try:
        main()
    except (ValueError, RuntimeError, KeyError, OSError, subprocess.TimeoutExpired):
        # Avoid leaking tokens, source metadata or raw subprocess/API response bodies.
        print("Static GL publisher failed; inspect configuration and rerun after fixing it.", file=sys.stderr)
        raise SystemExit(1)
