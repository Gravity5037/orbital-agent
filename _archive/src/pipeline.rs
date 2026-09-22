//! The single, serialized pipeline: schema -> warden -> durable audit ->
//! decision consumption -> execution -> result audit. (R3, R4)
//!
//! `Pipeline::submit` is the ONLY public entry point in this crate that can
//! cause a tool to execute. `PolicyWarden::evaluate` and
//! `ExecutionGuard::execute` are `pub(crate)` — code outside this crate
//! (including `main.rs`, which depends on this crate like any other
//! external consumer) cannot reach them directly, cannot construct a
//! `WardenDecision`, and therefore cannot execute a tool except by calling
//! `submit` with bytes that pass schema validation and Warden approval.
//!
//! The whole authorization-audit-consume-execute critical section runs
//! under one `tokio::sync::Mutex`, which gives us, in one mechanism:
//! - R3.7: serialized execution (no parallel tool execution in v0.1).
//! - R4.7: concurrent duplicate-decision attempts cannot race — only one
//!   caller can be inside the critical section at a time, so there is no
//!   window for two callers to both observe "not yet consumed".
//! - R3.5: a single authoritative in-memory `expected_head`, updated only
//!   inside the same lock, so it can never be read/written concurrently
//!   with itself.

use std::collections::BTreeMap;
use std::sync::atomic::{AtomicBool, Ordering};
use std::time::Duration;

use tokio::sync::Mutex;

use crate::audit::{AuditError, AuditLog};
use crate::schema::{self, SchemaError};
use crate::tools::{self, ExecutionError, ToolOutput};
use crate::warden::PolicyWarden;

/// Hard wall-clock budget for a single tool-call cycle.
const TOOL_CYCLE_BUDGET: Duration = Duration::from_secs(5);

