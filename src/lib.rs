//! ORBITAL CORE v0.1
//!
//! Single-machine HOST daemon. Scope is intentionally minimal per the frozen
//! v0.1 specification: two tools, a deny-by-default Policy Warden, a
//! hash-chained SQLite audit log, Ed25519 node identity, and a localhost-only
//! model HTTP client. See README.md for the full list of out-of-scope items.

pub mod audit;
pub mod identity;
pub mod model_client;
pub mod pipeline;
pub mod schema;
pub mod tools;
pub mod warden;

pub use audit::AuditLog;
pub use identity::NodeIdentity;
pub use pipeline::{Pipeline, PipelineError};
pub use tools::ToolOutput;
// `PolicyWarden` and `ExecutionGuard` are intentionally NOT re-exported at
// the crate root as constructible types: their constructors are
// `pub(crate)`, and `Pipeline` is the only sanctioned entry point from
// outside this crate (R4.8). `WardenVerdict` is re-exported since it's a
// plain, harmless-to-construct enum useful for callers matching on
// `PipelineError::Denied`'s reason string context.
pub use warden::WardenVerdict;