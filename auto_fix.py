p = r"C:\Orbital\gui\cyber_organic_workstation.html"
with open(p, "r", encoding="utf-8") as f:
    html = f.read()

# 1. Wire the sidebar buttons with real onclick handlers
replacements = [
    ('<div class="nav-item">📷 Camera Feed (Optical)</div>', '<div class="nav-item" onclick="toggleCamera()">📷 Camera Feed (Optical)</div>'),
    ('<div class="nav-item">🎨 Nebula Image Generator</div>', '<div class="nav-item" onclick="alert(\'Nebula Active. Type /draw in chat\')">🎨 Nebula Image Generator</div>'),
    ('<div class="nav-item">📡 Wi-Fi CSI Radar</div>', '<div class="nav-item" onclick="alert(\'CSI Radar: Listening UDP 5555\')">📡 Wi-Fi CSI Radar</div>'),
    ('<div class="nav-item">⚙️ System Settings</div>', '<div class="nav-item" onclick="alert(\'Orbital OS: Port 5000 / Mesh 8765\')">⚙️ System Settings</div>')
]

for old, new in replacements:
    if old in html and "onclick" not in old:
        html = html.replace(old, new)

# 2. Inject Camera Feed function if missing
cam_script = """
<script>
async function toggleCamera() {
    let box = document.getElementById("orbital-cam-box");
    if (!box) {
        box = document.createElement("div");
        box.id = "orbital-cam-box";
        box.style.cssText = "position:fixed; bottom:25px; right:25px; width:340px; height:260px; background:#0B0E14; border:2px solid #00E5FF; border-radius:12px; z-index:999999; box-shadow:0 0 25px rgba(0,229,255,0.4); display:flex; flex-direction:column; overflow:hidden;";
        box.innerHTML = `
            <div style="background:rgba(0,229,255,0.2); color:#00E5FF; font-size:12px; font-weight:bold; padding:8px 12px; display:flex; justify-content:space-between; align-items:center; border-bottom:1px solid rgba(0,229,255,0.3);">
                <span>📷 OPTICAL HARDWARE FEED</span>
                <span style="cursor:pointer; font-size:14px;" onclick="document.getElementById('orbital-cam-box').remove()">✕</span>
            </div>
            <video id="orbital-cam-vid" autoplay playsinline style="width:100%; flex:1; object-fit:cover; background:#000;"></video>
        `;
        document.body.appendChild(box);
        try {
            const stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: false });
            document.getElementById("orbital-cam-vid").srcObject = stream;
        } catch(err) {
            alert("Camera Access Error: " + err.message);
            box.remove();
        }
    } else {
        box.remove();
    }
}
</script>
"""

if "function toggleCamera()" not in html:
    html = html.replace("</body>", cam_script + "\n</body>")

with open(p, "w", encoding="utf-8") as f:
    f.write(html)

print("[✔] HTML UI successfully updated.")
