p = r"C:\Orbital\gui\cyber_organic_workstation.html"
with open(p, "r", encoding="utf-8-sig") as f:
    html = f.read()

# Make the camera box CSS resizable and add size controls/constraints
new_cam_box_style = "box.style.cssText = \"position:fixed; bottom:25px; right:25px; width:340px; height:260px; min-width:200px; min-height:160px; background:#0B0E14; border:2px solid #00E5FF; border-radius:12px; z-index:999999; box-shadow:0 0 25px rgba(0,229,255,0.4); display:flex; flex-direction:column; overflow:hidden; resize:both;\";"

# Insert the resize handler and dynamic visual indicator on the box internally
new_cam_interior = """
    box.innerHTML = `
        <div id="orbital-cam-header" style="background:rgba(0,229,255,0.25); color:#00E5FF; font-size:12px; font-weight:bold; padding:8px 12px; display:flex; justify-content:space-between; align-items:center; cursor:move; user-select:none; border-bottom:1px solid rgba(0,229,255,0.3);">
            <span>📷 OPTICAL FEED (DRAG HERE)</span>
            <span style="cursor:pointer; font-size:16px; font-weight:bold; padding:0 4px;" onclick="toggleCamera()">✕</span>
        </div>
        <video id="orbital-cam-vid" autoplay playsinline style="width:100%; height:calc(100% - 31px); object-fit:cover; background:#000; pointer-events:none;"></video>
        <div style="position:absolute; bottom:0; right:0; width:12px; height:12px; cursor:se-resize; pointer-events:none; background:linear-gradient(135deg, transparent 60%, #00E5FF 60%); border-radius:0 0 10px 0;"></div>
    `;
"""

import re
# Look for box.style.cssText configuration in the toggleCamera function
if 'box.style.cssText = "position:fixed; bottom:25px; right:25px; width:340px; height:260px; min-width:200px; min-height:160px;' in html or "resize:both" not in html:
    html = re.sub(r'box\.style\.cssText = "[^"]+";', new_cam_box_style, html, count=1)
    
# Substitute the inner HTML with the explicit bottom-right resize drag affordance
html = re.sub(r'box\.innerHTML = `[\s\S]*?`;', new_cam_interior.strip(), html, count=1)

with open(p, "w", encoding="utf-8-sig") as f:
    f.write(html)
print("[✔] Drag-and-resize webcam upgrade applied.")