#[derive(Debug, thiserror::Error)]
pub enum PipelineError {
    #[error("system is locked down due to a prior integrity failure; no execution is permitted")]
    LockedDown,
    #[error("schema rejected: {0}")]
    Schema(#[from] SchemaError),
    #[error("denied: {0}")]
    Denied(&'static str),
    #[error("audit failure, refusing to execute: {0}")]
    Audit(#[from] AuditError),
    #[error("runtime integrity mismatch detected; entering permanent lockdown")]
    RuntimeIntegrityMismatch,
    #[error("execution error: {0}")]
    Execution(#[from] ExecutionError),
    #[error("tool execution exceeded hard budget")]
    Timeout,
}

struct Guarded {
    audit: AuditLog,
    /// Authoritative in-memory record of what we believe the chain head
    /// to be, updated only while holding the lock that also guards
    /// `audit`. Any external modification to the DB between our own
    /// writes will surface here as a mismatch against what SQLite reports.
    expected_head: (i64, String),
}

pub struct Pipeline {
    warden: PolicyWarden,
    guard: tools::ExecutionGuard,
    config_store: BTreeMap<String, String>,
    state: Mutex<Guarded>,
    /// Set once, on any runtime integrity failure. Never cleared for the
    /// lifetime of the process (R3.5: "do not automatically recover").
    locked_down: AtomicBool,
}

impl Pipeline {
    /// Construct a pipeline from an already-opened, already-verified
    /// `AuditLog`. `AuditLog::open` itself performs the full startup
    /// integrity/sentinel check (R3.4) and returns `Err` if it fails, so
    /// by the time a `Pipeline` exists, startup verification has already
    /// passed.
    pub fn new(audit: AuditLog, config_store: BTreeMap<String, String>) -> Result<Self, AuditError> {
        let expected_head = audit.current_head()?;
        Ok(Self {
            warden: PolicyWarden::new(),
            guard: tools::ExecutionGuard::new(),
            config_store,
            state: Mutex::new(Guarded { audit, expected_head }),
            locked_down: AtomicBool::new(false),
        })
    }

    pub fn is_locked_down(&self) -> bool {
        self.locked_down.load(Ordering::SeqCst)
    }

    /// Process one raw tool-call request end to end. This is the only
    /// path by which a tool executes.
    pub async fn submit(&self, raw_request: &[u8]) -> Result<ToolOutput, PipelineError> {
        if self.is_locked_down() {
            return Err(PipelineError::LockedDown);
        }

        // 1. Schema validation. Pure, no shared state — fine to run
        // outside the lock. Untrusted bytes never reach the Warden raw.
        let request = schema::validate(raw_request)?;

        // 2. Deterministic Warden evaluation. Also pure/stateless aside
        // from the monotonic sequence counter, which is independently
        // atomic — fine outside the lock too.
        let decision = self.warden.evaluate(&request);

        // Everything from here on (audit write, runtime-integrity check,
        // decision consumption, execution) is one serialized critical
        // section.
        let mut guarded = self.state.lock().await;

        // R3.5: runtime integrity check. If what SQLite reports as the
        // current head no longer matches what we last wrote ourselves,
        // something modified the DB out of band since our last write —
        // lock down immediately and do not attempt recovery.
        match guarded.audit.current_head() {
            Ok(head) if head == guarded.expected_head => {}
            _ => {
                self.locked_down.store(true, Ordering::SeqCst);
                return Err(PipelineError::RuntimeIntegrityMismatch);
            }
        }

        let decision_payload = format!(
            "{{\"tool\":\"{}\",\"verdict\":\"{:?}\",\"sequence\":{},\"fingerprint\":\"{}\",\"reason\":\"{}\"}}",
            request.tool_id.as_str(),
            decision.verdict(),
            decision.sequence(),
            decision.request_fingerprint(),
            decision.reason(),
        );

        // 3. Authorization audit: insert + durable commit + sentinel
        // checkpoint (all inside `AuditLog::record`). This is the
        // fail-closed gate — any Err here means NO execution, full stop.
        // Deliberately NOT `let _ = ...`.
        let new_seq = guarded.audit.record("warden_decision", &decision_payload)?;
        let (_, new_hash) = guarded.audit.current_head()?;
        guarded.expected_head = (new_seq, new_hash);

        if !decision.is_allow() {
            return Err(PipelineError::Denied(decision.reason()));
        }

        // 4. Decision is now accepted-to-execute. Consuming it here (via
        // `guard.execute`, which performs the single-use check as its
        // first act) is the "consume on accept-to-execute" point required
        // by R4.4 — everything after this cannot be reached again for
        // this same decision even if execution itself later fails.
        let exec_result = tokio::time::timeout(TOOL_CYCLE_BUDGET, async {
            self.guard.execute(&request, &decision, &self.config_store)
        })
        .await;

        let output = match exec_result {
            Ok(Ok(output)) => output,
            Ok(Err(e)) => {
                let _ = guarded.audit.record("tool_execution_error", &format!("{e}"));
                return Err(PipelineError::Execution(e));
            }
            Err(_) => {
                let _ = guarded.audit.record("tool_execution_timeout", request.tool_id.as_str());
                return Err(PipelineError::Timeout);
            }
        };

        // 5. Result audit. Per R3.9, this is NOT the fail-closed
        // invariant — the tool has already run and the authorization
        // record is already durably committed. A failure here is a
        // forensic gap, not a security violation, and is logged but does
        // not itself trigger lockdown.
        if let Ok(seq) = guarded.audit.record("tool_executed", &format!("{output:?}")) {
            if let Ok((_, hash)) = guarded.audit.current_head() {
                guarded.expected_head = (seq, hash);
            }
        }

        Ok(output)
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use tempfile::tempdir;

    fn config_store() -> BTreeMap<String, String> {
        let mut m = BTreeMap::new();
        m.insert("node.profile".to_string(), "HOST".to_string());
        m
    }

    fn pipeline(dir: &std::path::Path) -> Pipeline {
        let path = dir.join("audit.sqlite3");
        let audit = AuditLog::open(path.to_str().unwrap()).unwrap();
        Pipeline::new(audit, config_store()).unwrap()
    }

    #[tokio::test]
    async fn full_cycle_allows_time_now() {
        let dir = tempdir().unwrap();
        let p = pipeline(dir.path());
        let raw = br#"{"tool":"tool.time.now","params":{}}"#;
        assert!(p.submit(raw).await.is_ok());
    }

    #[tokio::test]
    async fn shell_tool_rejected_before_warden() {
        let dir = tempdir().unwrap();
        let p = pipeline(dir.path());
        let raw = br#"{"tool":"tool.shell.exec","params":{"cmd":"rm -rf /"}}"#;
        assert!(matches!(p.submit(raw).await, Err(PipelineError::Schema(_))));
    }

    #[tokio::test]
    async fn config_get_outside_allowlist_denied_and_audited() {
        let dir = tempdir().unwrap();
        let p = pipeline(dir.path());
        let raw = br#"{"tool":"tool.config.get","params":{"key":"secret.api.key"}}"#;
        assert!(matches!(p.submit(raw).await, Err(PipelineError::Denied(_))));
    }

    #[tokio::test]
    async fn concurrent_identical_requests_each_get_independently_allowed_decisions() {
        // Two concurrent submissions of the SAME raw bytes each go through
        // schema+warden independently and receive DIFFERENT decisions
        // (different sequence numbers), so both may legitimately execute.
        // This documents that "single-use" applies per-decision, not
        // per-raw-request — see tools.rs tests for the actual replay
        // rejection of one fixed decision object.
        let dir = tempdir().unwrap();
        let p = pipeline(dir.path());
        let raw = br#"{"tool":"tool.time.now","params":{}}"#;
        let (r1, r2) = tokio::join!(p.submit(raw), p.submit(raw));
        assert!(r1.is_ok());
        assert!(r2.is_ok());
    }

    #[tokio::test]
    async fn out_of_band_db_modification_triggers_lockdown() {
        let dir = tempdir().unwrap();
        let path = dir.path().join("audit.sqlite3");
        let audit = AuditLog::open(path.to_str().unwrap()).unwrap();
        let p = Pipeline::new(audit, config_store()).unwrap();

        let raw = br#"{"tool":"tool.time.now","params":{}}"#;
        assert!(p.submit(raw).await.is_ok());

        // Simulate an external process appending a row directly to the
        // SQLite file without going through our sentinel-checkpoint path
        // (or, equivalently here, without updating our in-memory
        // `expected_head`) — the simplest reliable simulation is to reach
        // into the connection via a second connection and insert a row.
        {
            let conn2 = rusqlite::Connection::open(&path).unwrap();
            conn2
                .execute(
                    "INSERT INTO audit_log (ts_unix_ms, event_type, payload, prev_hash, hash)
                     VALUES (0, 'external', 'x', 'bogus', 'bogus')",
                    [],
                )
                .unwrap();
        }

        let result = p.submit(raw).await;
        assert!(matches!(result, Err(PipelineError::RuntimeIntegrityMismatch)));
        assert!(p.is_locked_down());

        // Lockdown persists: even a well-formed subsequent request is
        // rejected without re-attempting the integrity check.
        let result2 = p.submit(raw).await;
        assert!(matches!(result2, Err(PipelineError::LockedDown)));
    }
}