//! Read-only adapter for the fixture-proven subset of XTrackCAD format 12.
//! Native geometry conventions: see the XTrackCAD LayoutElements,
//! CompoundElements and ParameterFileInformation references in research.md.
use crate::layout::*;
use std::{collections::HashSet, fs, path::Path};

pub fn read(path: &Path) -> Result<Layout, Diagnostic> {
    let name = path.to_string_lossy().into_owned();
    let fail = |code: &str, message: String| Diagnostic::new(code, message, &name, None);
    if path.as_os_str().is_empty() {
        return Err(fail("unreadable_path", "Path is empty".into()));
    }
    let metadata = fs::metadata(path).map_err(|e| fail("unreadable_path", e.to_string()))?;
    if !metadata.is_file() {
        return Err(fail("unreadable_path", "Expected a regular file".into()));
    }
    if !path
        .extension()
        .is_some_and(|e| e.eq_ignore_ascii_case("xtc"))
    {
        return Err(fail(
            "unsupported_format",
            "Expected a plain-text .xtc file".into(),
        ));
    }
    let bytes = fs::read(path).map_err(|e| fail("unreadable_path", e.to_string()))?;
    let text = std::str::from_utf8(&bytes).map_err(|e| fail("invalid_utf8", e.to_string()))?;
    let mut parser = Parser {
        path: &name,
        lines: text.lines().enumerate().map(|(i, l)| (i + 1, l)).collect(),
        index: 0,
        diagnostics: Vec::new(),
        geometry_complete: true,
    };
    let mut layout = parser.parse()?;
    // A deterministic content fingerprint, not an authentication mechanism.
    let hash = bytes.iter().fold(0xcbf29ce484222325u64, |h, b| {
        (h ^ u64::from(*b)).wrapping_mul(0x100000001b3)
    });
    layout.source.fingerprint = format!("fnv1a64:{hash:016x}");
    Ok(layout)
}

