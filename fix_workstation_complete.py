p = r"C:\Orbital\gui\cyber_organic_workstation.html"
with open(p, "r", encoding="utf-8") as f:
    html = f.read()

# Ensure clean layout and working camera/terminal bindings
full_fix = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta http-equiv="Content-Type" content="text/html; charset=utf-8">
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
            margin: 0; padding: 0; background: var(--bg-dark); color: var(--text-main);
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            display: flex; height: 100vh; overflow: hidden;
        }
        .sidebar {
            width: 260px; background: var(--panel-bg); backdrop-filter: blur(12px);
            border-right: 1px solid var(--border); display: flex; flex-direction: column; padding: 20px; user-select: none;
        }
        .brand {
            font-size: 1.3rem; font-weight: 700; color: var(--accent-cyan); letter-spacing: 2px;
            margin-bottom: 25px; text-shadow: 0 0 10px var(--accent-glow); display: flex; align-items: center; gap: 8px;
        }
        .nav-item {
            padding: 12px 16px; margin-bottom: 8px; border-radius: 8px; cursor: pointer;
            color: var(--text-muted); transition: all 0.2s ease; font-size: 0.95rem; display: flex; align-items: center; gap: 10px;
        }
        .nav-item.active, .nav-item:hover {
            background: rgba(0, 229, 255, 0.12); color: var(--accent-cyan); border-left: 3px solid var(--accent-cyan);
        }
        .main-content {
            flex: 1; display: flex; flex-direction: column; height: 100vh; position: relative;
        }
        .header {
            height: 60px; border-bottom: 1px solid var(--border); display: flex;
            align-items: center; justify-content: space-between; padding: 0 25px; background: var(--panel-bg);
        }
        .status-badge {
            background: rgba(16, 185, 129, 0.15); color: #10B981; padding: 6px 14px;
            border-radius: 20px; font-size: 0.82rem; border: 1px solid rgba(16, 185, 129, 0.3); font-weight: 600;
        }
        .workstation-split {
            flex: 1; display: flex; height: calc(100vh - 60px); overflow: hidden;
        }
        .chat-section {
            flex: 1; display: flex; flex-direction: column; border-right: 1px solid var(--border); height: 100%;
        }
        .chat-container {
            flex: 1; padding: 25px; display: flex; flex-direction: column; gap: 15px; overflow-y: auto;
        }
        .chat-container::-webkit-scrollbar { width: 6px; }
        .chat-container::-webkit-scrollbar-thumb { background: var(--border); border-radius: 4px; }
        .message {
            max-width: 85%; padding: 12px 16px; border-radius: 10px; line-height: 1.5; font-size: 0.95rem; word-break: break-word;
        }
        .user-msg {
            align-self: flex-end; background: rgba(0, 229, 255, 0.15); border: 1px solid var(--border); color: #FFF;
        }
        .ai-msg {
            align-self: flex-start; background: var(--panel-bg); border: 1px solid var(--border); box-shadow: 0 4px 20px rgba(0,0,0,0.3);
        }
        .input-bar {
            padding: 15px 25px; background: var(--panel-bg); border-top: 1px solid var(--border); display: flex; gap: 12px;
        }
        input[type="text"] {
            flex: 1; background: rgba(11, 14, 20, 0.85); border: 1px solid var(--border); border-radius: 8px;
            padding: 12px 16px; color: #FFF; font-size: 0.95rem; outline: none;
        }
        input[type="text"]:focus {
            border-color: var(--accent-cyan); box-shadow: 0 0 10px var(--accent-glow);
        }
        button.send-btn {
            background: var(--accent-cyan); color: #0B0E14; border: none; border-radius: 8px;
            padding: 0 24px; font-weight: 700; cursor: pointer; transition: all 0.2s ease;
        }
        button.send-btn:hover { box-shadow: 0 0 15px var(--accent-glow); }
        .terminal-section {
            width: 48%; background: #000; display: flex; flex-direction: column; height: 100%;
        }
        .terminal-header {
            height: 35px; background: rgba(0, 229, 255, 0.1); border-bottom: 1px solid var(--border);
            color: var(--accent-cyan); font-size: 0.8rem; font-weight: bold; display: flex; align-items: center; padding: 0 15px; letter-spacing: 1px;
        }
        .terminal-frame {
            flex: 1; border: none; width: 100%; height: 100%;
        }
    </style>
