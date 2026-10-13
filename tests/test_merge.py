"""Merge semantics tests.

The properties that make multi-device continuity work:

  * union        — no message is ever lost
  * no dupes     — no message appears twice
  * commutative  — merge(A,B) == merge(B,A)
  * idempotent   — merge(A,A) == A
  * associative  — merge(merge(A,B),C) == merge(A,merge(B,C))
  * deterministic conflicts
  * total order agreed by all nodes
"""

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.environ["ORBITAL_BASE"] = "/tmp/orbtest_state"

from core.statestore import StateStore  # noqa: E402

results = []


def check(name, cond, detail=""):
    results.append((name, bool(cond)))
    print(f"{'PASS' if cond else 'FAIL'}  {name}" + (f"  — {detail}" if detail else ""))


def ids(store):
    return sorted(store.messages)


def make(node, messages):
    s = StateStore(node_id=node)
    for i, (role, text) in enumerate(messages):
        s.add_message(role, text, ts=1000 + i, msg_id=f"{node}-{i}")
    return s


def main():
    # --- divergence: two nodes that talked while apart
    a = make("node-a", [("user", "from a1"), ("assistant", "from a2")])
    b = make("node-b", [("user", "from b1"), ("assistant", "from b2")])

    m1, r1 = a.merge(b)

    check("union keeps every message from both sides",
          len(m1.messages) == 4, f"{len(m1.messages)} messages")
    check("no duplicates",
          len(set(ids(m1))) == len(ids(m1)))
    check("merge does not mutate the inputs",
          len(a.messages) == 2 and len(b.messages) == 2)

    # --- commutativity
    m2, _ = b.merge(a)
    check("commutative: merge(A,B) == merge(B,A)",
          ids(m1) == ids(m2),
          f"{ids(m1)} vs {ids(m2)}")
    check("commutative: identical ordering too",
          [x["id"] for x in m1.ordered_messages()] ==
          [x["id"] for x in m2.ordered_messages()])

    # --- idempotence
    m3, _ = a.merge(a)
    check("idempotent: merge(A,A) == A",
          ids(m3) == ids(a), f"{len(m3.messages)} vs {len(a.messages)}")

    # --- associativity
    c = make("node-c", [("user", "from c1")])
    left, _ = a.merge(b)
    left, _ = left.merge(c)
    right, _ = b.merge(c)
    right, _ = a.merge(right)
    check("associative: merge(merge(A,B),C) == merge(A,merge(B,C))",
          ids(left) == ids(right) and len(left.messages) == len(right.messages),
          f"{len(left.messages)} vs {len(right.messages)}")

    # --- ordering is agreed
    check("all nodes agree on the message order",
          [x["id"] for x in left.ordered_messages()] ==
          [x["id"] for x in right.ordered_messages()])

    # --- lamport clock advances past both
    check("merged clock is ahead of both inputs",
          m1.clock > max(a.clock, b.clock),
          f"{m1.clock} > max({a.clock},{b.clock})")

    # --- same id, different content: deterministic, and reported
    x = StateStore(node_id="x")
    x.add_message("user", "version one", ts=100, msg_id="dup", origin="x")
    y = StateStore(node_id="y")
    y.add_message("user", "version two", ts=200, msg_id="dup", origin="y")

    xy, rxy = x.merge(y)
    yx, ryx = y.merge(x)
    check("id collision resolves to one message",
          len(xy.messages) == 1, f"{len(xy.messages)}")
    check("id collision resolves the same way both directions",
          xy.messages["dup"]["content"] == yx.messages["dup"]["content"],
          f"{xy.messages['dup']['content']!r} vs {yx.messages['dup']['content']!r}")
    check("id collision is reported, not hidden",
          len(rxy["conflicts"]) == 1 and rxy["conflicts"][0]["type"] == "message_id_collision",
          str(rxy["conflicts"]))
    check("conflict keeps the newer content",
          xy.messages["dup"]["content"] == "version two",
          xy.messages["dup"]["content"])

    # --- attention: last write wins
    p = StateStore(node_id="p")
    p.set_attention("topic", "orbital")
    q = StateStore(node_id="q")
    q.attention["topic"] = {"value": "something else", "ts": p.attention["topic"]["ts"] + 50,
                            "origin": "q", "lamport": 99}
    pq, _ = p.merge(q)
    qp, _ = q.merge(p)
    check("attention resolves last-write-wins",
          pq.attention_value("topic") == "something else",
          str(pq.attention_value("topic")))
    check("attention resolves identically both directions",
          pq.attention_value("topic") == qp.attention_value("topic"))

    # --- attention keys are unioned
    p.set_attention("only_in_p", 1)
    q.set_attention("only_in_q", 2)
    pq2, _ = p.merge(q)
    check("attention keys are unioned",
          "only_in_p" in pq2.attention and "only_in_q" in pq2.attention,
          str(sorted(pq2.attention)))

    # --- logs dedupe
    g = StateStore(node_id="g")
    g.add_log("INFO", "shared line")
    h = StateStore(node_id="g")  # same origin, same content
    h.logs = list(g.logs)
    gh, _ = g.merge(h)
    check("identical log lines are deduplicated",
          len(gh.logs) == 1, f"{len(gh.logs)} lines")

    # --- absorbing a round-tripped image is idempotent
    import core.oostate as oostate

    blob = oostate.pack(m1.to_dict())
    restored = StateStore.from_dict(oostate.unpack(blob)[0])
    again, _ = m1.merge(restored)
    check("merging a round-tripped copy changes nothing",
          ids(again) == ids(m1), f"{len(again.messages)} vs {len(m1.messages)}")

    # --- empty merge
    empty = StateStore(node_id="empty")
    em, _ = m1.merge(empty)
    check("merging with an empty store is a no-op",
          ids(em) == ids(m1))

    passed = sum(1 for _, ok in results if ok)
    print(f"\n{passed}/{len(results)} checks passed")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
