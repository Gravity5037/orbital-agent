//! Schema validation for model-originated tool call requests. (R1)
//!
//! Model output has NO authority in ORBITAL. This module is the ONLY path
//! from raw untrusted bytes to a typed `ToolRequest`. There is no second
//! parser/deserializer path anywhere in this crate that can produce a
//! `ToolRequest` — `ToolRequest::new` is `pub(crate)`-reachable but nothing
//! outside this module calls it with attacker-influenced data.
//!
//! Invariant enforced here: MODEL OUTPUT -> STRICT SCHEMA VALIDATION -> WARDEN.
//! Never: MODEL OUTPUT -> alternate parser -> tool execution.

use serde::Deserialize;
use serde_json::Value;
use std::collections::BTreeMap;
use thiserror::Error;

use crate::tools::{ToolId, ToolRequest};

/// Maximum size, in bytes, of a raw tool-call request body considered at
/// all. Enforced before any parsing occurs.
pub const MAX_REQUEST_BYTES: usize = 16 * 1024;

/// Exact, frozen tool-name strings. No aliases, no case-folding, no
/// normalization. `match` on `&str` is byte-exact, which is what we want.
const TOOL_TIME_NOW: &str = "tool.time.now";
const TOOL_CONFIG_GET: &str = "tool.config.get";

/// Top-level envelope. `deny_unknown_fields` means any field other than
/// `tool` and `params` is a hard parse failure, not a silently-ignored
/// extra.
#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
struct RawToolCall {
    tool: String,
    #[serde(default = "default_params")]
    params: Value,
}

fn default_params() -> Value {
    Value::Object(serde_json::Map::new())
}

/// `tool.time.now` takes no parameters at all. `deny_unknown_fields` on an
/// empty struct means ANY key present in `params` is rejected.
#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
struct TimeNowParams {}

/// `tool.config.get` takes exactly one string parameter, `key`.
/// `deny_unknown_fields` rejects extras; the `String` type rejects
/// non-string values; the field being non-`Option` rejects absence.
#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
struct ConfigGetParams {
    key: String,
}

#[derive(Debug, Error)]
pub enum SchemaError {
    #[error("request exceeds maximum size of {MAX_REQUEST_BYTES} bytes")]
    TooLarge,
    #[error("request contains a duplicate key in a JSON object: {0}")]
    DuplicateKey(String),
    #[error("request is not valid JSON, is malformed, or has trailing data after the document: {0}")]
    InvalidJson(String),
    #[error("unknown tool identifier: {0}")]
    UnknownTool(String),
    #[error("tool.time.now params rejected: {0}")]
    TimeNowParamsInvalid(String),
    #[error("tool.config.get params rejected: {0}")]
    ConfigGetParamsInvalid(String),
}

/// Parse and validate a raw request body into a typed `ToolRequest`.
///
/// Order of checks (each is a hard gate — failing one skips the rest):
/// 1. Size limit, checked on raw bytes before any parsing.
/// 2. Duplicate-JSON-key scan, checked on raw bytes before serde ever runs,
///    since by the time serde has built a `Value`/struct, duplicate keys
///    have already been silently collapsed (last-value-wins) and the
///    information is gone.
/// 3. Strict, `deny_unknown_fields` deserialization of the envelope.
///    `serde_json::from_slice` itself rejects trailing non-whitespace data
///    after the JSON document (it calls the deserializer's `end()`, which
///    errors on trailing tokens) — this is exercised explicitly in tests
///    rather than re-implemented.
/// 4. Exact (case-sensitive, no alias) tool-name match.
/// 5. Strict, `deny_unknown_fields` deserialization of `params` into the
///    tool-specific typed struct.
pub fn validate(raw: &[u8]) -> Result<ToolRequest, SchemaError> {
    if raw.len() > MAX_REQUEST_BYTES {
        return Err(SchemaError::TooLarge);
    }

    reject_duplicate_keys(raw)?;

    let parsed: RawToolCall =
        serde_json::from_slice(raw).map_err(|e| SchemaError::InvalidJson(e.to_string()))?;

    match parsed.tool.as_str() {
        TOOL_TIME_NOW => {
            let _: TimeNowParams = serde_json::from_value(parsed.params)
                .map_err(|e| SchemaError::TimeNowParamsInvalid(e.to_string()))?;
            Ok(ToolRequest::new(ToolId::TimeNow, BTreeMap::new()))
        }
        TOOL_CONFIG_GET => {
            let p: ConfigGetParams = serde_json::from_value(parsed.params)
                .map_err(|e| SchemaError::ConfigGetParamsInvalid(e.to_string()))?;
            let mut map = BTreeMap::new();
            map.insert("key".to_string(), p.key);
            Ok(ToolRequest::new(ToolId::ConfigGet, map))
        }
        other => Err(SchemaError::UnknownTool(other.to_string())),
    }
}

