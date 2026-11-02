"""Local MCP tools for generating and inspecting XTrackCAD layouts in mm."""

from collections import Counter
from dataclasses import dataclass
from html import escape
from math import atan2, cos, degrees, dist, isfinite, radians, sin, sqrt
from pathlib import Path
import shlex
from tempfile import NamedTemporaryFile
from typing import Any

from mcp.server.fastmcp import FastMCP

ROOT = Path(__file__).resolve().parent
CATALOGUE = ROOT / "files/mrklnhoc-de.xtp"
OUTPUT = ROOT / "layouts"
PREVIEWS = ROOT / "previews"
MM = 25.4
POSITION_TOLERANCE = 0.1
ANGLE_TOLERANCE = 0.1
mcp = FastMCP("turnout")


@dataclass
class Part:
    title: str
    ends: list[tuple[float, float, float]]
    rows: list[str]

    @property
    def number(self):
        return self.title.split("\t")[-1]


def load_catalogue():
    """Only ordinary two-ended pieces with one straight or circular centreline."""
    parts = {}
    for block in CATALOGUE.read_text(encoding="utf-8").split("TURNOUT HO ")[1:]:
        header, *lines = block.splitlines()
        title = header.strip().strip('"')
        rows = []
        for line in lines:
            line = line.strip()
            if line == "END":
                break
            rows.append(line)
        ends = [tuple(float(v) * (MM if i < 2 else 1)
                      for i, v in enumerate(row.split()[1:]))
                for row in rows if row.startswith("E ")]
        geometry = [r for r in rows if r.startswith(("S ", "C "))]
        ordinary = "\tGerade " in title or "\tGebogen " in title
        if ordinary and len(ends) == 2 and len(geometry) == 1:
            part = Part(title, ends, [r for r in rows if r.startswith(("P ", "S ", "C ", "L ", "A "))])
            parts[part.number] = part
    return parts


def transform(point, origin, angle):
    # XTrackCAD angles run clockwise from north; rotation is clockwise too.
    c, s = cos(radians(angle)), sin(radians(angle))
    x, y = point[:2]
    return origin[0] + x * c + y * s, origin[1] - x * s + y * c


def angle_error(a, b):
    return abs((a - b + 180) % 360 - 180)


@dataclass
class Segment:
    a: tuple[float, float]
    b: tuple[float, float]
    center: tuple[float, float] | None = None
    radius: float = 0
    start: float = 0
    sweep: float = 0

    def point(self, angle):
        return (self.center[0] + self.radius * sin(radians(angle)),
                self.center[1] + self.radius * cos(radians(angle)))

    def contains(self, point):
        if self.center is not None:
            angle = degrees(atan2(point[0] - self.center[0], point[1] - self.center[1]))
            offset = (angle - self.start) % 360
            return (abs(dist(point, self.center) - self.radius) <= POSITION_TOLERANCE
                    and (offset <= self.sweep + 0.0001 or offset >= 360 - 0.0001))
        return dist(self.a, point) + dist(point, self.b) <= dist(self.a, self.b) + 1e-7

    def bounds_points(self):
        if self.center is None:
            return [self.a, self.b]
        return [self.a, self.b] + [self.point(a) for a in (0, 90, 180, 270)
                                  if self.contains(self.point(a))]


def segment(part, origin, angle):
    row = next(r for r in part.rows if r.startswith(("S ", "C ")))
    return segment_row(row, origin, angle)


def segment_row(row, origin, angle):
    """Transform one embedded straight/arc record from inches to world mm."""
    row = row.split()
    values = list(map(float, row[3:]))
    if row[0] == "S":
        x1, y1, x2, y2 = values
        return Segment(transform((x1 * MM, y1 * MM), origin, angle),
                       transform((x2 * MM, y2 * MM), origin, angle))
    radius, cx, cy, start, sweep = values
    curve = Segment((0, 0), (0, 0), transform((cx * MM, cy * MM), origin, angle),
                    abs(radius) * MM, (start + angle) % 360, sweep)
    curve.a, curve.b = curve.point(curve.start), curve.point(curve.start + sweep)
    return curve