struct Parser<'a> {
    path: &'a str,
    lines: Vec<(usize, &'a str)>,
    index: usize,
    diagnostics: Vec<Diagnostic>,
    geometry_complete: bool,
}
impl Parser<'_> {
    fn error(&self, line: usize, message: impl Into<String>) -> Diagnostic {
        Diagnostic::new("malformed_record", message, self.path, Some(line))
    }
    fn number(&self, f: &[&str], i: usize, line: usize) -> Result<f64, Diagnostic> {
        let value = f
            .get(i)
            .and_then(|s| s.parse::<f64>().ok())
            .filter(|n| n.is_finite())
            .ok_or_else(|| {
                self.error(line, format!("Invalid or missing finite numeric field {i}"))
            })?;
        Ok(value)
    }
    fn integer(&self, f: &[&str], i: usize, line: usize) -> Result<u32, Diagnostic> {
        f.get(i)
            .and_then(|s| s.parse().ok())
            .ok_or_else(|| self.error(line, format!("Invalid or missing integer field {i}")))
    }
    fn warning(&mut self, line: usize, code: &str, message: impl Into<String>) {
        self.diagnostics
            .push(Diagnostic::new(code, message, self.path, Some(line)).warning());
    }
    fn parse(&mut self) -> Result<Layout, Diagnostic> {
        let versions: Vec<_> = self
            .lines
            .iter()
            .copied()
            .filter(|(_, l)| l.split_whitespace().next() == Some("VERSION"))
            .collect();
        if versions.len() != 1 {
            return Err(self.error(
                versions.first().map_or(1, |v| v.0),
                "Expected exactly one VERSION declaration",
            ));
        }
        let (version_line, version_text) = versions[0];
        let version: Vec<_> = version_text.split_whitespace().collect();
        if version.len() != 3 {
            return Err(self.error(
                version_line,
                "VERSION requires format number and application version",
            ));
        }
        let format_version = self.integer(&version, 1, version_line)?;
        if format_version != 12 {
            return Err(Diagnostic::new(
                "unsupported_version",
                format!("Only layout format 12 is supported; found {format_version}"),
                self.path,
                Some(version_line),
            ));
        }
        let mut summary = LayoutSummary {
            titles: Vec::new(),
            format_version,
            application_version: version[2].into(),
            map_scale: None,
            scale: None,
            room_dimensions: None,
            bounds: None,
            track_count: 0,
            turnout_count: 0,
        };
        let mut tracks = Vec::new();
        let mut ids = HashSet::new();
        let mut terminated = false;
        while let Some(&(line, raw)) = self.lines.get(self.index) {
            self.index += 1;
            let text = raw.trim();
            if text.is_empty() || text.starts_with('#') {
                continue;
            }
            if terminated {
                return Err(self.error(line, "Unexpected record after END$TRACKS"));
            }
            let f: Vec<_> = text.split_whitespace().collect();
            match f[0] {
                "VERSION" => {}
                "TITLE1" | "TITLE2" => {
                    // Remove only the delimiter, preserving the declared title text.
                    let rest = &raw.trim_start()[f[0].len()..];
                    summary
                        .titles
                        .push(rest.strip_prefix([' ', '\t']).unwrap_or(rest).into());
                }
                "MAPSCALE" => {
                    if f.len() != 2 {
                        return Err(self.error(line, "MAPSCALE requires exactly one value"));
                    }
                    let value = self.number(&f, 1, line)?;
                    if value <= 0.0 {
                        return Err(self.error(line, "MAPSCALE must be positive"));
                    }
                    summary.map_scale = Some(value);
                }
                "SCALE" => {
                    if f.len() != 2 {
                        return Err(self.error(line, "SCALE requires one value"));
                    }
                    summary.scale = Some(f[1].into());
                }
                "ROOMSIZE" => {
                    if f.len() != 4 || f[2] != "x" {
                        return Err(self.error(line, "ROOMSIZE requires width x height"));
                    }
                    let width = self.number(&f, 1, line)?;
                    let height = self.number(&f, 3, line)?;
                    if width <= 0.0 || height <= 0.0 {
                        return Err(self.error(line, "ROOMSIZE must be positive"));
                    }
                    summary.room_dimensions = Some(RoomDimensions {
                        width,
                        height,
                        unit: "inch",
                    });
                }
                "LAYERS" => {}
                "STRAIGHT" | "CURVE" | "TURNOUT" => {
                    if line < version_line {
                        return Err(self.error(line, "VERSION must precede track records"));
                    }
                    let id = self.integer(&f, 1, line)?;
                    if !ids.insert(id.to_string()) {
                        return Err(self.error(line, format!("Duplicate track ID {id}")));
                    }
                    tracks.push(self.track(&f, line)?);
                }
                "END$TRACKS" => {
                    if f.len() != 1 {
                        return Err(self.error(line, "Invalid END$TRACKS terminator"));
                    }
                    terminated = true;
                }
                "END$SEGS" => return Err(self.error(line, "Unmatched END$SEGS")),
                tag => {
                    self.warning(
                        line,
                        "unsupported_record",
                        format!("Unsupported top-level record {tag}"),
                    );
                    // Only these documented object kinds are known to be non-track.
                    if !matches!(tag, "DRAW" | "STRUCTURE" | "CAR" | "NOTE" | "TEXT") {
                        self.geometry_complete = false;
                    }
                    self.skip_unknown_block(line)?;
                }
            }
        }
        if !terminated {
            return Err(self.error(self.lines.len().max(1), "Missing END$TRACKS"));
        }
        for t in &tracks {
            for e in &t.endpoints {
                if let Some(target) = &e.connected_to
                    && !ids.contains(target)
                {
                    self.diagnostics.push(
                        Diagnostic::new(
                            "invalid_reference",
                            format!(
                                "Track {} endpoint references unavailable track {target}",
                                t.id
                            ),
                            self.path,
                            e.location.line,
                        )
                        .warning(),
                    );
                }
            }
        }
        let mut bounds: Option<Bounds> = None;
        if tracks.is_empty() {
            self.geometry_complete = false;
        }
        for track in &tracks {
            if track.segments.is_empty() {
                self.geometry_complete = false;
            }
            for segment in &track.segments {
                if let Some(b) = segment.bounds() {
                    match bounds.as_mut() {
                        Some(acc) => acc.merge(b),
                        None => bounds = Some(b),
                    }
                } else {
                    self.geometry_complete = false;
                }
            }
        }
        if self.geometry_complete {
            summary.bounds = bounds;
        }
        if summary.bounds.is_none() {
            self.diagnostics.push(Diagnostic::new("bounds_unavailable",
                "Complete track centerline bounds are unavailable: no tracks or incomplete/unsupported track geometry",
                self.path,None).warning());
        }
        summary.track_count = tracks.len();
        summary.turnout_count = tracks.iter().filter(|t| t.kind == "turnout").count();
        Ok(Layout {
            source: LayoutSource {
                path: self.path.into(),
                format: "xtrackcad-xtc-text",
                fingerprint: String::new(),
            },
            summary,
            tracks,
            diagnostics: std::mem::take(&mut self.diagnostics),
        })
    }

    fn skip_unknown_block(&mut self, header_line: usize) -> Result<(), Diagnostic> {
        let mut consumed = false;
        let mut ended = false;
        while let Some(&(line, raw)) = self.lines.get(self.index) {
            let text = raw.trim();
            if text.is_empty() || text.starts_with('#') {
                self.index += 1;
                continue;
            }
            if text == "END$SEGS" {
                self.index += 1;
                ended = true;
                break;
            }
            if !raw.starts_with(char::is_whitespace) {
                break;
            }
            if text == "END$TRACKS" {
                return Err(self.error(line, "Missing END$SEGS in unsupported object"));
            }
            consumed = true;
            self.index += 1;
        }
        if consumed && !ended {
            return Err(self.error(header_line, "Unterminated unsupported object"));
        }
        Ok(())
    }

    fn endpoint(&self, f: &[&str], line: usize) -> Result<Endpoint, Diagnostic> {
        let connected = f[0].starts_with('T');
        let offset = if connected { 2 } else { 1 };
        let target = if connected {
            Some(self.integer(f, 1, line)?.to_string())
        } else {
            None
        };
        let x = self.number(f, offset, line)?;
        let y = self.number(f, offset + 1, line)?;
        let angle = self.number(f, offset + 2, line)?;
        for i in offset + 3..f.len() {
            self.number(f, i, line)?;
        }
        Ok(Endpoint {
            state: if connected { "connected" } else { "open" }.into(),
            connected_to: target,
            position: Position::new(x, y),
            orientation: Angle::new(angle),
            location: SourceLocation {
                path: self.path.into(),
                line: Some(line),
            },
        })
    }

    fn polygon_decoration(&mut self, f: &[&str], line: usize) -> Result<(), Diagnostic> {
        // F3/Y3 and F4/Y4 have a counted, multiline vertex payload. Consume it
        // as decoration so its coordinates cannot masquerade as track records.
        let version_four = matches!(f[0], "F4" | "Y4");
        if f.len() != if version_four { 5 } else { 4 } {
            return Err(self.error(line, "Malformed polygon decoration header"));
        }
        self.integer(f, 1, line)?;
        self.number(f, 2, line)?;
        let vertices = self.integer(f, 3, line)?;
        if vertices < 3 {
            return Err(self.error(line, "Polygon decoration requires at least three vertices"));
        }
        if version_four {
            self.integer(f, 4, line)?;
        }
        for _ in 0..vertices {
            let &(vertex_line, raw) = self
                .lines
                .get(self.index)
                .ok_or_else(|| self.error(line, "Truncated polygon decoration"))?;
            let fields: Vec<_> = raw.split_whitespace().collect();
            if fields.len() != 3 {
                return Err(self.error(vertex_line, "Polygon vertex requires X, Y and vertex type"));
            }
            self.number(&fields, 0, vertex_line)?;
            self.number(&fields, 1, vertex_line)?;
            self.integer(&fields, 2, vertex_line)?;
            self.index += 1;
        }
        Ok(())
    }

    fn track(&mut self, f: &[&str], line: usize) -> Result<TrackObject, Diagnostic> {
        let turnout = f[0] == "TURNOUT";
        let curve = f[0] == "CURVE";
        let minimum = if turnout {
            13
        } else if curve {
            15
        } else {
            10
        };
        if f.len() < minimum {
            return Err(self.error(line, "Incomplete track header"));
        }
        let id = self.integer(f, 1, line)?.to_string();
        self.integer(f, 2, line)?;
        self.number(f, 3, line)?;
        self.number(f, 4, line)?;
        self.number(f, 5, line)?;
        self.integer(f, 7, line)?;
        let origin = if turnout || curve {
            Position::new(self.number(f, 8, line)?, self.number(f, 9, line)?)
        } else {
            Position::new(0.0, 0.0)
        };
        let rotation = if turnout {
            self.number(f, 11, line)?
        } else {
            0.0
        };
        if turnout || curve {
            self.number(f, 10, line)?;
        }
        let radius = if curve {
            Some(Distance::new(self.number(f, 11, line)?))
        } else {
            None
        };
        if radius.is_some_and(|r| r.value == 0.0) {
            return Err(self.error(line, "Curve radius must be nonzero"));
        }
        let helix = if curve {
            self.number(f, 12, line)?
        } else {
            0.0
        };
        if helix < 0.0 {
            return Err(self.error(line, "Helix turns must be nonnegative"));
        }
        if !turnout {
            for i in 8..f.len() {
                self.number(f, i, line)?;
            }
        }
        let label = if turnout {
            let raw = self.lines[line - 1].1;
            let first = raw
                .find('"')
                .ok_or_else(|| self.error(line, "Missing quoted turnout label"))?;
            let last = raw
                .rfind('"')
                .filter(|p| *p > first)
                .ok_or_else(|| self.error(line, "Unterminated turnout label"))?;
            if !raw[last + 1..].trim().is_empty() {
                return Err(self.error(line, "Unexpected data after turnout label"));
            }
            Some(raw[first + 1..last].into())
        } else {
            None
        };
        let mut track = TrackObject {
            id,
            kind: f[0].to_lowercase(),
            label,
            scale: Some(f[6].into()),
            position: if turnout || curve { Some(origin) } else { None },
            orientation: if turnout {
                Some(Angle::new(rotation))
            } else {
                None
            },
            radius,
            length: None,
            sweep: None,
            endpoints: Vec::new(),
            segments: Vec::new(),
        };
        let mut ended = false;
        while let Some(&(ln, raw)) = self.lines.get(self.index) {
            let text = raw.trim();
            if text.is_empty() || text.starts_with('#') {
                self.index += 1;
                continue;
            }
            let sf: Vec<_> = text.split_whitespace().collect();
            if matches!(sf[0], "END$TRACKS" | "STRAIGHT" | "CURVE" | "TURNOUT") {
                return Err(self.error(ln, "Track missing END$SEGS before next top-level record"));
            }
            self.index += 1;
            match sf[0] {
                "END$SEGS" => {
                    if sf.len() != 1 {
                        return Err(self.error(ln, "Malformed END$SEGS"));
                    }
                    ended = true;
                    break;
                }
                "E4" | "T4" | "E" | "T" => track.endpoints.push(self.endpoint(&sf, ln)?),
                "S" if turnout => {
                    if sf.len() != 7 {
                        return Err(self.error(ln, "S requires color, width and two endpoints"));
                    }
                    for i in 1..sf.len() {
                        self.number(&sf, i, ln)?;
                    }
                    let start = Position::new(self.number(&sf, 3, ln)?, self.number(&sf, 4, ln)?)
                        .transformed(origin, rotation);
                    let end = Position::new(self.number(&sf, 5, ln)?, self.number(&sf, 6, ln)?)
                        .transformed(origin, rotation);
                    track.segments.push(Segment::Straight { start, end });
                }
                "C" if turnout => {
                    if sf.len() != 8 {
                        return Err(self.error(
                            ln,
                            "C requires color, width, radius, center, start and sweep",
                        ));
                    }
                    for i in 1..sf.len() {
                        self.number(&sf, i, ln)?;
                    }
                    let radius = self.number(&sf, 3, ln)?;
                    let start = self.number(&sf, 6, ln)?;
                    let sweep = self.number(&sf, 7, ln)?;
                    if radius == 0.0 || sweep == 0.0 || sweep.abs() > 360.0 {
                        return Err(self.error(ln, "Invalid turnout curve radius/sweep"));
                    }
                    let center = Position::new(self.number(&sf, 4, ln)?, self.number(&sf, 5, ln)?)
                        .transformed(origin, rotation);
                    // Native radius sign selects path traversal; start/sweep define its locus.
                    track.segments.push(Segment::Curve {
                        center,
                        radius: Distance::new(radius),
                        start: Angle::new(start + rotation),
                        sweep: Angle::new(sweep),
                    });
                }
                "D" => {
                    for i in 1..sf.len() {
                        self.number(&sf, i, ln)?;
                    }
                }
                "P" if turnout => {
                    let raw_path = raw.trim();
                    let a = raw_path.find('"');
                    let b = raw_path.rfind('"');
                    if let (Some(a), Some(b)) = (a, b) {
                        if a == b {
                            return Err(self.error(ln, "Unterminated turnout path label"));
                        }
                        let fields: Vec<_> = raw_path[b + 1..].split_whitespace().collect();
                        for i in 0..fields.len() {
                            self.integer(&fields, i, ln)?;
                        }
                    } else {
                        return Err(self.error(ln, "Missing turnout path label"));
                    }
                }
                "F3" | "Y3" | "F4" | "Y4" => self.polygon_decoration(&sf, ln)?,
                tag if is_decoration(tag) => {}
                tag => {
                    self.geometry_complete = false;
                    self.warning(
                        ln,
                        "unsupported_record",
                        format!("Unsupported nested record {tag} in track {}", track.id),
                    );
                }
            }
        }
        if !ended {
            return Err(self.error(line, "Track missing END$SEGS"));
        }
        if track.endpoints.len() < 2 || (!turnout && track.endpoints.len() != 2) {
            return Err(self.error(
                line,
                "Track requires two endpoints (at least two for compound turnouts)",
            ));
        }
        if !turnout {
            let a = track.endpoints[0].position;
            let b = track.endpoints[1].position;
            if !curve {
                track.position = Some(a);
                let length = (b.x - a.x).hypot(b.y - a.y);
                if length == 0.0 {
                    return Err(self.error(line, "Straight endpoints coincide"));
                }
                track.length = Some(Distance::new(length));
                track.orientation = Some(Angle::new(
                    (b.x - a.x).atan2(b.y - a.y).to_degrees().rem_euclid(360.0),
                ));
                track.segments.push(Segment::Straight { start: a, end: b });
            } else {
                let r = radius.ok_or_else(|| self.error(line, "Missing curve radius"))?;
                // Native endpoints are serialized in clockwise radial order.
                // 1e-5 inch permits rounding in six-decimal native coordinate records.
                const ROUNDING_TOLERANCE: f64 = 1e-5;
                let consistent = [a, b].iter().all(|p| {
                    ((p.x - origin.x).hypot(p.y - origin.y) - r.value.abs()).abs()
                        <= ROUNDING_TOLERANCE
                });
                if consistent {
                    let start = (a.x - origin.x)
                        .atan2(a.y - origin.y)
                        .to_degrees()
                        .rem_euclid(360.0);
                    let end = (b.x - origin.x)
                        .atan2(b.y - origin.y)
                        .to_degrees()
                        .rem_euclid(360.0);
                    let mut sweep = (end - start).rem_euclid(360.0);
                    if sweep == 0.0 || helix >= 1.0 {
                        sweep = 360.0;
                    }
                    track.orientation = Some(track.endpoints[0].orientation);
                    if helix == 0.0 {
                        track.sweep = Some(Angle::new(sweep));
                        track.length = Some(Distance::new(r.value.abs() * sweep.to_radians()));
                    } else {
                        // The helix field guarantees a full XY revolution at >= 1,
                        // but does not supply the validated 3D path/length semantics
                        // required to publish a total length or traversal sweep.
                        self.warning(
                            line,
                            "unsupported_geometry",
                            "Helix total length and sweep are unsupported and unavailable",
                        );
                    }
                    if helix == 0.0 || helix >= 1.0 {
                        track.segments.push(Segment::Curve {
                            center: origin,
                            radius: r,
                            start: Angle::new(start),
                            sweep: Angle::new(sweep),
                        });
                    } else {
                        self.geometry_complete = false;
                    }
                } else {
                    self.geometry_complete = false;
                    self.warning(
                        line,
                        "invalid_geometry",
                        "Curve endpoints do not lie on the declared circle",
                    );
                }
            }
        }
        if track.segments.is_empty() {
            self.geometry_complete = false;
        }
        // Overflow after transforms/length calculations must not become fabricated JSON nulls.
        if track.segments.iter().any(|s| s.bounds().is_none())
            || track.length.is_some_and(|v| !v.value.is_finite())
        {
            return Err(self.error(line, "Geometry exceeds supported finite numeric range"));
        }
        Ok(track)
    }
}
fn is_decoration(tag: &str) -> bool {
    matches!(
        tag,
        "L" | "L3" | "A" | "A3" | "F" | "F4" | "Y" | "Y4" | "G" | "G3" | "Z" | "Z3"
    )
}
