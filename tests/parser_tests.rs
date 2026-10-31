use std::{fs, path::Path};
use turnout::xtc;

fn parse_text(text: &str) -> Result<turnout::layout::Layout, turnout::layout::Diagnostic> {
    let dir = tempfile::tempdir().unwrap();
    let path = dir.path().join("case.xtc");
    fs::write(&path, text).unwrap();
    xtc::read(&path)
}

#[test]
fn malformed_polygon_payloads_fail_with_source_locations() {
    for polygon in [
        "F4 0 0 nope 0\n",
        "F4 0 0 2 0\n 0 0 0\n 1 1 0\n",
        "Y4 0 0 3\n 0 0 0\n 1 0 0\n 1 1 0\n",
        "F4 0 0 3 0\n 0 0 0\n 1 0 0\n",
        "Y4 0 0 3 0\n 0 0 0\n NaN 0 0\n 1 1 0\n",
        "F3 0 0 3\n 0 0 0\n 1 0\n 1 1 0\n",
    ] {
        let text = format!(
            "VERSION 12 app\nTURNOUT 1 0 0 0 0 HO 2 0 0 0 0 \"Polygon\"\n E4 0 0 0\n E4 1 0 180\n S 0 0 0 0 1 0\n {polygon} END$SEGS\nEND$TRACKS\n"
        );
        let error = parse_text(&text).unwrap_err();
        assert_eq!(error.code, "malformed_record", "{polygon}");
        assert!(error.location.unwrap().line.unwrap() >= 6);
    }
}

#[test]
fn strict_format_12_is_independent_of_application_version() {
    for app in ["5.2.0", "5.3.1GA", "99.0.0"] {
        let l = parse_text(&format!("VERSION 12 {app}\nEND$TRACKS\n")).unwrap();
        assert_eq!(l.summary.format_version, 12);
        assert_eq!(l.summary.application_version, app);
    }
    for version in [0, 11, 13, 999] {
        let e = parse_text(&format!("VERSION {version} 5.3.1GA\nEND$TRACKS\n")).unwrap_err();
        assert_eq!(e.code, "unsupported_version");
        assert_eq!(e.location.unwrap().line, Some(1));
    }
}

#[test]
fn malformed_or_conflicting_versions_are_rejected() {
    for text in [
        "END$TRACKS\n",
        "VERSION nope app\nEND$TRACKS\n",
        "VERSION 12\nEND$TRACKS\n",
        "VERSION 12 app\nVERSION 13 app\nEND$TRACKS\n",
        "VERSION 12 app extra\nEND$TRACKS\n",
    ] {
        assert_eq!(
            parse_text(text).unwrap_err().code,
            "malformed_record",
            "{text}"
        );
    }
}

#[test]
fn invalid_metadata_is_not_silently_skipped() {
    for body in [
        "MAPSCALE NaN",
        "MAPSCALE 0",
        "ROOMSIZE 0 x 1",
        "ROOMSIZE 1 x NaN",
        "ROOMSIZE -1 x 2",
        "ROOMSIZE 1 by 2",
        "SCALE",
    ] {
        let e = parse_text(&format!("VERSION 12 app\n{body}\nEND$TRACKS\n")).unwrap_err();
        assert_eq!(e.code, "malformed_record");
        assert_eq!(e.location.unwrap().line, Some(2));
    }
}

#[test]
fn supported_metadata_rejects_trailing_fields_with_locations() {
    for record in [
        "MAPSCALE 53 garbage",
        "MAPSCALE 53 54",
        "SCALE HO extra",
        "ROOMSIZE 10 x 20 extra",
        "VERSION 12 app extra",
    ] {
        let text = if record.starts_with("VERSION") {
            format!("{record}\nEND$TRACKS\n")
        } else {
            format!("VERSION 12 app\n{record}\nEND$TRACKS\n")
        };
        let e = parse_text(&text).unwrap_err();
        assert_eq!(e.code, "malformed_record");
        assert_eq!(e.severity, "error");
        let location = e.location.unwrap();
        assert!(location.path.ends_with("case.xtc"));
        assert_eq!(
            location.line,
            Some(if record.starts_with("VERSION") { 1 } else { 2 })
        );
    }
}

