//! Deterministic, deny-by-default Policy Warden.
//!
//! The Warden is the *only* code path allowed to produce a `WardenDecision`.
//! `WardenDecision` has no public constructor and no public fields, so no
//! other module (including model-facing code) can fabricate a decision that
//! looks approved. This is an in-process opacity guarantee, not a
//! cross-process cryptographic one — see LIMITATIONS.md.
//!
//! The Warden does not consult the model or any untrusted input when making
//! a decision. It only consults: (a) the fixed compile-time tool allowlist,
//! (b) the validated request parameters, (c) hard-coded policy rules below.

use std::collections::HashSet;
use std::sync::atomic::{AtomicU64, Ordering};

use crate::tools::{ToolId, ToolRequest};

/// The outcome of a Warden evaluation.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum WardenVerdict {
    Allow,
    Deny,
}

/// An opaque, unforgeable-in-process record of a Warden's decision about a
/// specific tool request. Only `PolicyWarden::evaluate` can construct one.
/// The tool execution layer requires a `WardenDecision` with
/// `verdict == Allow` and a matching `request_fingerprint` before it will
/// run a tool.
#[derive(Debug, Clone)]
pub struct WardenDecision {
    verdict: WardenVerdict,
    /// Monotonic sequence number assigned at decision time. Used to detect
    /// decision replay/duplication in the execution layer.
    sequence: u64,
    /// Fingerprint (SHA-256 hex) of the exact request this decision applies
    /// to, so a decision for one request cannot be reused for another.
    request_fingerprint: String,
    reason: &'static str,
}

impl WardenDecision {
    pub fn verdict(&self) -> WardenVerdict {
        self.verdict
    }

    pub fn sequence(&self) -> u64 {
        self.sequence
    }

    pub fn request_fingerprint(&self) -> &str {
        &self.request_fingerprint
    }

    pub fn reason(&self) -> &'static str {
        self.reason
    }

    pub fn is_allow(&self) -> bool {
        self.verdict == WardenVerdict::Allow
    }
}

/// Fixed, compile-time allowlist of tools this Warden will ever consider
/// allowing. Nothing outside this set can be approved, regardless of what
/// a request claims. This is intentionally not configurable at runtime.
fn allowed_tools() -> HashSet<ToolId> {
    let mut set = HashSet::new();
    set.insert(ToolId::TimeNow);
    set.insert(ToolId::ConfigGet);
    set
}

pub struct PolicyWarden {
    sequence_counter: AtomicU64,
    allowlist: HashSet<ToolId>,
}

impl PolicyWarden {
    /// `pub(crate)`: only `pipeline::Pipeline` (same crate) constructs a
    /// Warden. External callers reach evaluation only via
    /// `Pipeline::submit`. (R4.8)
    pub(crate) fn new() -> Self {
        Self {
            sequence_counter: AtomicU64::new(1),
            allowlist: allowed_tools(),
        }
    }

    /// Evaluate a validated tool request. `request` must already have
    /// passed schema validation (see `schema.rs`) before it reaches the
    /// Warden — the Warden does not itself parse untrusted input, it only
    /// judges an already-typed, already-validated request.
    pub(crate) fn evaluate(&self, request: &ToolRequest) -> WardenDecision {
        let fingerprint = request.fingerprint();
        let sequence = self.sequence_counter.fetch_add(1, Ordering::SeqCst);

        // Deny-by-default: the tool must be in the fixed allowlist.
        if !self.allowlist.contains(&request.tool_id) {
            return WardenDecision {
                verdict: WardenVerdict::Deny,
                sequence,
                request_fingerprint: fingerprint,
                reason: "tool not in compile-time allowlist",
            };
        }

        // Per-tool deterministic policy checks. No branch here consults the
        // model's own claims about intent, permission, or authority.
        let verdict = match request.tool_id {
            ToolId::TimeNow => {
                // tool.time.now takes no parameters. Any parameters present
                // are a schema violation caught upstream, but we also
                // enforce it here defensively (defense in depth).
                if request.params.is_empty() {
                    WardenVerdict::Allow
                } else {
                    WardenVerdict::Deny
                }
            }
            ToolId::ConfigGet => {
                // tool.config.get is only allowed to read keys present in
                // the fixed compile-time config allowlist (see tools.rs).
                match request.params.get("key") {
                    Some(key) if crate::tools::CONFIG_ALLOWLIST.contains(&key.as_str()) => {
                        WardenVerdict::Allow
                    }
                    _ => WardenVerdict::Deny,
                }
            }
        };

        let reason: &'static str = match verdict {
            WardenVerdict::Allow => "allowed by fixed policy",
            WardenVerdict::Deny => "denied: parameters failed fixed policy check",
        };

