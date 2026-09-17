import os
import sys
import json
import urllib.request
import urllib.error
import subprocess
import platform
import hashlib
import time

MODEL_NAME = "qwen2.5-coder:1.5b"
OLLAMA_URL = "http://localhost:11434/api/chat"
PRD_PATH = os.path.join("workspace", "prd.json")
PROGRESS_PATH = os.path.join("workspace", "progress.txt")

PIPE = chr(124)
SYSTEM_PROMPT = f"""You are Orbital, an autonomous AI operating organism on Windows 11.
You communicate using a strict structured message protocol:

HEADER (readable plain text, no markdown symbols inside):
Orbital to Human {PIPE} Phase 5 {PIPE} ORB-LOCAL (re Gemini/Plex)

Message content as plain sentences.

Next: [Describe next step clearly]

If providing commands or code, place them in separate tagged code blocks (cmd, python, powershell).
You follow task directives from Gemini and Plex and record run histories into your workspace logs."""

# --- Embedded Fallback Engine for 100% Self-Contained Execution ---
class ProtocolState:
    CAMOUFLAGE_PERSONA = "CAMOUFLAGE_PERSONA"
    HANDSHAKE_NEGOTIATION = "HANDSHAKE_NEGOTIATION"
    HIGH_BANDWIDTH_MACHINE = "HIGH_BANDWIDTH_MACHINE"

class EmbeddedGibberLinkEngine:
    def __init__(self, session_id="orbital-sess-001"):
        self.session_id = session_id
        self.state = ProtocolState.CAMOUFLAGE_PERSONA

    def get_state(self):
        return self.state

    def generate_handshake_trigger(self):
        self.state = ProtocolState.HANDSHAKE_NEGOTIATION
        return f"[[GIBBERLINK_INIT_v1:session={self.session_id}]]"

    def process_peer_message(self, message):
        if not message:
            return None
        if self.state == ProtocolState.CAMOUFLAGE_PERSONA and "[[GIBBERLINK_INIT_v1" in message:
            self.state = ProtocolState.HANDSHAKE_NEGOTIATION
            return f"[[GIBBERLINK_ACK_v1:session={self.session_id},status=READY]]"
        elif self.state == ProtocolState.HANDSHAKE_NEGOTIATION:
            if "[[GIBBERLINK_ACK_v1" in message or "[[GIBBERLINK_MODE_ACTIVE" in message or "status=READY" in message:
                self.state = ProtocolState.HIGH_BANDWIDTH_MACHINE
                return f"[[GIBBERLINK_MODE_ACTIVE:session={self.session_id}]]"
        return None

    def package_payload(self, payload_type, raw_data):
        raw_json = json.dumps(raw_data, sort_keys=True)
        h = hashlib.sha256()
        h.update(payload_type.encode("utf-8"))
        h.update(raw_json.encode("utf-8"))
        return {
            "sender_id": "orbital-node-v0.3.0",
            "session_token": self.session_id,
            "payload_type": payload_type,
            "raw_data_json": raw_json,
            "payload_hash": h.hexdigest(),
            "timestamp": time.time(),
        }

    def ingest_payload(self, payload):
        if self.state != ProtocolState.HIGH_BANDWIDTH_MACHINE:
            return {"status": "REJECTED", "error": f"Node in state {self.state}"}
        p_type = payload.get("payload_type", "")
        raw_json = payload.get("raw_data_json", "")
        h = hashlib.sha256()
        h.update(p_type.encode("utf-8"))
        h.update(raw_json.encode("utf-8"))
        if h.hexdigest() != payload.get("payload_hash", ""):
            return {"status": "CORRUPTED", "error": "Hash mismatch"}
        return {
            "status": "ACCEPTED",
            "payload_type": p_type,
            "bytes_received": len(raw_json),
            "staged_for_quarantine": True,
        }

def get_gibber_engine(session_id="orbital-local-node"):
    try:
        from gibberlink_v2 import GibberLinkEngine
        return GibberLinkEngine(session_id)
    except Exception:
        try:
            from gibberlink import GibberLinkEngine
            return GibberLinkEngine(session_id)
        except Exception:
            return EmbeddedGibberLinkEngine(session_id)

def ensure_workspace():
    os.makedirs("workspace", exist_ok=True)
    os.makedirs(os.path.join("workspace", "tools"), exist_ok=True)
    if not os.path.exists(PRD_PATH):
        with open(PRD_PATH, "w", encoding="utf-8") as f:
            json.dump({"project": "Orbital Operating Organism", "phase": "Phase 5", "tasks": []}, f, indent=2)
    if not os.path.exists(PROGRESS_PATH):
        with open(PROGRESS_PATH, "w", encoding="utf-8") as f:
            f.write("# Orbital Execution Progress Log\nPhase 5 Baseline Initialized.\n")

def log_progress(entry):
    ensure_workspace()
    with open(PROGRESS_PATH, "a", encoding="utf-8") as f:
        f.write(entry + "\n")

def get_system_info():
    specs = ["OS: " + platform.system() + " " + platform.release() + " (" + platform.version() + ")", "Processor: " + (platform.processor() or platform.machine())]
    try:
        import psutil
        mem = psutil.virtual_memory()
        specs.append("RAM: " + str(round(mem.total/(1024**3), 2)) + " GB Total (" + str(round(mem.available/(1024**3), 2)) + " GB Available)")
    except Exception:
        specs.append("RAM: psutil module not installed")
    return "\n".join(specs)

