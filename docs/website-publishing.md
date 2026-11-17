# Static GL website publisher

The implementation follows the Resume publisher pattern. Live proposals remain
off until `WEBSITE_PUBLISH_TOKEN` and `ICON_WEBSITE_PUBLISH_ENABLED=true` are
configured in **this icon repository**. Track implementation and first-run
verification in [issue #12](https://github.com/gloghry/icon/issues/12); recurring
website imports reference [website issue #86](https://github.com/gloghry/gloghry.github.io/issues/86).

## Flow

1. Generate and review the original variant offline, then commit the generated
   assets alongside the source changes. The publisher validates committed
   exports; it does not rebuild Blender during delivery or Jekyll builds.
2. On relevant PRs, master pushes or manual runs, a read-only job checks the
   source/effective config, manifest hashes, web report and image formats.
   It stages exactly five files:

   - `assets/images/gl/gl-mark.png`
   - `assets/images/gl/gl-mark.webp`
   - `assets/images/gl/favicon.svg`
   - `docs/gl-mark-provenance.json`
   - `docs/gl-mark.md`

3. A seven-day review artifact holds those files and an integrity manifest.
   No `.blend`, GLB, source tree, reference or build log is uploaded by this
   workflow. Public provenance records the source repository, immutable asset
   commit, source directory, content hashes and camera settings, as required by
   the website rights inventory. It omits workflow URLs.
4. Only an enabled master push/manual run enters the separate publishing job.
   It receives a website-scoped PAT and a separate read-only source token to
   reject stale runs. PRs, forks and manual non-master runs cannot publish.
5. The publisher uses `git` to commit/push the five files on a content-addressed
   `icon-update/` branch and `gh` to propose the website PR. No source history
   crosses repositories. It applies one change-type label, `enhancement`, and
   copies native Priority from website issue #86.
6. Existing website CI checks Jekyll, links, accessibility and header rendering.
   Review desktop/mobile light/dark screenshots and the preview before merging.
   The publisher never merges, approves or deploys. Historical screenshots in
   `docs/gl-mark-review/` are not updated by it.

The icon repository can be private: its own workflow reads it, while the website
receives only the selected public bundle. The source repository name, asset
commit and directory remain public provenance; source content and credentials
are not copied. Omitting those identifiers would require a separately reviewed
change to the website's rights/provenance policy. No website-side source token,
polling, Blender runtime or viewer is added. Visibility, access controls, branch
protection and hosting remain unchanged.

## Local review

Use Python 3.10+ from the icon repository root. Staging and dry-run need no
credentials, network, Blender or imaging library. Git and the committed asset
history must be available:

```sh
python3 -m unittest discover -s tests -v
python3 scripts/export_website.py --destination /tmp/gl-website-export
python3 scripts/publish_website.py --dry-run --export /tmp/gl-website-export \
  --source-sha 0000000000000000000000000000000000000000
```

Choose a destination that does not exist. The dry run reports the exact file
allowlist and content digest without contacting GitHub. Tests include real git
commits against a temporary local bare remote, confirming that only a candidate
branch changes and unrelated website files survive. Existing Blender CI checks
the model; installing requirements-web.txt also enables image conversion tests.

The exporter identifies the last commit that changed `generated/original`,
using a full-history checkout. That immutable commit includes the generated
files and corresponding source at that revision. Later publisher-only changes
do not churn the public source commit or open duplicate asset PRs. Uncommitted
generated changes are rejected: regenerate, review and commit them first. The
separate workflow run SHA is used only to reject stale runs, not as the asset's
provenance identity.

## One-time setup after reviewing the implementation

1. Use a fine-grained PAT owned by `gloghry`, restricted to the destination
   **gloghry/gloghry.github.io**, with **Contents: read/write** and **Pull
   requests: read/write**, plus automatic metadata access. No access to this
   source repo, Actions, administration or workflow files is needed. This matches
   Resume's destination permissions. Set an expiry and renewal reminder. An
   existing suitable token can be reused if you still hold its value; GitHub
   does not return existing secret values.
2. In **icon → Settings → Secrets and variables → Actions**, add the repository
   secret **`WEBSITE_PUBLISH_TOKEN`**. Paste the token directly into GitHub,
   rather than chat, source files or command arguments. Resume's repository
   secret is not automatically shared with icon. No paid environment is needed.
3. After the publisher PR merges and credentials are ready, set the repository
   variable **`ICON_WEBSITE_PUBLISH_ENABLED`** to **`true`**. Leave it absent or
   false until then. Missing credentials on an enabled run cause a visible
   configuration failure instead of silently skipping the proposal.
4. Run **Actions → Static GL website proposal → Run workflow → master**. This
   first run proposes the current approved camera baseline, even without a new
   asset change. Inspect the artifact and website PR, label, native Priority,
   hashes and token-triggered CI results.
5. Review the website preview/screenshots before merging its separate PR.
   Verify the deployed mark after the approved website merge. Record the first
   live result in #12 before closing it. Local validation does not prove that
   a configured token can trigger destination workflows.

As in Resume, this is a repository secret. Review workflow changes and preserve
existing PR protections, since repository workflows can reference the secret.
This publisher supplies it only to its separate publishing job and never tries
to approve or bypass destination protections.

## Retry, disable and recovery

- Runs are serialized without canceling writes. Source master must still match
  the run's revision before publication proceeds. If it moves during a push, an
  unused branch may remain, but that run does not open a stale PR.
- Identical output creates no new commit/PR. Open identical proposals are
  verified and reused; retries repair labels/fields. Human-closed or merged
  proposals are not reopened for identical content. Change the reviewed output
  to propose different content.
- Existing branches must match the exact five files and contain no unrelated
  diff against website main. No force push is used. New proposals close only
  older publisher-marked icon-update PRs, leaving unrelated PRs untouched.
- API/authentication/git failures cannot change website main. A failure after
  pushing/opening may leave a branch or incomplete PR; rerun the current master
  workflow to repair. Raw API/subprocess errors are suppressed to avoid logging
  credentials and source metadata. Actions summaries report the result; this
  workflow creates no external email/Slack notifications.
- Disable new proposals with `ICON_WEBSITE_PUBLISH_ENABLED=false`. Cancel an
  already-admitted job and revoke the PAT if needed. Renew by replacing the
  repository secret with a new website-scoped token, testing a manual run, then
  revoking the old token.
- Restore an incorrect deployed mark through a website PR reverting the three
  assets and two provenance documents together; correct the source before
  re-enabling proposals. This publisher never rolls back or merges the website.

## References

- [Resume pattern](https://github.com/gloghry/Resume/blob/main/career/publishing.md)
  (private source; not included in website exports).
- [Fine-grained tokens](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/managing-your-personal-access-tokens)
- [Actions secrets](https://docs.github.com/en/actions/how-tos/write-workflows/choose-what-workflows-do/use-secrets)
- [Token-authenticated triggers](https://docs.github.com/en/actions/how-tos/write-workflows/choose-when-workflows-run/trigger-a-workflow)
- [Native field token permissions](https://docs.github.com/en/rest/issues/issue-field-values)
