p = r"C:\Orbital\gui\cyber_organic_workstation.html"
with open(p, "r", encoding="utf-8") as f:
    html = f.read()

# 1. Add the Biometric Nav Button to the sidebar
nav_old = '<div class="nav-item" onclick="toggleCamera()">📷 Camera Feed (Optical)</div>'
nav_new = '<div class="nav-item" onclick="toggleCamera()">📷 Camera Feed (Optical)</div>\n        <div class="nav-item" onclick="toggleBiometrics()">👁️ Biometric HUD (Face/Hands)</div>'

if nav_old in html and "toggleBiometrics()" not in html:
    html = html.replace(nav_old, nav_new)

# 2. Inject the Holistic Tracking Engine (Face, Hands, Pose)
bio_js = """
<script src="https://cdn.jsdelivr.net/npm/@mediapipe/camera_utils/camera_utils.js" crossorigin="anonymous"></script>
<script src="https://cdn.jsdelivr.net/npm/@mediapipe/drawing_utils/drawing_utils.js" crossorigin="anonymous"></script>
<script src="https://cdn.jsdelivr.net/npm/@mediapipe/holistic/holistic.js" crossorigin="anonymous"></script>

<script>
let bioActive = false;
let bioCamera = null;
let bioBox = null;

async function toggleBiometrics() {
    if (bioActive) {
        if (bioCamera) bioCamera.stop();
        if (bioBox) bioBox.remove();
        bioActive = false;
        return;
    }

    bioBox = document.createElement("div");
    bioBox.id = "orbital-bio-box";
    bioBox.style.cssText = "position:fixed; bottom:25px; left:280px; width:480px; height:360px; background:#0B0E14; border:2px solid #00FF9D; border-radius:12px; z-index:999999; box-shadow:0 0 25px rgba(0,255,157,0.4); display:flex; flex-direction:column; overflow:hidden; resize:both;";
    bioBox.innerHTML = `
        <div id="bio-header" style="background:rgba(0,255,157,0.2); color:#00FF9D; font-size:12px; font-weight:bold; padding:8px 12px; display:flex; justify-content:space-between; align-items:center; cursor:move; user-select:none; border-bottom:1px solid rgba(0,255,157,0.3);">
            <span>👁️ NEURAL HOLISTIC MESH (DRAG)</span>
            <span style="cursor:pointer; font-size:14px;" onclick="toggleBiometrics()">✕</span>
        </div>
        <div style="position:relative; flex:1; background:#000;">
            <video id="bio-video" autoplay playsinline style="display:none;"></video>
            <canvas id="bio-canvas" style="position:absolute; top:0; left:0; width:100%; height:100%; object-fit:cover; transform: scaleX(-1);"></canvas>
            <div id="bio-status" style="position:absolute; top:10px; left:10px; color:#00FF9D; font-family:monospace; font-size:12px; text-shadow:0 0 5px #000;">Booting Neural Models...</div>
        </div>
    `;
    document.body.appendChild(bioBox);
    bioActive = true;

    let isDragging = false, startX, startY, initialX, initialY;
    document.getElementById("bio-header").onmousedown = function(e) {
        isDragging = true; startX = e.clientX; startY = e.clientY;
        initialX = bioBox.offsetLeft; initialY = bioBox.offsetTop;
        bioBox.style.position = "fixed"; bioBox.style.bottom = "auto"; bioBox.style.right = "auto";
        bioBox.style.left = initialX + "px"; bioBox.style.top = initialY + "px"; e.preventDefault();
    };
    window.addEventListener("mousemove", e => { if(isDragging) { bioBox.style.left = (initialX + e.clientX - startX) + "px"; bioBox.style.top = (initialY + e.clientY - startY) + "px"; }});
    window.addEventListener("mouseup", () => { isDragging = false; });

    const videoElement = document.getElementById('bio-video
ghv




