p = r"C:\Orbital\gui\cyber_organic_workstation.html"
with open(p, "r", encoding="utf-8") as f:
    c = f.read()

# Clean out the accidentally injected script fragments
import re
c = re.sub(r"\\n\s*Nebula Image Generator.*?'@\s*python C:\\Orbital\\enable_camera\.py", "", c, flags=re.DOTALL)

# Add clean HTML5 camera popup handler if not already present
cam_code = """
<script>
async function toggleCamera() {
    let box = document.getElementById("orbital-cam-box");
    if (!box) {
        box = document.createElement("div");
        box.id = "orbital-cam-box";
        box.style.cssText = "position:fixed; bottom:20px; right:20px; width:300px; height:230px; background:#0B0E14; border:2px solid #00E5FF; border-radius:10px; z-index:99999; box-shadow:0 0 15px rgba(0,229,255,0.4); display:flex; flex-direction:column; overflow:hidden;";
        box.innerHTML = `
            <div style="background:rgba(0,229,255,0.2); color:#00E5FF; font-size:11px; font-weight:bold; padding:6px 10px; display:flex; justify-content:space-between; align-items:center;">
                <span>📷 OPTICAL FEED</span>
                <span style="cursor:pointer;" onclick="document.getElementById('orbital-cam-box').remove()">✖</span>
            </div>
            <video id="orbital-cam-vid" autoplay playsinline style="width:100%; flex:1; object-fit:cover; background:#000;"></video>
        `;
        document.body.appendChild(box);
        try {
            const stream = await navigator.mediaDevices.getUserMedia({ video: true });
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

if "toggleCamera()" not in c:
    c = c.replace("</body>", cam_code + "</body>")

# Ensure sidebar has the clickable camera button
if "toggleCamera()" not in c.split('<div class="sidebar">')[1].split('</div>')[0] if '<div class="sidebar">' in c else False:
    c = c.replace('<div class="nav-item">🎨 Nebula Image Generator</div>', '<div class="nav-item" onclick="toggleCamera()">📷 Camera Feed (Optical)</div>\n        <div class="nav-item">🎨 Nebula Image Generator</div>')

with open(p, "w", encoding="utf-8") as f:
    f.write(c)

print("[OK] UI Cleaned & Camera Feed Ready")
