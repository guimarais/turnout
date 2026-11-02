"""Local MCP tools for generating and inspecting XTrackCAD layouts in mm."""

from collections import Counter
from dataclasses import dataclass
from html import escape
from math import atan2, cos, degrees, dist, isfinite, radians, sin, sqrt
import re
import shlex
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any

from mcp.server.fastmcp import FastMCP

ROOT = Path(__file__).resolve().parents[2]
CATALOGUE = ROOT / "data/catalogues/mrklnhoc-de.xtp"
CATALOGUES = CATALOGUE.parent
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
    scale: str = "HO"
    options: int = 0

    @property
    def number(self):
        return self.title.split("\t")[-1]


def load_catalogue(path=None, ordinary_only=False):
    """Read compound track definitions, including their paths and artwork."""
    parts = {}
    text = (path or CATALOGUE).read_text(encoding="utf-8-sig")
    for block in re.split(r"(?m)^TURNOUT\s+", text)[1:]:
        header, *lines = block.splitlines()
        fields = shlex.split(header)
        if len(fields) not in (2, 3):
            raise ValueError("Unsupported catalogue track header.")
        scale, title = fields[:2]
        options = int(fields[2]) if len(fields) == 3 else 0
        if options & ~512:
            raise ValueError("Unsupported catalogue track options.")
        rows = []
        for line in lines:
            line = line.strip()
            if line in {"END", "END$SEGS"}:
                break
            if line and not line.startswith(("#", "U ")):
                rows.append(line)
        else:
            raise ValueError("Unterminated catalogue track.")
        ends = [tuple(float(v) * (MM if i < 2 else 1)
                      for i, v in enumerate(row.split()[1:]))
                for row in rows if row.startswith("E ")]
        if any(len(end) != 3 or not all(isfinite(v) and abs(v) <= 1e9 for v in end) for end in ends):
            raise ValueError("Catalogue endpoints need three finite coordinates.")
        geometry = [r for r in rows if r.startswith(("S ", "C "))]
        ordinary = "\tGerade " in title or "\tGebogen " in title
        if not ordinary_only or ordinary and len(ends) == 2 and len(geometry) == 1:
            part = Part(title, ends, [r for r in rows if not r.startswith("E ")], scale, options)
            if len(title.split("\t")) != 3 or not ends or not geometry or part.number in parts:
                raise ValueError("Catalogue tracks need unique part numbers, endpoints and geometry.")
            # Parse our exported form too: unknown records must fail before editing.
            block_text = piece_text(part, 1, (0, 0), 0)
            parsed, _ = read_layout(layout_header() + block_text + "END$TRACKS\n")
            if parsed["warnings"]:
                raise ValueError(f"Unsupported catalogue records for {part.number}.")
            parts[part.number] = part
    if not parts:
        raise ValueError("No supported track definitions in parameter file.")
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


def catalogue_path(name):
    path = (CATALOGUES / name).resolve()
    if path.parent != CATALOGUES.resolve() or path.suffix.lower() != ".xtp":
        raise ValueError("Choose an .xtp file directly inside data/catalogues/.")
    return path


@mcp.tool()
def list_parts(query: str = "", catalogue: str = "mrklnhoc-de.xtp") -> list[dict[str, Any]]:
    """Search all track in a data/catalogues/ .xtp file. Endpoint indices are zero-based.

    attach_track accepts every listed piece. build_layout still accepts only ordinary
    straights/curves. Length is total rail centreline, not usable train length.
    """
    result = []
    for part in load_catalogue(catalogue_path(catalogue)).values():
        if query.casefold() not in part.title.casefold():
            continue
        shapes = [segment_row(row, (0, 0), 0) for row in part.rows if row.startswith(("S ", "C "))]
        shape = shapes[0]
        result.append({"part_number": part.number, "description": part.title.split("\t")[1],
                       "kind": "terminal" if len(part.ends) == 1 else "compound" if len(shapes) > 1 else "curve" if shape.center else "straight",
                       "length_mm": sum(s.radius * radians(s.sweep) if s.center else dist(s.a, s.b) for s in shapes),
                       "radius_mm": shape.radius if len(shapes) == 1 and shape.center else None,
                       "angle_deg": shape.sweep if len(shapes) == 1 else None,
                       "endpoints_mm": part.ends, "scale": part.scale,
                       "paths": [shlex.split(row)[1:] for row in part.rows if row.startswith("P ")]})
    return result


