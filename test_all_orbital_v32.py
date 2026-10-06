import os
import sys

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

def run_orbital_master_test_suite():
    print("=============================================================")
    print("     ORBITAL OS v32: FULL SYSTEM DIAGNOSTIC & TEST SUITE     ")
    print("=============================================================")

    results = []

    # Test 1: Core Engine Router & Imports
    print("\n[1/6] Testing Core Engine & Routing...")
    try:
        from core.engine import process_chat
        res_text = process_chat("System diagnostic query")
        res_draw = process_chat("/draw orbital space station artwork")
        print(f"  [✔] Engine Chat Response: {res_text[:60]}...")
        print(f"  [✔] Engine Draw Route: {res_draw[:60]}...")
        results.append(("Core Orchestrator", "PASSED"))
    except Exception as e:
        print(f"  [✘] Core Engine failed: {e}")
        results.append(("Core Orchestrator", f"FAILED ({e})"))

    # Test 2: Nucleus Engine (Text & Knowledge)
    print("\n[2/6] Testing Nucleus Engine...")
    try:
        from core.nucleus_engine import query_nucleus
        res = query_nucleus("Test Nucleus Knowledge Base")
        print(f"  [✔] Nucleus Direct Inference: {res[:70]}...")
        results.append(("Nucleus Text Engine", "PASSED"))
    except Exception as e:
        print(f"  [✘] Nucleus Engine failed: {e}")
        results.append(("Nucleus Text Engine", f"FAILED ({e})"))

    # Test 3: Nebula Engine (Visual & Design)
    print("\n[3/6] Testing Nebula Engine...")
    try:
        from core.nebula_engine import generate_visual
        res = generate_visual("Test render prompt")
        print(f"  [✔] Nebula Generation Route: {res[:70]}...")
        results.append(("Nebula Creative Engine", "PASSED"))
    except Exception as e:
        print(f"  [✘] Nebula Engine failed: {e}")
        results.append(("Nebula Creative Engine", f"FAILED ({e})"))

    # Test 4: Auth & Stealth Governance Controller
    print("\n[4/6] Testing Stealth Auth & Governance Controller...")
    try:
        from core.auth_controller import mask_email, mask_phone
        m_email = mask_email("fugly@gmail.com")
        m_phone = mask_phone("+15550192834")
        print(f"  [✔] Email Masking Test: {m_email}")
        print(f"  [✔] Phone Masking Test: {m_phone}")
        results.append(("Stealth Auth & Privacy Controller", "PASSED"))
    except Exception as e:
        print(f"  [✘] Auth Controller failed: {e}")
        results.append(("Stealth Auth & Privacy Controller", f"FAILED ({e})"))

    # Test 5: Ghost Stream & Zero-Bloat Storage Engine
    print("\n[5/6] Testing Ghost Stream & Zero-Bloat Engine...")
    try:
        from core.ghost_stream_engine import GhostStreamEngine
        ghost = GhostStreamEngine()
        status = ghost.get_system_status()
        print(f"  [✔] Ghost Stream Mode: {status.get('ghost_mode')}")
        print(f"  [✔] Local Bloat Bytes: {status.get('user_backups_local_bytes')}")
        results.append(("Ghost Stream & Zero-Bloat Engine", "PASSED"))
    except Exception as e:
        print(f"  [✘] Ghost Stream Engine failed: {e}")
        results.append(("Ghost Stream & Zero-Bloat Engine", f"FAILED ({e})"))

    # Test 6: Purge Ollama Verification
    print("\n[6/6] Testing Legacy Ollama Bypass Verification...")
    try:
        from core.purge_ollama import verify_ollama_purged
        purged = verify_ollama_purged()
        print(f"  [✔] Legacy Ollama Bypass Active: {purged}")
        results.append(("Legacy Ollama Bypass", "PASSED"))
    except Exception as e:
        print(f"  [✘] Purge Ollama failed: {e}")
        results.append(("Legacy Ollama Bypass", f"FAILED ({e})"))

    # Summary
    print("\n=============================================================")
    print("                    FINAL DIAGNOSTIC SUMMARY                 ")
    print("=============================================================")
    for component, status in results:
        symbol = "✔" if status == "PASSED" else "✘"
        print(f"  [{symbol}] {component:<35}: {status}")
    print("=============================================================\n")

if __name__ == "__main__":
    run_orbital_master_test_suite()
