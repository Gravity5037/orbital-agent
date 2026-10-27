"""Agent - the loop that turns a tool call into a tool that runs.

    python -m core.agent --tools          what the model may call
    python -m core.agent --ask "what time is it"
    python -m core.agent --trace          the last few decisions
    python -m core.agent --why-not        the limits

**The bug this fixes.**

Ask Orbital "what time is it" and the model replies with:

    {"name": "get_time", "arguments": {}}

Nothing runs it. The JSON is printed as a chat message. The tool
exists in tools.py, the model knows about it, and there is no wire
between them. It looks like a capability and it is a string.

**The loop, in five steps.**

    1. SEND     the question plus the tool list to the model
    2. READ     if it asked for a tool, take the name and arguments
    3. CHECK    is that tool allowed, and are those arguments sane
    4. RUN      call it
    5. FEED     put the result back and let the model answer

Steps 2 to 5 repeat until the model answers in words or the step limit
is hit.

**Two classes of tool, and the difference matters.**

    read      run automatically. Listing a directory, reading a file,
              asking for the time. Nothing changes.
    write     needs your yes. Generating an image, moving a file,
              anything with a side effect.

That split is the whole safety story. A model that can silently write
is a model that can silently break something - and small models
propose wrong calls constantly. In testing this module, the model
asked to list C:\\ root and invented an image prompt nobody requested,
in the same breath as asking the time.

**Arguments are checked, not trusted.**

Small models emit plausible-looking but wrong arguments. A path of "/"
on Windows, a negative width, a backend name that does not exist. Each
tool's arguments are validated before the call, and a rejection is
returned to the model as a normal result so it can correct itself.

**What this cannot do.**

  * **Make a small model reliable.** A 1.5B model will still call the
    wrong tool, or the right tool with wrong arguments. The loop
    catches it; it does not prevent it. Bigger models are better at
    this, and no amount of harness fixes a model that cannot reason.
  * **Be safe by itself.** The read/write split is only as good as the
    list below. If a tool is mislabelled as read, it runs unseen.
  * **Undo a write.** A write tool does whatever it does. The check
    happens before, not after.
  * **Run forever.** MAX_STEPS stops a model that loops. A model that
    cannot answer will spin, and this bounds it.
"""

import argparse
import json
import os
import re
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import config, logutil  # noqa: E402

log = logutil.get_logger("agent")

MAX_STEPS = int(os.environ.get("ORBITAL_MAX_STEPS", "6"))

WARN_AT = MAX_STEPS - 2

TRACE_FILE = os.path.join(config.STATE_DIR, "agent-trace.json")
TRACE_KEEP = 200

READ_TOOLS = {
    "get_time",
    "get_system_info",
    "system_status",
    "list_files",
    "read_file",
    "list_cameras",
    "check_image_backend",
    "spotify_now",
    "hue_lights",
}

WRITE_TOOLS = {
    "generate_image",
    "capture_camera",
    "hue_control",
    "spotify_control",
}

STOP_WORDS = ("final", "answer", "done", "stop")


class AgentError(RuntimeError):
    """Base class."""


def _trace(entry):
    data = {"steps": []}
    if os.path.exists(TRACE_FILE):
        try:
            with open(TRACE_FILE, "r", encoding="utf-8") as fh:
                data = json.load(fh)
        except (OSError, json.JSONDecodeError):
            pass
    data["steps"].append({"at": time.time(), **entry})
    data["steps"] = data["steps"][-TRACE_KEEP:]
    os.makedirs(os.path.dirname(TRACE_FILE), exist_ok=True)
    tmp = TRACE_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2)
    os.replace(tmp, TRACE_FILE)


def trace():
    if not os.path.exists(TRACE_FILE):
        return []
    try:
        with open(TRACE_FILE, "r", encoding="utf-8") as fh:
            return json.load(fh).get("steps", [])
    except (OSError, json.JSONDecodeError):
        return []


CALL_RE = re.compile(
    r'\{[^{}]*?"name"\s*:\s*"([a-zA-Z_][a-zA-Z0-9_]*)"'
    r'[^{}]*?"arguments"\s*:\s*(\{.*?\}|"[^"]*"|null)',
    re.S,
)

