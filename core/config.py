"""Central configuration. Everything is overridable by environment variable
so the same tree runs on Windows (C:\\Orbital) and on a Linux/mac node.
"""

import os

# --- base directory -------------------------------------------------------
# Windows default is C:\Orbital. Elsewhere, the repo root is the parent of core/.
# Override with ORBITAL_BASE.
def _default_base():
    env = os.environ.get("ORBITAL_BASE")
    if env:
        return os.path.abspath(env)
    if os.name == "nt":
        return r"C:\Orbital"
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


BASE_DIR = _default_base()
CORE_DIR = os.path.join(BASE_DIR, "core")
GUI_DIR = os.path.join(BASE_DIR, "gui")
LOG_DIR = os.path.join(BASE_DIR, "logs")
STATE_DIR = os.path.join(BASE_DIR, "state")

# --- network bindings -----------------------------------------------------
# Loopback by default. Setting these to 0.0.0.0 exposes the API to the LAN;
# the token gate still applies, but don't do it on an untrusted network.
ENGINE_HOST = os.environ.get("ORBITAL_ENGINE_HOST", "127.0.0.1")
ENGINE_PORT = int(os.environ.get("ORBITAL_ENGINE_PORT", "5000"))

MESH_HOST = os.environ.get("ORBITAL_MESH_HOST", "127.0.0.1")
MESH_PORT = int(os.environ.get("ORBITAL_MESH_PORT", "8765"))

# Nucleus talks to an Ollama-compatible endpoint. Ollama's own default is 11434.
OLLAMA_BASE = os.environ.get("ORBITAL_OLLAMA", "http://127.0.0.1:11434")
MODEL = os.environ.get("ORBITAL_MODEL", "qwen2.5-coder:1.5b")

# --- peers ----------------------------------------------------------------
# Comma-separated ws:// URLs of other nodes to dial. This is the hive.
# e.g. ORBITAL_PEERS=ws://100.64.0.5:8765,ws://100.64.0.9:8765
def peers():
    raw = os.environ.get("ORBITAL_PEERS", "").strip()
    return [p.strip() for p in raw.split(",") if p.strip()]


NODE_ID = os.environ.get("ORBITAL_NODE_ID", "")


def node_id():
    """Stable-ish identity for this node. Prefers ORBITAL_NODE_ID, else hostname."""
    if NODE_ID:
        return NODE_ID
    import socket

    return socket.gethostname()


# --- shell bridge ---------------------------------------------------------
# /ps and /cmd run PowerShell. They are token-gated and loopback-only, but
# this switch lets you turn them off entirely.
SHELL_ENABLED = os.environ.get("ORBITAL_ENABLE_SHELL", "1") not in ("0", "false", "no")
SHELL_TIMEOUT = int(os.environ.get("ORBITAL_SHELL_TIMEOUT", "60"))

# --- image/video backend pool --------------------------------------------
# ComfyUI endpoint. Single-machine default; the pool below adds more.
COMFY_BASE = os.environ.get("ORBITAL_COMFY", "http://127.0.0.1:8188")


def backends():
    """Parse ORBITAL_BACKENDS into a list of {name, url, weight}.

    Format:  name=url[@weight],name=url[@weight]
    Example: desktop=http://100.64.0.5:8188,laptop=http://100.64.0.9:8188@2

    A bare url with no name is accepted; the host:port becomes the name.
    """
    raw = os.environ.get("ORBITAL_BACKENDS", "").strip()
    if not raw:
        return []

    out = []
    for chunk in raw.split(","):
        chunk = chunk.strip()
        if not chunk:
            continue

        weight = 1.0
        if "@" in chunk:
            chunk, _, w = chunk.rpartition("@")
            try:
                weight = float(w)
            except ValueError:
                weight = 1.0

        if "=" in chunk:
            name, _, url = chunk.partition("=")
            name, url = name.strip(), url.strip()
        else:
            name, url = "", chunk.strip()

        if not url:
            continue
        if not url.startswith(("http://", "https://")):
            url = "http://" + url
        out.append({"name": name, "url": url, "weight": weight})
    return out


BACKEND_STATUS_TTL = float(os.environ.get("ORBITAL_BACKEND_TTL", "5"))

# --- paths ----------------------------------------------------------------
TOKEN_FILE = os.path.join(STATE_DIR, "engine.token")
MEMORY_FILE = os.path.join(STATE_DIR, "chat_memory.json")
STATE_FILE = os.environ.get("ORBITAL_STATE", os.path.join(STATE_DIR, "OOSTATE.BIN"))
WORKSTATION_HTML = os.path.join(GUI_DIR, "cyber_organic_workstation.html")


def ensure_dirs():
    for d in (LOG_DIR, STATE_DIR):
        os.makedirs(d, exist_ok=True)
