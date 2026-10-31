use rmcp::{ServiceExt, transport::stdio};
use turnout::mcp::InspectionServer;

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    let service = InspectionServer::default().serve(stdio()).await?;
    service.waiting().await?;
    Ok(())
}
