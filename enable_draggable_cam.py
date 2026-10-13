p = r"C:\Orbital\gui\cyber_organic_workstation.html"
with open(p, "r", encoding="utf-8") as f:
    html = f.read()

# Replace toggleCamera with fully draggable and dismissible floating modal
import re
new_cam_func = """
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
            <span>📷 OPTICAL HARDWARE FEED (DRAG HERE)</span>
            <span style="cursor:pointer; font-size:16px; font-weight:bold; padding:0 4px;" onclick="toggleCamera()">✕</span>
        </div>
        <video id="orbital-cam-vid" autoplay playsinline style="width:100%; flex:1; object-fit:cover; background:#000; pointer-events:none;"></video>
    `;
    document.body.appendChild(box);

    // Draggable behavior via header
    const header = document.getElementById("orbital-cam-header");
    let isDragging = false, startX, startY, initX, initY;

    header.onmousedown = (e) => {
        isDragging = true;
        startX = e.clientX;
        startY = e.clientY;
        const rect = box.getBoundingClientRect();
        initX = rect.left;
        initY = rect.top;
        box.style.right = "auto";
        box.style.bottom = "auto";
        box.style.left = initX + "px";
        box.style.top = initY + "px";
        document.onmousemove = (ev) => {
            if (!isDragging) return;
            box.style.left = (initX + (ev.clientX - startX)) + "px";
            box.style.top = (initY + (ev.clientY - startY)) + "px";
        };
        document.onmouseup = () => {
            isDragging = false;
            document.onmousemove = null;
            document.onmouseup = null;
        };
    };

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

# Replace existing toggleCamera definition
if "async function toggleCamera()" in html:
    html = re.sub(r"async function toggleCamera\(\)\s*\{[\s\S]*?\n\}", new_cam_func.strip(), html)
    with open(p, "w", encoding="utf-8-sig") as f:
        f.write(html)
    print("[✔] Draggable webcam upgraded successfully.")
else:
    print("[!] toggleCamera function not located.")