def cross(a, b):
    return a[0] * b[1] - a[1] * b[0]


def subtract(a, b):
    return a[0] - b[0], a[1] - b[1]


def intersections(a, b):
    """Analytic line/arc intersections, including coincident overlaps."""
    if a.center is None and b.center is None:
        v, w = subtract(a.b, a.a), subtract(b.b, b.a)
        denominator = cross(v, w)
        if abs(denominator) < 1e-9:
            return [p for p in (a.a, a.b, b.a, b.b) if a.contains(p) and b.contains(p)]
        t = cross(subtract(b.a, a.a), w) / denominator
        points = [(a.a[0] + t * v[0], a.a[1] + t * v[1])]
    elif a.center is None or b.center is None:
        line, arc = (a, b) if a.center is None else (b, a)
        v, f = subtract(line.b, line.a), subtract(line.a, arc.center)
        aa = v[0] ** 2 + v[1] ** 2
        bb = 2 * (f[0] * v[0] + f[1] * v[1])
        cc = f[0] ** 2 + f[1] ** 2 - arc.radius ** 2
        discriminant = bb ** 2 - 4 * aa * cc
        if discriminant < -1e-6:
            return []
        points = [(line.a[0] + t * v[0], line.a[1] + t * v[1])
                  for t in ((-bb - sqrt(max(0, discriminant))) / (2 * aa),
                            (-bb + sqrt(max(0, discriminant))) / (2 * aa))]
    else:
        d = dist(a.center, b.center)
        if d < POSITION_TOLERANCE and abs(a.radius - b.radius) < POSITION_TOLERANCE:
            # Endpoints expose partial overlaps; midpoints expose identical arcs.
            return [p for p in (a.a, a.b, b.a, b.b,
                                a.point(a.start + a.sweep / 2),
                                b.point(b.start + b.sweep / 2)) if a.contains(p) and b.contains(p)]
        if d < 1e-9 or d > a.radius + b.radius or d < abs(a.radius - b.radius):
            return []
        along = (a.radius ** 2 - b.radius ** 2 + d ** 2) / (2 * d)
        height = sqrt(max(0, a.radius ** 2 - along ** 2))
        ux, uy = subtract(b.center, a.center)
        ux, uy = ux / d, uy / d
        x, y = a.center[0] + along * ux, a.center[1] + along * uy
        points = [(x - height * uy, y + height * ux), (x + height * uy, y - height * ux)]
    return [p for p in points if a.contains(p) and b.contains(p)]


@mcp.tool()
def list_parts(query: str = "") -> list[dict[str, Any]]:
    """Find supported ordinary Märklin C-track straights/curves by number or description.

    Dimensions are mm. Build sequences enter endpoint 0 and leave endpoint 1;
    curves turn left. Turnouts, special tracks and catalogue editing are unsupported.
    """
    result = []
    for part in load_catalogue().values():
        if query.casefold() not in part.title.casefold():
            continue
        shape = segment(part, (0, 0), 0)
        result.append({"part_number": part.number, "description": part.title.split("\t")[1],
                       "kind": "curve" if shape.center else "straight",
                       "length_mm": shape.radius * radians(shape.sweep) if shape.center else dist(shape.a, shape.b),
                       "radius_mm": shape.radius if shape.center else None,
                       "angle_deg": shape.sweep,
                       "endpoints_mm": part.ends})
    return result


