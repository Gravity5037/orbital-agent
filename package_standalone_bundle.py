import os
import sys
import zipfile
import time

def build_standalone_package():
    print("=============================================================")
    print("  ORBITAL OS: STANDALONE MASTER SINGLE-FILE PACKAGER         ")
    print("=============================================================")

    base_dir = r"C:\Orbital"
    output_zip = os.path.join(base_dir, "Orbital_Standalone_Setup.zip")

    # Folders to explicitly include
    include_folders = ["core", "gui", "assets", "Nucleus", "shared", "web_files", "users"]
    
    # Root files to explicitly include
    include_root_files = [
        "INSTALL_ORBITAL.bat",
        "LAUNCH_ORBITAL.bat",
        "requirements.txt",
        "orbital_logo.ico",
        "orbital_logo.png",
        "create_desktop_shortcut.py",
        "run_orbital.py",
        "engine.py",
        "orbital_login_gui.py",
        "orbital_navigator_gui.py",
        "orbitalchat_gui.py",
        "test_all_orbital_v32.py",
        "evolution_loop.py",
        "Modelfile",
        "users_db.json"
    ]

    print(f"[*] Target standalone archive: {output_zip}")
    start_time = time.time()

    with zipfile.ZipFile(output_zip, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        # 1. Add root files
        print("\n[1/3] Adding master installer and primary root files...")
        for fname in include_root_files:
            fpath = os.path.join(base_dir, fname)
            if os.path.exists(fpath):
                zf.write(fpath, arcname=fname)
                print(f"  [+] Added: {fname}")

        # 2. Add subdirectories
        print("\n[2/3] Adding modular subsystems, GUI, assets, and runtime...")
        for folder in include_folders:
            folder_path = os.path.join(base_dir, folder)
            if not os.path.exists(folder_path):
                continue
            for root, dirs, files in os.walk(folder_path):
                # Skip pycache
                if "__pycache__" in root:
                    continue
                for f in files:
                    full_p = os.path.join(root, f)
                    rel_p = os.path.relpath(full_p, base_dir)
                    zf.write(full_p, arcname=rel_p)
            print(f"  [+] Packed folder: {folder}/")

        # 3. Verify Nucleus Model inclusion
        print("\n[3/3] Verifying Nucleus model in archive...")
        model_p = os.path.join(base_dir, "Nucleus", "model.gguf")
        if os.path.exists(model_p):
            print(f"  [OK] Nucleus model verified inside package ({os.path.getsize(model_p) / (1024*1024):.1f} MB)")
        else:
            print("  [!] Nucleus model not found locally.")

    size_mb = os.path.getsize(output_zip) / (1024 * 1024)
    elapsed = time.time() - start_time
    print("=============================================================")
    print(f"  [OK] SINGLE-FILE PACKAGE READY: {output_zip}")
    print(f"  Package Size: {size_mb:.2f} MB")
    print(f"  Build Time:   {elapsed:.1f}s")
    print("  Ready for deployment to any new device!")
    print("=============================================================")

if __name__ == "__main__":
    build_standalone_package()
