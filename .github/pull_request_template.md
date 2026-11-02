## Change

Describe the problem and resulting behavior. Link an issue if there is one.

## Verification

- [ ] `uv sync --locked`
- [ ] `uv run --locked python -m unittest discover -s tests -v`
- [ ] Added a regression check for changed behavior, where applicable.
- [ ] Updated affected paths, launch instructions, and documentation.
- [ ] `main` remains usable; unfinished functionality is inaccessible.

For changes to track geometry or XTrackCAD records, describe the representative
fixture and XTrackCAD open/save/reopen result. Otherwise, write “not applicable”.
Include the XTrackCAD version used.

## Risks

Describe material risks and recovery steps where relevant, or write “none”.

## Emergency bypass

Write “not applicable” for routine changes. For emergency recovery, explain why
the merge gates must be bypassed, skipped or failed validation, risks, and
recovery or follow-up work.
