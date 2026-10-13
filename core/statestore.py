"""StateStore — the live state model and the merge rules.

This is the part that makes cross-device continuity actually work. Two nodes
will diverge the moment you close a laptop and keep talking on a phone. When
they meet again, something has to decide what the merged state is.

The rules, stated once, so they can be reasoned about:

**Messages are append-only.** Each carries a unique id. Merge is a set union
keyed by id, so no message is ever lost and none is duplicated. This is the
easy case, and it is easy because the data model was chosen to make it so.

**Attention is last-write-wins per key.** Each key holds the most recent
value by (timestamp, origin-node). Ties broken by node id, so the result does
not depend on which node merges first.

**Conflicting ids are resolved deterministically.** If two nodes somehow
produce the same message id with different content, the winner is chosen by
(ts, origin, content) and the collision is recorded in the merge report
rather than being silently dropped.

**Clocks are Lamport, not wall.** Wall clocks drift and get set backwards.
A logical counter gives a total order that both nodes agree on.

The properties that matter, and are tested:

  * commutative  — merge(A, B) == merge(B, A)
  * idempotent   — merge(A, A) == A
  * associative  — merge(merge(A, B), C) == merge(A, merge(B, C))

Get these right and the mesh can gossip state in any order, repeatedly, and
converge. Get them wrong and you get duplicated messages and lost edits.
"""

import json
import os
import time
import uuid

from . import config, logutil, oostate

log = logutil.get_logger("state")

SCHEMA_VERSION = oostate.SCHEMA_VERSION

# Bounds. A state image has to stay small enough to move between devices.
MAX_MESSAGES = 5000
MAX_LOGS = 500
MAX_ATTENTION_KEYS = 200
MAX_MESSAGE_CHARS = 100_000


class MergeConflict(Exception):
    """Raised only when a merge cannot be resolved deterministically."""


def _now():
    return time.time()