#[test]
fn unsupported_helix_length_is_never_reported_as_one_revolution() {
    for turns in [0.5, 1.0, 2.0, 3.25] {
        let l=parse_text(&format!("VERSION 12 app\nCURVE 1 0 0 0 0 HO 2 0 0 0 2 {turns} 0 0\nE4 0 2 0\nE4 2 0 90\nEND$SEGS\nEND$TRACKS\n")).unwrap();
        assert!(l.tracks[0].length.is_none());
        assert!(l.tracks[0].sweep.is_none());
        assert!(
            l.diagnostics
                .iter()
                .any(|d| d.code == "unsupported_geometry"
                    && d.location.as_ref().unwrap().line == Some(2))
        );
    }
}

#[test]
fn sample_endpoint_coordinates_directions_and_targets_match_the_source() {
    let l = xtc::read(Path::new("layouts/mrkln_sample.xtc")).unwrap();
    let expected = [
        vec![
            (18.25, 39.125, 270.0, Some("4")),
            (27.277559, 39.125, 90.0, Some("2")),
        ],
        vec![
            (27.277559, 39.125, 270.0, Some("1")),
            (34.364173, 41.023853, 60.0, Some("3")),
        ],
        vec![
            (34.364173, 41.023853, 240.0, Some("2")),
            (39.551934, 46.211615, 30.0, None),
        ],
        vec![
            (10.836614, 39.125, 270.0, None),
            (18.25, 39.125, 90.0, Some("1")),
            (17.924706, 37.598974, 114.3, None),
        ],
    ];
    let anchors = [
        (18.25, 39.125, 0.0),
        (27.277559, 39.125, 0.0),
        (34.364173, 41.023853, 330.0),
        (10.836614, 39.125, 0.0),
    ];
    for (i, t) in l.tracks.iter().enumerate() {
        assert_eq!(t.id, (i + 1).to_string());
        assert_eq!(t.scale.as_deref(), Some("HO"));
        let p = t.position.unwrap();
        assert_eq!((p.x, p.y, t.orientation.unwrap().value), anchors[i]);
        assert_eq!(t.endpoints.len(), expected[i].len());
        for (endpoint, (x, y, angle, target)) in t.endpoints.iter().zip(&expected[i]) {
            assert_eq!(
                (
                    endpoint.position.x,
                    endpoint.position.y,
                    endpoint.orientation.value
                ),
                (*x, *y, *angle)
            );
            assert_eq!(endpoint.connected_to.as_deref(), *target);
            assert_eq!(
                endpoint.state,
                if target.is_some() {
                    "connected"
                } else {
                    "open"
                }
            );
        }
    }
}

#[test]
fn mixed_geometry_values_and_source_ids_are_exact() {
    let l = xtc::read(Path::new("tests/fixtures/authored/mixed.xtc")).unwrap();
    let straight = &l.tracks[0];
    let curve = &l.tracks[1];
    assert_eq!((&*straight.id, &*curve.id), ("1", "2"));
    for t in &l.tracks {
        assert_eq!(t.scale.as_deref(), Some("HO"));
    }
    assert_eq!(
        (straight.position.unwrap().x, straight.position.unwrap().y),
        (-2.0, 0.0)
    );
    assert_eq!(straight.orientation.unwrap().value, 90.0);
    assert_eq!(straight.length.unwrap().value, 2.0);
    assert_eq!(
        (curve.position.unwrap().x, curve.position.unwrap().y),
        (0.0, 2.0)
    );
    assert_eq!(curve.orientation.unwrap().value, 180.0);
    assert_eq!(curve.radius.unwrap().value, 2.0);
    assert_eq!(curve.sweep.unwrap().value, 90.0);
    assert!((curve.length.unwrap().value - std::f64::consts::PI).abs() < 1e-12);
}

#[test]
fn malformed_track_blocks_report_the_source_location() {
    let header = "VERSION 12 app\nSTRAIGHT 1 0 0 0 0 HO 2 0 0\n";
    for tail in [
        "E4 NaN 0 90\nE4 1 0 270\nEND$SEGS\nEND$TRACKS\n",
        "E4 0 0 90\nE4 1e999 0 270\nEND$SEGS\nEND$TRACKS\n",
        "E4 0 0\nE4 1 0 270\nEND$SEGS\nEND$TRACKS\n",
        "E4 0 0 90\nE4 1 0 270\nEND$TRACKS\n",
        "E4 0 0 90\nE4 1 0 270\nEND$SEGS junk\nEND$TRACKS\n",
    ] {
        let e = parse_text(&format!("{header}{tail}")).unwrap_err();
        assert_eq!(e.code, "malformed_record");
        assert!(e.location.unwrap().line.is_some());
    }
}

