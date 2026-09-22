//! The exactly-two tools permitted in v0.1, plus the execution guard that
//! prevents a single Warden Decision from being used to run a tool twice.
//!
//! `ToolId` is a closed enum. There is no "other" or "custom" variant and no
//! way to construct a `ToolRequest` for a tool that isn't one of these two —
//! this is what "exactly two tools, fixed at compile time" means concretely
//! in Rust: it is not a runtime allowlist that could be extended by config,
//! it is the type system.

use std::collections::{BTreeMap, HashSet};
use std::sync::Mutex;
use std::time::{SystemTime, UNIX_EPOCH};

use sha2::{Digest, Sha256};

use crate::warden::{WardenDecision, WardenVerdict};

#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
pub enum ToolId {
    TimeNow,
    ConfigGet,
}

impl ToolId {
    pub fn as_str(&self) -> &'static str {
        match self {
            ToolId::TimeNow => "tool.time.now",
            ToolId::ConfigGet => "tool.config.get",
        }
    }
}

/// Fixed, compile-time allowlist of config keys `tool.config.get` may read.
/// Nothing outside this list is readable through the tool, regardless of
/// what actually exists in the runtime config store.
pub const CONFIG_ALLOWLIST: &[&str] = &["node.profile", "node.version", "warden.mode"];

/// A schema-validated request to run a tool. Constructing one does not
/// grant any authority — it must still pass through `PolicyWarden::evaluate`
/// before `execute` will run it.
#[derive(Debug, Clone)]
pub struct ToolRequest {
    pub tool_id: ToolId,
    pub params: BTreeMap<String, String>,
}

impl ToolRequest {
    /// `pub(crate)`: only `schema::validate` (same crate) may construct a
    /// `ToolRequest` from scratch, since it's the only place strict
    /// schema validation has already happened. (R1/R4.8)
    pub(crate) fn new(tool_id: ToolId, params: BTreeMap<String, String>) -> Self {
        Self { tool_id, params }
    }

    /// Deterministic fingerprint of this exact request, used to bind a
    /// Warden Decision to the specific request it was issued for.
    pub fn fingerprint(&self) -> String {
        let mut hasher = Sha256::new();
        hasher.update(self.tool_id.as_str().as_bytes());
        for (k, v) in &self.params {
            hasher.update(b"|");
            hasher.update(k.as_bytes());
            hasher.update(b"=");
            hasher.update(v.as_bytes());
        }
        hex::encode(hasher.finalize())
    }
}

#[derive(Debug, thiserror::Error)]
pub enum ExecutionError {
    #[error("warden did not allow this request")]
    NotAllowed,
    #[error("decision does not match this request (fingerprint mismatch)")]
    FingerprintMismatch,
    #[error("this decision has already been used to execute a tool")]
    DuplicateExecution,
    #[error("config key not found")]
    ConfigKeyNotFound,
}

#[derive(Debug, Clone)]
pub enum ToolOutput {
    TimeNow { unix_seconds: u64 },
    ConfigValue { key: String, value: String },
}

/// Tracks which Warden Decisions (by sequence number) have already been
/// used to execute a tool, so a single Allow decision cannot be replayed
/// to run the tool multiple times.
pub struct ExecutionGuard {
    used_sequences: Mutex<HashSet<u64>>,
}

impl ExecutionGuard {
    pub(crate) fn new() -> Self {
        Self {
            used_sequences: Mutex::new(HashSet::new()),
        }
    }

