//! Append-only, hash-chained SQLite audit log, plus a durable Sentinel
//! checkpoint used to detect DB deletion/replacement across restarts. (R3)
//!
//! Two files, deliberately separate:
//! - `<path>` — the mutable SQLite database. Hash-chained, but on its own
//!   an attacker who can delete/replace the whole file can make an empty
//!   DB look like a legitimate fresh genesis.
//! - `<path>.sentinel` — a small, independently-written JSON checkpoint
//!   recording `(initialized, checkpoint_sequence, checkpoint_hash)`. Its
//!   only job is to let us tell "this system was never initialized" apart
//!   from "this system WAS initialized and the DB has since been
//!   deleted/replaced/truncated". A checkpoint is a claim of the form
//!   "row N of the chain has hash H"; on startup, if row N in the current
//!   DB does not have hash H (or row N doesn't exist), the DB cannot be
//!   the same history the sentinel attests to, and we lock down rather
//!   than accept it as a new genesis.
//!
//! This does not defend against an attacker who can delete/replace BOTH
//! files with matching fabricated content — that is out of scope for a
//! single unprivileged local file pair in v0.1. It defends against the
//! specific failure mode named in the remediation brief: the audit DB
//! being deleted, truncated, or swapped for an empty/different DB while
//! the sentinel is left untouched (the common case for "oops, deleted the
//! wrong file" or a crude tamper attempt).

use rusqlite::{params, Connection, OptionalExtension};
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use std::fs;
use std::io::Write;
use std::path::{Path, PathBuf};
use thiserror::Error;

#[derive(Debug, Error)]
pub enum AuditError {
    #[error("sqlite error: {0}")]
    Sqlite(#[from] rusqlite::Error),
    #[error("io error: {0}")]
    Io(#[from] std::io::Error),
    #[error("sentinel file is malformed: {0}")]
    MalformedSentinel(String),
    #[error("audit chain is broken at sequence {sequence}: expected prev_hash {expected}, found {found}")]
    ChainBroken {
        sequence: i64,
        expected: String,
        found: String,
    },
    #[error(
        "sentinel/DB mismatch: sentinel attests sequence {sentinel_sequence} has hash {sentinel_hash}, \
         but the current database {actual}. This database is not the one the sentinel was checkpointed \
         against — treating as post-initialization tamper/replacement, not a fresh genesis."
    )]
    SentinelMismatch {
        sentinel_sequence: i64,
        sentinel_hash: String,
        actual: String,
    },
    #[error("system was previously initialized (sentinel present) but the audit database is missing or empty")]
    InitializedButDbMissing,
    #[error("audit database exists but no sentinel is present; cannot attest this is a genuine genesis state")]
    DbPresentWithoutSentinel,
}

#[derive(Debug, Serialize, Deserialize)]
struct Sentinel {
    initialized: bool,
    checkpoint_sequence: i64,
    checkpoint_hash: String,
}

pub struct AuditLog {
    conn: Connection,
    sentinel_path: PathBuf,
}

const GENESIS_HASH: &str = "0000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000";

impl AuditLog {
    /// Open the audit log at `db_path`, using `<db_path>.sentinel` as the
    /// separate checkpoint file. Performs the full R3 startup sequence:
    /// chain integrity verification, then sentinel-vs-chain cross-check,
    /// distinguishing genuine first-run from post-initialization tamper.
    /// Returns `Err` (and the caller MUST treat this as lockdown — no tool
    /// execution) if any check fails.
    pub fn open(db_path: &str) -> Result<Self, AuditError> {
        let sentinel_path = PathBuf::from(format!("{db_path}.sentinel"));
        let db_existed_before_open = Path::new(db_path).exists();

        let conn = Connection::open(db_path)?;
        conn.pragma_update(None, "journal_mode", "WAL")?;
        conn.pragma_update(None, "synchronous", "FULL")?;
        conn.execute_batch(
            "CREATE TABLE IF NOT EXISTS audit_log (
                sequence    INTEGER PRIMARY KEY AUTOINCREMENT,
                ts_unix_ms  INTEGER NOT NULL,
                event_type  TEXT NOT NULL,
                payload     TEXT NOT NULL,
                prev_hash   TEXT NOT NULL,
                hash        TEXT NOT NULL
            );",
        )?;

        let mut log = Self { conn, sentinel_path };

        // Full chain-internal integrity check first: catches tampering,
        // truncation, reordering within whatever DB is actually present.
        log.verify_chain_internal()?;

        let sentinel = log.read_sentinel()?;
        let row_count = log.row_count()?;

