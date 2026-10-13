p = r"C:\Orbital\gui\cyber_organic_workstation.html"
with open(p, "r", encoding="utf-8") as f:
    html = f.read()

# Ensure camera button invokes toggleCamera()
html = html.replace('<div class="nav-item">📷 Camera Feed (Optical)</div>', '<div class="nav-item" onclick="toggleCamera()">📷 Camera Feed (Optical)</div>')

draggable_func = """
async function toggleCamera() {
    let box = document.getElementById("orbital-cam-box");
    if (box) {
        if (box._stream) {
            box._stream.getTracks().forEach(t => t.stop());
        }
        box.remove();
        return;
    }

    box = document.createElement("div");
    box.id = "orbital-cam-box";
    box.style.cssText = "position:fixed; bottom:25px; right:25px; width:340px; height:260px; min-width:200px; min-height:160px; background:#0B0E14; border:2px solid #00E5FF; border-radius:12px; z-index:999999; box-shadow:0 0 25px rgba(0,229,255,0.4); display:flex; flex-direction:column; overflow:hidden; resize:both;";
    box.innerHTML = `
        <div id="orbital-cam-header" style="background:rgba(0,229,255,0.25); color:#00E5FF; font-size:12px; font-weight:bold; padding:8px 12px; display:flex; justify-content:space-between; align-items:center; cursor:move; user-select:none; border-bottom:1px solid rgba(0,229,255,0.3);">
            <span>📷 OPTICAL FEED (DRAG HERE)</span>
            <span style="cursor:pointer; font-size:14px;" onclick="let b=document.getElementById('orbital-cam-box'); if(b._stream){b._stream.getTracks().forEach(t=>t.stop());} b.remove();">✕</span>
        </div>
        <video id="orbital-cam-vid" autoplay playsinline style="width:100%; flex:1; object-fit:cover; background:#000;"></video>
    `;
    document.body.appendChild(box);

    let isDragging = false, startX, startY, initialX, initialY;
    document.getElementById("orbital-cam-header").onmousedown = function(e) {
        isDragging = true;
        startX = e.clientX;
        startY = e.clientY;
        initialX = box.offsetLeft;
        initialY = box.offsetTop;
        box.style.position = "fixed";
        box.style.bottom = "auto";
        box.style.right = "auto";
        box.style.left = initialX + "px";
        box.style.top = initialY + "px";
        e.preventDefault();
    };

    window.onmousemove = function(e) {
        if (!isDragging) return;
        let dx = e.clientX - startX;
        let dy = e.clientY - startY;
        box.style.left = (initialX + dx) + "px";
        box.style.top = (initialY + dy) + "px";
    };

    window.onmouseup = function() { isDragging = false; };

    try {
        const stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: false });
        box._stream = stream;
        document.getElementById("orbital-cam-vid").srcObject = stream;
    } catch(err) {
        alert("Camera Access Error: " + err.message);
        box.remove();
    }
}
"""

if "function toggleCamera()" in html:
    import re
    html = re.sub(r'async function toggleCamera\(\)\s*\{.*?\}(?=\s*(?:async function|\<\!DOCTYPE|</html>|\Z))', draggable_func, html, flags=re.DOTALL)
else:
    html = html.replace("</body>", f"<script>{draggable_func}</script>\n</body>")

with open(p, "w", encoding="utf-8") as f:
    f.write(html)

print("[✔] Draggable camera successfully configured.")