    /// Execute `request` if, and only if, `decision` is an Allow verdict
    /// that (a) matches this exact request's fingerprint and (b) has not
    /// already been consumed. `pub(crate)`: the only caller is
    /// `pipeline::Pipeline::submit`, which alone holds the serialization
    /// lock required for R3/R4's ordering guarantees. (R4.8)
    pub(crate) fn execute(
        &self,
        request: &ToolRequest,
        decision: &WardenDecision,
        config_store: &BTreeMap<String, String>,
    ) -> Result<ToolOutput, ExecutionError> {
        if decision.verdict() != WardenVerdict::Allow {
            return Err(ExecutionError::NotAllowed);
        }
        if decision.request_fingerprint() != request.fingerprint() {
            return Err(ExecutionError::FingerprintMismatch);
        }

        {
            let mut used = self.used_sequences.lock().expect("guard mutex poisoned");
            if used.contains(&decision.sequence()) {
                return Err(ExecutionError::DuplicateExecution);
            }
            used.insert(decision.sequence());
        }

        match request.tool_id {
            ToolId::TimeNow => {
                let unix_seconds = SystemTime::now()
                    .duration_since(UNIX_EPOCH)
                    .unwrap_or_default()
                    .as_secs();
                Ok(ToolOutput::TimeNow { unix_seconds })
            }
            ToolId::ConfigGet => {
                let key = request
                    .params
                    .get("key")
                    .expect("warden already validated key presence");
                match config_store.get(key) {
                    Some(value) => Ok(ToolOutput::ConfigValue {
                        key: key.clone(),
                        value: value.clone(),
                    }),
                    None => Err(ExecutionError::ConfigKeyNotFound),
                }
            }
        }
    }
}

// Deliberately no `impl Default for ExecutionGuard`, for the same reason
// as `PolicyWarden` in warden.rs: it would be a public back door around
// `pub(crate) fn new()`.

#[cfg(test)]
mod tests {
    use super::*;
    use crate::warden::PolicyWarden;

    fn config_store() -> BTreeMap<String, String> {
        let mut m = BTreeMap::new();
        m.insert("node.profile".to_string(), "HOST".to_string());
        m.insert("node.version".to_string(), "0.1.0".to_string());
        m.insert("warden.mode".to_string(), "deny-by-default".to_string());
        m
    }

    #[test]
    fn allowed_request_executes_once() {
        let warden = PolicyWarden::new();
        let guard = ExecutionGuard::new();
        let req = ToolRequest::new(ToolId::TimeNow, BTreeMap::new());
        let decision = warden.evaluate(&req);
        let result = guard.execute(&req, &decision, &config_store());
        assert!(result.is_ok());
    }

    #[test]
    fn same_decision_cannot_execute_twice() {
        let warden = PolicyWarden::new();
        let guard = ExecutionGuard::new();
        let req = ToolRequest::new(ToolId::TimeNow, BTreeMap::new());
        let decision = warden.evaluate(&req);
        let first = guard.execute(&req, &decision, &config_store());
        let second = guard.execute(&req, &decision, &config_store());
        assert!(first.is_ok());
        assert!(matches!(second, Err(ExecutionError::DuplicateExecution)));
    }

    #[test]
    fn denied_decision_never_executes() {
        let warden = PolicyWarden::new();
        let guard = ExecutionGuard::new();
        let mut params = BTreeMap::new();
        params.insert("key".to_string(), "not_allowed".to_string());
        let req = ToolRequest::new(ToolId::ConfigGet, params);
        let decision = warden.evaluate(&req);
        let result = guard.execute(&req, &decision, &config_store());
        assert!(matches!(result, Err(ExecutionError::NotAllowed)));
    }

    #[test]
    fn decision_for_different_request_is_rejected() {
        let warden = PolicyWarden::new();
        let guard = ExecutionGuard::new();
        let req_a = ToolRequest::new(ToolId::TimeNow, BTreeMap::new());
        let mut params_b = BTreeMap::new();
        params_b.insert("key".to_string(), "node.profile".to_string());
        let req_b = ToolRequest::new(ToolId::ConfigGet, params_b);

        let decision_for_a = warden.evaluate(&req_a);
        // Attempt to use A's decision to execute B — must be rejected even
        // though decision_for_a.verdict() == Allow.
        let result = guard.execute(&req_b, &decision_for_a, &config_store());
        assert!(matches!(result, Err(ExecutionError::FingerprintMismatch)));
    }

    #[test]
    fn config_get_reads_only_allowlisted_key_value() {
        let warden = PolicyWarden::new();
        let guard = ExecutionGuard::new();
        let mut params = BTreeMap::new();
        params.insert("key".to_string(), "node.profile".to_string());
        let req = ToolRequest::new(ToolId::ConfigGet, params);
        let decision = warden.evaluate(&req);
        let result = guard.execute(&req, &decision, &config_store()).unwrap();
        match result {
            ToolOutput::ConfigValue { key, value } => {
                assert_eq!(key, "node.profile");
                assert_eq!(value, "HOST");
            }
            _ => panic!("expected ConfigValue"),
        }
    }
}