        match sentinel {
            None => {
                // No sentinel on disk at all.
                if row_count == 0 && !db_existed_before_open {
                    // Genuine first run: nothing existed before this call.
                    // Nothing to checkpoint yet — the first successful
                    // `record()` call will create the sentinel.
                    Ok(log)
                } else {
                    // Either the DB file already existed with rows but no
                    // sentinel ever got written (should not happen in
                    // normal operation, since `record()` always updates
                    // the sentinel), or the DB existed but empty with no
                    // sentinel — in neither case can we attest this is a
                    // genuine, never-tampered-with genesis.
                    Err(AuditError::DbPresentWithoutSentinel)
                }
            }
            Some(s) if !s.initialized => Err(AuditError::MalformedSentinel(
                "sentinel present but marked uninitialized".to_string(),
            )),
            Some(s) => {
                if row_count == 0 {
                    return Err(AuditError::InitializedButDbMissing);
                }
                // The sentinel claims row `checkpoint_sequence` has hash
                // `checkpoint_hash`. Verify that claim against the
                // (already internally-consistent) current chain.
                let actual_hash = log.hash_at_sequence(s.checkpoint_sequence)?;
                match actual_hash {
                    Some(h) if h == s.checkpoint_hash => Ok(log),
                    Some(h) => Err(AuditError::SentinelMismatch {
                        sentinel_sequence: s.checkpoint_sequence,
                        sentinel_hash: s.checkpoint_hash,
                        actual: h,
                    }),
                    None => Err(AuditError::SentinelMismatch {
                        sentinel_sequence: s.checkpoint_sequence,
                        sentinel_hash: s.checkpoint_hash,
                        actual: "<no such sequence in current database>".to_string(),
                    }),
                }
            }
        }
    }

    fn row_count(&self) -> Result<i64, AuditError> {
        let count: i64 = self
            .conn
            .query_row("SELECT COUNT(*) FROM audit_log", [], |row| row.get(0))?;
        Ok(count)
    }

    fn hash_at_sequence(&self, sequence: i64) -> Result<Option<String>, AuditError> {
        let result: Option<String> = self
            .conn
            .query_row(
                "SELECT hash FROM audit_log WHERE sequence = ?1",
                params![sequence],
                |row| row.get(0),
            )
            .optional()?;
        Ok(result)
    }

    fn read_sentinel(&self) -> Result<Option<Sentinel>, AuditError> {
        if !self.sentinel_path.exists() {
            return Ok(None);
        }
        let bytes = fs::read(&self.sentinel_path)?;
        let sentinel: Sentinel = serde_json::from_slice(&bytes)
            .map_err(|e| AuditError::MalformedSentinel(e.to_string()))?;
        Ok(Some(sentinel))
    }

    /// Durably overwrite the sentinel checkpoint. Uses write-to-temp +
    /// atomic rename so a crash mid-write cannot leave a half-written,
    /// unparseable sentinel that would falsely trigger `MalformedSentinel`
    /// on next start.
    fn write_sentinel(&self, sequence: i64, hash: &str) -> Result<(), AuditError> {
        let sentinel = Sentinel {
            initialized: true,
            checkpoint_sequence: sequence,
            checkpoint_hash: hash.to_string(),
        };
        let tmp_path = self.sentinel_path.with_extension("sentinel.tmp");
        let mut file = fs::File::create(&tmp_path)?;
        file.write_all(serde_json::to_vec(&sentinel).unwrap().as_slice())?;
        file.sync_all()?;
        drop(file);
        fs::rename(&tmp_path, &self.sentinel_path)?;
        Ok(())
    }

    fn last_hash(&self) -> Result<String, AuditError> {
        let result: Option<String> = self
            .conn
            .query_row(
                "SELECT hash FROM audit_log ORDER BY sequence DESC LIMIT 1",
                [],
                |row| row.get(0),
            )
            .optional()?;
        Ok(result.unwrap_or_else(|| GENESIS_HASH.to_string()))
    }

    /// Durably append one event AND update the sentinel checkpoint to
    /// point at it, as a single logical unit. Returns the new row's
    /// sequence number only once BOTH the SQLite commit and the sentinel
    /// write have succeeded. If the sentinel write fails after a
    /// successful SQLite commit, this returns `Err` — per R3, callers
    /// (specifically the authorization-audit call site) MUST treat any
    /// `Err` here as "do not execute", even though the SQLite row itself
    /// is already durably committed at that point; the row existing
    /// without an up-to-date checkpoint is a weaker guarantee than the
    /// invariant requires.
    pub fn record(&mut self, event_type: &str, payload: &str) -> Result<i64, AuditError> {
        let prev_hash = self.last_hash()?;
        let ts_unix_ms = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap_or_default()
            .as_millis() as i64;

        let mut hasher = Sha256::new();
        hasher.update(prev_hash.as_bytes());
        hasher.update(ts_unix_ms.to_le_bytes());
        hasher.update(event_type.as_bytes());
        hasher.update(payload.as_bytes());
        let hash = hex::encode(hasher.finalize());

        let tx = self.conn.transaction()?;
        tx.execute(
            "INSERT INTO audit_log (ts_unix_ms, event_type, payload, prev_hash, hash)
             VALUES (?1, ?2, ?3, ?4, ?5)",
            params![ts_unix_ms, event_type, payload, prev_hash, hash],
        )?;
        let sequence = tx.last_insert_rowid();
        tx.commit()?;

        // Sentinel update is part of the durable-commit invariant for R3:
        // a row that exists in SQLite but isn't yet checkpointed is not
        // considered "durably recorded" for gating purposes.
        self.write_sentinel(sequence, &hash)?;

        Ok(sequence)
    }

    /// Returns the current chain head `(sequence, hash)` as known to the
    /// database right now. Used by the pipeline to maintain its own
    /// in-memory expected-head and detect out-of-band modification
    /// between calls (R3.5, runtime integrity).
    pub fn current_head(&self) -> Result<(i64, String), AuditError> {
        let result: Option<(i64, String)> = self
            .conn
            .query_row(
                "SELECT sequence, hash FROM audit_log ORDER BY sequence DESC LIMIT 1",
                [],
                |row| Ok((row.get(0)?, row.get(1)?)),
            )
            .optional()?;
        Ok(result.unwrap_or((0, GENESIS_HASH.to_string())))
    }

    /// Full internal chain-consistency check: every row's hash matches
    /// what would be recomputed from its predecessor. Does not consult
    /// the sentinel — that cross-check happens separately in `open()`.
    fn verify_chain_internal(&self) -> Result<(), AuditError> {
        let mut stmt = self.conn.prepare(
            "SELECT sequence, ts_unix_ms, event_type, payload, prev_hash, hash
             FROM audit_log ORDER BY sequence ASC",
        )?;
        let rows = stmt.query_map([], |row| {
            Ok((
                row.get::<_, i64>(0)?,
                row.get::<_, i64>(1)?,
                row.get::<_, String>(2)?,
                row.get::<_, String>(3)?,
                row.get::<_, String>(4)?,
                row.get::<_, String>(5)?,
            ))
        })?;

        let mut expected_prev = GENESIS_HASH.to_string();
        for row in rows {
            let (sequence, ts_unix_ms, event_type, payload, prev_hash, hash) = row?;

            if prev_hash != expected_prev {
                return Err(AuditError::ChainBroken {
                    sequence,
                    expected: expected_prev,
                    found: prev_hash,
                });
            }

            let mut hasher = Sha256::new();
            hasher.update(prev_hash.as_bytes());
            hasher.update(ts_unix_ms.to_le_bytes());
            hasher.update(event_type.as_bytes());
            hasher.update(payload.as_bytes());
            let recomputed = hex::encode(hasher.finalize());

            if recomputed != hash {
                return Err(AuditError::ChainBroken {
                    sequence,
                    expected: recomputed,
                    found: hash,
                });
            }

            expected_prev = hash;
        }
        Ok(())
    }

    /// Public wrapper retained for callers/tests that want a plain
    /// integrity check without the sentinel cross-check semantics of
    /// `open()`.
    pub fn verify_chain(&self) -> Result<(), AuditError> {
        self.verify_chain_internal()
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use tempfile::tempdir;

    fn db_path(dir: &Path) -> String {
        dir.join("audit.sqlite3").to_str().unwrap().to_string()
    }

    #[test]
    fn first_run_genesis_succeeds() {
        let dir = tempdir().unwrap();
        let path = db_path(dir.path());
        let log = AuditLog::open(&path);
        assert!(log.is_ok());
    }

    #[test]
    fn appended_events_chain_and_checkpoint_correctly() {
        let dir = tempdir().unwrap();
        let path = db_path(dir.path());
        let mut log = AuditLog::open(&path).unwrap();
        log.record("warden_decision", "a").unwrap();
        log.record("tool_executed", "b").unwrap();
        assert!(log.verify_chain().is_ok());
        assert!(Path::new(&format!("{path}.sentinel")).exists());
    }

    #[test]
    fn reopening_existing_log_continues_the_chain() {
        let dir = tempdir().unwrap();
        let path = db_path(dir.path());
        {
            let mut log = AuditLog::open(&path).unwrap();
            log.record("a", "1").unwrap();
        }
        {
            let mut log = AuditLog::open(&path).unwrap();
            log.record("b", "2").unwrap();
            assert!(log.verify_chain().is_ok());
        }
    }

    #[test]
    fn initialized_db_deleted_causes_lockdown() {
        let dir = tempdir().unwrap();
        let path = db_path(dir.path());
        {
            let mut log = AuditLog::open(&path).unwrap();
            log.record("a", "1").unwrap();
        }
        fs::remove_file(&path).unwrap();
        let result = AuditLog::open(&path);
        assert!(matches!(result, Err(AuditError::InitializedButDbMissing)));
    }

    #[test]
    fn initialized_db_replaced_with_empty_db_causes_lockdown() {
        let dir = tempdir().unwrap();
        let path = db_path(dir.path());
        {
            let mut log = AuditLog::open(&path).unwrap();
            log.record("a", "1").unwrap();
        }
        fs::remove_file(&path).unwrap();
        // Recreate an empty, valid-but-fresh SQLite file at the same path.
        {
            let _ = Connection::open(&path).unwrap();
        }
        let result = AuditLog::open(&path);
        assert!(matches!(result, Err(AuditError::InitializedButDbMissing)));
    }

    #[test]
    fn tampered_payload_is_detected_at_open() {
        let dir = tempdir().unwrap();
        let path = db_path(dir.path());
        {
            let mut log = AuditLog::open(&path).unwrap();
            log.record("warden_decision", "original").unwrap();
            log.conn
                .execute("UPDATE audit_log SET payload = 'tampered' WHERE sequence = 1", [])
                .unwrap();
        }
        let result = AuditLog::open(&path);
        assert!(matches!(result, Err(AuditError::ChainBroken { .. })));
    }

    #[test]
    fn hash_altered_is_detected() {
        let dir = tempdir().unwrap();
        let path = db_path(dir.path());
        {
            let mut log = AuditLog::open(&path).unwrap();
            log.record("a", "1").unwrap();
            log.conn
                .execute("UPDATE audit_log SET hash = 'deadbeef' WHERE sequence = 1", [])
                .unwrap();
        }
        let result = AuditLog::open(&path);
        assert!(matches!(result, Err(AuditError::ChainBroken { .. })));
    }

    #[test]
    fn record_removed_breaks_chain_and_is_detected() {
        let dir = tempdir().unwrap();
        let path = db_path(dir.path());
        {
            let mut log = AuditLog::open(&path).unwrap();
            log.record("a", "1").unwrap();
            log.record("b", "2").unwrap();
            log.conn
                .execute("DELETE FROM audit_log WHERE sequence = 1", [])
                .unwrap();
        }
        // Row 2's prev_hash now points to a hash that no longer exists as
        // row 1's hash (row 1 is gone); the chain no longer starts at
        // GENESIS_HASH for row 2, so internal verification fails.
        let result = AuditLog::open(&path);
        assert!(matches!(result, Err(AuditError::ChainBroken { .. })));
    }

    #[test]
    fn db_present_without_sentinel_is_rejected() {
        let dir = tempdir().unwrap();
        let path = db_path(dir.path());
        {
            let mut log = AuditLog::open(&path).unwrap();
            log.record("a", "1").unwrap();
        }
        // Remove only the sentinel, leaving a perfectly valid, internally
        // consistent DB behind.
        fs::remove_file(format!("{path}.sentinel")).unwrap();
        let result = AuditLog::open(&path);
        assert!(matches!(result, Err(AuditError::DbPresentWithoutSentinel)));
    }

    #[test]
    fn sentinel_mismatch_after_db_rollback_is_detected() {
        let dir = tempdir().unwrap();
        let path = db_path(dir.path());
        let mut log = AuditLog::open(&path).unwrap();
        log.record("a", "1").unwrap();
        log.record("b", "2").unwrap();
        // Simulate an attacker restoring an OLDER backup of the DB (valid
        // internally, but behind what the sentinel has already attested).
        log.conn.execute("DELETE FROM audit_log WHERE sequence = 2", []).unwrap();
        drop(log);
        let result = AuditLog::open(&path);
        assert!(matches!(result, Err(AuditError::SentinelMismatch { .. })));
    }
}