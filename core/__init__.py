"""Orbital core package.

Modules:
    config      — paths, ports, env overrides
    logutil     — file+console logging
    auth        — API token generation and checking
    nucleus     — client for the Ollama-compatible text backend
    oostate     — the OOSTATE.BIN portable state container
    statestore  — live state model and deterministic merge
    state_cli   — inspect/export/import/merge from the command line
    engine      — the local HTTP API (port 5000)
    mesh        — the WebSocket peer mesh (port 8765)
    supervisor  — starts and restarts the above
"""

__version__ = "2.1.0"
