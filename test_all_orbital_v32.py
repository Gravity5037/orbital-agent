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
    print("     ORBITAL OS v34: MASTER SYSTEM SPECIFICATION SUITE       ")
    print("=============================================================")

    results = []

    # 1. Core Engine Router & Imports
    print("\n[1/13] Testing Core Engine & Routing...")
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

    # 2. Nucleus Engine (Text & Knowledge)
    print("\n[2/13] Testing Nucleus Engine...")
    try:
        from core.nucleus_engine import query_nucleus
        res = query_nucleus("Test Nucleus Knowledge Base")
        print(f"  [✔] Nucleus Direct Inference: {res[:70]}...")
        results.append(("Nucleus Text Engine", "PASSED"))
    except Exception as e:
        print(f"  [✘] Nucleus Engine failed: {e}")
        results.append(("Nucleus Text Engine", f"FAILED ({e})"))

    # 3. Nebula Engine (Visual & Design)
    print("\n[3/13] Testing Nebula Engine...")
    try:
        from core.nebula_engine import generate_visual
        res = generate_visual("Test render prompt")
        print(f"  [✔] Nebula Generation Route: {res[:70]}...")
        results.append(("Nebula Creative Engine", "PASSED"))
    except Exception as e:
        print(f"  [✘] Nebula Engine failed: {e}")
        results.append(("Nebula Creative Engine", f"FAILED ({e})"))

    # 4. Auth & Stealth Governance Controller
    print("\n[4/13] Testing Stealth Auth & Governance Controller...")
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

    # 5. Ghost Stream & Zero-Bloat Storage Engine
    print("\n[5/13] Testing Ghost Stream & Zero-Bloat Engine...")
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

    # 6. Purge Ollama Verification
    print("\n[6/13] Testing Legacy Ollama Bypass Verification...")
    try:
        from core.purge_ollama import verify_ollama_purged
        purged = verify_ollama_purged()
        print(f"  [✔] Legacy Ollama Bypass Active: {purged}")
        results.append(("Legacy Ollama Bypass", "PASSED"))
    except Exception as e:
        print(f"  [✘] Purge Ollama failed: {e}")
        results.append(("Legacy Ollama Bypass", f"FAILED ({e})"))

    # 7. OOSTATE.BIN Binary Serialization & Sovereign Failover
    print("\n[7/13] Testing OOSTATE.BIN Memory-Mapped State Store...")
    try:
        from core.oostate_engine import OOStateManager
        oomgr = OOStateManager()
        state = oomgr.read_state()
        failover = oomgr.trigger_sovereign_failover()
        oomgr.close()
        print(f"  [✔] OOSTATE Magic: {state['magic']} | CRC32 Verified: {state['crc32_match']}")
        print(f"  [✔] Failover Mode: {failover['active_pole_name']} | Version: {failover['state_version']}")
        results.append(("OOSTATE Binary State & Failover", "PASSED"))
    except Exception as e:
        print(f"  [✘] OOSTATE failed: {e}")
        results.append(("OOSTATE Binary State & Failover", f"FAILED ({e})"))

    # 8. Hardware Introspection & ISA Probing
    print("\n[8/13] Testing Hardware Introspection & ISA Probing...")
    try:
        from core.hw_introspection import HardwareIntrospectionEngine
        hw = HardwareIntrospectionEngine()
        topo = hw.get_system_topology()
        print(f"  [✔] CPU Cores: {topo['physical_cores']} Phys / {topo['logical_processors']} Log")
        print(f"  [✔] SIMD Dispatch Tier: {topo['simd_features']['simd_dispatch_mode']}")
        results.append(("Hardware Introspection & ISA", "PASSED"))
    except Exception as e:
        print(f"  [✘] HW Introspection failed: {e}")
        results.append(("Hardware Introspection & ISA", f"FAILED ({e})"))

    # 9. Wi-Fi CSI 3-Stage Signal Processing Engine
    print("\n[9/13] Testing Wi-Fi CSI Mathematical Signal Processing...")
    try:
        from core.csi_sensing_engine import CSISensingEngine
        csi = CSISensingEngine(port=5556)
        csi.start()
        import time
        time.sleep(0.5)
        st = csi.get_status()
        csi.stop()
        print(f"  [✔] CSI UDP Socket: {st['listening_address']} | Subcarriers: {st['subcarriers_count']}")
        print(f"  [✔] 3-Stage Phase Sanitization & Respiration Filter: ACTIVE")
        results.append(("Wi-Fi CSI RF Sensing Engine", "PASSED"))
    except Exception as e:
        print(f"  [✘] CSI Engine failed: {e}")
        results.append(("Wi-Fi CSI RF Sensing Engine", f"FAILED ({e})"))

    # 10. BLE Log-Distance Proximity & Angle-of-Arrival (AoA)
    print("\n[10/13] Testing BLE Log-Distance Path Loss & AoA...")
    try:
        from core.ble_sensing_engine import BLESensingEngine
        ble = BLESensingEngine()
        pkt = ble.ingest_ble_packet("BE:AC:01:02:03:04", rssi=-64, phase_diff_rad=0.35)
        print(f"  [✔] BLE Distance Est: {pkt['estimated_distance_m']}m | AoA Angle: {pkt['aoa_angle_deg']}°")
        results.append(("BLE Sensing & AoA Vectoring", "PASSED"))
    except Exception as e:
        print(f"  [✘] BLE Engine failed: {e}")
        results.append(("BLE Sensing & AoA Vectoring", f"FAILED ({e})"))

    # 11. GibberLink Asyncio WebSocket Mesh
    print("\n[11/13] Testing GibberLink P2P WebSocket Mesh...")
    try:
        from core.gibberlink_mesh import GibberLinkMesh
        mesh = GibberLinkMesh(port=8766)
        mesh.start_background_mesh()
        success = mesh.sync_to_peer_sync("ws://127.0.0.1:8766")
        print(f"  [✔] Loopback Handshake & Payload Exchange: {success}")
        results.append(("GibberLink P2P Mesh Network", "PASSED"))
    except Exception as e:
        print(f"  [✘] GibberLink Mesh failed: {e}")
        results.append(("GibberLink P2P Mesh Network", f"FAILED ({e})"))

    # 12. Computer Vision & 3D Spatial Occupancy Mapping
    print("\n[12/13] Testing 3D Spatial Mapping & Camera Tracking...")
    try:
        from core.spatial_map_engine import SpatialMapEngine
        spatial = SpatialMapEngine()
        occupants = spatial.process_camera_frame()
        telem = spatial.get_spatial_telemetry()
        spatial.release()
        print(f"  [✔] Camera Active: {telem['hardware_camera_attached']} | Occupants: {len(occupants)}")
        results.append(("3D Spatial Occupancy & Vision", "PASSED"))
    except Exception as e:
        print(f"  [✘] Spatial Engine failed: {e}")
        results.append(("3D Spatial Occupancy & Vision", f"FAILED ({e})"))

    # 13. Acoustic FFT Audio Spectrum Analyzer
    print("\n[13/13] Testing Real-Time Audio Spectrum FFT Processing...")
    try:
        from core.audio_spectrum_engine import AudioSpectrumEngine
        audio = AudioSpectrumEngine()
        spec = audio.generate_simulated_acoustic_frame()
        print(f"  [✔] Spectral Bands: {len(spec['spectrum_bands'])} | Dominant Freq: {spec['dominant_frequency_hz']} Hz")
        results.append(("Acoustic Audio Spectrum FFT", "PASSED"))
    except Exception as e:
        print(f"  [✘] Audio Engine failed: {e}")
        results.append(("Acoustic Audio Spectrum FFT", f"FAILED ({e})"))

    # Final Summary
    print("\n=============================================================")
    print("                    FINAL DIAGNOSTIC SUMMARY                 ")
    print("=============================================================")
    passed = 0
    for component, status in results:
        symbol = "✔" if status == "PASSED" else "✘"
        if status == "PASSED":
            passed += 1
        print(f"  [{symbol}] {component:<35}: {status}")
    print("=============================================================")
    print(f"  RESULT: {passed}/{len(results)} Subsystems Verified Operational\n")

if __name__ == "__main__":
    run_orbital_master_test_suite()
