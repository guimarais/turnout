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

## Main-branch policy

Every merge must leave `main` usable. Keep unfinished functionality inaccessible
until it is ready. Maintainer and agent changes follow the same rules.

The active [Main PR policy ruleset](https://github.com/guimarais/turnout/rules/26382156)
targets `refs/heads/main`. Its configuration and the repository merge settings
were applied and verified on 2026-11-02:

| Setting | Required value |
| --- | --- |
| Require a pull request before merging | Enabled |
| Required approving reviews | 0; no assigned reviewer requirement |
| Require conversation resolution | Enabled |
| Require status checks | Select the `tests` check from GitHub Actions |
| Require branches to be up to date | Enabled |
| Block force pushes | Enabled |
| Restrict deletions | Enabled |

Do not enable “Restrict updates”: that would prevent ordinary merges without a
bypass. Allow only squash merges and automatically delete merged branches.
Use descriptive PR titles without mandating a commit-message convention.

Repository administrators may bypass merge gates through a PR for emergency
recovery only. Record the reason, skipped or failed validation, risk, and recovery
or follow-up work in that PR. Routine changes must pass every gate. Direct
pushes, force pushes, and deletion of `main` are not emergency bypass paths.

Each PR must describe the problem, resulting behavior, validation performed, and
material risks. Keep changes focused, include relevant regression tests, and
update affected documentation. Validation must match the change: geometry or
export changes need representative fixtures and recorded XTrackCAD version and
open/save/reopen results. Arbitrary coverage percentages and PR size limits are
not required.

Hosted enforcement is separate from these files. Check the repository's active
rulesets and merge settings on GitHub when verifying enforcement. GitHub enforces
merge gates; PR evidence, continued usability, and the emergency-only bypass
policy remain maintainer responsibilities.

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
4. **Independent review if agreed later.** There is currently no approval or
   assigned reviewer requirement. Revisit this policy explicitly if review needs
   change; adding maintainers does not automatically introduce a requirement.
5. **Compatibility evidence as support expands.** Add Python/OS CI jobs for
   environments you commit to support and versioned XTrackCAD fixtures for new
   file formats. Keep manual open/save/reopen acceptance for writer changes.
6. **Release policy before the first release.** Define supported installation,
   versioning, release notes, and tagged releases before adding publishing
   automation. Keep coverage thresholds, signed commits, and release pipelines
   optional until there is a concrete need.
