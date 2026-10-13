p = r"C:\Orbital\gui\cyber_organic_workstation.html"

html = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Orbital OS - Cyber-Organic Workstation</title>
    <style>
        :root {
            --bg-dark: #0B0E14;
            --panel-bg: rgba(18, 24, 38, 0.85);
            --accent-cyan: #00E5FF;
            --accent-glow: rgba(0, 229, 255, 0.3);
            --text-main: #E2E8F0;
            --text-muted: #94A3B8;
            --border: rgba(0, 229, 255, 0.2);
        }
        * { box-sizing: border-box; }
        body {
            margin: 0; padding: 0;
            background: var(--bg-dark);
            color: var(--text-main);
            font-family: 'Segoe UI', Tahoma, sans-serif;
            display: flex; height: 100vh; overflow: hidden;
        }
        .sidebar {
            width: 250px;
            background: var(--panel-bg);
            border-right: 1px solid var(--border);
            display: flex; flex-direction: column;
            padding: 20px; user-select: none;
        }
        .brand {
            font-size: 1.3rem; font-weight: 700;
            color: var(--accent-cyan); letter-spacing: 2px;
            margin-bottom: 25px; text-shadow: 0 0 10px var(--accent-glow);
        }
        .nav-item {
            padding: 12px 14px; margin-bottom: 8px; border-radius: 8px;
            cursor: pointer; color: var(--text-muted); font-size: 0.95rem;
            transition: all 0.2s ease;
        }
        .nav-item.active, .nav-item:hover {
            background: rgba(0, 229, 255, 0.12);
            color: var(--accent-cyan);
            border-left: 3px solid var(--accent-cyan);
        }
        .main-content {
            flex: 1; display: flex; flex-direction: column; height: 100vh;
        }
        .header {
            height: 60px; border-bottom: 1px solid var(--border);
            display: flex; align-items: center; justify-content: space-between;
            padding: 0 25px; background: var(--panel-bg);
        }
        .status-badge {
            background: rgba(16, 185, 129, 0.15); color: #10B981;
            padding: 6px 14px; border-radius: 20px; font-size: 0.82rem;
            border: 1px solid rgba(16, 185, 129, 0.3); font-weight: 600;
        }
        .workstation-split {
            flex: 1; display: flex; height: calc(100vh - 60px); overflow: hidden;
        }
        .chat-section {
            flex: 1; display: flex; flex-direction: column;
            border-right: 1px solid var(--border); height: 100%;
        }
        .chat-container {
            flex: 1; padding: 25px; display: flex;
            flex-direction: column; gap: 15px; overflow-y: auto;
        }
        .message {
            max-width: 85%; padding: 12px 16px; border-radius: 10px;
            line-height: 1.5; font-size: 0.95rem; word-break: break-word;
        }
        .user-msg {
            align-self: flex-end; background: rgba(0, 229, 255, 0.15);
            border: 1px solid var(--border); color: #FFF;
        }
        .ai-msg {
            align-self: flex-start; background: var(--panel-bg);
            border: 1px solid var(--border);
        }
        .input-bar {
            padding: 15px 25px; background: var(--panel-bg);
            border-top: 1px solid var(--border); display: flex; gap: 12px;
        }
        #userInput {
            flex: 1; background: rgba(11, 14, 20, 0.85);
            border: 1px solid var(--border); border-radius: 8px;
            padding: 12px 16px; color: #FFF; font-size: 0.95rem; outline: none;
        }
        #userInput:focus {
            border-color: var(--accent-cyan); box-shadow: 0 0 10px var(--accent-glow);
        }
        .send-btn {
            background: var(--accent-cyan); color: #0B0E14; border: none;
            border-radius: 8px; padding: 0 24px; font-weight: 700;
            cursor: pointer; transition: all 0.2s ease;
        }
        .terminal-section {
            width: 48%; background: #000; display: flex; flex-direction: column; height: 100%;
        }
        .terminal-header {
            height: 35px; background: rgba(0, 229, 255, 0.1);
            border-bottom: 1px solid var(--border); color: var(--accent-cyan);
            font-size: 0.8rem; font-weight: bold; display: flex;
            align-items: center; padding: 0 15px; letter-spacing: 1px;
        }
        .terminal-frame {
            flex: 1; border: none; width: 100%; height: 100%;
        }
    </style>
