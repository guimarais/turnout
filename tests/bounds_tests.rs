use std::fs;
use turnout::{layout::Layout, xtc};

fn inspect(body: &str) -> Layout {
    let dir = tempfile::tempdir().unwrap();
    let path = dir.path().join("geometry.xtc");
    fs::write(&path, format!("VERSION 12 5.2.0\n{body}END$TRACKS\n")).unwrap();
    xtc::read(&path).unwrap()
}

fn check(layout: &Layout, expected: [f64; 4]) {
    let b = layout.summary.bounds.as_ref().expect("complete bounds");
    for (value, expected) in [b.min_x, b.min_y, b.max_x, b.max_y]
        .into_iter()
        .zip(expected)
    {
        assert!((value - expected).abs() < 1e-6, "{value} != {expected}");
    }
    assert_eq!(b.unit, "inch");
}

#[test]
fn straight_bounds_use_endpoints_not_description_or_room() {
    let l = inspect(
        "ROOMSIZE 100 x 200\nSTRAIGHT 1 0 0 0 0 HO 2 80 90\n E4 -2 3 90\n E4 4 8 270\n END$SEGS\n",
    );
    check(&l, [-2.0, 3.0, 4.0, 8.0]);
    assert_eq!(l.summary.room_dimensions.unwrap().width, 100.0);
}

fn turnout_curve(radius: f64, start: f64, sweep: f64, rotation: f64) -> Layout {
    inspect(&format!(
        "TURNOUT 1 0 0 0 0 HO 2 10 20 0 {rotation} \"Curve\"\n E4 0 0 0\n E4 0 0 0\n C 0 0 {radius} 0 0 {start} {sweep}\n END$SEGS\n"
    ))
}

#[test]
fn curve_bounds_include_interior_extrema() {
    check(
        &turnout_curve(2.0, 45.0, 90.0, 0.0),
        [
            10.0 + 2.0_f64.sqrt(),
            20.0 - 2.0_f64.sqrt(),
            12.0,
            20.0 + 2.0_f64.sqrt(),
        ],
    );
}

#[test]
fn negative_radius_preserves_the_native_arc_locus() {
    check(
        &turnout_curve(-2.0, 0.0, 90.0, 0.0),
        [10.0, 20.0, 12.0, 22.0],
    );
}

#[test]
fn rotated_arc_is_bounded_after_the_world_transform() {
    check(
        &turnout_curve(2.0, 0.0, 90.0, 45.0),
        [
            10.0 + 2.0_f64.sqrt(),
            20.0 - 2.0_f64.sqrt(),
            12.0,
            20.0 + 2.0_f64.sqrt(),
        ],
    );
}

#[test]
fn full_circle_has_circle_bounds() {
    check(
        &turnout_curve(2.0, 13.0, 360.0, 0.0),
        [8.0, 18.0, 12.0, 22.0],
    );
}

#[test]
fn rotated_asymmetric_turnout_ignores_decorations() {
    let l = inspect(
        "TURNOUT 1 0 0 0 0 HO 2 10 20 0 90 \"Asymmetric\"\n E4 10 20 0\n E4 10 16 180\n S 0 0 0 0 4 1\n L3 0 0 -999 -999 0 999 999 0\n END$SEGS\n",
    );
    check(&l, [10.0, 16.0, 11.0, 20.0]);
}

#[test]
fn polygon_decoration_payloads_do_not_change_track_bounds() {
    for header in ["F3 0 0 3", "Y3 0 0 3", "F4 0 0 3 0", "Y4 0 0 3 2"] {
        let l = inspect(&format!(
            "TURNOUT 1 0 0 0 0 HO 2 10 20 0 90 \"Decorated\"\n E4 10 20 0\n E4 11 16 180\n {header}\n -999 -999 0\n 999 -999 1\n 999 999 2\n S 0 0 0 0 4 1\n END$SEGS\n"
        ));
        check(&l, [10.0, 16.0, 11.0, 20.0]);
        assert!(l.diagnostics.is_empty(), "{header}: {:?}", l.diagnostics);
    }
}

#[test]
fn top_level_curve_uses_radial_endpoint_order() {
    let l = inspect("CURVE 1 0 0 0 0 HO 2 0 0 0 2 0 0 0\n E4 0 2 0\n E4 2 0 90\n END$SEGS\n");
    check(&l, [0.0, 0.0, 2.0, 2.0]);
}

#[test]
fn helix_xy_bounds_are_complete_only_for_a_known_full_revolution() {
    for turns in [1.0, 2.0, 3.25] {
        let l = inspect(&format!(
            "CURVE 1 0 0 0 0 HO 2 0 0 0 2 {turns} 0 0\n E4 0 2 0\n E4 2 0 90\n END$SEGS\n"
        ));
        check(&l, [-2.0, -2.0, 2.0, 2.0]);
    }
    let l = inspect("CURVE 1 0 0 0 0 HO 2 0 0 0 2 0.5 0 0\n E4 0 2 0\n E4 2 0 90\n END$SEGS\n");
    assert!(l.summary.bounds.is_none());
    assert!(l.diagnostics.iter().any(|d| d.code == "bounds_unavailable"));
}

#[test]
fn unknown_potential_track_or_nested_geometry_makes_bounds_unavailable() {
    for body in [
        "ALIEN 1\n",
        "TURNOUT 1 0 0 0 0 HO 2 0 0 0 0 \"Unknown\"\n E4 0 0 0\n E4 1 1 0\n J 1 2 3\n END$SEGS\n",
    ] {
        let l = inspect(body);
        assert!(l.summary.bounds.is_none());
        assert!(l.diagnostics.iter().any(|d| d.code == "bounds_unavailable"));
    }
}

#[test]
fn empty_layout_and_known_decoration_have_no_track_bounds() {
    let l = inspect("DRAW 1 0 0\n L3 0 0 1 2 0 3 4 0\n END$SEGS\n");
    assert_eq!(l.summary.track_count, 0);
    assert!(l.summary.bounds.is_none());
}

#[test]
fn supplied_turnout_anchors_and_rotation_are_correct() {
    let l = xtc::read(std::path::Path::new("layouts/mrkln_sample.xtc")).unwrap();
    assert_eq!(l.tracks[0].position.as_ref().unwrap().x, 18.25);
    assert_eq!(l.tracks[0].position.as_ref().unwrap().y, 39.125);
    assert_eq!(l.tracks[2].orientation.as_ref().unwrap().value, 330.0);
    let b = l.summary.bounds.unwrap();
    assert!((b.min_x - 10.836614).abs() < 1e-6);
    assert!((b.max_y - 46.211615).abs() < 1e-5);
}
