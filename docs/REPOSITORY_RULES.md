# Repository development rules

## Included in this checkout

- CI runs locked installation and the complete unittest suite on pushes and PRs.
  Its stable job/check name is `tests`, under the `CI` workflow.
- Workflow permissions are read-only, checkout credentials are not persisted,
  third-party actions are pinned to commit SHAs, and runs have a time limit.
- Dependabot proposes weekly updates for uv dependencies and GitHub Actions.
  Review updates through the same checks; automatic merging is not configured.
- Contribution guidance and issue/PR templates capture reproducible workflows,
  validation evidence, and manual XTrackCAD acceptance where relevant.

The configuration follows the official [uv Actions guide](https://docs.astral.sh/uv/guides/integration/github/)
and [uv Dependabot guide](https://docs.astral.sh/uv/guides/integration/dependabot/).

## Proposed default-branch ruleset

These are recommendations, not settings applied to GitHub. After the workflow
has run on GitHub, create an active branch ruleset under repository Settings →
Rules → Rulesets targeting the default branch:

| Setting | Recommended value |
| --- | --- |
| Require a pull request before merging | Enabled |
| Required approving reviews | 0 while there is one maintainer |
| Require conversation resolution | Enabled |
| Require status checks | Select the `tests` check from GitHub Actions |
| Require branches to be up to date | Enabled |
| Block force pushes | Enabled |
| Restrict deletions | Enabled |

Do not enable “Restrict updates”: that would prevent ordinary merges without a
bypass. Avoid routine bypasses; the maintainer should use PRs and passing checks
too. As a repository merge preference, enable squash merging and automatic
deletion of merged branches. Use descriptive PR titles without mandating a
commit-message convention.

See GitHub's [available rules and plan availability](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/available-rules-for-rulesets).
Require only checks that actually run on every PR; a renamed or filtered-out
required check can block merges.

## Further rules to add when useful

1. **Catalogue provenance before distribution.** Record the source, version, and
   redistribution terms for `data/catalogues/mrklnhoc-de.xtp`. The file has no
   provenance notice; do not infer its licensing from the repository's GPLv3
   license. Keep this a checkout-based application until distribution is defined.
2. **Security reporting before broader adoption.** Define a private reporting
   channel and supported versions in `SECURITY.md`. Review GitHub's
   [secret scanning and push protection](https://docs.github.com/en/code-security/secret-scanning/introduction/about-secret-scanning)
   options for the repository when enabling hosted security features.
3. **Formatting and linting when consistency becomes work.** Adopt one tool,
   such as Ruff, with an agreed configuration and a passing baseline before
   making its CI check mandatory. Avoid layering multiple overlapping tools.
4. **Independent review when there is a second maintainer.** Require one
   approval and dismiss stale approvals. Add CODEOWNERS only once ownership is
   established; do not create an approval requirement nobody can satisfy.
5. **Compatibility evidence as support expands.** Add Python/OS CI jobs for
   environments you commit to support and versioned XTrackCAD fixtures for new
   file formats. Keep manual open/save/reopen acceptance for writer changes.
6. **Release policy before the first release.** Define supported installation,
   versioning, release notes, and tagged releases before adding publishing
   automation. Keep coverage thresholds, signed commits, and release pipelines
   optional until there is a concrete need.
