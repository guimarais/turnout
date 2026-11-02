# Turnout feature roadmap

Proposed on 2026-11-02. This is a plan, not an implementation commitment.

## Direction

Help a Märklin C-track user design and revise a buildable layout through an AI,
while continuing to use XTrackCAD as the drawing editor and final review tool.
Keep the current local, file-based workflow: inspect a file, propose a change,
validate it, and write a new file. Python remains responsible for geometry.

The first milestone is complete: catalogue discovery and generation of a flat,
closed oval, with automated checks and user-confirmed XTrackCAD compatibility.
The next useful milestone is **an existing layout extended with a turnout and
siding, reviewed through a preview and opened successfully in XTrackCAD**.

XTrackCAD already supplies editing, layers, elevations, train operation and
printing facilities. The roadmap prioritizes making design tasks available to
the AI and improving feedback about buildability. See the upstream
[concepts](https://sourceforge.net/p/xtrkcad-fork/wiki/Concepts/),
[tutorial progression](https://sourceforge.net/p/xtrkcad-fork/wiki/BeginnerTutorial/)
and [project overview](https://sourceforge.net/p/xtrkcad-fork/wiki/Home/).

## 1. Read and explain an existing layout

Implemented on `feature/layout-inspection`: `inspect_layout(path)`, connection
reports and labelled SVG previews. Automated sample/oval and MCP checks pass;
previews have been visually checked. See [README](../README.md) for supported records and limits.

**User request:** “Open my unfinished layout. What have I built, and what still
needs connecting?”

- Read the `.xtc` format version used by the supplied sample and current exports.
- Report board size, scale, piece IDs, catalogue numbers, positions, orientation,
  explicit connections, layers and elevations that can be interpreted safely.
- Give every piece and endpoint a stable reference the AI can use in later calls.
- List disconnected components, open endpoints and inconsistent reciprocal links.
  Distinguish an open end from an error: a siding can intentionally terminate.
- Show a labelled SVG preview with piece IDs and open endpoints. Include a parts
  count and explain unsupported records instead of silently ignoring them.

**Done when:** the supplied unfinished sample and a generated oval can both be
inspected accurately; the sample's turnout is recognized; the oval has one
connected component and no open ends. The preview agrees with XTrackCAD.

**Boundary:** support known records first. Read-only reporting of unknown records
is acceptable; claiming complete understanding of an unsupported file is not.

## 2. Place and edit connected track, including turnouts

**User request:** “Add a right-hand turnout here and a siding long enough for my
train. Leave the rest of the layout where it is.”

- Support ordinary C-track turnouts, beginning with the supplied 24612 and its
  left-hand counterpart; then add curved and larger-radius turnouts as needed.
- Replace the single ordered-loop assumption with explicit piece/endpoint
  connections. Support branches, intentional open ends and buffer stops.
- Let the AI attach to a named endpoint, select entry/exit endpoints, traverse a
  curve in either direction, and move or rotate a selected group.
- Support adding, removing and replacing pieces, with clear handling of any
  connections broken by a change. Do not silently move unrelated track.
- Interpret catalogue paths through turnouts. Physical connectivity and a route
  available under a particular turnout setting are different things.
- Save every revision separately and return a change summary: pieces added,
  removed or moved; new open ends; and changes to parts quantities.
- Preserve unrelated metadata, drawings, layers and notes. If an unknown record
  cannot be preserved safely through an edit, refuse that edit with an explanation.

**Done when:** create an oval with a turnout and buffer-ended siding, then modify
its length. XTrackCAD opens/saves each revision, intended links remain reciprocal,
branch geometry matches the catalogue, and unrelated records remain unchanged.

**Depends on:** phase 1. This is the core of the next release; include its preview.

## 3. Help connect endpoints and build common arrangements

**User requests:** “Find C-track pieces that close this gap.” “Add a passing loop
with enough usable length for a 900 mm train.”

- Offer short connector sequences that satisfy both endpoint positions and
  directions using real catalogue pieces. Return a measured gap and angle error
  when no solution is found within the stated search limits.
- Bound the search by piece count, candidate part types and runtime. Report
  “no solution found within limits” rather than claiming none exists.
- Start with common arrangements: siding, passing loop, double-track oval and
  station approach. Make arrangements editable track, not opaque generated objects.
- Offer a few alternatives ranked by explicit preferences, such as fewer pieces,
  larger minimum radius or a smaller footprint. Report the tradeoffs.
- Measure usable siding/platform length between clearance points, not just total
  track length. Requires an explicit clearance rule or vehicle assumptions.

**Done when:** close a known solvable gap, reject an impossible-within-limits case
without inserting flex track, and generate a connected passing loop whose usable
length meets the requested target in XTrackCAD.

**Depends on:** phase 2. Accurate usable-length claims also depend on phase 4's
clearance rules; begin with connector suggestions if those rules are not ready.

## 4. Check whether the layout can be built and used

**User request:** “Check this plan for my room and my longest coaches.”

- Support board outlines, cut-outs and keep-out areas, with adjustable edge margins.
  Represent nonrectangular boards inside XTrackCAD's rectangular layout area.
- Check the track/roadbed envelope against boundaries, not just the centreline.
- Add user-specified minimum radius and parallel-track spacing constraints.
- Add vehicle-based clearance checks for curves, adjacent tracks and structures.
  Require dimensions or a named, documented rule; do not infer them from scale alone.
- Identify tight S-bends, short turnout approaches and potentially awkward access
  areas. Treat advice separately from hard geometric failures.
- Return issues with piece IDs, locations, measurements and preview highlights.
  Make intended open ends and accepted exceptions explicit.
- Revisit the current crossing rejection when catalogue crossings are supported:
  an intentional component crossing is different from two ordinary tracks colliding.

**Done when:** controlled examples flag a board-edge conflict, a cut-out conflict,
a too-small radius and a known clearance conflict; accepted examples remain clean.

**Depends on:** phases 1–2. Clearance rules are an input to phase 3's train-length
and track-spacing promises. Introduce these checks incrementally.

## 5. Design around owned track and compare alternatives

**User request:** “Use the track I own, and show me what I need to buy for each plan.”

- Accept a simple CSV or JSON inventory keyed by catalogue number and quantity.
- Report used, remaining and missing quantities; export a shopping list.
- Let users choose a hard inventory limit or a soft preference for existing stock.
- Optionally accept user-maintained prices and currency to estimate purchase cost.
  Do not present catalogue availability as live stock information.
- Compare a few saved alternatives using the same metrics: footprint, minimum
  radius, usable siding length, parts shortages and estimated additional cost.
- Feed inventory and price preferences into the bounded connector search only
  after the basic inventory report works.

**Done when:** a known inventory produces exact shortages for a saved layout,
and a small set of alternatives has reproducible quantities and costs.

**Depends on:** phase 1 for reporting, phases 2–3 for inventory-aware generation.
This can move earlier if buying decisions become the user's main concern.

## 6. Add elevations and operational review

**User requests:** “Can this track cross over that one?” “Can a train reach every
siding without being trapped?”

- Read existing elevations before offering edits. Add explicit heights and grade
  constraints, then grade-transition checks and a vertical profile preview.
- Check over/under clearance using rail levels plus user-specified structure depth
  and vehicle clearance. A centreline height difference alone is insufficient.
- Allow projected track crossings only when horizontal and vertical geometry are
  understood and the intended separation is valid.
- Analyze routes using turnout paths/settings, buffer ends and connected sections.
  Add train-length-dependent operating advice once usable lengths are reliable.
- Keep actual train simulation in XTrackCAD; provide a short operating checklist
  and routes to try there.

**Done when:** a known overpass passes or fails for the correct measured reason,
and route checks distinguish a connected network from a route blocked by turnout
settings. Generated changes survive an XTrackCAD open/save round trip.

**Depends on:** phases 2 and 4. Defer until flat layouts are dependable.

## Delivery rules

- Deliver one user workflow per increment, with a small runnable check and an
  XTrackCAD open/save example for each new record or geometry type.
- Begin format compatibility with the installed version and supplied examples.
  Expand supported versions only using representative saved files.
- Keep edits explicit and outputs separate. A user edit made in XTrackCAD becomes
  the input to the next operation; do not apply changes to a stale cached copy.
- Reuse Python's standard library and the existing MCP SDK. Add dependencies only
  when a demonstrated requirement makes them worthwhile.
- Add tools around user operations as needed. Do not decide the complete future
  MCP interface, introduce persistent server sessions or build a generic plugin
  framework before the workflows require them.
- Continue to use XTrackCAD for detailed manual editing, printing and simulation.
  Remote hosting, accounts, live GUI synchronization, other track systems and
  unrestricted automatic layout design remain outside this roadmap's early releases.

## Recommended next implementation sequence

1. Read-only inspection of the sample and generated oval, with stable endpoint IDs.
2. Labelled preview and a validation report that permits intentional open ends.
3. Catalogue paths plus ordinary left/right turnouts and buffer stops.
4. Attach a siding to an existing layout; save a separate revision and a change summary.
5. Verify preservation and the XTrackCAD round trip, then tackle gap-filling search.
