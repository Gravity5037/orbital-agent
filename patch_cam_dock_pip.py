p = r"C:\Orbital\gui\cyber_organic_workstation.html"
with open(p, "r", encoding="utf-8-sig") as f:
    html = f.read()

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
    box.dataset.docked = "false";
    box.style.cssText = "position:fixed; bottom:25px; right:25px; width:340px; height:260px; min-width:220px; min-height:160px; background:#0B0E14; border:2px solid #00E5FF; border-radius:12px; z-index:999999; box-shadow:0 0 25px rgba(0,229,255,0.4); display:flex; flex-direction:column; overflow:hidden; resize:both;";
    box.innerHTML = `
        <div id="orbital-cam-header" style="background:rgba(0,229,255,0.25); color:#00E5FF; font-size:11px; font-weight:bold; padding:8px 10px; display:flex; justify-content:space-between; align-items:center; cursor:move; user-select:none; border-bottom:1px solid rgba(0,229,255,0.3);">
            <span>📷 OPTICAL FEED</span>
            <div style="display:flex; align-items:center; gap:8px;">
                <button title="Pop out into separate OS floating window" onclick="popOutPiP()" style="background:transparent; border:1px solid #00E5FF; color:#00E5FF; border-radius:4px; font-size:10px; padding:2px 6px; cursor:pointer;">Pop-Out</button>
                <button title="Snap / Dock to Workstation Side" onclick="toggleSnapDock()" style="background:transparent; border:1px solid #00E5FF; color:#00E5FF; border-radius:4px; font-size:10px; padding:2px 6px; cursor:pointer;">Snap</button>
                <span title="Close Feed" style="cursor:pointer; font-size:16px; font-weight:bold; padding:0 4px;" onclick="toggleCamera()">✕</span>
            </div>
        </div>
        <video id="orbital-cam-vid" autoplay playsinline style="width:100%; height:calc(100% - 33px); object-fit:cover; background:#000; pointer-events:auto;"></video>
        <div style="position:absolute; bottom:0; right:0; width:12px; height:12px; cursor:se-resize; pointer-events:none; background:linear-gradient(135deg, transparent 60%, #00E5FF 60%); border-radius:0 0 10px 0;"></div>
    `;
    document.body.appendChild(box);

    const header = document.getElementById("orbital-cam-header");
    let isDragging = false, startX, startY, initX, initY;
    header.onmousedown = (e) => {
        if (e.target.tagName === 'BUTTON' || e.target.tagName === 'SPAN') return;
        if (box.dataset.docked === "true") return;
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
        const vid = document.getElementById("orbital-cam-vid");
        vid.srcObject = stream;
    } catch(err) {
        alert("Camera Access Error: " + err.message);
        box.remove();
    }
}

async function popOutPiP() {
    const vid = document.getElementById("orbital-cam-vid");
    if (!vid) return;
    try {
        if (document.pictureInPictureElement) {
            await document.exitPictureInPicture();
        } else {
            await vid.requestPictureInPicture();
        }
    } catch (err) {
        alert("Picture-in-Picture Error: " + err.message);
    }
}

function toggleSnapDock() {
    const box = document.getElementById("orbital-cam-box");
    if (!box) return;
    if (box.dataset.docked === "true") {
        // Restore to floating
        box.dataset.docked = "false";
        box.style.position = "fixed";
        box.style.top = "auto";
        box.style.left = "auto";
        box.style.bottom = "25px";
        box.style.right = "25px";
        box.style.width = "340px";
        box.style.height = "260px";
        box.style.borderRadius = "12px";
        box.style.resize = "both";
    } else {
        // Snap dock to top-right of page
        box.dataset.docked = "true";
        box.style.position = "fixed";
        box.style.top = "60px";
        box.style.right = "0px";
        box.style.left = "auto";
        box.style.bottom = "auto";
        box.style.width = "320px";
        box.style.height = "240px";
        box.style.borderRadius = "0 0 0 12px";
        box.style.resize = "none";
    }
}
"""

html = re.sub(r"async function toggleCamera\(\)\s*\{[\s\S]*?\n\}", new_cam_func.strip(), html)

with open(p, "w", encoding="utf-8-sig") as f:
    f.write(html)
print("[✔] Snap dock and Pop-Out PiP window controls integrated.")