#[test]
fn duplicate_identity_fails_and_dangling_reference_warns() {
    let track = "STRAIGHT 1 0 0 0 0 HO 2 0 0\nE4 0 0 90\nT4 99 1 0 270\nEND$SEGS\n";
    let l = parse_text(&format!("VERSION 12 app\n{track}END$TRACKS\n")).unwrap();
    let d = l
        .diagnostics
        .iter()
        .find(|d| d.code == "invalid_reference")
        .unwrap();
    assert_eq!(d.severity, "warning");
    assert_eq!(d.location.as_ref().unwrap().line, Some(4));
    assert_eq!(
        parse_text(&format!("VERSION 12 app\n{track}{track}END$TRACKS\n"))
            .unwrap_err()
            .code,
        "malformed_record"
    );
}

#[test]
fn preserves_declared_title_whitespace_and_null_optional_fields() {
    let l = parse_text("VERSION 12 app\nTITLE1  Märklin  \nEND$TRACKS\n").unwrap();
    assert_eq!(l.summary.titles, [" Märklin  "]);
    let json = serde_json::to_value(&l.summary).unwrap();
    for key in ["map_scale", "scale", "room_dimensions", "bounds"] {
        assert!(json.get(key).unwrap().is_null());
    }
}

#[test]
fn all_committed_fixtures_remain_byte_and_mtime_identical() {
    for name in [
        "layouts/mrkln_sample.xtc",
        "tests/fixtures/authored/mixed.xtc",
        "tests/fixtures/authored/unknown.xtc",
        "tests/fixtures/authored/malformed.xtc",
    ] {
        let path = Path::new(name);
        let bytes = fs::read(path).unwrap();
        let modified = fs::metadata(path).unwrap().modified().unwrap();
        let _ = xtc::read(path);
        assert_eq!(bytes, fs::read(path).unwrap());
        assert_eq!(modified, fs::metadata(path).unwrap().modified().unwrap());
    }
}

#[cfg(unix)]
#[test]
fn unreadable_file_is_reported_when_permissions_are_enforced() {
    use std::os::unix::fs::PermissionsExt;
    let dir = tempfile::tempdir().unwrap();
    let path = dir.path().join("locked.xtc");
    fs::write(&path, "VERSION 12 app\nEND$TRACKS\n").unwrap();
    fs::set_permissions(&path, fs::Permissions::from_mode(0o000)).unwrap();
    let enforced = fs::read(&path).is_err();
    if enforced {
        assert_eq!(xtc::read(&path).unwrap_err().code, "unreadable_path");
    }
    fs::set_permissions(&path, fs::Permissions::from_mode(0o600)).unwrap();
}

#[test]
fn parses_supplied_xtrackcad_sample_summary_and_turnouts() {
    let layout = xtc::read(Path::new("layouts/mrkln_sample.xtc")).unwrap();
    assert_eq!(layout.summary.titles, ["mcptest", "Trying to connect it"]);
    assert_eq!(layout.summary.format_version, 12);
    assert_eq!(layout.summary.application_version, "5.2.0");
    assert_eq!(layout.summary.map_scale, Some(53.0));
    assert_eq!(layout.summary.scale.as_deref(), Some("HO"));
    assert_eq!(layout.summary.room_dimensions.unwrap().width, 96.0);
    assert_eq!(layout.summary.room_dimensions.unwrap().height, 48.0);
    assert_eq!(layout.summary.turnout_count, 4);
    assert_eq!(layout.tracks.len(), 4);
}

#[test]
fn retains_utf8_turnout_labels_and_source_order() {
    let layout = xtc::read(Path::new("layouts/mrkln_sample.xtc")).unwrap();
    assert_eq!(
        layout
            .tracks
            .iter()
            .map(|t| t.id.as_str())
            .collect::<Vec<_>>(),
        ["1", "2", "3", "4"]
    );
    assert!(
        layout.tracks[0]
            .label
            .as_deref()
            .unwrap()
            .contains("Märklin")
    );
}