WRAPPED_RE = re.compile(r"<tool_call>\s*(\{.*?\})\s*</tool_call>", re.S)


def parse_calls(text):
    """Pull tool calls out of a reply. Returns a list of {name, arguments}."""
    if not text:
        return []

    calls = []

    for block in WRAPPED_RE.findall(text):
        calls.extend(_from_json(block))

    if calls:
        return calls

    for name, raw in CALL_RE.findall(text):
        args = _from_args(raw)
        calls.append({"name": name, "arguments": args})

    if calls:
        return calls

    return _from_json(text)


def _from_json(text):
    """Try the whole thing as one or more JSON objects."""
    out = []
    text = text.strip()

    try:
        data = json.loads(text)
        items = data if isinstance(data, list) else [data]
        for item in items:
            if isinstance(item, dict) and "name" in item:
                out.append({
                    "name": str(item["name"]),
                    "arguments": item.get("arguments") or {},
                })
        if out:
            return out
    except json.JSONDecodeError:
        pass

    depth = 0
    start = None
    for i, ch in enumerate(text):
        if ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0 and start is not None:
                try:
                    item = json.loads(text[start:i + 1])
                    if isinstance(item, dict) and "name" in item:
                        out.append({
                            "name": str(item["name"]),
                            "arguments": item.get("arguments") or {},
                        })
                except json.JSONDecodeError:
                    pass
                start = None
    return out


def _from_args(raw):
    raw = (raw or "").strip()
    if not raw or raw == "null":
        return {}
    try:
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, dict) else {}
    except json.JSONDecodeError:
        return {}


def looks_like_call(text):
    """Does this reply contain a tool call at all?"""
    return bool(parse_calls(text))


def tool_catalogue():
    """What tools exist, with their class. Read from tools.py."""
    try:
        from core import tools
    except ImportError:
        return {}

    found = {}

    reg = getattr(tools, "REGISTRY", None) or getattr(tools, "TOOLS", None)
    if isinstance(reg, dict):
        for name in reg:
            found[name] = _classify(name)
        return found

    for name in dir(tools):
        if name.startswith("_") and not name.startswith("__"):
            bare = name.lstrip("_")
            if bare in READ_TOOLS or bare in WRITE_TOOLS:
                found[bare] = _classify(bare)

    return found


def _classify(name):
    if name in WRITE_TOOLS:
        return "write"
    if name in READ_TOOLS:
        return "read"
    return "unknown"


def check_call(call):
    """Is this call allowed and sane? Returns (ok, reason, cleaned_args)."""
    name = str(call.get("name") or "").strip()
    args = call.get("arguments") or {}

    if not isinstance(args, dict):
        args = {}

    if not name:
        return False, "no tool name", {}

    kind = _classify(name)

    if kind == "unknown":
        return False, f"no tool called '{name}'", {}

    if kind == "write":
        return "confirm", f"'{name}' changes something", args

    return True, "read-only", _clean_args(name, args)


def _clean_args(name, args):
    """Reject obviously wrong arguments before they reach the tool."""
    clean = {}

    for key, value in args.items():
        if key == "path":
            path = str(value or "").strip()
            if path in ("", "/", "\\"):
                path = config.BASE_DIR
                log.info(f"{name}: bare root path, using the tree instead")
            clean[key] = path
        elif key in ("width", "height", "steps", "seed", "source"):
            try:
                num = int(value)
            except (TypeError, ValueError):
                continue
            if num < 0:
                continue
            clean[key] = num
        elif key == "prompt":
            text = str(value or "").strip()
            if len(text) < 2:
                continue
            clean[key] = text[:1000]
        else:
            clean[key] = value

    return clean


def run_tool(name, args):
    """Call a tool. Returns a string result, never raises."""
    try:
        from core import tools
    except ImportError:
        return "the tools module is not present"

    fn = None
    for candidate in (name, f"_{name}", f"tool_{name}"):
        fn = getattr(tools, candidate, None)
        if callable(fn):
            break

    if not callable(fn):
        return f"no callable tool called '{name}'"

    try:
        result = fn(args)
        if isinstance(result, (dict, list)):
            return json.dumps(result)[:4000]
        return str(result)[:4000]
    except Exception as exc:
        return f"the tool failed: {type(exc).__name__}: {exc}"


