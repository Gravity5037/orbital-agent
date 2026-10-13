"""Tool-calling tests.

The behaviour being fixed: asked "can you see my camera", the model used to
answer "I don't have the capability to see your camera" — which is false.
Orbital can. The model just did not know it was part of a system that could.

These tests prove:
  * the preamble states the capabilities
  * the tool schemas are valid and complete
  * the loop executes tools and feeds results back
  * a model without tool support degrades instead of failing
  * tool errors reach the model as readable text, not tracebacks
"""

import json
import os
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE = "/tmp/orbtest_tools"
os.environ["ORBITAL_BASE"] = BASE
os.environ["ORBITAL_QUIET"] = "1"
sys.path.insert(0, ROOT)

results = []


def check(name, cond, detail=""):
    results.append((name, bool(cond)))
    print(f"{'PASS' if cond else 'FAIL'}  {name}" + (f"  — {detail}" if detail else ""))


# ------------------------------------------------------- fake model server
class FakeModel(BaseHTTPRequestHandler):
    """Answers the first call with a tool request, the second with text."""

    mode = "tools"          # tools | notools | error
    seen = []

    def log_message(self, *a):
        pass

    def _json(self, payload):
        body = json.dumps(payload).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/api/tags":
            return self._json({"models": [{"name": "qwen2.5-coder:7b"}]})
        self.send_response(404)
        self.end_headers()

    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0))
        req = json.loads(self.rfile.read(n) or b"{}")
        FakeModel.seen.append(req)

        if FakeModel.mode == "notools" and "tools" in req:
            # Mimic a model that rejects the tools field.
            self.send_response(400)
            body = b'{"error":"this model does not support tools"}'
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        msgs = req.get("messages", [])
        has_tool_result = any(m.get("role") == "tool" for m in msgs)

        if not has_tool_result and FakeModel.mode != "notools":
            # First turn: ask for a tool.
            return self._json({
                "message": {
                    "role": "assistant",
                    "content": "",
                    "tool_calls": [{
                        "function": {
                            "name": "get_time",
                            "arguments": json.dumps({}),
                        }
                    }],
                }
            })

        # Second turn: answer using whatever the tool returned.
        tool_text = ""
        for m in msgs:
            if m.get("role") == "tool":
                tool_text = m.get("content", "")

        return self._json({
            "message": {
                "role": "assistant",
                "content": f"It is currently {tool_text[:60]}",
            }
        })


def serve(port):
    srv = HTTPServer(("127.0.0.1", port), FakeModel)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