def layout_header(width=2000, height=1200):
    return "\n".join(["# Generated by turnout", "VERSION 12 5.2.0", "TITLE1 Turnout C-track layout",
             "TITLE2 Flat closed loop", "MAPSCALE 32",
             f"ROOMSIZE {width / MM:.6f} x {height / MM:.6f}", "SCALE HO",
             'LAYERS 0 1 0 1 192 0 0 0 0 "Main" 1 0 9.750000 0.000000 0.616800 0.100000 0.200000',
             "LAYERS CURRENT 0", ""])


def piece_text(part, track_id, origin, angle, layer=0, links=None):
    """Export one compound piece; retain catalogue ordering and drawing geometry."""
    links = links or {}
    lines = [f'TURNOUT {track_id} {layer} {part.options} 0 0 {part.scale} 2 {origin[0] / MM:.6f} {origin[1] / MM:.6f} 0 {angle:.6f} "{part.title}"']
    for index, end in enumerate(part.ends):
        x, y = transform(end, origin, angle)
        tag = f"T4 {links[index]}" if index in links else "E4"
        lines.append(f'\t{tag} {x / MM:.6f} {y / MM:.6f} {(end[2] + angle) % 360:.6f} 0 0.0 0.0 0.0 0.0 0 0 0 0.000000')
    lines.append("\tD 0.000000 0.000000")
    vertices = 0
    for row in part.rows:
        fields = row.split()
        if vertices:
            if len(fields) != 2:
                raise ValueError("Expected catalogue polygon vertex.")
            row += " 0"
            vertices -= 1
        elif fields[0] == "L":
            row = " ".join(["L3", *fields[1:5], "0", *fields[5:], "0"])
        elif fields[0] == "A":
            row = " ".join(["A3", *fields[1:6], "0", *fields[6:]])
        elif fields[0] == "G":
            row = " ".join(["G3", *fields[1:], "0"])
        elif fields[0] == "F":
            if len(fields) != 4:
                raise ValueError("Invalid catalogue polygon header.")
            vertices = int(fields[3])
            row = " ".join(["F3", *fields[1:]])
        lines.append("\t" + row)
    if vertices:
        raise ValueError("Unterminated catalogue polygon.")
    return "\n".join(lines + ["\tEND$SEGS", ""])