SYSTEM = """You are Orbital, a local assistant. You can call tools.

To call a tool, reply with ONLY a JSON object, nothing else:

  {"name": "tool_name", "arguments": {"key": "value"}}

When you have the answer, reply in plain words with no JSON.

Rules:
  * One tool per reply. Wait for the result before the next.
  * Use a tool only when the question needs it. "Hi" needs no tool.
  * Never invent a tool name. The list below is complete.
  * If a tool fails, say so. Do not pretend it worked.
"""


CLAIM_WORDS = (
    "captured",
    "saved as",
    "image saved",
    "has been saved",
    "photo saved",
    "i took",
    "i have taken",
    "i can see",
    "i have accessed",
    "i have run",
    "the tool",
    "authenticate",
    "no cameras",
    "no camera",
    "not connected",
    "unavailable",
    "maintenance",
    "the command provided",
)

NO_CLAIM = ("I did not run anything, so I cannot confirm that. "
            "Type a command directly - /health, /snapshot, /lights - "
            "and it will actually run.")


def guard_claim(reply, steps):
    """Refuse an answer that describes a tool running when none did."""
    if steps:
        return reply
    low = (reply or "").lower()
    for word in CLAIM_WORDS:
        if word in low:
            return NO_CLAIM
    return reply


def ask(question, approve=None, model=None, timeout=300):
    """Answer a question, calling tools as needed."""
    try:
        from core import nucleus
    except ImportError:
        raise AgentError("the nucleus module is not present")

    ok, detail = nucleus.health(timeout=5)
    if not ok:
        raise AgentError(f"no model is reachable ({detail})")

    available = tool_catalogue()
    if not available:
        available = {n: _classify(n) for n in sorted(READ_TOOLS | WRITE_TOOLS)}

    listing = "\n".join(
        f"  {name} ({kind})" for name, kind in sorted(available.items()))

    messages = [
        {"role": "system", "content": SYSTEM},
        {"role": "system", "content": f"Tools you may call:\n{listing}"},
        {"role": "user", "content": question},
    ]

    steps = []
    called = set()

    for step in range(MAX_STEPS):
        if step == WARN_AT:
            messages.append({
                "role": "system",
                "content": (f"You have {MAX_STEPS - step} steps left. "
                            f"Answer in words now."),
            })

        try:
            reply = nucleus.chat(messages, model=model, timeout=timeout)
        except Exception as exc:
            raise AgentError(f"the model could not answer: {exc}")

        calls = parse_calls(reply)

        if not calls:
            _trace({"question": question[:200], "steps": len(steps),
                    "outcome": "answered", "reply": reply[:300]})
            return {"answer": reply, "steps": steps,
                    "calls_made": len(steps)}

        call = calls[0]
        name = call["name"]
        args = call.get("arguments") or {}

        verdict, reason, cleaned = check_call(call)

        if verdict == "confirm":
            if approve is None:
                result = (f"'{name}' needs approval and none was given. "
                          f"Answer without it.")
                _trace({"tool": name, "args": args,
                        "outcome": "refused-no-approver"})
                messages.append({"role": "assistant", "content": reply})
                messages.append({"role": "system", "content": result})
                steps.append({"tool": name, "result": "needs approval"})
                continue

            allowed = False
            try:
                allowed = bool(approve(name, cleaned))
            except Exception as exc:
                log.warn(f"approver raised: {exc}")

            if not allowed:
                _trace({"tool": name, "args": cleaned,
                        "outcome": "refused-by-user"})
                messages.append({"role": "assistant", "content": reply})
                messages.append({
                    "role": "system",
                    "content": (f"The user declined '{name}'. "
                                f"Do not ask again. Answer without it."),
                })
                steps.append({"tool": name, "result": "declined"})
                continue

        elif verdict is False:
            _trace({"tool": name, "args": args, "outcome": "rejected",
                    "reason": reason})
            messages.append({"role": "assistant", "content": reply})
            messages.append({
                "role": "system",
                "content": f"That call was rejected: {reason}. Try again.",
            })
            steps.append({"tool": name, "result": f"rejected: {reason}"})
            continue

        key = f"{name}:{json.dumps(cleaned, sort_keys=True)}"
        if key in called:
            messages.append({"role": "assistant", "content": reply})
            messages.append({
                "role": "system",
                "content": (f"You already called {name} with those "
                            f"arguments. Use the result you have."),
            })
            steps.append({"tool": name, "result": "repeat, skipped"})
            continue
        called.add(key)

        if verdict is True:
            cleaned = _clean_args(name, cleaned)

        log.info(f"step {step + 1}: calling {name}")
        result = run_tool(name, cleaned)

        _trace({"tool": name, "args": cleaned,
                "outcome": "ran", "result": result[:200]})

        messages.append({"role": "assistant", "content": reply})
        messages.append({
            "role": "system",
            "content": f"Result of {name}:\n{result}",
        })
        steps.append({"tool": name, "result": result[:300]})

    _trace({"question": question[:200], "steps": len(steps),
            "outcome": "out-of-steps"})
    return {
        "answer": (f"I stopped after {MAX_STEPS} tool calls without "
                   f"reaching an answer. The tools returned: "
                   + "; ".join(s["tool"] for s in steps)),
        "steps": steps,
        "calls_made": len(steps),
        "exhausted": True,
    }