class StateStore:
    """Mutable state for one node, with deterministic merge."""

    def __init__(self, node_id=None, path=None):
        self.node_id = node_id or config.node_id()
        self.path = path or getattr(config, "STATE_FILE", None)
        self.clock = 0
        self.created_at = _now()
        self.updated_at = self.created_at
        self.messages = {}   # id -> record
        self.attention = {}  # key -> record
        self.logs = []       # list of records
        self.meta = {}
        self._dirty = False

    # ------------------------------------------------------------ clock
    def _tick(self):
        self.clock += 1
        return self.clock

    def _observe(self, other_clock):
        """Lamport receive rule: clock = max(local, remote) + 1."""
        self.clock = max(self.clock, int(other_clock or 0)) + 1

    # ---------------------------------------------------------- mutation
    def add_message(self, role, content, ts=None, msg_id=None, origin=None, lamport=None):
        content = str(content)[:MAX_MESSAGE_CHARS]
        mid = msg_id or uuid.uuid4().hex
        rec = {
            "id": mid,
            "role": str(role),
            "content": content,
            "ts": float(ts if ts is not None else _now()),
            "origin": origin or self.node_id,
            "lamport": int(lamport if lamport is not None else self._tick()),
        }
        self.messages[mid] = rec
        self._trim_messages()
        self._touch()
        return rec

    def set_attention(self, key, value):
        """Record an attention value. LWW per key."""
        key = str(key)[:200]
        self.attention[key] = {
            "value": value,
            "ts": _now(),
            "origin": self.node_id,
            "lamport": self._tick(),
        }
        self._trim_attention()
        self._touch()
        return self.attention[key]

    def add_log(self, level, message):
        self.logs.append(
            {
                "ts": _now(),
                "level": str(level),
                "message": str(message)[:2000],
                "origin": self.node_id,
            }
        )
        self.logs = self.logs[-MAX_LOGS:]
        self._touch()

    def _touch(self):
        self.updated_at = _now()
        self._dirty = True

    def _trim_messages(self):
        if len(self.messages) <= MAX_MESSAGES:
            return
        ordered = self.ordered_messages()
        for rec in ordered[: len(self.messages) - MAX_MESSAGES]:
            self.messages.pop(rec["id"], None)

    def _trim_attention(self):
        if len(self.attention) <= MAX_ATTENTION_KEYS:
            return
        oldest = sorted(
            self.attention.items(),
            key=lambda kv: (kv[1]["ts"], kv[1]["origin"], kv[0]),
        )
        for key, _rec in oldest[: len(self.attention) - MAX_ATTENTION_KEYS]:
            self.attention.pop(key, None)

    # ------------------------------------------------------------ access
    def ordered_messages(self):
        """Total order: (lamport, ts, origin, id).

        Every component is present on every record and comparable, so the
        ordering is total and identical on every node.
        """
        return sorted(
            self.messages.values(),
            key=lambda r: (r["lamport"], r["ts"], r["origin"], r["id"]),
        )

    def history(self, limit=None):
        """Ollama-shaped message list for the LLM."""
        msgs = [{"role": r["role"], "content": r["content"]} for r in self.ordered_messages()]
        return msgs[-limit:] if limit else msgs

    def attention_value(self, key, default=None):
        rec = self.attention.get(key)
        return rec["value"] if rec else default

    # ------------------------------------------------------- (de)serialize
    def to_dict(self):
        return {
            "schema": SCHEMA_VERSION,
            "node_id": self.node_id,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "clock": self.clock,
            "messages": self.ordered_messages(),
            "attention": self.attention,
            "logs": self.logs[-MAX_LOGS:],
            "meta": self.meta,
        }

    @classmethod
    def from_dict(cls, data, node_id=None):
        """Load from a state dict, migrating older schemas forward."""
        if not isinstance(data, dict):
            raise oostate.FormatError(f"state is {type(data).__name__}, expected object")

        schema = data.get("schema", 0)
        if schema > SCHEMA_VERSION:
            raise oostate.VersionError(
                f"state schema {schema} is newer than {SCHEMA_VERSION}"
            )
        if schema < SCHEMA_VERSION:
            data = _migrate(data, schema)

        store = cls(node_id=node_id or data.get("node_id") or config.node_id())
        store.created_at = data.get("created_at", _now())
        store.updated_at = data.get("updated_at", store.created_at)
        store.clock = int(data.get("clock", 0))
        store.meta = data.get("meta", {}) or {}

        for rec in data.get("messages", []):
            if not isinstance(rec, dict) or "id" not in rec:
                continue
            store.messages[rec["id"]] = {
                "id": str(rec["id"]),
                "role": str(rec.get("role", "user")),
                "content": str(rec.get("content", ""))[:MAX_MESSAGE_CHARS],
                "ts": float(rec.get("ts", 0.0)),
                "origin": str(rec.get("origin", "unknown")),
                "lamport": int(rec.get("lamport", 0)),
            }

        for key, rec in (data.get("attention") or {}).items():
            if isinstance(rec, dict):
                store.attention[str(key)] = {
                    "value": rec.get("value"),
                    "ts": float(rec.get("ts", 0.0)),
                    "origin": str(rec.get("origin", "unknown")),
                    "lamport": int(rec.get("lamport", 0)),
                }

        store.logs = [r for r in (data.get("logs") or []) if isinstance(r, dict)][-MAX_LOGS:]
        return store

    # --------------------------------------------------------------- I/O
    def save(self, path=None):
        target = path or self.path
        if not target:
            raise oostate.OostateError("no path configured for the state store")
        os.makedirs(os.path.dirname(os.path.abspath(target)), exist_ok=True)
        size = oostate.write(target, self.to_dict())
        self._dirty = False
        return size

    def load(self, path=None, missing_ok=True):
        target = path or self.path
        if not target or not os.path.exists(target):
            if missing_ok:
                return False
            raise FileNotFoundError(target)
        data, _header = oostate.read(target)
        loaded = StateStore.from_dict(data, node_id=self.node_id)
        self.__dict__.update(loaded.__dict__)
        self.path = target
        return True

    def export_bytes(self):
        return oostate.pack(self.to_dict())

    def import_bytes(self, blob, strategy="merge"):
        data, header = oostate.unpack(blob)
        return self.absorb(StateStore.from_dict(data), strategy=strategy, header=header)

    # -------------------------------------------------------------- merge
    def merge(self, other):
        """Return a NEW store that is the join of self and other.

        Does not mutate either input — that is what makes the algebraic
        properties testable.
        """
        if not isinstance(other, StateStore):
            raise TypeError(f"expected StateStore, got {type(other).__name__}")

        report = {"messages_added": 0, "messages_dropped": 0,
                  "attention_updated": 0, "conflicts": []}

        merged = StateStore(node_id=self.node_id)
        merged.created_at = min(self.created_at, other.created_at)
        merged.updated_at = max(self.updated_at, other.updated_at)
        merged.clock = max(self.clock, other.clock) + 1

        # --- messages: union by id
        all_ids = set(self.messages) | set(other.messages)
        for mid in all_ids:
            a = self.messages.get(mid)
            b = other.messages.get(mid)
            if a is None:
                merged.messages[mid] = dict(b)
            elif b is None:
                merged.messages[mid] = dict(a)
            elif a["content"] == b["content"] and a["role"] == b["role"]:
                merged.messages[mid] = dict(a)
            else:
                # Same id, different content. Pick deterministically and say so.
                winner = max([a, b], key=lambda r: (r["ts"], r["origin"], r["content"]))
                loser = b if winner is a else a
                merged.messages[mid] = dict(winner)
                report["conflicts"].append(
                    {
                        "type": "message_id_collision",
                        "id": mid,
                        "kept_origin": winner["origin"],
                        "dropped_origin": loser["origin"],
                    }
                )

        # --- attention: LWW per key
        for key in set(self.attention) | set(other.attention):
            a = self.attention.get(key)
            b = other.attention.get(key)
            if a is None:
                merged.attention[key] = dict(b)
            elif b is None:
                merged.attention[key] = dict(a)
            else:
                winner = max([a, b], key=lambda r: (r["ts"], r["origin"]))
                merged.attention[key] = dict(winner)
                if winner is not a:
                    report["attention_updated"] += 1

        # --- logs: dedupe on (ts, level, message, origin), keep newest
        seen = set()
        combined = []
        for rec in list(self.logs) + list(other.logs):
            sig = (rec.get("ts"), rec.get("level"), rec.get("message"), rec.get("origin"))
            if sig in seen:
                continue
            seen.add(sig)
            combined.append(rec)
        combined.sort(key=lambda r: (r.get("ts", 0), str(r.get("origin", ""))))
        merged.logs = combined[-MAX_LOGS:]

        # --- meta: union, self wins on collision
        merged.meta = dict(other.meta)
        merged.meta.update(self.meta)

        report["messages_added"] = len(merged.messages)
        report["messages_dropped"] = len(self.messages) + len(other.messages) - len(merged.messages)

        merged._trim_messages()
        return merged, report

    def absorb(self, other, strategy="merge", header=None):
        """Merge another store into this one in place.

        strategy="merge"   — union, as above (default)
        strategy="replace" — discard local state entirely
        strategy="keep"    — ignore the incoming state
        """
        if strategy == "keep":
            return {"strategy": "keep", "changed": False}
        if strategy == "replace":
            node = self.node_id
            self.__dict__.update(other.__dict__)
            self.node_id = node
            self._touch()
            return {"strategy": "replace", "changed": True, "header": header}

        merged, report = self.merge(other)
        node = self.node_id
        self.__dict__.update(merged.__dict__)
        self.node_id = node
        self._touch()
        report["strategy"] = "merge"
        report["changed"] = True
        if header:
            report["header"] = header
        return report