#[test]
fn parses_turnout_connected_and_open_ends() {
    let layout = xtc::read(Path::new("layouts/mrkln_sample.xtc")).unwrap();
    assert!(
        layout.tracks[0]
            .endpoints
            .iter()
            .any(|e| e.state == "connected" && e.connected_to.as_deref() == Some("4"))
    );
    assert!(
        layout.tracks[2]
            .endpoints
            .iter()
            .any(|e| e.state == "open" && e.connected_to.is_none())
    );
}

#[test]
fn inspection_does_not_change_sample_bytes_or_modification_time() {
    let path = Path::new("layouts/mrkln_sample.xtc");
    let before = fs::read(path).unwrap();
    let modified = fs::metadata(path).unwrap().modified().unwrap();
    xtc::read(path).unwrap();
    assert_eq!(fs::read(path).unwrap(), before);
    assert_eq!(fs::metadata(path).unwrap().modified().unwrap(), modified);
}

#[test]
fn rejects_missing_terminator_and_non_utf8_input() {
    let dir = tempfile::tempdir().unwrap();
    let malformed = dir.path().join("bad.xtc");
    fs::write(&malformed, "VERSION 12 5.2.0\n").unwrap();
    assert_eq!(xtc::read(&malformed).unwrap_err().code, "malformed_record");
    fs::write(&malformed, [0xff, 0xfe]).unwrap();
    assert_eq!(xtc::read(&malformed).unwrap_err().code, "invalid_utf8");
}

#[test]
fn reports_missing_files_and_unsupported_extensions() {
    let missing = xtc::read(Path::new("layouts/not-present.xtc")).unwrap_err();
    assert_eq!(missing.code, "unreadable_path");
    let dir = tempfile::tempdir().unwrap();
    let archive = dir.path().join("archive.xtce");
    fs::write(&archive, b"archive placeholder").unwrap();
    let unsupported = xtc::read(&archive).unwrap_err();
    assert_eq!(unsupported.code, "unsupported_format");
}

#[test]
fn unknown_top_level_records_are_reported() {
    let dir = tempfile::tempdir().unwrap();
    let path = dir.path().join("unknown.xtc");
    fs::write(&path, "VERSION 12 5.2.0\nALIEN 1 2\nEND$TRACKS\n").unwrap();
    let layout = xtc::read(&path).unwrap();
    assert!(
        layout
            .diagnostics
            .iter()
            .any(|d| d.code == "unsupported_record")
    );
}

#[test]
fn parses_straight_and_curve_records_with_endpoints() {
    let dir = tempfile::tempdir().unwrap();
    let path = dir.path().join("tracks.xtc");
    fs::write(
        &path,
        concat!(
            "VERSION 12 5.2.0\n",
            "STRAIGHT 1 1 0 0 0 HO 2 0 0 0 0\n",
            " E4 0 0 90\n T4 2 6 0 270\n END$SEGS\n",
            "CURVE 2 1 0 0 0 HO 2 0 12 0 12 0 0 0\n",
            " E4 18 12 0\n T4 1 6 0 90\n END$SEGS\nEND$TRACKS\n"
        ),
    )
    .unwrap();
    let layout = xtc::read(&path).unwrap();
    assert_eq!(
        layout
            .tracks
            .iter()
            .map(|t| t.kind.as_str())
            .collect::<Vec<_>>(),
        ["straight", "curve"]
    );
    assert_eq!(layout.tracks[0].endpoints.len(), 2);
    assert_eq!(layout.tracks[1].radius.unwrap().value, 12.0);
    assert_eq!(layout.summary.track_count, 2);
}

#[test]
fn rejects_directory_empty_path_and_invalid_supported_numeric_fields() {
    let dir = tempfile::tempdir().unwrap();
    assert_eq!(xtc::read(dir.path()).unwrap_err().code, "unreadable_path");
    assert_eq!(
        xtc::read(Path::new("")).unwrap_err().code,
        "unreadable_path"
    );
    let path = dir.path().join("bad.xtc");
    fs::write(
        &path,
        "VERSION 12 5.2.0\nSTRAIGHT x 1 0 0 0 HO 2 0 0 0 0\nEND$TRACKS\n",
    )
    .unwrap();
    assert_eq!(xtc::read(&path).unwrap_err().code, "malformed_record");
}
