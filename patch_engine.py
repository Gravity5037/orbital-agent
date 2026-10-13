p = r"C:\Orbital\engine.py"
with open(p, "r", encoding="utf-8") as f:
    c = f.read()

cam_code = """
            if p.lower() in ["/camera", "/cam", "camera:toggle"]:
                import subprocess
                subprocess.Popen(["python.exe", r"C:\\Orbital\\cam_window.py"])
                reply = "[✔] Native Optical window launched."
"""

if "/camera" not in c:
    c = c.replace("if p.startswith('/ps '):", cam_code + "\n            elif p.startswith('/ps '):")
    with open(p, "w", encoding="utf-8") as f:
        f.write(c)

# Update the workstation button handler
hp = r"C:\Orbital\gui\cyber_organic_workstation.html"
with open(hp, "r", encoding="utf-8") as f:
    h = f.read()

h = h.replace("document.getElementById('btn-camera').addEventListener('click', toggleCamera);", 
"""document.getElementById('btn-camera').addEventListener('click', () => {
    fetch('http://127.0.0.1:5000/api/chat', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({prompt: '/camera'})
    });
});""")

with open(hp, "w", encoding="utf-8") as f:
    f.write(h)

print("[✔] Native camera window fully configured.")