def layout_text(placed, width, height):
    lines = ["# Generated by turnout", "VERSION 12 5.2.0", "TITLE1 Turnout C-track layout",
             "TITLE2 Flat closed loop", "MAPSCALE 32",
             f"ROOMSIZE {width / MM:.6f} x {height / MM:.6f}", "SCALE HO",
             'LAYERS 0 1 0 1 192 0 0 0 0 "Main" 1 0 9.750000 0.000000 0.616800 0.100000 0.200000',
             "LAYERS CURRENT 0"]
    for i, (part, origin, angle) in enumerate(placed):
        lines.append(f'TURNOUT {i + 1} 0 0 0 0 HO 2 {origin[0] / MM:.6f} {origin[1] / MM:.6f} 0 {angle:.6f} "{part.title}"')
        neighbors = ((i - 1) % len(placed) + 1, (i + 1) % len(placed) + 1)
        for end, neighbor in zip(part.ends, neighbors):
            x, y = transform(end, origin, angle)
            lines.append(f'\tT4 {neighbor} {x / MM:.6f} {y / MM:.6f} {(end[2] + angle) % 360:.6f} 0 0.0 0.0 0.0 0.0 0 0 0 0.000000')
        lines.append("\tD 0.000000 0.000000")
        for row in part.rows:
            fields = row.split()
            if fields[0] == "L":
                fields = ["L3", *fields[1:5], "0", *fields[5:], "0"]
                row = " ".join(fields)
            elif fields[0] == "A":
                fields = ["A3", *fields[1:6], "0", *fields[6:]]
                row = " ".join(fields)
            lines.append("\t" + row)
        lines.append("\tEND$SEGS")
    return "\n".join(lines + ["END$TRACKS", ""])


@mcp.tool()
def build_layout(parts: list[str], width_mm: float = 2000, height_mm: float = 1200) -> dict[str, Any]:
    """Build a flat closed loop from an ordered list of catalogue part numbers.

    Python attaches endpoint 0 to the previous endpoint 1. All curves turn left.
    Example oval: six 24130, one 24188, six 24130, one 24188.
    Centres the result on the board with a fixed 50 mm centreline edge margin.
    Rejects gaps >0.1 mm, angle errors >0.1 degrees, crossings and overlaps.
    On failure returns measured errors and writes nothing. On success creates a
    unique .xtc in this project's layouts/ and returns its path and parts list.
    Does not open XTrackCAD or check rolling-stock clearance.
    """
    errors = []
    if not all(isfinite(v) and 100 < v <= 100000 for v in (width_mm, height_mm)):
        return {"ok": False, "errors": [{"type": "board", "message": "Board dimensions must be finite and >100 to 100000 mm."}]}
    if not 3 <= len(parts) <= 500:
        return {"ok": False, "errors": [{"type": "parts", "message": "Supply 3 to 500 part numbers."}]}
    catalogue = load_catalogue()
    unknown = sorted(set(parts) - catalogue.keys())
    if unknown:
        return {"ok": False, "errors": [{"type": "unsupported_parts", "parts": unknown}]}
    placed, shapes = [], []
    entry, entry_angle = (0, 0), 270
    for number in parts:
        part = catalogue[number]
        angle = (entry_angle - part.ends[0][2]) % 360
        offset = transform(part.ends[0], (0, 0), angle)
        origin = subtract(entry, offset)
        placed.append((part, origin, angle))
        shapes.append(segment(part, origin, angle))
        entry = transform(part.ends[1], origin, angle)
        entry_angle = (part.ends[1][2] + angle + 180) % 360
    gap, mismatch = dist(entry, (0, 0)), angle_error(entry_angle, 270)
    if gap > POSITION_TOLERANCE or mismatch > ANGLE_TOLERANCE:
        errors.append({"type": "closure", "gap_mm": gap, "angle_error_deg": mismatch})
    points = [point for shape in shapes for point in shape.bounds_points()]
    low = tuple(min(p[i] for p in points) for i in (0, 1))
    high = tuple(max(p[i] for p in points) for i in (0, 1))
    footprint = (high[0] - low[0], high[1] - low[1])
    for axis, used, available in zip(("width", "height"), footprint, (width_mm, height_mm)):
        if used + 100 > available:
            errors.append({"type": "boundary", "axis": axis, "required_mm": used + 100,
                           "available_mm": available, "excess_mm": used + 100 - available})
    # ponytail: O(n²) intersection checks capped at 500 pieces; spatial index if larger plans matter.
    for i, a in enumerate(shapes):
        for j in range(i + 1, len(shapes)):
            allowed = []
            if j == i + 1:
                allowed.append(transform(placed[i][0].ends[1], placed[i][1], placed[i][2]))
            if i == 0 and j == len(shapes) - 1:
                allowed.append((0, 0))
            if any(all(dist(p, joint) > POSITION_TOLERANCE for joint in allowed)
                   for p in intersections(a, shapes[j])):
                errors.append({"type": "intersection", "piece_indices": [i + 1, j + 1]})
    if errors:
        return {"ok": False, "errors": errors}
    shift = ((width_mm - footprint[0]) / 2 - low[0], (height_mm - footprint[1]) / 2 - low[1])
    placed = [(part, (origin[0] + shift[0], origin[1] + shift[1]), angle)
              for part, origin, angle in placed]
    text = layout_text(placed, width_mm, height_mm)
    OUTPUT.mkdir(exist_ok=True)
    with NamedTemporaryFile(mode="w", encoding="utf-8", prefix="layout-", suffix=".xtc",
                            dir=OUTPUT, delete=False) as file:
        path = Path(file.name)
        try:
            file.write(text)
        except BaseException:
            path.unlink(missing_ok=True)
            raise
    return {"ok": True, "path": str(path), "parts": dict(Counter(parts)),
            "piece_count": len(parts), "board_mm": [width_mm, height_mm],
            "centreline_footprint_mm": list(footprint), "edge_margin_mm": 50,
            "closure_gap_mm": gap, "closure_angle_error_deg": mismatch,
            "xtrackcad_verified": False}


