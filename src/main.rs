use std::collections::BTreeMap;
use std::path::PathBuf;

use orbital_core::{audit::AuditLog, identity::NodeIdentity, pipeline::Pipeline};

#[tokio::main]
async fn main() {
    let data_dir = PathBuf::from(
        std::env::var("ORBITAL_DATA_DIR").unwrap_or_else(|_| "./orbital-data".to_string()),
    );
    std::fs::create_dir_all(&data_dir).expect("failed to create data directory");

    // R2: identity load/create enforces restrictive permissions and
    // rejects symlink/reparse-point substitution on the identity path.
    let identity = NodeIdentity::load_or_create(&data_dir.join("identity"))
        .expect("failed to load or create node identity (see R2 permission/symlink checks)");
    println!("[orbital-core] node identity: {}", identity.public_key_hex());

    // R3: AuditLog::open performs the full startup sequence — chain
    // integrity verification, then sentinel-vs-chain cross-check. Any
    // failure here (including a deleted/replaced/tampered DB) is fatal:
    // we refuse to start rather than silently treat it as a new genesis.
    let audit_path = data_dir.join("audit.sqlite3");
    let audit = match AuditLog::open(audit_path.to_str().expect("non-utf8 audit path")) {
        Ok(a) => a,
        Err(e) => {
            eprintln!("[orbital-core] AUDIT INTEGRITY/LOCKDOWN FAILURE AT STARTUP: {e}");
            eprintln!("[orbital-core] refusing to start; explicit operator intervention required.");
            std::process::exit(1);
        }
    };
    println!("[orbital-core] audit chain and sentinel verified consistent");

    let mut config_store = BTreeMap::new();
    config_store.insert("node.profile".to_string(), "HOST".to_string());
    config_store.insert("node.version".to_string(), "0.1.0".to_string());
    config_store.insert("warden.mode".to_string(), "deny-by-default".to_string());

    let pipeline = Pipeline::new(audit, config_store).expect("failed to construct pipeline");

    // Minimal demonstration cycle: v0.1 has no inbound network listener
    // (out of scope). A real caller supplies `raw_request` bytes obtained
    // from the out-of-process model via `model_client::ModelClient`, only
    // after its streamed response has completed in full. `Pipeline::submit`
    // is the only path that can execute a tool — see pipeline.rs.
    let demo_request = br#"{"tool":"tool.time.now","params":{}}"#;
    match pipeline.submit(demo_request).await {
        Ok(output) => println!("[orbital-core] tool result: {:?}", output),
        Err(e) => println!("[orbital-core] tool call rejected: {e}"),
    }

    println!("[orbital-core] entering idle/wait state; press Ctrl+C to shut down");
    tokio::signal::ctrl_c()
        .await
        .expect("failed to listen for shutdown signal");

    println!("[orbital-core] shutdown complete");
}