"""Local MCP tools for closed Märklin C-track layouts. All geometry is in mm."""

from collections import Counter
from dataclasses import dataclass
from math import atan2, cos, degrees, dist, isfinite, radians, sin, sqrt
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any

from mcp.server.fastmcp import FastMCP

ROOT = Path(__file__).resolve().parent
CATALOGUE = ROOT / "files/mrklnhoc-de.xtp"
OUTPUT = ROOT / "layouts"
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
    row = next(r for r in part.rows if r.startswith(("S ", "C "))).split()
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


if __name__ == "__main__":
    mcp.run(transport="stdio")
