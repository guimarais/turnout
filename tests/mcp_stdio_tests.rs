use rmcp::{
    ClientHandler, RoleClient, ServiceExt,
    model::{CallToolRequestParam, CallToolResult, ClientInfo},
};
use serde_json::{Value, json};
use std::{fs, path::PathBuf, process::Stdio, time::Duration};
use tokio::{
    process::{Child, Command},
    time::timeout,
};
use turnout::mcp::InspectionServer;

const LIMIT: Duration = Duration::from_secs(10);
#[derive(Default, Debug)]
struct TestClient;
impl ClientHandler for TestClient {
    fn get_info(&self) -> ClientInfo {
        ClientInfo::default()
    }
}
struct Harness {
    client: rmcp::service::RunningService<RoleClient, TestClient>,
    child: Option<Child>,
    server: Option<tokio::task::JoinHandle<()>>,
}
fn fixture(name: &str) -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR")).join(name)
}
impl Harness {
    async fn memory() -> Self {
        let (server_io, client_io) = tokio::io::duplex(64 * 1024);
        let server = tokio::spawn(async move {
            let running = InspectionServer::default().serve(server_io).await.unwrap();
            running.waiting().await.unwrap();
        });
        let client = timeout(LIMIT, TestClient.serve(client_io))
            .await
            .expect("handshake timeout")
            .unwrap();
        Self {
            client,
            child: None,
            server: Some(server),
        }
    }
    async fn process() -> Self {
        let mut child = Command::new(env!("CARGO_BIN_EXE_turnout"))
            .current_dir(std::env::temp_dir())
            .kill_on_drop(true)
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .stderr(Stdio::inherit())
            .spawn()
            .unwrap();
        let stdout = child.stdout.take().unwrap();
        let stdin = child.stdin.take().unwrap();
        let connect = timeout(LIMIT, TestClient.serve((stdout, stdin))).await;
        let client = match connect {
            Ok(Ok(client)) => client,
            other => {
                child.kill().await.unwrap();
                let _ = child.wait().await;
                panic!("STDIO handshake failed: {other:?}");
            }
        };
        Self {
            client,
            child: Some(child),
            server: None,
        }
    }
    async fn invoke(&self, name: &str, args: Option<Value>) -> CallToolResult {
        timeout(
            LIMIT,
            self.client.call_tool(CallToolRequestParam {
                name: name.to_string().into(),
                arguments: args.map(|v| v.as_object().unwrap().clone()),
            }),
        )
        .await
        .expect("tool request timeout")
        .unwrap()
    }
    async fn call(&self, name: &str, args: Option<Value>) -> Value {
        let result = self.invoke(name, args).await;
        let structured = result
            .structured_content
            .as_ref()
            .expect("structured result");
        let text = result
            .content
            .first()
            .and_then(|c| c.raw.as_text())
            .unwrap();
        assert_eq!(
            *structured,
            serde_json::from_str::<Value>(&text.text).unwrap()
        );
        structured.clone()
    }
    async fn open(&self, name: &str) -> Value {
        self.call("open_layout", Some(json!({"path":fixture(name)})))
            .await
    }
    async fn close(mut self) {
        timeout(LIMIT, self.client.cancel())
            .await
            .expect("shutdown timeout")
            .unwrap();
        if let Some(child) = self.child.as_mut() {
            let status = timeout(LIMIT, child.wait())
                .await
                .expect("child did not exit")
                .unwrap();
            assert!(status.success(), "server exited unsuccessfully: {status}");
        }
        if let Some(server) = self.server.take() {
            timeout(LIMIT, server)
                .await
                .expect("server did not stop")
                .unwrap();
        }
    }
}
async fn summary_flow(h: &Harness) {
    let tools = timeout(LIMIT, h.client.peer().list_tools(Default::default()))
        .await
        .unwrap()
        .unwrap();
    let names: Vec<_> = tools.tools.iter().map(|t| t.name.as_ref()).collect();
    assert_eq!(names.len(), 3);
    for name in ["open_layout", "get_layout_info", "list_tracks"] {
        assert!(names.contains(&name));
    }
    let open_tool = tools
        .tools
        .iter()
        .find(|t| t.name == "open_layout")
        .unwrap();
    assert!(
        open_tool
            .input_schema
            .get("required")
            .unwrap()
            .as_array()
            .unwrap()
            .contains(&json!("path"))
    );
    let missing = h.call("list_tracks", None).await;
    assert_eq!(missing["diagnostics"][0]["code"], "no_open_layout");
    let source = fixture("layouts/mrkln_sample.xtc");
    let before = fs::read(&source).unwrap();
    let mtime = fs::metadata(&source).unwrap().modified().unwrap();
    let opened = h.open("layouts/mrkln_sample.xtc").await;
    assert_eq!(opened["ok"], true);
    assert_eq!(opened["source"]["path"], source.to_string_lossy().as_ref());
    assert!(
        opened["source"]["fingerprint"]
            .as_str()
            .unwrap()
            .starts_with("fnv1a64:")
    );
    assert_eq!(opened["summary"]["format_version"], 12);
    assert_eq!(opened["summary"]["application_version"], "5.2.0");
    assert_eq!(
        opened["summary"]["room_dimensions"],
        json!({"width":96.0,"height":48.0,"unit":"inch"})
    );
    assert!(opened["summary"]["bounds"].is_object());
    assert_eq!(opened["summary"]["bounds"]["unit"], "inch");
    assert_eq!(opened["summary"]["turnout_count"], 4);
    let info = h.call("get_layout_info", None).await;
    assert_eq!(opened, info);
    let tracks = h.call("list_tracks", None).await;
    assert_eq!(tracks["tracks"].as_array().unwrap().len(), 4);
    for (i, track) in tracks["tracks"].as_array().unwrap().iter().enumerate() {
        assert_eq!(track["id"], (i + 1).to_string());
        assert_eq!(track["kind"], "turnout");
        assert_eq!(track["position"]["unit"], "inch");
        assert_eq!(track["orientation"]["unit"], "degree");
        assert_eq!(track["orientation"]["clockwise"], true);
        for e in track["endpoints"].as_array().unwrap() {
            assert_eq!(e["position"]["unit"], "inch");
            assert_eq!(e["orientation"]["unit"], "degree");
        }
    }
    let expected_endpoints = [
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
    for (track, expected) in tracks["tracks"]
        .as_array()
        .unwrap()
        .iter()
        .zip(&expected_endpoints)
    {
        assert_eq!(track["scale"], "HO");
        assert_eq!(track["endpoints"].as_array().unwrap().len(), expected.len());
        for (e, (x, y, angle, target)) in
            track["endpoints"].as_array().unwrap().iter().zip(expected)
        {
            assert_eq!(e["position"], json!({"x":x,"y":y,"unit":"inch"}));
            assert_eq!(
                e["orientation"],
                json!({"value":angle,"unit":"degree","clockwise":true})
            );
            assert_eq!(e["connected_to"], json!(target));
            assert_eq!(
                e["state"],
                if target.is_some() {
                    "connected"
                } else {
                    "open"
                }
            );
        }
    }
    assert!(
        tracks["tracks"][0]["label"]
            .as_str()
            .unwrap()
            .contains("Märklin")
    );
    assert_eq!(before, fs::read(&source).unwrap());
    assert_eq!(mtime, fs::metadata(&source).unwrap().modified().unwrap());
}
#[tokio::test]
async fn discovers_and_calls_layout_tools() {
    let h = Harness::memory().await;
    summary_flow(&h).await;
    h.close().await;
}
#[tokio::test]
async fn executable_serves_all_layout_tools_over_stdio() {
    let h = Harness::process().await;
    summary_flow(&h).await;
    h.close().await;
}
#[tokio::test]
async fn stdio_malformed_and_version_failed_opens_clear_the_session() {
    let h = Harness::process().await;
    let dir = tempfile::tempdir().unwrap();
    for (name, text, code) in [
        (
            "bad.xtc",
            "VERSION 12 app\nSTRAIGHT junk\nEND$TRACKS\n",
            "malformed_record",
        ),
        (
            "new.xtc",
            "VERSION 13 app\nEND$TRACKS\n",
            "unsupported_version",
        ),
    ] {
        assert_eq!(h.open("layouts/mrkln_sample.xtc").await["ok"], true);
        let p = dir.path().join(name);
        fs::write(&p, text).unwrap();
        let before = fs::read(&p).unwrap();
        let mtime = fs::metadata(&p).unwrap().modified().unwrap();
        let result = h.call("open_layout", Some(json!({"path":p}))).await;
        assert_eq!(result["ok"], false);
        assert_eq!(result["diagnostics"][0]["code"], code);
        assert_eq!(result["diagnostics"][0]["severity"], "error");
        assert_eq!(
            result["diagnostics"][0]["location"]["path"],
            p.to_string_lossy().as_ref()
        );
        assert!(result["diagnostics"][0]["location"]["line"].is_number());
        for tool in ["get_layout_info", "list_tracks"] {
            assert_eq!(
                h.call(tool, None).await["diagnostics"][0]["code"],
                "no_open_layout"
            );
        }
        assert_eq!(fs::read_to_string(&p).unwrap(), text);
        assert_eq!(before, fs::read(&p).unwrap());
        assert_eq!(mtime, fs::metadata(&p).unwrap().modified().unwrap());
    }
    h.close().await;
}
#[tokio::test]
async fn missing_and_directory_inputs_fail_without_stale_state() {
    let h = Harness::memory().await;
    for path in [
        fixture("layouts/not-present.xtc"),
        fixture("layouts"),
        PathBuf::new(),
    ] {
        h.open("layouts/mrkln_sample.xtc").await;
        let result = h.call("open_layout", Some(json!({"path":path}))).await;
        assert_eq!(result["diagnostics"][0]["code"], "unreadable_path");
        assert_eq!(h.call("get_layout_info", None).await["ok"], false);
    }
    h.close().await;
}
#[tokio::test]
async fn unsupported_geometry_warnings_are_immediate_and_bounds_are_null() {
    let h = Harness::memory().await;
    let result = h.open("tests/fixtures/authored/unknown.xtc").await;
    assert_eq!(result["ok"], true);
    assert!(result["summary"]["bounds"].is_null());
    for code in ["unsupported_record", "bounds_unavailable"] {
        assert!(
            result["diagnostics"]
                .as_array()
                .unwrap()
                .iter()
                .any(|d| d["code"] == code)
        );
    }
    h.close().await;
}
#[tokio::test]
async fn mixed_tracks_have_units_and_correct_kind_counts() {
    let h = Harness::memory().await;
    let open = h.open("tests/fixtures/authored/mixed.xtc").await;
    assert_eq!(open["summary"]["track_count"], 2);
    assert_eq!(open["summary"]["turnout_count"], 0);
    let result = h.call("list_tracks", None).await;
    assert_eq!(result["tracks"][0]["kind"], "straight");
    assert_eq!(result["tracks"][1]["kind"], "curve");
    assert_eq!(result["tracks"][1]["radius"]["unit"], "inch");
    assert_eq!(result["tracks"][1]["sweep"]["unit"], "degree");
    assert!(result["tracks"][0]["radius"].is_null());
    let straight = &result["tracks"][0];
    let curve = &result["tracks"][1];
    assert_eq!(straight["id"], "1");
    assert_eq!(curve["id"], "2");
    assert_eq!(straight["scale"], "HO");
    assert_eq!(curve["scale"], "HO");
    assert_eq!(
        straight["position"],
        json!({"x":-2.0,"y":0.0,"unit":"inch"})
    );
    assert_eq!(curve["position"], json!({"x":0.0,"y":2.0,"unit":"inch"}));
    assert_eq!(straight["orientation"]["value"], 90.0);
    assert_eq!(curve["orientation"]["value"], 180.0);
    assert_eq!(straight["length"], json!({"value":2.0,"unit":"inch"}));
    assert_eq!(curve["radius"], json!({"value":2.0,"unit":"inch"}));
    assert_eq!(
        curve["sweep"],
        json!({"value":90.0,"unit":"degree","clockwise":true})
    );
    assert!((curve["length"]["value"].as_f64().unwrap() - std::f64::consts::PI).abs() < 1e-12);
    h.close().await;
}
#[tokio::test]
async fn invalid_arguments_are_protocol_errors_not_file_failures() {
    let h = Harness::memory().await;
    for args in [
        json!({}),
        json!({"path":9}),
        json!({"path":"file.xtc","extra":true}),
    ] {
        let result = timeout(
            LIMIT,
            h.client.call_tool(CallToolRequestParam {
                name: "open_layout".into(),
                arguments: Some(args.as_object().unwrap().clone()),
            }),
        )
        .await
        .unwrap();
        assert!(
            result.is_err(),
            "invalid arguments must be rejected by the MCP schema"
        );
    }
    h.close().await;
}
#[tokio::test]
async fn stdio_fixture_reads_preserve_valid_and_invalid_inputs() {
    let h = Harness::process().await;
    for name in [
        "tests/fixtures/authored/mixed.xtc",
        "tests/fixtures/authored/unknown.xtc",
        "tests/fixtures/authored/malformed.xtc",
    ] {
        let path = fixture(name);
        let before = fs::read(&path).unwrap();
        let mtime = fs::metadata(&path).unwrap().modified().unwrap();
        h.open(name).await;
        assert_eq!(before, fs::read(&path).unwrap());
        assert_eq!(mtime, fs::metadata(&path).unwrap().modified().unwrap());
    }
    h.close().await;
}
