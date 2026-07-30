# Release automation via semantic-release

Date: 2026-07-30

## Goal

Cut a GitHub Release automatically whenever main is updated with a releasable
change, without hand-editing version numbers.

## Approach

Conventional-commit-driven releases via `python-semantic-release` (PSR).
Chosen over `release-please` because PSR is Python-native (installable via
`uv`/`pip`, no Node toolchain) and this is a Python HA custom integration.
Chosen to release directly on push to main (no standing release PR) rather
than a review-gated release PR, for simplicity.

Because the existing commit history is not consistently conventional-commit
style (merge commits, plain messages), this only works going forward if main's
history is conventional-commit-shaped. That requires two supporting changes:

1. Squash-merge only, so each PR becomes one commit on main.
2. A PR-title lint check, so that commit message is guaranteed parseable.

## Components

### 1. Repo setting: squash-merge only

GitHub repo setting: disable "Create a merge commit" and "Rebase merge",
keep only "Squash and merge" enabled. One-time change via `gh api` or repo
Settings UI, requires explicit confirmation before applying (affects
collaborators' merge experience).

### 2. PR title lint — `.github/workflows/pr-title-lint.yaml`

Triggers: `pull_request` types `[opened, edited, synchronize]`.
Uses `amannn/action-semantic-pull-request` to validate the PR title matches
conventional-commit format (type prefix from the allowed list below). Fails
the check if not.

Allowed types (matches PSR's Angular-style default + `chore`):
`feat`, `fix`, `perf`, `refactor`, `docs`, `test`, `build`, `ci`, `chore`,
`style`, `revert`.

### 3. Release job — new job in `.github/workflows/ci.yaml`

```yaml
release:
  needs: test
  runs-on: ubuntu-latest
  if: github.ref == 'refs/heads/main' && github.event_name == 'push'
  permissions:
    contents: write
  steps:
    - uses: actions/checkout@v4
      with:
        fetch-depth: 0
    - name: Release
      uses: python-semantic-release/python-semantic-release@v9
      with:
        github_token: ${{ secrets.GITHUB_TOKEN }}
```

Behavior:
- Parses commits since the last `vX.Y.Z` tag for `feat`/`fix`/`BREAKING
  CHANGE` etc., computes next semver version.
- Bumps `version` in `pyproject.toml` (native TOML support) and in
  `custom_components/parkeren_nijmegen/manifest.json` (regex-based
  `version_variables`, since PSR doesn't have native JSON support but its
  regex substitution works on any text file containing `"version": "x.y.z"`).
- Generates/updates `CHANGELOG.md`.
- Commits as `chore(release): vX.Y.Z [skip ci]`, tags `vX.Y.Z`, pushes to
  main. `[skip ci]` avoids re-triggering the workflow on the bot's own push.
- Creates a GitHub Release from the tag with changelog notes.
- No PyPI publish step (not a published package) and no zip build artifact
  (this repo's `hacs.json` does not set `zip_release`, so HACS installs
  directly from the tagged ref).
- If no commit since the last tag carries a releasable type, the job is a
  no-op (no tag, no release) — expected and fine.

### 4. PSR config — new block in `pyproject.toml`

```toml
[tool.semantic_release]
version_toml = ["pyproject.toml:project.version"]
version_variables = ["custom_components/parkeren_nijmegen/manifest.json:version"]
branch = "main"
build_command = ""
commit_message = "chore(release): v{version} [skip ci]"
tag_format = "v{version}"
```

### 5. One-time bootstrap tag

Tag current HEAD (`089172b`) as `v0.1.0` and push it, before the release job
goes live, so PSR's first real run diffs from this baseline instead of the
entire project history. Requires explicit confirmation before pushing (tag
push to origin is shared/hard-to-reverse).

### 6. CLAUDE.md update

Add a "Commit / PR conventions" section to this repo's `CLAUDE.md`:
- Squash-merge only; PR titles must be conventional-commit style
  (list the allowed types from §2).
- Releases are cut automatically by semantic-release from PR titles on main
  — do not hand-bump `version` in `manifest.json` or `pyproject.toml`.
- A PR with a non-conforming title will fail the `pr-title-lint` check.

## Testing / verification

- `ruff check` / `ruff format --check` on the new workflow YAML is N/A (not
  Python); validate YAML syntax via `actionlint` or a dry push to a branch.
- Verify PSR config by running `uv run semantic-release version --print`
  locally (dry run, no push) against the current repo state once the
  bootstrap tag exists, to confirm it detects `0.1.0` as current and computes
  a sane next version from real commits.
- After merging, confirm the next conventional-commit PR (squash-merged)
  triggers the release job and produces a tag + GitHub Release + updated
  `manifest.json`/`pyproject.toml`/`CHANGELOG.md`.

## Out of scope

- PyPI publishing (not applicable).
- HACS zip release assets (not needed per current `hacs.json`).
- Migrating/rewriting past commit history to conventional-commit style.