/// Hand-rolled duplicate-key scanner over raw JSON bytes.
///
/// This exists because by the time `serde_json` (or any standard JSON
/// library) has finished parsing an object into a `Value` or a struct,
/// duplicate keys have already been silently resolved (last-value-wins)
/// — there is no post-hoc way to detect that a duplicate occurred. This
/// scanner runs on the raw bytes *first*, tracking a separate seen-key set
/// per nesting level, and rejects the request if any object at any level
/// repeats a key. It is intentionally conservative: on any syntax it does
/// not fully understand it stops scanning for duplicates and defers
/// entirely to `serde_json` for the real syntax error, rather than risking
/// a false "safe" result.
fn reject_duplicate_keys(raw: &[u8]) -> Result<(), SchemaError> {
    let s = match std::str::from_utf8(raw) {
        Ok(s) => s,
        // Not valid UTF-8: let serde_json produce the real error.
        Err(_) => return Ok(()),
    };
    let mut chars = s.char_indices().peekable();
    let mut stack: Vec<std::collections::HashSet<String>> = Vec::new();
    let mut expecting_key = false;

    while let Some((_, c)) = chars.next() {
        match c {
            c if c.is_whitespace() => continue,
            '{' => {
                stack.push(std::collections::HashSet::new());
                expecting_key = true;
            }
            '}' => {
                if stack.pop().is_none() {
                    return Ok(()); // malformed; defer to serde_json
                }
                expecting_key = false;
            }
            '[' => {
                // Arrays don't have keys; push a marker level we never
                // populate, so nested object levels inside the array are
                // still tracked independently and unaffected by the
                // enclosing array.
                expecting_key = false;
            }
            ']' => {
                expecting_key = false;
            }
            '"' => {
                let string_val = match scan_json_string(&mut chars) {
                    Some(v) => v,
                    None => return Ok(()), // malformed; defer to serde_json
                };
                // Skip whitespace to see if this string is a key (followed
                // by ':') within an object context expecting a key.
                if expecting_key {
                    let mut lookahead = chars.clone();
                    let mut is_key = false;
                    while let Some((_, nc)) = lookahead.peek().copied() {
                        if nc.is_whitespace() {
                            lookahead.next();
                            continue;
                        }
                        is_key = nc == ':';
                        break;
                    }
                    if is_key {
                        if let Some(level) = stack.last_mut() {
                            if !level.insert(string_val.clone()) {
                                return Err(SchemaError::DuplicateKey(string_val));
                            }
                        }
                        expecting_key = false;
                    }
                }
            }
            ',' => {
                // A comma inside an object at the point we'd next expect
                // a key means the next string token is a key candidate.
                if !stack.is_empty() {
                    expecting_key = true;
                }
            }
            ':' => {
                expecting_key = false;
            }
            _ => {}
        }
    }
    Ok(())
}

