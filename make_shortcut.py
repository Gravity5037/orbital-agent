import os
import subprocess
from PIL import Image, ImageDraw

def create_logo_and_shortcut():
    orbital_dir = r"C:\Orbital"
    flashdrive_dir = r"C:\Orbital_FlashDrive"
    
    if not os.path.exists(orbital_dir):
        os.makedirs(orbital_dir, exist_ok=True)
        
    ico_path = os.path.join(orbital_dir, "orbital_logo.ico")
    
    # Generate 256x256 Glowing Iridescent Orb Icon
    img = Image.new('RGBA', (256, 256), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.ellipse((16, 16, 240, 240), fill=(10, 14, 26, 255), outline=(0, 242, 254, 255), width=6)
    draw.ellipse((48, 48, 208, 208), fill=(139, 92, 246, 200))
    draw.ellipse((80, 80, 176, 176), fill=(0, 242, 254, 230))
    
    img.save(ico_path, format='ICO')
    print(f"[✔] Glowing Orb icon generated at: {ico_path}")

    target_gui = os.path.join(flashdrive_dir, "orbital_login_gui.py")

    ps_script = (
        '$ws = New-Object -ComObject WScript.Shell; '
        '$desktop = [System.IO.Path]::Combine($env:USERPROFILE, "Desktop"); '
        '$shortcutPath = [System.IO.Path]::Combine($desktop, "Launch Orbital.lnk"); '
        '$s = $ws.CreateShortcut($shortcutPath); '
        '$s.TargetPath = "pythonw.exe"; '
        f'$s.Arguments = "{target_gui}"; '
        f'$s.WorkingDirectory = "{flashdrive_dir}"; '
        f'$s.IconLocation = "{ico_path},0"; '
        '$s.Save();'
    )
    
    subprocess.run(["powershell", "-NoProfile", "-Command", ps_script], check=True)
    print("[✔] 'Launch Orbital' Desktop shortcut created successfully with glowing logo icon!")

if __name__ == "__main__":
    create_logo_and_shortcut()