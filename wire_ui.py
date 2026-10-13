p = r"C:\Orbital\gui\cyber_organic_workstation.html"
with open(p, "r", encoding="utf-8") as f:
    html = f.read()

old_nav = """        <div class="nav-item active">💬 AI Chat Interface</div>
        <div class="nav-item">🎨 Nebula Image Generator</div>
        <div class="nav-item">📡 Wi-Fi CSI Radar</div>
        <div class="nav-item">⚙️ System Settings</div>"""

new_nav = """        <div class="nav-item active" onclick="showView('chat')">💬 AI Chat Interface</div>
        <div class="nav-item" onclick="toggleCamera()">📷 Camera Feed (Optical)</div>
        <div class="nav-item" onclick="showModal('nebula')">🎨 Nebula Image Generator</div>
        <div class="nav-item" onclick="showModal('csi')">📡 Wi-Fi CSI Radar</div>
        <div class="nav-item" onclick="showModal('settings')">⚙️ System Settings</div>"""

if 'onclick="toggleCamera()"' not in html:
    html = html.replace(old_nav, new_nav)

interactive_scripts = """
<div id="orbital-modal" style="display:none; position:fixed; inset:0; background:rgba(0,0,0,0.7); backdrop-filter:blur(8px); z-index:99998; align-items:center; justify-content:center;">
    <div style="background:#0F141F; border:2px solid #00E5FF; border-radius:12px; width:480px; padding:24px; box-shadow:0 0 30px rgba(0,229,255,0.3); color:#E2E8F0; position:relative;">
        <span onclick="closeModal()" style="position:absolute; top:12px; right:16px; cursor:pointer; color:#00E5FF; font-size:18px; font-weight:bold;">✕</span>
        <h3 id="modal-title" style="color:#00E5FF; margin-top:0;">Orbital Subsystem</h3>
        <div id="modal-body" style="font-size:14px; line-height:1.6; color:#94A3B8;"></div>
    </div>
</div>

<script>
function showModal(type) {
    const m = document.getElementById('orbital-modal');
    const t = document.getElementById('modal-title');
    const b = document.getElementById('modal-body');
    m.style.display = 'flex';
    if(type === 'nebula') {
        t.innerText = '🎨 Nebula Image Engine';
        b.innerHTML = '<p>Local PyTorch & Diffusers sub-second generator active.</p><p>To generate images, type <code>/draw &lt;prompt&gt;</code> directly in the chat bar below.</p>';
    } else if(type === 'csi') {
        t.innerText = '📡 Wi-Fi CSI Spatial Radar';
        b.innerHTML = '<p>Listening on UDP port 5555 for ESP32 / 802.11bf subcarrier frames.</p><p>Status: <strong>Standby / Variance Tracking Active</strong></p>';
    } else if(type === 'settings') {
        t.innerText = '⚙️ Orbital System Settings';
        b.innerHTML = '<p><strong>Engine Port:</strong> 5000<br><strong>Nucleus Port:</strong> 11434<br><strong>Mesh WS:</strong> 8765<br><strong>Mode:</strong> Hybrid Standalone / Hive</p>';
    }
}
function closeModal() {
    document.getElementById('orbital-modal').style.display = 'none';
}
function showView(view) {
    closeModal();
}
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

if 'id="orbital-modal"' not in html:
    html = html.replace("</body>", interactive_scripts + "\n</body>")

with open(p, "w", encoding="utf-8") as f:
    f.write(html)

print("[✔] Sidebar buttons wired up.")