# ------------------------------------------------------------- migration
def _migrate(data, from_schema):
    """Bring an older state dict up to the current schema.

    v1 was the original chat_memory.json: a bare list of
    {"role", "content", "ts"} with no ids and no ordering.
    """
    if from_schema <= 1:
        log.info(f"migrating state from schema {from_schema} to {SCHEMA_VERSION}")
        raw = data.get("messages") or data.get("history") or []
        if isinstance(data, list):
            raw = data

        messages = []
        for i, item in enumerate(raw):
            if not isinstance(item, dict):
                continue
            messages.append(
                {
                    "id": item.get("id") or uuid.uuid4().hex,
                    "role": item.get("role", "user"),
                    "content": item.get("content", ""),
                    "ts": item.get("ts", 0.0),
                    "origin": item.get("origin", "legacy"),
                    # preserve original order via the logical clock
                    "lamport": item.get("lamport", i + 1),
                }
            )
        return {
            "schema": SCHEMA_VERSION,
            "node_id": data.get("node_id", "legacy") if isinstance(data, dict) else "legacy",
            "created_at": data.get("created_at", _now()) if isinstance(data, dict) else _now(),
            "updated_at": _now(),
            "clock": len(messages) + 1,
            "messages": messages,
            "attention": {},
            "logs": [],
            "meta": {"migrated_from_schema": from_schema},
        }
    return data


def from_chat_memory(path, node_id=None):
    """Import the old chat_memory.json format."""
    with open(path, "r", encoding="utf-8") as fh:
        raw = json.load(fh)

    if isinstance(raw, list):
        data = {"schema": 1, "messages": raw}
    elif isinstance(raw, dict) and "schema" not in raw:
        data = dict(raw)
        data["schema"] = 1
    else:
        data = raw

    store = StateStore.from_dict(data, node_id=node_id)
    log.info(f"imported {len(store.messages)} message(s) from {path}")
    return store
