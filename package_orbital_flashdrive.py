import os
import sys
import shutil
import glob
import subprocess

def create_orbital_icon(icon_path):
    try:
        from PIL import Image, ImageDraw
        img = Image.new("RGBA", (256, 256), (15, 17, 26, 255))
        draw = ImageDraw.Draw(img)
        draw.ellipse([20, 20, 236, 236], outline=(0, 242, 254, 255), width=8)
        draw.ellipse([60, 60, 196, 196], outline=(189, 147, 249, 255), width=6)
        draw.ellipse([100, 100, 156, 156], fill=(0, 242, 254, 255))
        draw.polygon([(128, 40), (145, 90), (111, 90)], fill=(80, 250, 123, 255))
        draw.polygon([(128, 216), (145, 166), (111, 166)], fill=(80, 250, 123, 255))
        draw.polygon([(40, 128), (90, 145), (90, 111)], fill=(80, 250, 123, 255))
        draw.polygon([(216, 128), (166, 145), (166, 111)], fill=(80, 250, 123, 255))
        img.save(icon_path, format="ICO", sizes=[(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)])
        print("[✔] Created Orbital Cybernetic Icon: " + icon_path)
        return True
    except Exception as e:
        print("[!] Icon generation note: " + str(e))
        return False

def package_flashdrive():
    print("=================================================================")
    print("   ORBITAL PORTABLE FLASH DRIVE PACKAGER & ICON INITIALIZER      ")
    print("=================================================================")

    source_dir = r"C:\Orbital"
    target_dir = r"C:\Orbital_FlashDrive"

    if not os.path.exists(source_dir):
        os.makedirs(source_dir, exist_ok=True)

    print("[*] Target Portable Directory: " + target_dir)
    os.makedirs(target_dir, exist_ok=True)

    folders = ["Nucleus", "dist", "assets"]
    for folder in folders:
        os.makedirs(os.path.join(target_dir, folder), exist_ok=True)

    icon_path = os.path.join(target_dir, "orbital_icon.ico")
    create_orbital_icon(icon_path)

    files_to_copy = [
        "orbitalchat_gui.py",
        "engine.py",
        "setup_orbital_sd.py",
        "orbital_sync_engine.py",
        "gibberlink_websocket_gateway-v2.py",
        "wifi_csi_sensing-v2.py",
        "LAUNCH_ORBITAL_HUD.bat",
        "LAUNCH_ORBITAL_FULL.bat",
        "launch_orbital_gui.vbs",
        "launch_nucleus_silent.vbs",
        "setup_orbital_fully_integrated.py",
        "package_orbital_flashdrive.py"
    ]

    print("[*] Packaging core scripts & runtimes...")
    for fname in files_to_copy:
        src = os.path.join(source_dir, fname)
        if os.path.exists(src):
            shutil.copy2(src, os.path.join(target_dir, fname))
            print("  [✔] Copied: " + fname)

    nucleus_src = os.path.join(source_dir, "Nucleus")
    nucleus_dst = os.path.join(target_dir, "Nucleus")
    if os.path.exists(nucleus_src):
        for item in os.listdir(nucleus_src):
            s = os.path.join(nucleus_src, item)
            d = os.path.join(nucleus_dst, item)
            if os.path.isfile(s):
                shutil.copy2(s, d)
                print("  [✔] Copied Nucleus Asset: " + item)

    autorun_path = os.path.join(target_dir, "autorun.inf")
    autorun_content = "[autorun]\nopen=LAUNCH_ORBITAL_HUD.bat\nicon=orbital_icon.ico\nlabel=Orbital Agent OS\n"
    with open(autorun_path, "w", encoding="utf-8") as f:
        f.write(autorun_content)
    print("[✔] Created autorun.inf drive branding")

    desktop_ini_path = os.path.join(target_dir, "desktop.ini")
    ini_content = "[.ShellClassInfo]\nIconResource=orbital_icon.ico,0\n[ViewState]\nMode=\nVid=\nFolderType=Generic\n"
    with open(desktop_ini_path, "w", encoding="utf-8") as f:
        f.write(ini_content)
    print("[✔] Created desktop.ini folder icon")

    try:
        subprocess.run(["attrib", "+h", autorun_path], capture_output=True)
        subprocess.run(["attrib", "+h", "+s", desktop_ini_path], capture_output=True)
        subprocess.run(["attrib", "+r", target_dir], capture_output=True)
    except Exception:
        pass

    user_desktop = os.path.join(os.path.expanduser("~"), "Desktop")
    shortcut_path = os.path.join(user_desktop, "Orbital Portable.lnk")
    vbs_target = os.path.join(target_dir, "launch_orbital_gui.vbs")

    ps_script = (
        "$WshShell = New-Object -comObject WScript.Shell; " +
        "$Shortcut = $WshShell.CreateShortcut('" + shortcut_path + "'); " +
        "$Shortcut.TargetPath = 'wscript.exe'; " +
        "$Shortcut.Arguments = '\"" + vbs_target + "\"'; " +
        "$Shortcut.WorkingDirectory = '" + target_dir + "'; " +
        "$Shortcut.IconLocation = '" + icon_path + "'; " +
        "$Shortcut.Save();"
    )

    try:
        subprocess.run(["powershell", "-Command", ps_script], capture_output=True, check=True)
        print("[✔] Created Desktop Shortcut: Orbital Portable.lnk")
    except Exception as e:
        print("[!] Shortcut note: " + str(e))

    print("=================================================================")
    print(" SUCCESS! Orbital Portable Flash Drive folder ready at:")
    print(" " + target_dir)
    print(" You can now copy the Orbital_FlashDrive folder to your USB drive!")
    print("=================================================================")

if __name__ == "__main__":
    package_flashdrive()