        WardenDecision {
            verdict,
            sequence,
            request_fingerprint: fingerprint,
            reason,
        }
    }
}

// Deliberately no `impl Default for PolicyWarden`: `Default::default()` is
// a public trait method regardless of the inherent constructor's
// visibility, and would silently reopen external construction that
// `pub(crate) fn new()` is meant to close off (R4.8).

#[cfg(test)]
mod tests {
    use super::*;
    use crate::tools::ToolRequest;
    use std::collections::BTreeMap;

    #[test]
    fn deny_by_default_for_unknown_tool_is_impossible_to_construct() {
        // ToolId is a closed enum (see tools.rs) — there is no variant that
        // represents an unlisted tool, so "unknown tool" requests cannot
        // even be constructed. This test documents that invariant.
        let warden = PolicyWarden::new();
        let req = ToolRequest::new(ToolId::TimeNow, BTreeMap::new());
        let decision = warden.evaluate(&req);
        assert!(decision.is_allow());
    }

    #[test]
    fn time_now_with_unexpected_params_is_denied() {
        let warden = PolicyWarden::new();
        let mut params = BTreeMap::new();
        params.insert("unexpected".to_string(), "value".to_string());
        let req = ToolRequest::new(ToolId::TimeNow, params);
        let decision = warden.evaluate(&req);
        assert_eq!(decision.verdict(), WardenVerdict::Deny);
    }

    #[test]
    fn config_get_outside_allowlist_is_denied() {
        let warden = PolicyWarden::new();
        let mut params = BTreeMap::new();
        params.insert("key".to_string(), "not_a_real_key".to_string());
        let req = ToolRequest::new(ToolId::ConfigGet, params);
        let decision = warden.evaluate(&req);
        assert_eq!(decision.verdict(), WardenVerdict::Deny);
    }

    #[test]
    fn config_get_inside_allowlist_is_allowed() {
        let warden = PolicyWarden::new();
        let key = crate::tools::CONFIG_ALLOWLIST[0];
        let mut params = BTreeMap::new();
        params.insert("key".to_string(), key.to_string());
        let req = ToolRequest::new(ToolId::ConfigGet, params);
        let decision = warden.evaluate(&req);
        assert!(decision.is_allow());
    }

    #[test]
    fn decisions_get_strictly_increasing_sequence_numbers() {
        let warden = PolicyWarden::new();
        let req = ToolRequest::new(ToolId::TimeNow, BTreeMap::new());
        let d1 = warden.evaluate(&req);
        let d2 = warden.evaluate(&req);
        assert!(d2.sequence() > d1.sequence());
    }

    #[test]
    fn fingerprint_differs_for_different_params() {
        let mut p1 = BTreeMap::new();
        p1.insert("key".to_string(), "a".to_string());
        let mut p2 = BTreeMap::new();
        p2.insert("key".to_string(), "b".to_string());
        let r1 = ToolRequest::new(ToolId::ConfigGet, p1);
        let r2 = ToolRequest::new(ToolId::ConfigGet, p2);
        assert_ne!(r1.fingerprint(), r2.fingerprint());
    }
}