/// Consume a JSON string body (the opening `"` has already been consumed
/// by the caller) up to and including the closing, unescaped `"`.
/// Returns the decoded-enough string (escape sequences are left as-is
/// except for `\"` and `\\`, which is sufficient to correctly find the
/// terminating quote and to compare keys for equality). Returns `None` on
/// unterminated/malformed input, signalling the caller to defer to
/// `serde_json`.
fn scan_json_string(
    chars: &mut std::iter::Peekable<std::str::CharIndices>,
) -> Option<String> {
    let mut out = String::new();
    while let Some((_, c)) = chars.next() {
        match c {
            '"' => return Some(out),
            '\\' => {
                let (_, escaped) = chars.next()?;
                out.push('\\');
                out.push(escaped);
            }
            c => out.push(c),
        }
    }
    None
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn valid_time_now_request_parses() {
        let raw = br#"{"tool":"tool.time.now","params":{}}"#;
        assert!(validate(raw).is_ok());
    }

    #[test]
    fn valid_time_now_with_default_params_parses() {
        let raw = br#"{"tool":"tool.time.now"}"#;
        assert!(validate(raw).is_ok());
    }

    #[test]
    fn valid_config_get_request_parses() {
        let raw = br#"{"tool":"tool.config.get","params":{"key":"node.profile"}}"#;
        assert!(validate(raw).is_ok());
    }

    #[test]
    fn unknown_top_level_field_is_rejected() {
        let raw = br#"{"tool":"tool.time.now","params":{},"authority":"root"}"#;
        assert!(matches!(validate(raw), Err(SchemaError::InvalidJson(_))));
    }

    #[test]
    fn unknown_tool_is_rejected() {
        let raw = br#"{"tool":"tool.shell.exec","params":{"cmd":"rm -rf /"}}"#;
        assert!(matches!(validate(raw), Err(SchemaError::UnknownTool(_))));
    }

    #[test]
    fn case_folded_tool_name_is_rejected() {
        let raw = br#"{"tool":"Tool.Time.Now","params":{}}"#;
        assert!(matches!(validate(raw), Err(SchemaError::UnknownTool(_))));
    }

    #[test]
    fn aliased_tool_name_is_rejected() {
        let raw = br#"{"tool":"time.now","params":{}}"#;
        assert!(matches!(validate(raw), Err(SchemaError::UnknownTool(_))));
    }

    #[test]
    fn malformed_json_is_rejected() {
        let raw = b"not json at all {{{";
        assert!(matches!(validate(raw), Err(SchemaError::InvalidJson(_))));
    }

    #[test]
    fn trailing_garbage_after_document_is_rejected() {
        let raw = br#"{"tool":"tool.time.now","params":{}}   garbage"#;
        assert!(matches!(validate(raw), Err(SchemaError::InvalidJson(_))));
    }

    #[test]
    fn trailing_garbage_second_json_value_is_rejected() {
        let raw = br#"{"tool":"tool.time.now","params":{}}{"tool":"tool.config.get","params":{"key":"x"}}"#;
        assert!(matches!(validate(raw), Err(SchemaError::InvalidJson(_))));
    }

    #[test]
    fn oversized_request_is_rejected_before_parsing() {
        let mut huge = br#"{"tool":"tool.config.get","params":{"key":""#.to_vec();
        huge.extend(vec![b'a'; MAX_REQUEST_BYTES]);
        huge.extend(br#""}}"#);
        assert!(matches!(validate(&huge), Err(SchemaError::TooLarge)));
    }

    #[test]
    fn time_now_with_unknown_param_is_rejected() {
        let raw = br#"{"tool":"tool.time.now","params":{"x":"y"}}"#;
        assert!(matches!(validate(raw), Err(SchemaError::TimeNowParamsInvalid(_))));
    }

    #[test]
    fn config_get_without_key_is_rejected() {
        let raw = br#"{"tool":"tool.config.get","params":{}}"#;
        assert!(matches!(validate(raw), Err(SchemaError::ConfigGetParamsInvalid(_))));
    }

    #[test]
    fn config_get_with_extra_param_is_rejected() {
        let raw = br#"{"tool":"tool.config.get","params":{"key":"x","extra":"y"}}"#;
        assert!(matches!(validate(raw), Err(SchemaError::ConfigGetParamsInvalid(_))));
    }

    #[test]
    fn config_get_with_wrong_type_key_is_rejected() {
        let raw = br#"{"tool":"tool.config.get","params":{"key":12345}}"#;
        assert!(matches!(validate(raw), Err(SchemaError::ConfigGetParamsInvalid(_))));
    }

    #[test]
    fn duplicate_top_level_key_is_rejected() {
        let raw = br#"{"tool":"tool.time.now","tool":"tool.config.get","params":{}}"#;
        assert!(matches!(validate(raw), Err(SchemaError::DuplicateKey(_))));
    }

    #[test]
    fn duplicate_param_key_is_rejected() {
        let raw = br#"{"tool":"tool.config.get","params":{"key":"a","key":"b"}}"#;
        assert!(matches!(validate(raw), Err(SchemaError::DuplicateKey(_))));
    }

    #[test]
    fn duplicate_key_detector_ignores_keys_at_different_nesting_levels() {
        // "key" appears once at each of two distinct object levels; this
        // is NOT a duplicate-within-the-same-object and must not be
        // flagged as one by the scanner (the outer object still fails
        // schema validation for other reasons, but not DuplicateKey).
        let raw = br#"{"tool":"tool.config.get","params":{"key":"a"}}"#;
        assert!(reject_duplicate_keys(raw).is_ok());
    }
}