def layout_text(placed, width, height):
    text = layout_header(width, height)
    for i, (part, origin, angle) in enumerate(placed):
        neighbors = ((i - 1) % len(placed) + 1, (i + 1) % len(placed) + 1)
        text += piece_text(part, i + 1, origin, angle, links=dict(enumerate(neighbors)))
    return text + "END$TRACKS\n"


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
    catalogue = load_catalogue(ordinary_only=True)
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
    vertices = 0
    segment_ordinal = 0
    for line_number, raw in enumerate(lines, 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        try:
            tag = line.split()[0]
            if vertices:
                values = finite_numbers(line.split())
                if len(values) != 3:
                    raise ValueError("Expected a three-coordinate polygon vertex.")
                if values[2] != 0:
                    warning(line_number, "drawing_elevation", piece)
                vertices -= 1
                continue
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
                    indices = path["segments"]
                    if not indices[0] or not indices[-1] or any(a == b == 0 for a, b in zip(indices, indices[1:])):
                        raise ValueError("Empty route in compound path.")
                    if any(index and abs(index) not in piece["track_segment_indices"] for index in indices):
                        if not any(w.get("piece_id") == piece["id"] for w in layout["warnings"]):
                            raise ValueError("Path refers to a missing track segment.")
                        warning(line_number, "unresolved_path", piece)
                piece["kind"] = ("terminal" if len(piece["endpoints"]) == 1
                                 else "crossing" if len(piece["paths"]) == 1 and 0 in piece["paths"][0]["segments"]
                                 else "turnout" if len(piece["endpoints"]) > 2 or len(piece["paths"]) > 1
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
                    segment_ordinal += 1
                    piece["track_segment_indices"].append(segment_ordinal)
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
                elif tag in {"D", "L3", "A3", "G3", "F3"}:
                    if tag != "D":
                        segment_ordinal += 1
                    expected = {"D": 3, "L3": 9, "A3": 9, "G3": 7, "F3": 4}[tag]
                    if len(fields) != expected:
                        raise ValueError(f"Invalid {tag} drawing record.")
                    values = finite_numbers(fields[1:])
                    if tag == "F3":
                        vertices = int(fields[3])
                        if not 3 <= vertices <= 10000 or values[2] != vertices:
                            raise ValueError("Invalid polygon vertex count.")
                    elif tag != "D":
                        z_values = values[4::3] if tag == "L3" else [values[5]]
                        if any(z_values):
                            warning(line_number, "drawing_elevation", piece)
                else:
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
                         "endpoints": [], "paths": [], "track_segment_indices": [],
                         "unsupported_transform": bool(options & 16)}
                endpoint_ordinal = 0
                segment_ordinal = 0
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
    if vertices:
        raise ValueError("Unterminated polygon.")
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


def read_layout_file(path):
    source = Path(path).expanduser()
    if not source.is_absolute():
        source = ROOT / source
    source = source.resolve()
    if source.suffix.lower() != ".xtc":
        raise ValueError("Supply an .xtc layout file.")
    with source.open("rb") as file:
        content = file.read(5_000_001)
    if len(content) > 5_000_000:
        raise ValueError("Layouts are limited to 5 MB files.")
    text = content.decode("utf-8-sig")
    if any(ord(char) < 32 and char not in "\t\r\n" for char in text):
        raise ValueError("Layout contains invalid control characters.")
    return source, content, text


def matches_catalogue(piece, shapes, part):
    """Match identity AND embedded geometry: a part number alone is insufficient."""
    if piece["title"] != part.title or piece["scale"] != part.scale or len(piece["endpoints"]) != len(part.ends):
        return False
    origin, angle = piece["position_mm"], piece["rotation_deg"]
    for end, expected in zip(piece["endpoints"], part.ends):
        if (dist(end["position_mm"], transform(expected, origin, angle)) > POSITION_TOLERANCE
                or angle_error(end["angle_deg"], expected[2] + angle) > ANGLE_TOLERANCE):
            return False
    expected_shapes = [segment_row(row, origin, angle) for row in part.rows if row.startswith(("S ", "C "))]
    if len(shapes) != len(expected_shapes):
        return False
    for actual, expected in zip(shapes, expected_shapes):
        if (actual.center is None) != (expected.center is None):
            return False
        if actual.center is None:
            if dist(actual.a, expected.a) > POSITION_TOLERANCE or dist(actual.b, expected.b) > POSITION_TOLERANCE:
                return False
        elif (dist(actual.center, expected.center) > POSITION_TOLERANCE
              or abs(actual.radius - expected.radius) > POSITION_TOLERANCE
              or angle_error(actual.start, expected.start) > ANGLE_TOLERANCE
              or abs(actual.sweep - expected.sweep) > ANGLE_TOLERANCE):
            return False
    paths = [{"name": fields[1], "segments": list(map(int, fields[2:]))}
             for fields in (shlex.split(row) for row in part.rows if row.startswith("P "))]
    return piece["paths"] == paths


def resolve_track_system(layout, shapes, selection=""):
    """One .xtp is the authority for a layout; never infer from the requested addition."""
    paths = [catalogue_path(selection)] if selection else sorted(CATALOGUES.glob("*.xtp"))
    matches, errors = [], []
    for path in paths:
        try:
            parts = load_catalogue(catalogue_path(path.name))
            if layout["pieces"] and all(
                piece["scale"] == layout["scale"] and piece["part_number"] in parts
                and matches_catalogue(piece, shapes[piece["id"]], parts[piece["part_number"]])
                for piece in layout["pieces"]
            ):
                matches.append((path, parts))
        except (OSError, ValueError, UnicodeError) as error:
            errors.append({"catalogue": path.name, "message": str(error)})
    report = {"status": "matched" if len(matches) == 1 else "selection_required",
              "catalogue": matches[0][0].name if len(matches) == 1 else None,
              "candidates": [p.name for p, _ in matches],
              "available_catalogues": sorted(p.name for p in CATALOGUES.glob("*.xtp")),
              "catalogue_errors": errors}
    return report, matches


@mcp.tool()
def attach_track(path: str, endpoint: str, part_number: str, entry_endpoint: int = 0,
                 catalogue: str = "") -> dict[str, Any]:
    """Attach ONE catalogue piece to an explicitly open pieceID:endpointIndex.

    Read the layout's system first using data/catalogues/*.xtp. Missing/ambiguous
    matches require explicit catalogue selection; all existing pieces must match it.
    Entry indices are zero-based, permitting reversed curves and any turnout entry.
    Remaining endpoints stay open, including those of crossings. A buffer terminates.
    Reject incomplete/inconsistent inputs, board overflow and new centreline collisions.
    Preserve existing positions and unrelated bytes; save a unique revision + SVG.
    Does not check roadbed/vehicle clearance or simulate turnout routes.
    """
    try:
        source, content, text = read_layout_file(path)
        layout, shapes = read_layout(text)
        issues, _ = inspect_connections(layout["pieces"])
        if layout["warnings"] or issues:
            return {"ok": False, "errors": [{"type": "input_layout", "message": "Editing requires a fully understood layout with consistent connections.",
                                             "warnings": layout["warnings"], "connection_issues": issues}]}
        system, matches = resolve_track_system(layout, shapes, catalogue)
        if len(matches) != 1:
            return {"ok": False, "track_system": system, "errors": [{"type": "track_system", "message": "Select a unique .xtp matching every existing piece; mixed systems or altered catalogue geometry cannot be edited."}]}
        _, parts = matches[0]
        if part_number not in parts:
            raise ValueError("Requested part is absent from the layout's parameter file.")
        if len(layout["pieces"]) >= 500:
            raise ValueError("Attachment is limited to 500 total pieces.")
        targets = [(piece, end) for piece in layout["pieces"] for end in piece["endpoints"] if end["ref"] == endpoint]
        if len(targets) != 1 or targets[0][1]["status"] != "open":
            raise ValueError("Choose an existing explicitly open endpoint (pieceID:index).")
        parent, target = targets[0]
        part = parts[part_number]
        if part.scale != layout["scale"]:
            raise ValueError("Requested piece scale differs from the layout scale.")
        if isinstance(entry_endpoint, bool) or not isinstance(entry_endpoint, int) or not 0 <= entry_endpoint < len(part.ends):
            raise ValueError("Entry endpoint index is outside this catalogue piece.")
        angle = (target["angle_deg"] + 180 - part.ends[entry_endpoint][2]) % 360
        origin = subtract(target["position_mm"], transform(part.ends[entry_endpoint], (0, 0), angle))
        added_shapes = [segment_row(row, origin, angle) for row in part.rows if row.startswith(("S ", "C "))]
        errors = []
        for axis, limit in enumerate(layout["board_mm"]):
            coordinates = [p[axis] for shape in added_shapes for p in shape.bounds_points()]
            low, high = min(coordinates), max(coordinates)
            if low < -POSITION_TOLERANCE or high > limit + POSITION_TOLERANCE:
                errors.append({"type": "boundary", "axis": "xy"[axis], "minimum_mm": low, "maximum_mm": high, "board_limit_mm": limit})
        # ponytail: O(new segments × existing segments), capped at 500 pieces; index if larger plans matter.
        for piece_id, group in shapes.items():
            if any(dist(point, target["position_mm"]) > POSITION_TOLERANCE or piece_id != parent["id"]
                   for a in added_shapes for b in group for point in intersections(a, b)):
                errors.append({"type": "intersection", "existing_piece_id": piece_id})
        if errors:
            return {"ok": False, "errors": errors}
        new_id = max(piece["id"] for piece in layout["pieces"]) + 1
        block = piece_text(part, new_id, origin, angle, parent["layer"], {entry_endpoint: parent["id"]})
        # Patch the original bytes, including BOM, line endings, whitespace and comments.
        lines = content.splitlines(keepends=True)
        newline = b"\r\n" if b"\r\n" in content else b"\n"
        current_id, ordinal, changed, inserted = None, 0, False, False
        revised = []
        for raw in lines:
            fields = raw.decode("utf-8-sig").split()
            if fields and fields[0] == "TURNOUT":
                current_id, ordinal = int(fields[1]), 0
            elif fields and fields[0] in {"E4", "T4"}:
                if current_id == parent["id"] and ordinal == int(endpoint.split(":")[1]):
                    raw = raw.replace(b"E4", f"T4 {new_id}".encode(), 1)
                    changed = True
                ordinal += 1
            elif fields and fields[0] == "END$TRACKS":
                revised.append(block.replace("\n", newline.decode()).encode("utf-8"))
                inserted = True
            revised.append(raw)
        if not changed or not inserted:
            raise ValueError("Could not locate the source records safely.")
        output = b"".join(revised)
        if len(output) > 5_000_000:
            raise ValueError("Revised layout would exceed the 5 MB input limit.")
        result_layout, result_shapes = read_layout(output.decode("utf-8-sig"))
        result_issues, components = inspect_connections(result_layout["pieces"])
        if result_layout["warnings"] or result_issues:
            raise ValueError("Revised layout failed connection/format validation.")
        preview = Path(write_preview(result_layout, result_shapes, result_issues, True))
        output_path = None
        try:
            OUTPUT.mkdir(exist_ok=True)
            with NamedTemporaryFile(mode="wb", prefix="revision-", suffix=".xtc", dir=OUTPUT, delete=False) as file:
                output_path = Path(file.name)
                file.write(output)
        except BaseException:
            preview.unlink(missing_ok=True)
            if output_path:
                output_path.unlink(missing_ok=True)
            raise
        open_ends = [e for p in result_layout["pieces"] for e in p["endpoints"] if e["status"] == "open"]
        return {"ok": True, "path": str(output_path), "source_path": str(source),
                "track_system": system, "preview_path": str(preview),
                "piece_count": len(result_layout["pieces"]),
                "parts": dict(Counter(p["part_number"] for p in result_layout["pieces"])),
                "changes": {"added_piece_ids": [new_id], "removed_piece_ids": [], "moved_piece_ids": [],
                            "parts_delta": {part_number: 1}, "connected_endpoints": [endpoint, f"{new_id}:{entry_endpoint}"],
                            "new_open_endpoints": [e["ref"] for e in open_ends if e["ref"].startswith(f"{new_id}:")],
                            "closed_open_endpoints": [endpoint]},
                "open_endpoints": open_ends, "open_endpoint_count": len(open_ends),
                "connection_issues": result_issues, "components": components,
                "xtrackcad_verified": False}
    except (OSError, ValueError, UnicodeError) as error:
        return {"ok": False, "errors": [{"type": "attachment", "message": str(error)}]}


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
    try:
        source, _, text = read_layout_file(path)
        layout, shapes = read_layout(text)
        issues, components = inspect_connections(layout["pieces"])
        complete = not layout["warnings"]
        if not complete:
            for issue in issues:
                if issue["type"] == "missing_neighbor":
                    issue["type"] = "unresolved_neighbor"
                    issue["message"] = "Neighbor is absent from the supported subset; unsupported elements may contain it."
        system, _ = resolve_track_system(layout, shapes)
        preview = write_preview(layout, shapes, issues, complete)
    except (OSError, ValueError, UnicodeError) as error:
        return {"ok": False, "errors": [{"type": "inspection", "message": str(error)}]}
    open_ends = [end for piece in layout["pieces"] for end in piece["endpoints"] if end["status"] == "open"]
    return {"ok": True, "status": "complete" if complete else "incomplete", "source_path": str(source),
            "track_system": system,
            "reference_scope": "Piece IDs and endpoint ordinals refer to this file snapshot only.",
            **layout, "piece_count": len(layout["pieces"]),
            "parts": dict(Counter(p["part_number"] or "unknown" for p in layout["pieces"])),
            "open_endpoints": open_ends, "open_endpoint_count": len(open_ends),
            "connection_issues": issues, "components": components, "component_count": len(components),
            "topology_complete": complete, "preview_path": preview}


def run():
    """Start the local MCP server over stdio."""
    mcp.run(transport="stdio")
