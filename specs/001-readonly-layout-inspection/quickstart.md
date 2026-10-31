# Quickstart: Validate Read-Only Layout Inspection

This validates the planned vertical slice; it is not implementation code.

## Prerequisites

- Rust stable toolchain selected by the repository.
- A plain-text `.xtc` fixture from `tests/fixtures/authored/` or a compatibility fixture with a provenance manifest.
- An MCP client that can launch a STDIO server, or the repository's STDIO integration test.

## Validate the fixture reader

1. Run `cargo test --test parser_tests`.
2. Confirm valid fixtures produce expected summary and supported straight, curve, and turnout counts. In particular, `layouts/mrkln_sample.xtc` returns four turnouts, its two titles, HO scale, room dimensions, UTF-8 Märklin labels, and endpoint states.
3. Confirm malformed and unsupported-feature fixtures produce expected diagnostic codes.
4. Confirm integrity assertions verify content and modification time are unchanged.

Expected outcome: format behavior is limited to the fixture-proven scope in [data-model.md](./data-model.md).

## Validate MCP over STDIO

1. Run `cargo test --test mcp_stdio_tests`.
2. The test launches Turnout as a subprocess over STDIO.
3. Invoke `tools/list`, `open_layout` with a valid fixture, `get_layout_info`, and `list_tracks`.
4. Assert results conform to [the tool contract](./contracts/read-only-tools.md), including units, ordering, counts, and diagnostics.
5. Repeat with a nonexistent path, malformed fixture, and unsupported-record fixture; verify expected errors or warnings.

Expected outcome: a client completes the inspection sequence without conversion or source-file changes.

## Compatibility-corpus acceptance

Before adding a tool-produced fixture, record creator/version, origin or permission, SHA-256, and expected supported/unsupported records in the corpus manifest. Run both test layers. A mismatch is a finding to investigate, not permission to broaden advertised support.