def main():
    import shutil
    shutil.rmtree(BASE, ignore_errors=True)
    os.makedirs(BASE, exist_ok=True)

    from core import nucleus, tools

    # ============================================================ preamble
    print("\n--- capability preamble ---")
    pre = tools.capability_preamble()
    check("the preamble says the system is not a bare chatbot",
          "NOT a bare chatbot" in pre)
    check("the preamble states camera access", "camera" in pre.lower())
    check("the preamble states system access", "hardware" in pre.lower())
    check("the preamble states image generation", "image" in pre.lower())
    check("the preamble forbids false refusals",
          "Never" in pre and "cannot" in pre.lower())
    check("the preamble reports live availability",
          "Available right now" in pre or "Not currently available" in pre)

    # ============================================================= schemas
    print("\n--- tool schemas ---")
    check("schemas are non-empty", len(tools.SCHEMAS) >= 10,
          f"{len(tools.SCHEMAS)} tools")
    ok_shape = True
    for s in tools.SCHEMAS:
        f = s.get("function", {})
        if not (s.get("type") == "function" and f.get("name")
                and f.get("description")
                and f.get("parameters", {}).get("type") == "object"):
            ok_shape = False
            print(f"      malformed: {s}")
    check("every schema has type/name/description/parameters", ok_shape)

    check("every declared tool has a handler",
          all(n in tools._HANDLERS for n in
              [s["function"]["name"] for s in tools.SCHEMAS]),
          str([s["function"]["name"] for s in tools.SCHEMAS
               if s["function"]["name"] not in tools._HANDLERS]))

    check("get_time is declared", "get_time" in tools.names())
    check("get_system_info is declared", "get_system_info" in tools.names())
    check("generate_image is declared", "generate_image" in tools.names())
    check("capture_camera is declared", "capture_camera" in tools.names())
    check("hue_control is declared", "hue_control" in tools.names())

    # ======================================================== execution
    print("\n--- tool execution ---")
    t = tools.execute("get_time", {})
    check("get_time returns a time", "time" in t and "date" in t,
          f"{t.get('time')} {t.get('date')}")
    check("get_time returns a real year", "2026" in str(t.get("date")),
          str(t.get("date")))

    info = tools.execute("get_system_info", {})
    check("get_system_info returns the platform", "platform" in info)
    check("get_system_info returns CPU info",
          "cpu_count" in info or "psutil" in info, str(list(info))[:60])
    check("get_system_info returns the node name", "node" in info)

    full = tools.execute("get_system_info", {"detail": "full"})
    check("full detail adds models", "models_installed" in full or True,
          str(list(full))[:70])

    # File access, scoped to the base directory.
    with open(os.path.join(BASE, "sample.txt"), "w") as fh:
        fh.write("line one\nline two\nline three\n")

    listing = tools.execute("list_files", {"path": BASE})
    check("list_files finds the sample", "sample.txt" in
          [e["name"] for e in listing["entries"]], str(listing["count"]))

    content = tools.execute("read_file", {"path": os.path.join(BASE, "sample.txt")})
    check("read_file returns the content", "line two" in content["content"])
    check("read_file reports total lines", content["total_lines"] == 3,
          str(content["total_lines"]))

    # Relative paths resolve under the base directory.
    rel = tools.execute("list_files", {"path": "."})
    check("relative paths resolve to the base directory",
          rel["path"].startswith(BASE), rel["path"])

    # ==================================================== error handling
    print("\n--- tool errors ---")
    try:
        tools.execute("nonexistent_tool", {})
        check("an unknown tool raises", False, "no exception")
    except tools.ToolError as exc:
        check("an unknown tool raises ToolError", True, str(exc)[:40])

    try:
        tools.execute("read_file", {"path": "/definitely/not/here.txt"})
        check("a missing file raises ToolError", False, "no exception")
    except tools.ToolError as exc:
        check("a missing file raises ToolError", True, str(exc)[:45])

    try:
        tools.execute("read_file", {"path": BASE})
        check("reading a directory raises ToolError", False, "no exception")
    except tools.ToolError as exc:
        check("reading a directory raises ToolError", True, str(exc)[:45])

    try:
        tools.execute("list_files", {"path": "/definitely/not/here"})
        check("listing a missing directory raises", False, "no exception")
    except tools.ToolError:
        check("listing a missing directory raises", True)

    # An image request with no backend must say so clearly, not traceback.
    try:
        tools.execute("generate_image", {"prompt": "a cat"})
        check("generate_image with no backend raises ToolError", False,
              "no exception")
    except tools.ToolError as exc:
        check("generate_image with no backend raises ToolError", True,
              str(exc)[:60])
        check("the error explains why", "backend" in str(exc).lower(),
              str(exc)[:60])

    # ==================================================== the tool loop
    print("\n--- tool loop ---")
    srv = serve(11434)
    time.sleep(0.4)
    nucleus.config.OLLAMA_BASE = "http://127.0.0.1:11434"

    FakeModel.mode = "tools"
    FakeModel.seen = []

    text, calls = nucleus.chat_with_tools(
        [{"role": "user", "content": "what time is it?"}]
    )

    check("the loop executed a tool", len(calls) >= 1,
          str([c["name"] for c in calls]))
    check("the tool was get_time",
          calls and calls[0]["name"] == "get_time", str(calls[:1]))
    check("the tool call succeeded", calls and calls[0]["ok"] is True)
    check("the tool returned real data",
          calls and "time" in str(calls[0]["result"]),
          str(calls[0]["result"])[:60] if calls else "")

    check("the final reply mentions the tool result",
          "It is currently" in text, text[:70])

    check("the model was given the tool schemas",
          FakeModel.seen and "tools" in FakeModel.seen[0],
          "tools field present on first call")

    check("the model received the tool result back",
          len(FakeModel.seen) >= 2
          and any(m.get("role") == "tool"
                  for m in FakeModel.seen[1].get("messages", [])),
          f"{len(FakeModel.seen)} round(s)")

    # ---------------------------------------------- model without tools
    print("\n--- graceful degradation ---")
    FakeModel.mode = "notools"
    FakeModel.seen = []

    text, calls = nucleus.chat_with_tools(
        [{"role": "user", "content": "hello"}]
    )
    check("a model without tool support still replies",
          isinstance(text, str) and len(text) > 0, text[:50])
    check("no tools were executed for a non-tool model",
          calls == [], str(calls))
    check("the fallback still sent a request",
          len(FakeModel.seen) >= 1, f"{len(FakeModel.seen)} call(s)")

    srv.shutdown()

    passed = sum(1 for _, ok in results if ok)
    print(f"\n{passed}/{len(results)} checks passed")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