</head>
<body>
    <div class="sidebar">
        <div class="brand">🛸 ORBITAL OS</div>
        <div class="nav-item active" onclick="alert('AI Chat Interface active.')">💬 AI Chat Interface</div>
        <div class="nav-item" onclick="toggleCamera()">📷 Camera Feed (Optical)</div>
        <div class="nav-item" onclick="alert('Nebula Engine: Ready for /draw')">🎨 Nebula Image Generator</div>
        <div class="nav-item" onclick="alert('Wi-Fi CSI: Listening on UDP 5555')">📡 Wi-Fi CSI Radar</div>
        <div class="nav-item" onclick="alert('Orbital Settings: Engine 5000 active.')">⚙️ System Settings</div>
    </div>
    <div class="main-content">
        <div class="header">
            <h3 style="margin:0;">Cyber-Organic Workstation</h3>
            <span class="status-badge">● Nucleus Local AI Active</span>
        </div>
        <div class="workstation-split">
            <div class="chat-section">
                <div class="chat-container" id="chat">
                    <div class="message ai-msg">
                        <strong>🛸 Orbital AI:</strong> Workstation initialized. Terminal link and optical stream ready.
                    </div>
                </div>
                <div class="input-bar">
                    <input type="text" id="userInput" placeholder="Ask Orbital anything..." onkeydown="if(event.key==='Enter') sendMsg()">
                    <button class="send-btn" onclick="sendMsg()">Send</button>
                </div>
            </div>
            <div class="terminal-section">
                <div class="terminal-header">LIVE INTERACTIVE CONSOLE (PORT 7681)</div>
                <iframe class="terminal-frame" src="http://127.0.0.1:7681/"></iframe>
            </div>
        </div>
    </div>

    <script>
        async function sendMsg() {
            const input = document.getElementById('userInput');
            const chat = document.getElementById('chat');
            if(!input.value.trim()) return;
            const val = input.value;
            chat.innerHTML += `<div class="message user-msg"><strong>You:</strong> ${val}</div>`;
            input.value = '';
            chat.scrollTop = chat.scrollHeight;

            const msgId = 'ai-msg-' + Date.now();
            chat.innerHTML += `<div class="message ai-msg" id="${msgId}"><strong>🛸 Orbital AI:</strong> <em>Thinking...</em></div>`;
            chat.scrollTop = chat.scrollHeight;

            try {
                const res = await fetch('http://127.0.0.1:5000/api/chat', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ prompt: val })
                });
                const data = await res.json();
                document.getElementById(msgId).innerHTML = `<strong>🛸 Orbital AI:</strong> ${data.response}`;
            } catch(err) {
                document.getElementById(msgId).innerHTML = `<strong>🛸 Orbital AI:</strong> [Error connecting to engine backend on port 5000]`;
            }
            chat.scrollTop = chat.scrollHeight;
        }

        async function toggleCamera() {
            let box = document.getElementById('orbital-cam-box');
            if (box) {
                if (box._stream) box._stream.getTracks().forEach(t => t.stop());
                box.remove();
                return;
            }

            box = document.createElement('div');
            box.id = 'orbital-cam-box';
            box.style.cssText = 'position:fixed; bottom:25px; right:25px; width:340px; height:260px; min-width:200px; min-height:160px; background:#0B0E14; border:2px solid #00E5FF; border-radius:12px; z-index:999999; box-shadow:0 0 25px rgba(0,229,255,0.4); display:flex; flex-direction:column; overflow:hidden; resize:both;';
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
                box.style.left = (initialX + (e.clientX - startX)) + "px";
                box.style.top = (initialY + (e.clientY - startY)) + "px";
            };

            window.onmouseup = function() { isDragging = false; };

            try {
                const stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: false });
                box._stream = stream;
                document.getElementById('orbital-cam-vid').srcObject = stream;
            } catch(err) {
                alert('Camera Access Error: ' + err.message);
                box.remove();
            }
        }
    </script>
</body>
</html>
"""

with open(p, "w", encoding="utf-8-sig") as f:
    f.write(full_fix)

print("[✔] Workstation interface fully rebuilt with working terminal & camera.")
