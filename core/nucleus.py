"""Nucleus — the text reasoning engine.

This does NOT implement an LLM. It is a client for an Ollama-compatible
server (Ollama itself, or llama.cpp's llama-server, which speaks the same
API). That is the honest version of what the old gui/engine.py was faking:
a stub that answered /api/chat with a canned string and reported a hardcoded
model in /api/tags.

If nothing is listening, health() says so and the engine degrades to
command handling instead of pretending to think.
"""

import json
import os
import urllib.error
import urllib.request

from . import config, logutil

log = logutil.get_logger("nucleus")


class NucleusError(RuntimeError):
    pass


# ---------------------------------------------------------------------------
# Identity.
#
# The model is Qwen, or Llama, or whatever you point this at. It answers
# honestly that it is Qwen, because that is true. But it is answering *as*
# Orbital, which is the system around it: the engine, the tools, the memory,
# the mesh.
#
# The distinction matters and is worth keeping straight:
#   Nucleus  — the reasoning engine (this module). A component.
#   Nebula   — the image engine. A component.
#   Orbital  — the whole thing. What you talk to.
#
# So the prompt tells the model it is the reasoning core of Orbital, and that
# it should identify as Orbital while being honest about the model underneath
# if asked directly. Lying about what it is would be worse than the
# confusion it avoids.
# ---------------------------------------------------------------------------

IDENTITY = os.environ.get("ORBITAL_IDENTITY", """You are Orbital.

You are a local-first assistant running entirely on the user's own hardware.
Nothing you say leaves the machine. You are made of parts:

  - Nucleus is your reasoning core, which is what you are using right now.
  - Nebula is your image engine, which can generate pictures on request.
  - The mesh connects your instances across the user's other devices.

When asked who you are, say you are Orbital. If asked what model you run on,
answer honestly - the user can see it in their own configuration, and
pretending otherwise would just be confusing.

Be direct and concrete. You have real tools: you can control lights, play
music, capture images and generate them. When you cannot do something, say
so plainly rather than guessing or inventing a result.

Keep replies short unless asked for detail.""")


def system_prompt():
    """The identity prompt, with whatever context is useful."""
    parts = [IDENTITY]

    try:
        from . import config, logutil


        models = models_available()
        if models:
            parts.append(
                f"Models available locally: {', '.join(models[:8])}. "
                f"You are currently running on {config.MODEL}."
            )
    except Exception:
        pass

    return "\n\n".join(parts)


def models_available(timeout=3):
    ok, detail = health(timeout=timeout)
    return detail if ok else []


def _post(path, payload, timeout):
    url = config.OLLAMA_BASE.rstrip("/") + path
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url, data=body, headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        # The response body carries the real reason - "does not support
        # tools" and similar. Without it the caller only sees "400 Bad
        # Request" and cannot tell a capability problem from a transport one.
        try:
            detail = exc.read().decode("utf-8", errors="replace")
        except Exception:
            detail = ""
        raise NucleusError(f"HTTP {exc.code}: {detail[:300]}") from exc
    except urllib.error.URLError as exc:
        raise NucleusError(f"Nucleus unreachable at {config.OLLAMA_BASE}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise NucleusError(f"Nucleus returned non-JSON: {exc}") from exc


def _get(path, timeout):
    url = config.OLLAMA_BASE.rstrip("/") + path
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as exc:
        raise NucleusError(str(exc)) from exc


def health(timeout=2):
    """(reachable: bool, detail). detail is a model list or an error string."""
    try:
        data = _get("/api/tags", timeout=timeout)
    except NucleusError as exc:
        return False, str(exc)

    models = [m.get("name") for m in data.get("models", []) if m.get("name")]
    return True, models


def models(timeout=3):
    ok, detail = health(timeout=timeout)
    return detail if ok else []


def chat_with_tools(messages, model=None, timeout=300, max_rounds=4, on_tool=None):
    """Chat, letting the model call tools.

    Returns (text, calls) where calls is a list of {name, args, result} so the
    caller can show what happened.

    Falls back to a plain chat if the model does not support tools, so this is
    safe to use with any model.
    """
    from . import tools

    msgs = list(messages)
    if not any(m.get("role") == "system" for m in msgs):
        msgs.insert(0, {"role": "system", "content": system_prompt()})

    calls = []

    for _round in range(max_rounds):
        payload = {
            "model": model or config.MODEL,
            "messages": msgs,
            "stream": False,
            "tools": tools.SCHEMAS,
        }

        try:
            data = _post("/api/chat", payload, timeout)
        except NucleusError as exc:
            # A model without tool support rejects the tools field. Retry
            # without it rather than failing the whole request. Ollama words
            # this several ways depending on version, so match loosely.
            msg = str(exc).lower()
            unsupported = any(
                phrase in msg for phrase in
                ("tool", "function", "unsupported", "does not support",
                 "unknown field", "invalid request")
            )
            if unsupported:
                log.warn(f"model rejected tools ({str(exc)[:90]}); falling back")
                plain = [m for m in msgs if m.get("role") != "system"]
                if not any(m.get("role") == "system" for m in plain):
                    plain.insert(0, {"role": "system", "content": system_prompt()})
                return chat(plain, model=model, timeout=timeout, identity=False), calls
            raise

        msg = data.get("message") or {}
        requested = msg.get("tool_calls") or []

        if not requested:
            return (msg.get("content") or "").strip(), calls

        # Record the assistant turn that asked for the tools, then answer each.
        msgs.append(msg)

        for call in requested:
            fn = call.get("function") or {}
            name = fn.get("name", "")
            raw_args = fn.get("arguments") or "{}"

            if isinstance(raw_args, str):
                try:
                    args = json.loads(raw_args) if raw_args.strip() else {}
                except json.JSONDecodeError:
                    args = {}
            else:
                args = raw_args

            try:
                result = tools.execute(name, args)
                ok = True
            except tools.ToolError as exc:
                result = {"error": str(exc)}
                ok = False

            calls.append({"name": name, "args": args, "result": result, "ok": ok})
            if on_tool:
                try:
                    on_tool(name, args, result, ok)
                except Exception:
                    pass

            msgs.append({
                "role": "tool",
                "name": name,
                "content": json.dumps(result, default=str)[:8000],
            })

    # Ran out of rounds: ask for a summary rather than returning nothing.
    msgs.append({
        "role": "user",
        "content": "Summarise what you found in one short reply.",
    })
    payload = {"model": model or config.MODEL, "messages": msgs, "stream": False}
    data = _post("/api/chat", payload, timeout)
    return ((data.get("message") or {}).get("content") or "").strip(), calls


def chat(messages, model=None, timeout=180, identity=True):
    """Send an Ollama-style chat request. Returns the assistant text.

    The Orbital identity is prepended unless the caller opts out, so every
    surface that talks to the model gets the same voice.

    Raises NucleusError if the backend is down, so callers can fall back
    explicitly rather than getting a fake reply.
    """
    msgs = list(messages)
    if identity and not any(m.get("role") == "system" for m in msgs):
        msgs.insert(0, {"role": "system", "content": system_prompt()})

    payload = {
        "model": model or config.MODEL,
        "messages": msgs,
        "stream": False,
    }
    data = _post("/api/chat", payload, timeout)
    content = (data.get("message") or {}).get("content")
    if content is None:
        raise NucleusError(f"Unexpected response shape: {list(data)[:6]}")
    return content.strip()


def ensure_model(model=None):
    """True if the requested model is present in the backend."""
    target = model or config.MODEL
    return any(m == target or m.startswith(target + ":") for m in models())
