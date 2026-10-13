p = r"C:\Orbital\gui\cyber_organic_workstation.html"
html = """<!DOCTYPE html>
<html lang="en">
<head>
    <title>Orbital OS - Host Node</title>
    <style>
        body { margin: 0; background: #0B0E14; color: #E2E8F0; font-family: 'Segoe UI', sans-serif; display: flex; height: 100vh; overflow: hidden; }
        .sidebar { width: 260px; background: rgba(18, 24, 38, 0.85); border-right: 1px solid rgba(0, 229, 255, 0.2); padding: 20px; }
        .main-content { flex: 1; display: flex; flex-direction: column; }
        .header { height: 60px; border-bottom: 1px solid rgba(0, 229, 255, 0.2); display: flex; align-items: center; padding: 0 25px; }
        .workstation-split { flex: 1; display: flex; }
        .chat-section { flex: 1; display: flex; flex-direction: column; border-right: 1px solid rgba(0, 229, 255, 0.2); }
        .chat-container { flex: 1; padding: 25px; overflow-y: auto; display: flex; flex-direction: column; gap: 15px; }
        .input-bar { padding: 15px 25px; background: rgba(18, 24, 38, 0.85); border-top: 1px solid rgba(0, 229, 255, 0.2); display: flex; gap: 12px; }
        input { flex: 1; background: rgba(11, 14, 20, 0.85); border: 1px solid rgba(0, 229, 255, 0.2); border-radius: 8px; padding: 12px 16px; color: #FFF; outline: none; }
        button { background: #00E5FF; color: #0B0E14; border: none; border-radius: 8px; padding: 0 24px; font-weight: bold; cursor: pointer; }
        .terminal-section { width: 50%; background: #000; }
        iframe { width: 100%; height: 100%; border: none; }
    </style>
</head>
<body>
    <div class="sidebar">
        <h3 style="color:#00E5FF; letter-spacing:2px;">🛸 ORBITAL OS</h3>
        <p style="color:#94A3B8; cursor:pointer;">💬 Hive Chat Sync</p>
    </div>
    <div class="main-content">
        <div class="header"><h3 style="margin:0;">Cyber-Organic Workstation</h3></div>
        <div class="workstation-split">
            <div class="chat-section">
                <div class="chat-container" id="chat"></div>
                <div class="input-bar">
                    <input type="text" id="userInput" onkeydown="if(event.key==='Enter') sendMsg()">
                    <button onclick="sendMsg()">Send</button>
                </div>
            </div>
            <div class="terminal-section">
                <iframe src="http://127.0.0.1:7681/"></iframe>
            </div>
        </div>
    </div>
    <script>
        let lastLog = -1;
        setInterval(async () => {
            try {
                const res = await fetch('http://127.0.0.1:5000/api/sync');
                const data = await res.json();
                if(data.log && data.log.length !== lastLog) {
                    lastLog = data.log.length;
                    document.getElementById('chat').innerHTML = data.log.map(m => {
                        let isU = m.sender === 'user';
                        return `<div style="max-width:85%; padding:12px; margin-bottom:10px; border-radius:10px; align-self:${isU ? 'flex-end' : 'flex-start'}; background:${isU ? 'rgba(0,229,255,0.15)' : 'rgba(18,24,38,0.85)'}; border:1px solid rgba(0,229,255,0.2); color:#FFF;"><strong>${isU ? 'You' : '🛸 Orbital'}:</strong> <span style="white-space:pre-wrap">${m.text}</span></div>`;
                    }).join('');
                    document.getElementById('chat').scrollTop = document.getElementById('chat').scrollHeight;
                }
            } catch(e) {}
        }, 1000);
        async function sendMsg() {
            const v = document.getElementById('userInput').value;
            if(!v.trim()) return;
            document.getElementById('userInput').value = '';
            fetch('http://127.0.0.1:5000/api/chat', { method: 'POST', body: JSON.stringify({prompt: v}) });
        }
    </script>
</body>
</html>"""
with open(p, "w", encoding="utf-8") as f:
    f.write(html)
print("[✔] PC Workstation UI structural layout repaired.")