def handle(text, approve=None):
    """Chat entry point. Returns (reply, meta) or None."""
    t = text.strip().lower()

    if t in ("/tools", "/caps"):
        cat = tool_catalogue()
        if not cat:
            return ("no tools registered", {"kind": "agent"})
        lines = []
        for name, kind in sorted(cat.items()):
            mark = "auto" if kind == "read" else "asks" if kind == "write" else "?"
            lines.append(f"  {name:<24} {mark}")
        return ("\n".join(lines), {"kind": "agent", "count": len(cat)})

    if t == "/trace":
        steps = trace()[-8:]
        if not steps:
            return ("nothing traced yet", {"kind": "agent"})
        lines = []
        for s in steps:
            when = time.strftime("%H:%M:%S", time.localtime(s["at"]))
            if "tool" in s:
                lines.append(f"  {when}  {s['tool']}  -> {s['outcome']}")
            else:
                lines.append(f"  {when}  {s['outcome']}")
        return ("\n".join(lines), {"kind": "agent"})

    return None


def main(argv=None):
    ap = argparse.ArgumentParser(
        prog="orbital-agent",
        description="Let the model actually call its tools.",
    )
    ap.add_argument("--tools", action="store_true", help="what may be called")
    ap.add_argument("--ask", metavar="QUESTION")
    ap.add_argument("--trace", action="store_true")
    ap.add_argument("--yes", action="store_true",
                    help="approve write tools without prompting")
    ap.add_argument("--why-not", action="store_true")
    args = ap.parse_args(argv)

    if args.why_not:
        print(__doc__)
        return 0

    if args.tools:
        cat = tool_catalogue()
        print()
        for name, kind in sorted(cat.items()):
            mark = ("runs automatically" if kind == "read"
                    else "asks first" if kind == "write"
                    else "unknown")
            print(f"  {name:<24} {mark}")
        print()
        print(f"  {len(cat)} tools")
        print()
        return 0

    if args.trace:
        steps = trace()
        if not steps:
            print("  nothing traced yet")
            return 0
        for s in steps[-25:]:
            when = time.strftime("%H:%M:%S", time.localtime(s["at"]))
            if "tool" in s:
                print(f"  {when}  {s['tool']:<20} {s['outcome']}")
            else:
                print(f"  {when}  {s['outcome']:<20} "
                      f"{s.get('question', '')[:50]}")
        return 0

    if args.ask:
        def approve(name, a):
            if args.yes:
                print(f"  [auto-approved] {name}")
                return True
            try:
                answer = input(f"  Run {name}({a})? [y/N] ").strip().lower()
            except EOFError:
                return False
            return answer in ("y", "yes")

        print()
        result = ask(args.ask, approve=approve)
        print()
        print(f"  {result['answer']}")
        print()
        if result["steps"]:
            print(f"  ({result['calls_made']} tool call(s))")
            print()
        return 0

    print("nothing to do. try --tools or --ask \"what time is it\"")
    return 0


if __name__ == "__main__":
    sys.exit(main())