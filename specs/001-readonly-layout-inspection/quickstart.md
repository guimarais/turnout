# Quickstart: Validate Read-Only Layout Inspection

This validates the planned vertical slice; it is not implementation code.

## Prerequisites

- Rust stable toolchain selected by the repository; record `rustc --version` and `cargo --version` with verification results. The channel is rolling rather than an exact compiler pin.
- A plain-text `.xtc` fixture from `tests/fixtures/authored/` or a compatibility fixture with a provenance manifest.
- An MCP client that can launch a STDIO server, or the repository's STDIO integration test.

## Validate the fixture reader

1. Run `cargo test --test parser_tests`.
2. Confirm valid fixtures produce expected summary and supported straight, curve, and turnout counts. In particular, `layouts/mrkln_sample.xtc` returns four turnouts, its two titles, HO scale, room dimensions, UTF-8 Märklin labels, and endpoint states.
3. Confirm malformed and unsupported-feature fixtures produce expected diagnostic codes.
4. Confirm integrity assertions verify content and modification time are unchanged.
5. Confirm format 12 is accepted independently of producing application version; format 11 and 13 fail with `unsupported_version`, while missing/malformed format declarations fail with `malformed_record`.
6. Check analytical bounds for straight segments, arcs crossing cardinal extrema, negative-radius direction handling, full circles, and asymmetric rotated turnout segments. Check that decorative segments do not expand bounds and that room dimensions are separate.
7. Confirm unknown potentially-track objects, unsupported track segments, missing geometry, and empty layouts return null bounds with `bounds_unavailable`; never accept partial extents as complete. Validate non-finite numbers, duplicate IDs, missing segment terminators, and dangling endpoint references with source diagnostics.

Expected outcome: format behavior is limited to the fixture-proven scope in [data-model.md](./data-model.md).

## Validate MCP over STDIO

1. Run `cargo test --test mcp_stdio_tests`.
2. The test launches Turnout as a subprocess over STDIO.
3. Invoke `tools/list`, `open_layout` with a valid fixture, `get_layout_info`, and `list_tracks`.
4. Assert results conform to [the tool contract](./contracts/read-only-tools.md), including units, ordering, counts, and diagnostics.
5. Repeat with a nonexistent path, malformed fixture, and unsupported-record fixture; verify expected errors or warnings.
6. Verify immediate open diagnostics, distinct format/application versions, explicit null optional fields, bounds availability, and units for every returned geometric field. Verify a failed open clears the previous session.

Expected outcome: a client completes the inspection sequence without conversion or source-file changes.

## Compatibility-corpus acceptance

Before adding a tool-produced fixture, record creator/version, origin or permission, SHA-256, and expected supported/unsupported records in the corpus manifest. Run both test layers. A mismatch is a finding to investigate, not permission to broaden advertised support.

## Final Linux checks

Run `cargo fmt --check`, `cargo clippy --all-targets -- -D warnings`, and `cargo test --locked` after completing implementation. Record the actual compiler versions, test totals, and outcomes here only after these commands run. The design above is the acceptance target; this planning pass does not constitute implementation validation.

## Verified implementation results — 2026-10-31

Validated on Linux x86_64 using `rustc 1.99.1 (58cf8f9c3 2026-10-13)` and `cargo 1.99.1 (5f94df478 2026-08-27)`. The toolchain uses the rolling stable channel with rustfmt and Clippy components; dependency versions are recorded in `Cargo.lock`.

| Command | Result |
|---|---|
| `cargo fmt --check` | PASS |
| `cargo clippy --all-targets --locked -- -D warnings` | PASS, no warnings |
| `cargo test --locked` | PASS, 42 integration tests: 22 parser, 12 bounds, 8 MCP |
| `cargo build --release --locked` | PASS |

MCP tests invoke all three tools, validate structured and equivalent text results, and launch the built executable over actual STDIO from a different working directory using absolute input paths. Handshake/request/shutdown timeouts and successful child exit are checked. Both valid and malformed fixture reads preserve input bytes and modification time. The Unix permission-denial assertion runs only when the executing account is subject to the file's permission restrictions.

Validated geometry includes curve interior extrema, full circles, native negative-radius locus behavior, and rotated compound turnout lines/arcs. The supplied layout retains four turnout records with corrected anchors and rotation. Unknown potentially-track geometry and empty layouts produce explicit null bounds with diagnostics. Other producers, advanced record kinds, Windows, and macOS have not been certified by this run.

The convergence follow-up also verifies metadata trailing-field rejection with source locations, exact sample endpoint coordinates/directions and mixed-track scales/geometry, and failed-open session clearing through the real executable STDIO transport. Helix total length and sweep are withheld with `unsupported_geometry`; fractional-turn helix bounds are unavailable, while full-revolution XY projections retain complete circle bounds. Formatting, Clippy, and all 40 tests passed again after these changes.

## Feature 001 closeout — 2026-10-31

Reviewed all 15 functional requirements, 6 success criteria, 13 user-story acceptance scenarios, and implementation tasks against the reader, owned model, MCP tools, and regression suite. The final review found one remaining bounds issue: decorative polygon vertex rows were interpreted as unsupported nested track records. T043 fixes counted F3/Y3 and F4/Y4 payload consumption, with a test demonstrated failing before the fix and passing afterwards, plus malformed/truncated-payload checks with source locations.

Final verification passed formatting, warning-free Clippy, all 42 integration tests, and an optimized release build. All 43 tasks are complete. Feature 001 is complete within its declared Linux, format-12, read-only inspection scope. Track-system `.xtp` catalogue retrieval is documented as subsequent work in [the catalogue requirements](../../docs/track-parameter-catalog.md); it is not a missing requirement of feature 001.