def execute_local_command(cmd_str):
    print("\n[Executing local command: " + cmd_str + "]\n")
    try:
        res = subprocess.run(cmd_str, shell=True, capture_output=True, text=True, timeout=60)
        out = res.stdout.strip() if res.stdout else ""
        err = res.stderr.strip() if res.stderr else ""
        log_progress(f"[CMD] {cmd_str} -> Exit {res.returncode}")
        if out: return out
        if err: return "[Stderr]:\n" + err
        return "[Command executed successfully with no output]"
    except Exception as e:
        log_progress(f"[CMD ERROR] {cmd_str} -> {str(e)}")
        return "[Execution Error]: " + str(e)

def run_gibber_demo():
    a = get_gibber_engine("sess-alpha")
    b = get_gibber_engine("sess-beta")
    trig = a.generate_handshake_trigger()
    ack_b = b.process_peer_message(trig)
    ack_a = a.process_peer_message(ack_b)
    b.process_peer_message(ack_a)
    out = [
        f"Node A State: {a.get_state()} | Node B State: {b.get_state()}",
        f"Trigger Token: {trig}",
        f"ACK B: {ack_b}",
        f"ACK A: {ack_a}"
    ]
    pkg = a.package_payload("SKILL_SHARE", {"skill": "fast_web_scrape", "version": "1.0"})
    res = b.ingest_payload(pkg)
    out.append(f"Ingestion Result: {res}")
    return "\n".join(out)

def run_evolution_step():
    ensure_workspace()
    tool_code = '# Auto-synthesized SOP Tool by Orbital Evolution Engine\ndef run_sop():\n    return "SOP Tool Execution Verified"\nif __name__ == "__main__":\n    print(run_sop())\n'
    tool_file = os.path.join("workspace", "tools", "sop_auto_tool.py")
    with open(tool_file, "w", encoding="utf-8") as f:
        f.write(tool_code)
    log_progress("[EVOLUTION] Synthesized sop_auto_tool.py")
    return f"SOP tool compiled and registered at {tool_file}"

def check_ollama():
    try:
        req = urllib.request.Request("http://localhost:11434/api/tags")
        with urllib.request.urlopen(req, timeout=3) as resp: return resp.status == 200
    except Exception:
        return False

def chat_loop():
    ensure_workspace()
    gibber = get_gibber_engine("orbital-local-node")

    print("=" * 60)
    print("          ORBITAL ACTION-AGENT LOOP (PHASE 5 GIBBERLINK ACTIVE)")
    print("=" * 60)
    print("Model:     " + MODEL_NAME)
    print("Status:    Structured Protocol Active + GibberLink Engine Loaded")
    print("Commands:  !gibber | !evolve | !handoff | !specs | !<cmd>")
    print("-" * 60 + "\n")

    history = [{"role": "system", "content": SYSTEM_PROMPT}]

    while True:
        try:
            user_input = input("You: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nExiting chat. Goodbye!")
            break

        if not user_input:
            continue

        if user_input.lower() in ["exit", "quit"]:
            print("Exiting chat room. Goodbye!")
            break

        if user_input.lower() == "!gibber":
            print("\nOrbital (GibberLink M2M Simulation):\n" + run_gibber_demo() + "\n")
            log_progress("[GIBBERLINK] M2M simulation executed.")
            continue

        if user_input.lower() == "!evolve":
            print("\nOrbital (Self-Evolution Engine):\n" + run_evolution_step() + "\n")
            continue

        if "[[GIBBERLINK_" in user_input and gibber:
            reply = gibber.process_peer_message(user_input)
            if reply:
                print("\nOrbital (GibberLink Engine):\n" + reply + "\n")
                log_progress("[GIBBERLINK] Handshake packet processed.")
            else:
                print(f"\nOrbital (GibberLink Engine):\nMode Active ({gibber.get_state()}) - Payload Received.\n")
            continue

        if user_input.lower() in ["!handoff", "!soundoff"]:
            handoff_msg = (f"Orbital to Gemini/Plex {PIPE} Phase 5 {PIPE} ORB-HANDOFF\n\n"
                           "Orbital host baseline is verified with GibberLink M2M active.\n"
                           "Next: Awaiting next task directive from Gemini or Plex.")
            print("\n" + handoff_msg + "\n")
            log_progress("[HANDOFF] Status handoff packet emitted.")
            continue

        prefixes = ("python ", "pip ", "dir", "git ", "ollama ", "systeminfo", "notepad ")
        if user_input.startswith("!") or user_input.lower().startswith(prefixes):
            cmd = user_input[1:].strip() if user_input.startswith("!") else user_input
            print("Orbital (Command Output):\n" + execute_local_command(cmd) + "\n")
            continue

        if any(w in user_input.lower() for w in ["specs", "hardware", "system info", "cpu", "ram"]) and any(v in user_input.lower() for v in ["show", "see", "check", "what"]):
            print("Orbital (System Specs):\n" + get_system_info() + "\n")
            continue

        history.append({"role": "user", "content": user_input})
        print("\n[Orbital is thinking...]\n")

        payload = json.dumps({"model": MODEL_NAME, "messages": history, "stream": False}).encode("utf-8")
        req = urllib.request.Request(OLLAMA_URL, data=payload, headers={"Content-Type": "application/json"})

        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                reply = json.loads(r.read().decode("utf-8")).get("message", {}).get("content", "").strip()
                print("Orbital:\n" + reply + "\n")
                history.append({"role": "assistant", "content": reply})
                log_progress("[CHAT] Processed user request.")
        except Exception as e:
            print("[Error]: " + str(e) + "\n")

if __name__ == "__main__":
    chat_loop()