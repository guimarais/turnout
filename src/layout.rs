use schemars::JsonSchema;
use serde::Serialize;

#[derive(Clone, Debug, Serialize, JsonSchema)]
pub struct SourceLocation {
    pub path: String,
    pub line: Option<usize>,
}

#[derive(Clone, Debug, Serialize, JsonSchema)]
pub struct Diagnostic {
    pub severity: String,
    pub code: String,
    pub message: String,
    pub location: Option<SourceLocation>,
}

impl Diagnostic {
    pub fn new(code: &str, message: impl Into<String>, path: &str, line: Option<usize>) -> Self {
        Self {
            severity: "error".into(),
            code: code.into(),
            message: message.into(),
            location: Some(SourceLocation {
                path: path.into(),
                line,
            }),
        }
    }
    pub fn warning(mut self) -> Self {
        self.severity = "warning".into();
        self
    }
}

#[derive(Clone, Copy, Debug, Serialize, JsonSchema)]
pub struct Position {
    pub x: f64,
    pub y: f64,
    pub unit: &'static str,
}
impl Position {
    pub fn new(x: f64, y: f64) -> Self {
        Self { x, y, unit: "inch" }
    }
    pub fn transformed(self, origin: Self, degrees: f64) -> Self {
        let (sin, cos) = degrees.to_radians().sin_cos();
        Self::new(
            origin.x + self.x * cos + self.y * sin,
            origin.y - self.x * sin + self.y * cos,
        )
    }
}
#[derive(Clone, Copy, Debug, Serialize, JsonSchema)]
pub struct Angle {
    pub value: f64,
    pub unit: &'static str,
    pub clockwise: bool,
}
impl Angle {
    pub fn new(value: f64) -> Self {
        Self {
            value,
            unit: "degree",
            clockwise: true,
        }
    }
}
#[derive(Clone, Copy, Debug, Serialize, JsonSchema)]
pub struct Distance {
    pub value: f64,
    pub unit: &'static str,
}
impl Distance {
    pub fn new(value: f64) -> Self {
        Self {
            value,
            unit: "inch",
        }
    }
}
#[derive(Clone, Debug, Serialize, JsonSchema)]
pub struct Endpoint {
    pub state: String,
    pub connected_to: Option<String>,
    pub position: Position,
    pub orientation: Angle,
    pub location: SourceLocation,
}
#[derive(Clone, Debug, Serialize, JsonSchema)]
#[serde(tag = "kind", rename_all = "snake_case")]
pub enum Segment {
    Straight {
        start: Position,
        end: Position,
    },
    Curve {
        center: Position,
        radius: Distance,
        start: Angle,
        sweep: Angle,
    },
}
impl Segment {
    pub fn bounds(&self) -> Option<Bounds> {
        let points = match self {
            Self::Straight { start, end } => vec![*start, *end],
            Self::Curve {
                center,
                radius,
                start,
                sweep,
            } => {
                let r = radius.value.abs();
                if r == 0.0 {
                    return None;
                }
                let point = |a: f64| {
                    let (sin, cos) = a.to_radians().sin_cos();
                    Position::new(center.x + r * sin, center.y + r * cos)
                };
                let mut points = vec![point(start.value), point(start.value + sweep.value)];
                for a in [0.0, 90.0, 180.0, 270.0] {
                    let delta = if sweep.value >= 0.0 {
                        (a - start.value).rem_euclid(360.0)
                    } else {
                        (start.value - a).rem_euclid(360.0)
                    };
                    if sweep.value.abs() >= 360.0 || delta <= sweep.value.abs() {
                        points.push(point(a));
                    }
                }
                points
            }
        };
        Bounds::from_points(&points)
    }
}
#[derive(Clone, Debug, Serialize, JsonSchema)]
pub struct TrackObject {
    pub id: String,
    pub kind: String,
    pub label: Option<String>,
    pub scale: Option<String>,
    pub position: Option<Position>,
    pub orientation: Option<Angle>,
    pub radius: Option<Distance>,
    pub length: Option<Distance>,
    pub sweep: Option<Angle>,
    pub endpoints: Vec<Endpoint>,
    pub segments: Vec<Segment>,
}
#[derive(Clone, Copy, Debug, Serialize, JsonSchema)]
pub struct Bounds {
    pub min_x: f64,
    pub min_y: f64,
    pub max_x: f64,
    pub max_y: f64,
    pub unit: &'static str,
}
impl Bounds {
    pub fn from_points(points: &[Position]) -> Option<Self> {
        let first = points.first()?;
        let mut b = Self {
            min_x: first.x,
            min_y: first.y,
            max_x: first.x,
            max_y: first.y,
            unit: "inch",
        };
        for p in points {
            if !p.x.is_finite() || !p.y.is_finite() {
                return None;
            }
            b.min_x = b.min_x.min(p.x);
            b.min_y = b.min_y.min(p.y);
            b.max_x = b.max_x.max(p.x);
            b.max_y = b.max_y.max(p.y);
        }
        Some(b)
    }
    pub fn merge(&mut self, other: Self) {
        self.min_x = self.min_x.min(other.min_x);
        self.min_y = self.min_y.min(other.min_y);
        self.max_x = self.max_x.max(other.max_x);
        self.max_y = self.max_y.max(other.max_y);
    }
}
#[derive(Clone, Copy, Debug, Serialize, JsonSchema)]
pub struct RoomDimensions {
    pub width: f64,
    pub height: f64,
    pub unit: &'static str,
}

#[derive(Clone, Debug, Serialize, JsonSchema)]
pub struct LayoutSummary {
    pub titles: Vec<String>,
    pub format_version: u32,
    pub application_version: String,
    pub map_scale: Option<f64>,
    pub scale: Option<String>,
    pub room_dimensions: Option<RoomDimensions>,
    pub bounds: Option<Bounds>,
    pub track_count: usize,
    pub turnout_count: usize,
}
#[derive(Clone, Debug, Serialize, JsonSchema)]
pub struct LayoutSource {
    pub path: String,
    pub format: &'static str,
    pub fingerprint: String,
}
#[derive(Clone, Debug, Serialize, JsonSchema)]
pub struct Layout {
    pub source: LayoutSource,
    pub summary: LayoutSummary,
    pub tracks: Vec<TrackObject>,
    pub diagnostics: Vec<Diagnostic>,
}
