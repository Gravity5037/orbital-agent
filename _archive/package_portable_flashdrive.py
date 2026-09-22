import os
import shutil
import sys

def package_flashdrive(drive_letter):
    drive = drive_letter.strip().rstrip(":\\").upper() + ":\\"
    target_dir = os.path.join(drive, "Orbital_Portable")
    source_dir = r"C:\Orbital"
    
    print("=" * 60)
    print(f" Packaging Orbital Flash Drive: {target_dir}")
    print("=" * 60)
    
    for sd in ["Nucleus", "src", "assets", "plugins"]:
        os.makedirs(os.path.join(target_dir, sd), exist_ok=True)

    file_map = {
        "LAUNCH_ORBITAL.bat": ["LAUNCH_ORBITAL.bat", "launch-v2.bat"],
        "launchnucleus.bat": ["launchnucleus.bat", "LAUNCH_NUCLEUS_SILENT.bat"],
        "sync_to_github.bat": ["sync_to_github.bat", "sync_to_github-v2.bat"],
        "orbitalchat.py": ["orbitalchat.py", "orbitalchat-v2.py"],
        "engine.py": ["engine.py", "run_orbital.py"],
        "README.md": ["README.md"]
    }

    for dest_name, fallback_list in file_map.items():
        copied = False
        for fname in fallback_list:
            src_path = os.path.join(source_dir, fname)
            if os.path.exists(src_path):
                shutil.copy2(src_path, os.path.join(target_dir, dest_name))
                print(f" [✔] Copied {dest_name} (from {fname})")
                copied = True
                break
        if not copied:
            print(f" [!] Missing {dest_name}")

    # Handle launch_nucleus.vbs (Copy or Auto-Generate)
    vbs_dest = os.path.join(target_dir, "launch_nucleus.vbs")
    vbs_candidates = ["launch_nucleus.vbs", "launch_nucleus_silent.vbs", "silent.vbs"]
    vbs_copied = False
    for vbs in vbs_candidates:
        src_vbs = os.path.join(source_dir, vbs)
        if os.path.exists(src_vbs):
            shutil.copy2(src_vbs, vbs_dest)
            print(f" [✔] Copied launch_nucleus.vbs (from {vbs})")
            vbs_copied = True
            break
    if not vbs_copied:
        with open(vbs_dest, "w", encoding="utf-8") as f:
            f.write('Set Shell = CreateObject("WScript.Shell")\n')
            f.write('SubDir = CreateObject("Scripting.FileSystemObject").GetParentFolderName(WScript.ScriptFullName)\n')
            f.write('Shell.Run Chr(34) & SubDir & "\\launchnucleus.bat" & Chr(34), 0, False\n')
        print(" [✔] Auto-generated launch_nucleus.vbs")

    # Handle remote_gateway-v2.py with fallbacks
    gateway_dest = os.path.join(target_dir, "remote_gateway-v2.py")
    gw_candidates = ["remote_gateway-v2.py", "remote_gateway.py", "gibberlink_websocket_gateway-v2.py", "gibberlink_websocket_gateway.py"]
    for gw in gw_candidates:
        src_gw = os.path.join(source_dir, gw)
        if os.path.exists(src_gw):
            shutil.copy2(src_gw, gateway_dest)
            print(f" [✔] Copied remote_gateway-v2.py (from {gw})")
            break

    # Handle orbital_sync_engine.py with fallbacks
    sync_dest = os.path.join(target_dir, "orbital_sync_engine.py")
    sync_candidates = ["orbital_sync_engine.py", "setup_sync.py", "auto_sync_watcher-v4.py"]
    for sync_f in sync_candidates:
        src_sync = os.path.join(source_dir, sync_f)
        if os.path.exists(src_sync):
            shutil.copy2(src_sync, sync_dest)
            print(f" [✔] Copied orbital_sync_engine.py (from {sync_f})")
            break

    # Recursively copy Nucleus, src, and assets subfolders
    for folder in ["src", "Nucleus", "assets"]:
        sf = os.path.join(source_dir, folder)
        df = os.path.join(target_dir, folder)
        if os.path.exists(sf):
            count = 0
            for root, _, files in os.walk(sf):
                for file in files:
                    if file.endswith((".tmp", ".pyc")):
                        continue
                    sp = os.path.join(root, file)
                    rel_p = os.path.relpath(sp, sf)
                    dp = os.path.join(df, rel_p)
                    os.makedirs(os.path.dirname(dp), exist_ok=True)
                    shutil.copy2(sp, dp)
                    count += 1
            print(f" [✔] Copied {folder}/ folder ({count} files)")

    # Generate Note 8 launcher batch file
    launcher_path = os.path.join(target_dir, "LAUNCH_NOTE8_SYNC.bat")
    with open(launcher_path, "w", encoding="utf-8") as f:
        f.write("""@echo off
TITLE Orbital Galaxy Note 8 Portable Node
cls
echo ============================================================
echo   ORBITAL PORTABLE OS - GALAXY NOTE 8 SYNC NODE
echo ============================================================
echo [1/2] Launching Background Nucleus Engine...
if exist "%~dp0launch_nucleus.vbs" (
    wscript "%~dp0launch_nucleus.vbs"
) else (
    start /b cmd /c "%~dp0launchnucleus.bat"
)

echo [2/2] Starting Note 8 Remote Gateway & Orbital Chat...
if exist "%~dp0remote_gateway-v2.py" (
    start python "%~dp0remote_gateway-v2.py"
)
python "%~dp0orbitalchat.py"
pause
""")
    print(" [✔] Generated LAUNCH_NOTE8_SYNC.bat")

    print("\n" + "=" * 60)
    print(f" SUCCESS! Portable Orbital drive completely built at: {target_dir}")
    print("=" * 60)

if __name__ == "__main__":
    drive_input = sys.argv[1] if len(sys.argv) > 1 else input("\nEnter Flash Drive Letter (e.g. G): ")
    package_flashdrive(drive_input)