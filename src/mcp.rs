use crate::{
    layout::{Diagnostic, Layout},
    xtc,
};
use rmcp::{
    ErrorData, ServerHandler,
    handler::server::{router::tool::ToolRouter, wrapper::Parameters},
    model::{CallToolResult, ServerCapabilities, ServerInfo},
    tool, tool_handler, tool_router,
};
use schemars::JsonSchema;
use serde::Deserialize;
use serde_json::json;
use std::sync::Mutex;

/// A single coherent inspection snapshot per server process.
pub struct InspectionServer {
    layout: Mutex<Option<Layout>>,
    tool_router: ToolRouter<Self>,
}
impl Default for InspectionServer {
    fn default() -> Self {
        Self {
            layout: Mutex::new(None),
            tool_router: Self::tool_router(),
        }
    }
}
#[derive(Deserialize, JsonSchema)]
#[serde(deny_unknown_fields)]
pub struct OpenArgs {
    pub path: String,
}

fn state_error() -> ErrorData {
    ErrorData::internal_error("Inspection state is unavailable", None)
}
fn no_layout() -> CallToolResult {
    CallToolResult::structured_error(json!({"ok":false,"diagnostics":[Diagnostic {
        severity:"error".into(),code:"no_open_layout".into(),message:"No layout is open".into(),location:None
    }]}))
}
fn info(layout: &Layout) -> CallToolResult {
    CallToolResult::structured(json!({"ok":true,"source":layout.source,
        "summary":layout.summary,"diagnostics":layout.diagnostics}))
}
#[tool_router(router=tool_router)]
impl InspectionServer {
    #[tool(
        description = "Open a format-12 plain-text XTrackCAD .xtc layout for read-only inspection"
    )]
    async fn open_layout(&self, args: Parameters<OpenArgs>) -> Result<CallToolResult, ErrorData> {
        let mut state = self.layout.lock().map_err(|_| state_error())?;
        // Parsing and replacement are serialized so readers never see mixed source/layout state.
        *state = None;
        match xtc::read(std::path::Path::new(&args.0.path)) {
            Ok(layout) => {
                let result = info(&layout);
                *state = Some(layout);
                Ok(result)
            }
            Err(error) => Ok(CallToolResult::structured_error(
                json!({"ok":false,"diagnostics":[error]}),
            )),
        }
    }
    #[tool(
        description = "Return source, metadata, room dimensions and complete-or-unavailable track bounds"
    )]
    async fn get_layout_info(&self) -> Result<CallToolResult, ErrorData> {
        let state = self.layout.lock().map_err(|_| state_error())?;
        Ok(state.as_ref().map_or_else(no_layout, info))
    }
    #[tool(
        description = "List supported tracks with explicit units, directions and endpoint references"
    )]
    async fn list_tracks(&self) -> Result<CallToolResult, ErrorData> {
        let state = self.layout.lock().map_err(|_| state_error())?;
        Ok(match state.as_ref() {
            Some(layout) => CallToolResult::structured(
                json!({"ok":true,"tracks":layout.tracks,"diagnostics":layout.diagnostics}),
            ),
            None => no_layout(),
        })
    }
}
#[tool_handler(router=self.tool_router)]
impl ServerHandler for InspectionServer {
    fn get_info(&self) -> ServerInfo {
        ServerInfo {instructions:Some("Read-only XTrackCAD format-12 inspection. Numeric geometry has explicit units. Null bounds mean geometry is incomplete; consult diagnostics.".into()),
            capabilities:ServerCapabilities::builder().enable_tools().build(),..Default::default()}
    }
}
