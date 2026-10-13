import os
from PIL import Image, ImageDraw
import subprocess

def create_logo_and_shortcut():
    target_dir = r"C:\Orbital"
    if not os.path.exists(target_dir):
        os.makedirs(target_dir, exist_ok=True)
        
    ico_path = os.path.join(target_dir, "orbital_logo.ico")
    
    # Generate Glowing Orb Icon
    img = Image.new('RGBA', (256, 256), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.ellipse((16, 16, 240, 240), fill=(10, 14, 26, 255), outline=(0, 242, 254, 255), width=6)
    draw.ellipse((48, 48, 208, 208), fill=(139, 92, 246, 200))
    draw.ellipse((80, 80, 176, 176), fill=(0, 242, 254, 230))
    
    try:
        img.save(ico_path, format='ICO')
        print(f"[✔] Logo icon saved: {ico_path}")
    except Exception as e:
        ico_path = "orbital_logo.ico"
        img.save(ico_path, format='ICO')
        print(f"[✔] Logo icon saved: {ico_path}")

    # Create shortcut using PowerShell
    ps_cmd = (
        '$s = (New-Object -ComObject WScript.Shell).CreateShortcut('
        '[System.IO.Path]::Combine($env:USERPROFILE, "Desktop", "Launch Orbital.lnk")); '
        '$s.TargetPath = "pythonw.exe"; '
        '$s.Arguments = "C:\\Orbital_FlashDrive\\orbital_login_gui.py"; '
        '$s.WorkingDirectory = "C:\\Orbital_FlashDrive"; '
        f'$s.IconLocation = "{ico_path},0"; '
        '$s.Save()'
    )
    
    try:
        subprocess.run(["powershell", "-Command", ps_cmd], check=True)
        print("[✔] 'Launch Orbital' shortcut created on Desktop with custom logo!")
    except Exception as e:
        print(f"[!] Shortcut created: {e}")

if __name__ == "__main__":
    create_logo_and_shortcut()
