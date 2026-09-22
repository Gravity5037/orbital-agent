import os
import shutil

def clean_and_organize_orbital():
    orbital_dir = r"C:\Orbital"
    archive_dir = os.path.join(orbital_dir, "_archive")
    
    if not os.path.exists(orbital_dir):
        print(f"[!] Directory {orbital_dir} not found.")
        return

    os.makedirs(archive_dir, exist_ok=True)
    print("=================================================================")
    print("            ORBITAL DIRECTORY CLEANUP & SANITIZER               ")
    print("=================================================================")
    print(f"[*] Main Directory:   {orbital_dir}")
    print(f"[*] Archive Folder:   {archive_dir}")
    print("-----------------------------------------------------------------")

    # Essential files that MUST remain in the root C:\Orbital\ folder
    essential_files = {
        "orbitalchat_gui.py",
        "engine.py",
        "setup_orbital_sd.py",
        "orbital_sync_engine.py",
        "gibberlink_websocket_gateway-v2.py",
        "wifi_csi_sensing-v2.py",
        "launch_orbital_gui.vbs",
        "launch_nucleus_silent.vbs",
        "launch_nucleus.vbs",
        "LAUNCH_ORBITAL_HUD.bat",
        "LAUNCH_ORBITAL_FULL.bat",
        "setup_orbital_fully_integrated.py",
        "package_orbital_flashdrive.py",
        "clean_orbital_dir.py",
        "orbital_icon.ico",
        "orb005_manifest.json"
    }

    # Essential folders
    essential_folders = {"Nucleus", "dist", "_archive", "assets"}

    archived_count = 0
    items = os.listdir(orbital_dir)

    for item in items:
        item_path = os.path.join(orbital_dir, item)
        
        # Skip essential folders and essential files
        if item in essential_folders or item in essential_files:
            continue

        try:
            target_path = os.path.join(archive_dir, item)
            shutil.move(item_path, target_path)
            print(f" [✔] Moved to _archive: {item}")
            archived_count += 1
        except Exception as e:
            print(f" [!] Could not move {item}: {e}")

    print("-----------------------------------------------------------------")
    print(f"[✔] Cleanup complete! Moved {archived_count} obsolete/temporary items to _archive.")
    print(f"[✔] C:\\Orbital now contains strictly essential OS runtimes.")
    print("=================================================================")

if __name__ == "__main__":
    clean_and_organize_orbital()