</head>
<body>
    <div class="sidebar">
        <div class="brand">&#128760; ORBITAL OS</div>
        <div class="nav-item active" id="btn-chat">&#128172; AI Chat Interface</div>
        <div class="nav-item" id="btn-camera">&#128247; Camera Feed (Optical)</div>
        <div class="nav-item" id="btn-nebula">&#127912; Nebula Image Generator</div>
        <div class="nav-item" id="btn-csi">&#128225; Wi-Fi CSI Radar</div>
        <div class="nav-item" id="btn-settings">&#9881; System Settings</div>
    </div>
    <div class="main-content">
        <div class="header">
            <h3 style="margin:0;">Cyber-Organic Workstation</h3>
            <span class="status-badge">&bull; Nucleus Local AI Active</span>
        </div>
        <div class="workstation-split">
            <div class="chat-section">
                <div class="chat-container" id="chat">
                    <div class="message ai-msg">
                        <strong>&#128760; Orbital AI:</strong> Workstation initialized. Subsystems ready.
                    </div>
                </div>
                <div class="input-bar">
                    <input type="text" id="userInput" placeholder="Ask Orbital anything...">
                    <button class="send-btn" id="sendBtn">Send</button>
                </div>
            </div>
            <div class="terminal-section">
                <div class="terminal-header">LIVE INTERACTIVE CONSOLE</div>
                <iframe class="terminal-frame" src="http://127.0.0.1:7681"></iframe>
            </div>
        </div>
    </div>

    <script>
        // Chat Execution
        async function doSend() {
            const input = document.getElementById('userInput');
            const chat = document.getElementById('chat');
            if (!input || !chat) return;
            const text = input.value.trim();
            if (!text) return;

            chat.innerHTML += '<div class="message user-msg"><strong>You:</strong> ' + text + '</div>';
            input.value = '';
            chat.scrollTop = chat.scrollHeight;

            const msgId = 'ai-msg-' + Date.now();
            chat.innerHTML += '<div class="message ai-msg" id="' + msgId + '"><strong>&#128760; Orbital AI:</strong> <em>Thinking...</em></div>';
            chat.scrollTop = chat.scrollHeight;

            try {
                const res = await fetch('http://127.0.0.1:5000/api/chat', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ prompt: text })
                });
                const data = await res.json();
                document.getElementById(msgId).innerHTML = '<strong>&#128760; Orbital AI:</strong> ' + data.response;
            } catch(e) {
                document.getElementById(msgId).innerHTML = '<strong>&#128760; Orbital AI:</strong> [Error: ' + e.message + ']';
            }
            chat.scrollTop = chat.scrollHeight;
        }

        document.getElementById('sendBtn').addEventListener('click', doSend);
        document.getElementById('userInput').addEventListener('keydown', (e) => {
            if (e.key === 'Enter') {
                e.preventDefault();
                doSend();
            }
        });

        // Sidebar Actions
        document.getElementById('btn-nebula').addEventListener('click', () => {
            const input = document.getElementById('userInput');
            input.value = '/draw a cyber-organic orb core';
            input.focus();
        });

        document.getElementById('btn-csi').addEventListener('click', () => {
            const chat = document.getElementById('chat');
            chat.innerHTML += '<div class="message ai-msg"><strong>&#128225; Wi-Fi CSI Radar:</strong> UDP 5555 active. Sensing live human presence and respiration vectors.</div>';
            chat.scrollTop = chat.scrollHeight;
        });

        document.getElementById('btn-settings').addEventListener('click', () => {
            const chat = document.getElementById('chat');
            chat.innerHTML += '<div class="message ai-msg"><strong>&#9881; System Settings:</strong> Engine on Port 5000 | TTYD Console on Port 7681 | Mesh Hub on Port 8765.</div>';
            chat.scrollTop = chat.scrollHeight;
        });

        // Camera Feed (Draggable, Resizable, Snap, PiP Detached)
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
                    <span>&#128247; OPTICAL FEED</span>
                    <div style="display:flex; align-items:center; gap:6px;">
                        <button id="cam-pip-btn" style="background:transparent; border:1px solid #00E5FF; color:#00E5FF; border-radius:4px; font-size:10px; padding:2px 6px; cursor:pointer;">Pop-Out</button>
                        <button id="cam-snap-btn" style="background:transparent; border:1px solid #00E5FF; color:#00E5FF; border-radius:4px; font-size:10px; padding:2px 6px; cursor:pointer;">Snap</button>
                        <span id="cam-close-btn" style="cursor:pointer; font-size:16px; font-weight:bold; padding:0 4px;">&#10005;</span>
                    </div>
                </div>
                <video id="orbital-cam-vid" autoplay playsinline style="width:100%; height:calc(100% - 33px); object-fit:cover; background:#000; pointer-events:auto;"></video>
                <div style="position:absolute; bottom:0; right:0; width:12px; height:12px; cursor:se-resize; pointer-events:none; background:linear-gradient(135deg, transparent 60%, #00E5FF 60%); border-radius:0 0 10px 0;"></div>
            `;
            document.body.appendChild(box);

            document.getElementById('cam-close-btn').onclick = toggleCamera;
            
            document.getElementById('cam-pip-btn').onclick = async () => {
                const vid = document.getElementById("orbital-cam-vid");
                if (!vid) return;
                try {
                    if (document.pictureInPictureElement) {
                        await document.exitPictureInPicture();
                    } else {
                        await vid.requestPictureInPicture();
                    }
                } catch(err) {
                    alert('Pop-Out PiP Error: ' + err.message);
                }
            };

            document.getElementById('cam-snap-btn').onclick = () => {
                if (box.dataset.docked === "true") {
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
            };

            // Drag handler
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
                document.getElementById("orbital-cam-vid").srcObject = stream;
            } catch(err) {
                alert("Camera Access Error: " + err.message);
                box.remove();
            }
        }

        document.getElementById('btn-camera').addEventListener('click', toggleCamera);
    </script>
</body>
</html>
"""

with open(p, "w", encoding="utf-8") as f:
    f.write(html)
print("[✔] Workstation HTML compiled and verified.")