def finite_numbers(values):
    result = [float(value) for value in values]
    if any(not isfinite(value) or abs(value) > 1e9 for value in result):
        raise ValueError("Numeric values must be finite and within ±1e9.")
    return result


def read_layout(text):
    """Parse the observed VERSION 12 compound-track subset; never infer links."""
    layout = {"version": None, "title": [], "board_mm": None, "scale": None,
              "layers": [], "pieces": [], "warnings": []}
    shapes = {}
    lines = text.splitlines()
    versions = [line.split() for line in lines if line.startswith("VERSION ")]
    if len(versions) != 1 or len(versions[0]) != 3:
        raise ValueError("Expected exactly one VERSION record with format and application version.")
    layout["version"] = " ".join(versions[0][1:])
    version = int(versions[0][1])
    if version != 12:
        layout["warnings"].append({"record": "VERSION", "message": f"Unsupported format {version}; no track records interpreted."})
        return layout, shapes

    def warning(line, tag, piece=None):
        layout["warnings"].append({"line": line, "record": tag,
                                   "piece_id": piece["id"] if piece else None,
                                   "message": "Unsupported element; inspection and preview are incomplete."})

    piece = None
    endpoint_ordinal = 0
    skipping = False
    ended = False
    for line_number, raw in enumerate(lines, 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        try:
            tag = line.split()[0]
            if ended:
                raise ValueError("Unexpected data after END$TRACKS.")
            if skipping:
                if tag == "END$SEGS":
                    skipping = False
                    continue
                if raw[:1].isspace():
                    continue
                skipping = False
            if tag == "END$SEGS":
                if piece is None:
                    raise ValueError("END$SEGS without a compound piece.")
                if not piece["endpoints"]:
                    if not any(w.get("piece_id") == piece["id"] for w in layout["warnings"]):
                        raise ValueError("Compound track has no endpoints.")
                    warning(line_number, "missing_supported_endpoints", piece)
                segment_count = len(shapes[piece["id"]])
                if not segment_count:
                    warning(line_number, "missing_supported_geometry", piece)
                for path in piece["paths"]:
                    if any(index == 0 or abs(index) > segment_count for index in path["segments"]):
                        if not any(w.get("piece_id") == piece["id"] for w in layout["warnings"]):
                            raise ValueError("Path refers to a missing track segment.")
                        warning(line_number, "unresolved_path", piece)
                piece["kind"] = ("turnout" if len(piece["endpoints"]) > 2 or len(piece["paths"]) > 1
                                 else "curve" if segment_count == 1 and shapes[piece["id"]][0].center
                                 else "straight" if segment_count == 1 else "compound")
                piece = None
                continue
            if piece is not None:
                if tag in {"TURNOUT", "END$TRACKS", "VERSION"}:
                    raise ValueError("Missing END$SEGS before next record.")
                fields = shlex.split(line)
                if tag in {"E4", "T4"}:
                    offset = 2 if tag == "T4" else 1
                    if len(fields) != offset + 12:
                        raise ValueError(f"Expected the observed {tag} endpoint format.")
                    values = finite_numbers(fields[offset:])
                    neighbor = int(fields[1]) if tag == "T4" else None
                    endpoint = {"ref": f'{piece["id"]}:{endpoint_ordinal}',
                                "position_mm": [values[0] * MM, values[1] * MM],
                                "angle_deg": values[2] % 360, "neighbor_piece_id": neighbor,
                                "status": "open" if neighbor is None else "unchecked",
                                "connected_to": None}
                    piece["endpoints"].append(endpoint)
                    endpoint_ordinal += 1
                    if any(values[3:]):
                        warning(line_number, "endpoint_elevation_metadata", piece)
                elif tag in {"S", "C"}:
                    expected = 7 if tag == "S" else 8
                    if len(fields) != expected:
                        raise ValueError(f"Invalid {tag} geometry record.")
                    values = finite_numbers(fields[1:])
                    if (tag == "S" and dist(values[2:4], values[4:6]) == 0
                            or tag == "C" and (values[2] == 0 or not 0 < values[-1] <= 360)):
                        raise ValueError("Degenerate or invalid track geometry.")
                    shape = segment_row(line, piece["position_mm"], piece["rotation_deg"])
                    if not piece["unsupported_transform"]:
                        shapes[piece["id"]].append(shape)
                elif tag == "P":
                    if len(fields) < 3:
                        raise ValueError("A path needs a name and segment indices.")
                    piece["paths"].append({"name": fields[1], "segments": [int(v) for v in fields[2:]]})
                elif tag not in {"D", "L3", "A3"}:
                    if tag in {"E", "T", "E2", "T2", "E3", "T3"}:
                        endpoint_ordinal += 1
                    warning(line_number, tag, piece)
                continue
            if tag in {"TITLE1", "TITLE2"}:
                layout["title"].append(line.partition(" ")[2])
                continue
            fields = shlex.split(line)
            if tag == "TURNOUT":
                if len(fields) != 13:
                    raise ValueError("Expected the observed TURNOUT header format.")
                track_id, layer, options = int(fields[1]), int(fields[2]), int(fields[3])
                if track_id <= 0 or track_id in shapes:
                    raise ValueError("Track IDs must be unique positive integers.")
                numeric = finite_numbers(fields[8:12])
                title = fields[12].split("\t")
                piece = {"id": track_id, "title": fields[12],
                         "part_number": title[2] if len(title) >= 3 else None,
                         "description": title[1] if len(title) >= 2 else fields[12],
                         "layer": layer, "scale": fields[6],
                         "position_mm": [v * MM for v in numeric[:2]],
                         "elevation_mm": numeric[2] * MM, "rotation_deg": numeric[3] % 360,
                         "endpoints": [], "paths": [], "unsupported_transform": bool(options & 16)}
                endpoint_ordinal = 0
                shapes[track_id] = []
                layout["pieces"].append(piece)
                if piece["unsupported_transform"] or int(fields[4]) != 0 or int(fields[5]) != 0:
                    piece["unsupported_transform"] = True
                    warning(line_number, "placement_options", piece)
                if numeric[2] != 0:
                    warning(line_number, "elevation_projection", piece)
            elif tag == "ROOMSIZE":
                if len(fields) != 4 or fields[2] != "x" or layout["board_mm"] is not None:
                    raise ValueError("Expected one ROOMSIZE width x height record.")
                values = finite_numbers([fields[1], fields[3]])
                if min(values) <= 0:
                    raise ValueError("Board dimensions must be positive.")
                layout["board_mm"] = [v * MM for v in values]
            elif tag == "SCALE":
                if len(fields) != 2 or layout["scale"] is not None:
                    raise ValueError("Expected one SCALE record.")
                layout["scale"] = fields[1]
            elif tag == "LAYERS":
                if len(fields) < 3:
                    raise ValueError("Invalid LAYERS record.")
                if fields[1] != "CURRENT":
                    if len(fields) < 11:
                        raise ValueError("Missing layer name.")
                    layout["layers"].append({"id": int(fields[1]), "name": fields[10]})
            elif tag == "END$TRACKS":
                ended = True
            elif tag not in {"VERSION", "MAPSCALE"}:
                warning(line_number, tag)
                skipping = True
        except (ValueError, IndexError) as error:
            raise ValueError(f"Line {line_number}: {error}") from error
    if piece is not None:
        raise ValueError("Unterminated compound piece (missing END$SEGS).")
    if not ended or layout["board_mm"] is None or layout["scale"] is None:
        raise ValueError("Missing END$TRACKS, ROOMSIZE or SCALE record.")
    return layout, shapes


def inspect_connections(pieces):
    by_id = {piece["id"]: piece for piece in pieces}
    endpoints = {end["ref"]: end for piece in pieces for end in piece["endpoints"]}
    issues, choices = [], {}

    def issue(kind, endpoint, **details):
        endpoint["status"] = "issue"
        issues.append({"type": kind, "endpoint": endpoint["ref"], **details})

    for piece in pieces:
        for end in piece["endpoints"]:
            neighbor = end["neighbor_piece_id"]
            if neighbor is None:
                continue
            if neighbor not in by_id:
                issue("missing_neighbor", end, neighbor_piece_id=neighbor)
                continue
            if neighbor == piece["id"]:
                issue("self_connection", end)
                continue
            candidates = [e for e in by_id[neighbor]["endpoints"]
                          if e["neighbor_piece_id"] == piece["id"]]
            if not candidates:
                issue("nonreciprocal_link", end, neighbor_piece_id=neighbor)
                continue
            measurements = [(candidate, dist(end["position_mm"], candidate["position_mm"]),
                             angle_error(end["angle_deg"], candidate["angle_deg"] + 180))
                            for candidate in candidates]
            valid = [m for m in measurements if m[1] <= POSITION_TOLERANCE and m[2] <= ANGLE_TOLERANCE]
            if len(valid) == 1:
                choices[end["ref"]] = valid[0][0]["ref"]
            elif len(candidates) == 1:
                candidate, gap, angle = measurements[0]
                if gap > POSITION_TOLERANCE:
                    issue("position_gap", end, other_endpoint=candidate["ref"], gap_mm=gap)
                if angle > ANGLE_TOLERANCE:
                    issue("angle_mismatch", end, other_endpoint=candidate["ref"], angle_error_deg=angle)
            else:
                issue("ambiguous_link", end, candidates=[c["ref"] for c in candidates])
    graph = {piece["id"]: set() for piece in pieces}
    for ref, other in choices.items():
        end = endpoints[ref]
        if choices.get(other) != ref:
            issue("ambiguous_link", end, other_endpoint=other)
            continue
        end["status"], end["connected_to"] = "connected", other
        source, neighbor = int(ref.split(":")[0]), end["neighbor_piece_id"]
        graph[source].add(neighbor)
    remaining, components = set(graph), []
    while remaining:
        pending, component = [min(remaining)], set()
        while pending:
            track_id = pending.pop()
            if track_id not in component:
                component.add(track_id)
                pending.extend(graph[track_id] - component)
        remaining -= component
        components.append(sorted(component))
    return issues, components


def write_preview(layout, shapes, issues, complete):
    """Standalone SVG: fixed drawing area plus a label key, without dependencies."""
    board_known = layout["board_mm"] is not None
    width, height = layout["board_mm"] or (1000, 600)
    points = [(0, 0), (width, height)]
    points += [p for group in shapes.values() for shape in group for p in shape.bounds_points()]
    points += [end["position_mm"] for piece in layout["pieces"] for end in piece["endpoints"]]
    low = [min(p[i] for p in points) for i in (0, 1)]
    high = [max(p[i] for p in points) for i in (0, 1)]
    scale = min(1040 / max(1, high[0] - low[0]), 650 / max(1, high[1] - low[1]))

    def screen(point):
        return 70 + (point[0] - low[0]) * scale, 110 + (high[1] - point[1]) * scale

    key = [f'{p["id"]} · {p["part_number"] or "no catalogue number"} · {p["description"]}'
           for p in layout["pieces"]]
    svg_height = max(850, 180 + len(key) * 23)
    svg = [f'<svg xmlns="http://www.w3.org/2000/svg" width="1600" height="{svg_height}" viewBox="0 0 1600 {svg_height}">',
           '<title>Turnout layout inspection</title>',
           '<rect width="100%" height="100%" fill="#f8fafc"/>',
           '<g font-family="sans-serif" fill="#172033">',
           f'<text x="40" y="40" font-size="24">{escape(" · ".join(layout["title"]) or "Layout inspection")}</text>',
           f'<text x="40" y="70" font-size="15">{"COMPLETE" if complete else "INCOMPLETE — unsupported elements omitted"} · 2D centreline preview · dimensions in mm</text>',
           '<text x="1160" y="110" font-size="18">Piece ID · catalogue number</text>']
    x, y = screen((0, height))
    if board_known:
        svg.append(f'<rect x="{x:.3f}" y="{y:.3f}" width="{width * scale:.3f}" height="{height * scale:.3f}" fill="white" stroke="#94a3b8" stroke-width="2"/>')
    board_label = f"{width:.1f} × {height:.1f}" if board_known else "dimensions unavailable"
    svg.append(f'<text x="40" y="805" font-size="14">Board: {board_label} · Orange: explicit open ends · Red: connection issues</text>')
    open_count = sum(end["status"] == "open" for piece in layout["pieces"] for end in piece["endpoints"])
    svg.append(f'<text x="40" y="830" font-size="14">Supported subset: {len(layout["pieces"])} pieces · {open_count} open ends · {len(issues)} connection issues · Completeness does not imply a valid design.</text>')
    for track_id, group in shapes.items():
        for shape in group:
            if shape.center is None:
                sample = [shape.a, shape.b]
            else:
                # ponytail: ≤1° chords are for display only; validation uses exact endpoints.
                steps = max(1, int(shape.sweep) + 1)
                sample = [shape.point(shape.start + shape.sweep * i / steps) for i in range(steps + 1)]
            path = " ".join(f'{x:.3f},{y:.3f}' for x, y in map(screen, sample))
            svg.append(f'<polyline data-piece-id="{track_id}" points="{path}" fill="none" stroke="#334155" stroke-width="2.5" stroke-linejoin="round"/>')
    bad = {issue["endpoint"] for issue in issues}
    occupied = []

    def label(point, text, color):
        x, y = screen(point)
        # ponytail: greedy label placement suits small plans; add leader-line layout if dense plans need it.
        label_width = max(38, len(text) * 7.5)
        for offset in range(0, svg_height, 20):
            box = (x + 10, y - 25 + offset, x + 10 + label_width, y - 7 + offset)
            if all(box[2] < b[0] or box[0] > b[2] or box[3] < b[1] or box[1] > b[3] for b in occupied):
                break
        occupied.append(box)
        lx, ly = box[0], box[3] - 3
        svg.append(f'<path d="M{x:.3f},{y:.3f} L{lx:.3f},{ly:.3f}" stroke="{color}" stroke-width="0.8"/>')
        svg.append(f'<rect x="{lx - 2:.3f}" y="{ly - 14:.3f}" width="{label_width + 4:.3f}" height="18" rx="3" fill="white" fill-opacity="0.95"/>')
        svg.append(f'<text x="{lx:.3f}" y="{ly:.3f}" fill="{color}" font-size="13">{escape(text)}</text>')

    for piece in layout["pieces"]:
        group = shapes[piece["id"]]
        if group:
            shape = group[0]
            midpoint = (shape.point(shape.start + shape.sweep / 2) if shape.center
                        else tuple((a + b) / 2 for a, b in zip(shape.a, shape.b)))
            label(midpoint, f'{piece["id"]} · {piece["part_number"] or "?"}', '#172033')
        for end in piece["endpoints"]:
            color = '#dc2626' if end["ref"] in bad else '#c65d00' if end["status"] == "open" else None
            if color:
                x, y = screen(end["position_mm"])
                svg.append(f'<circle cx="{x:.3f}" cy="{y:.3f}" r="5" fill="{color}"/>')
                label(end["position_mm"], end["ref"], color)
    for i, text in enumerate(key):
        svg.append(f'<text x="1160" y="{145 + i * 23}" font-size="13">{escape(text)}</text>')
    svg.extend(['</g>', '</svg>'])
    PREVIEWS.mkdir(exist_ok=True)
    with NamedTemporaryFile(mode="w", encoding="utf-8", prefix="inspection-", suffix=".svg",
                            dir=PREVIEWS, delete=False) as file:
        file.write("\n".join(svg))
    return file.name


@mcp.tool()
def inspect_layout(path: str) -> dict[str, Any]:
    """Read an .xtc without modifying it; return pieces, endpoints, links and an SVG.

    Accepts absolute paths or paths relative to this project. Supports the observed
    VERSION 12 compound tracks, including turnouts with multiple S/C segments.
    Positions/dimensions are mm; angles use XTrackCAD's clockwise-from-north convention.
    Endpoint references are piece ID:zero-based endpoint ordinal, scoped to this file.
    E4 means intentional open end, not an error. T4 links are checked for reciprocal
    IDs, gaps <=0.1 mm and opposing directions within 0.1 degrees. Components include
    only verified links and do not imply traversable routes under turnout settings.
    Unsupported content returns status incomplete and warnings; summaries cover the
    supported subset only. Malformed supported records return ok false and no preview.
    SVGs are separate unique files in previews/. This is not a clearance/3D check.
    """
    source = Path(path).expanduser()
    if not source.is_absolute():
        source = ROOT / source
    try:
        source = source.resolve()
        if source.suffix.lower() != ".xtc":
            raise ValueError("Supply an .xtc layout file.")
        with source.open("rb") as file:
            content = file.read(5_000_001)
        if len(content) > 5_000_000:
            raise ValueError("Inspection is limited to 5 MB files.")
        text = content.decode("utf-8-sig")
        if any(ord(char) < 32 and char not in "\t\r\n" for char in text):
            raise ValueError("Layout contains invalid control characters.")
        layout, shapes = read_layout(text)
        issues, components = inspect_connections(layout["pieces"])
        complete = not layout["warnings"]
        if not complete:
            for issue in issues:
                if issue["type"] == "missing_neighbor":
                    issue["type"] = "unresolved_neighbor"
                    issue["message"] = "Neighbor is absent from the supported subset; unsupported elements may contain it."
        preview = write_preview(layout, shapes, issues, complete)
    except (OSError, ValueError, UnicodeError) as error:
        return {"ok": False, "errors": [{"type": "inspection", "message": str(error)}]}
    open_ends = [end for piece in layout["pieces"] for end in piece["endpoints"] if end["status"] == "open"]
    return {"ok": True, "status": "complete" if complete else "incomplete", "source_path": str(source),
            "reference_scope": "Piece IDs and endpoint ordinals refer to this file snapshot only.",
            **layout, "piece_count": len(layout["pieces"]),
            "parts": dict(Counter(p["part_number"] or "unknown" for p in layout["pieces"])),
            "open_endpoints": open_ends, "open_endpoint_count": len(open_ends),
            "connection_issues": issues, "components": components, "component_count": len(components),
            "topology_complete": complete, "preview_path": preview}


if __name__ == "__main__":
    mcp.run(transport="stdio")
