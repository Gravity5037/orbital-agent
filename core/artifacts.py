"""Artifact registry — every model, LoRA and dataset, with its lineage.

This is the backbone of the accumulation loop. A "self-growing" system needs
to remember what it made, what it made it from, and how it scored. Without
that you cannot reproduce anything, cannot tell improvement from noise, and
cannot roll back a bad generation.

Every artifact records:

    id          stable identifier
    kind        base | lora | merged | dataset | embedding
    path        where the file lives
    parents     ids of what produced it (empty for downloaded models)
    method      how it was made: downloaded | merged | trained | curated
    config      the exact parameters used
    metrics     scores, if it has been evaluated
    created     when

Provenance is a DAG, not a tree. A merge has several parents; a LoRA has a
base model and a dataset; a dataset has many source generations. That graph
is the thing that makes the whole system auditable — you can always ask
"where did this come from" and get a real answer.

Nothing here trains anything. It records what was trained, merged or
curated, and by which recipe, so the recipes are reproducible.
"""

import json
import os
import time
import uuid

from . import config, logutil

log = logutil.get_logger("artifacts")

REGISTRY_FILE = os.path.join(config.STATE_DIR, "artifacts.json")

KINDS = ("base", "lora", "merged", "dataset", "embedding")
METHODS = ("downloaded", "merged", "trained", "curated", "imported")


class ArtifactError(Exception):
    """Base class for registry problems."""


class NotFound(ArtifactError):
    pass


class Duplicate(ArtifactError):
    pass


class CycleError(ArtifactError):
    """A lineage link would create a cycle — the graph must stay a DAG."""


class Registry:
    """Persistent record of every model artifact and how it was made."""

    def __init__(self, path=None):
        self.path = path or REGISTRY_FILE
        self.artifacts = {}
        self._loaded = False

    # ------------------------------------------------------------- storage
    def load(self, missing_ok=True):
        if not os.path.exists(self.path):
            if not missing_ok:
                raise FileNotFoundError(self.path)
            self._loaded = True
            return False
        try:
            with open(self.path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            self.artifacts = data.get("artifacts", {}) if isinstance(data, dict) else {}
            log.info(f"loaded {len(self.artifacts)} artifact(s) from {self.path}")
            self._loaded = True
            return True
        except (OSError, json.JSONDecodeError) as exc:
            raise ArtifactError(f"registry unreadable: {exc}") from exc

    def save(self):
        config.ensure_dirs()
        payload = {
            "version": 1,
            "saved_at": time.time(),
            "artifacts": self.artifacts,
        }
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2, sort_keys=True)
        os.replace(tmp, self.path)
        return len(self.artifacts)

    def _ensure_loaded(self):
        if not self._loaded:
            self.load()

    # --------------------------------------------------------------- CRUD
    def add(
        self,
        name,
        kind,
        path="",
        parents=None,
        method="downloaded",
        config_data=None,
        metrics=None,
        notes="",
        artifact_id=None,
    ):
        """Register an artifact. Returns its id."""
        self._ensure_loaded()

        if kind not in KINDS:
            raise ArtifactError(f"unknown kind '{kind}'; expected one of {KINDS}")
        if method not in METHODS:
            raise ArtifactError(f"unknown method '{method}'; expected one of {METHODS}")

        parents = list(parents or [])
        for p in parents:
            if p not in self.artifacts:
                raise NotFound(f"parent '{p}' is not registered")
            if self._would_cycle(p, artifact_id):
                raise CycleError(f"linking {p} would create a cycle")

        aid = artifact_id or uuid.uuid4().hex[:12]
        if aid in self.artifacts:
            raise Duplicate(f"artifact '{aid}' already exists")

        self.artifacts[aid] = {
            "id": aid,
            "name": name,
            "kind": kind,
            "path": path,
            "parents": parents,
            "method": method,
            "config": config_data or {},
            "metrics": metrics or {},
            "notes": notes,
            "created": time.time(),
        }
        log.info(f"registered {kind} '{name}' ({aid}) via {method}")
        return aid

    def _would_cycle(self, parent_id, child_id):
        """Walk up from parent; if we reach child_id, the link is a cycle."""
        if not child_id:
            return False
        seen = set()
        stack = [parent_id]
        while stack:
            current = stack.pop()
            if current == child_id:
                return True
            if current in seen:
                continue
            seen.add(current)
            rec = self.artifacts.get(current)
            if rec:
                stack.extend(rec.get("parents", []))
        return False

    def get(self, artifact_id):
        self._ensure_loaded()
        rec = self.artifacts.get(artifact_id)
        if not rec:
            raise NotFound(f"no artifact '{artifact_id}'")
        return rec

    def find(self, name=None, kind=None, method=None):
        """Search by name substring and/or exact kind/method."""
        self._ensure_loaded()
        out = []
        for rec in self.artifacts.values():
            if kind and rec["kind"] != kind:
                continue
            if method and rec["method"] != method:
                continue
            if name and name.lower() not in rec["name"].lower():
                continue
            out.append(rec)
        return sorted(out, key=lambda r: r["created"], reverse=True)

    def update(self, artifact_id, **fields):
        self._ensure_loaded()
        rec = self.get(artifact_id)
        for key in ("name", "path", "notes"):
            if key in fields:
                rec[key] = fields[key]
        if "metrics" in fields:
            rec["metrics"] = dict(fields["metrics"])
        if "config" in fields:
            rec["config"] = dict(fields["config"])
        log.info(f"updated artifact {artifact_id}")
        return rec

    def remove(self, artifact_id, force=False):
        """Remove an artifact. Refuses if something depends on it."""
        self._ensure_loaded()
        rec = self.get(artifact_id)

        children = [r for r in self.artifacts.values()
                    if artifact_id in r.get("parents", [])]
        if children and not force:
            names = ", ".join(f"{c['name']} ({c['id']})" for c in children)
            raise ArtifactError(
                f"'{rec['name']}' has {len(children)} descendant(s): {names}. "
                f"Use force=True to remove anyway."
            )

        del self.artifacts[artifact_id]
        if force:
            for child in children:
                child["parents"] = [p for p in child["parents"] if p != artifact_id]
        log.info(f"removed artifact {artifact_id}")
        return rec

    # ------------------------------------------------------------ lineage
    def ancestors(self, artifact_id, depth=None):
        """Everything this artifact descends from, nearest first."""
        self._ensure_loaded()
        self.get(artifact_id)

        seen = set()
        order = []
        frontier = [(artifact_id, 0)]

        while frontier:
            current, level = frontier.pop(0)
            if depth is not None and level >= depth:
                continue
            rec = self.artifacts.get(current)
            if not rec:
                continue
            for parent in rec.get("parents", []):
                if parent in seen:
                    continue
                seen.add(parent)
                order.append((parent, level + 1))
                frontier.append((parent, level + 1))

        return [
            {"id": pid, "depth": lvl, **self.artifacts[pid]}
            for pid, lvl in order
        ]

    def descendants(self, artifact_id):
        """Everything built from this artifact."""
        self._ensure_loaded()
        self.get(artifact_id)
        out = []
        for rec in self.artifacts.values():
            if artifact_id in rec.get("parents", []):
                out.append(rec)
                out.extend(self.descendants(rec["id"]))
        return out

    def lineage_tree(self, artifact_id, indent=0):
        """Human-readable ancestry, as lines."""
        self._ensure_loaded()
        rec = self.artifacts.get(artifact_id)
        if not rec:
            return [(" " * indent) + f"<missing {artifact_id}>"]

        lines = [
            (" " * indent)
            + f"{rec['name']} [{rec['kind']}/{rec['method']}] ({rec['id']})"
        ]
        for parent in rec.get("parents", []):
            lines.extend(self.lineage_tree(parent, indent + 2))
        return lines

    def roots(self):
        """Artifacts with no parents — the downloaded bases."""
        self._ensure_loaded()
        return [r for r in self.artifacts.values() if not r.get("parents")]

    def stats(self):
        self._ensure_loaded()
        by_kind = {}
        by_method = {}
        for rec in self.artifacts.values():
            by_kind[rec["kind"]] = by_kind.get(rec["kind"], 0) + 1
            by_method[rec["method"]] = by_method.get(rec["method"], 0) + 1
        return {
            "total": len(self.artifacts),
            "by_kind": by_kind,
            "by_method": by_method,
            "roots": len(self.roots()),
        }


# ------------------------------------------------------------- singleton
_REGISTRY = None


def registry():
    global _REGISTRY
    if _REGISTRY is None:
        _REGISTRY = Registry()
        _REGISTRY.load()
    return _REGISTRY
