import re
p = r"C:\Orbital\gui\cyber_organic_workstation.html"
with open(p, "r", encoding="utf-8") as f:
    html = f.read()

# 1. Point the terminal iframe to the PC host for shared console sessions
html = re.sub(r'src="http://127\.0\.0\.1:7681/?"', 'src="http://10.0.0.129:7681/"', html)

# 2. Inject the real-time polling worker
sync_script = """
<script>
    // Real-Time Hive Sync Worker
    let lastLogLength = -1;
    setInterval(async () => {
        try {
            const res = await fetch('http://10.0.0.129:5000/api/sync');
            const data = await res.json();
            if (data.log && data.log.length !== lastLogLength) {
                lastLogLength = data.log.length;
                const chat = document.getElementById('chat');
                let newHTML = `<div class="message ai-msg"><strong>🛸 Orbital AI:</strong> Hive Link Synced.</div>`;
                data.log.forEach(msg => {
                    let isUser = msg.sender === 'user';
                    let cssClass = isUser ? 'user-msg' : 'ai-msg';
                    let prefix = isUser ? 'You' : '🛸 Orbital AI';
                    newHTML += `<div class="message ${cssClass}"><strong>${prefix}:</strong> <span style="white-space:pre-wrap;">${msg.text}</span></div>`;
                });
                chat.innerHTML = newHTML;
                chat.scrollTop = chat.scrollHeight;
            }
        } catch(err) {}
    }, 1000);
</script>
"""
if "Real-Time Hive Sync Worker" not in html:
    html = html.replace("</body>", sync_script + "\n</body>")
    with open(p, "w", encoding="utf-8-sig") as f:
        f.write(html)
    print("[✔] Real-time UI sync injected. Terminal iframe routed to PC.")
else:
    print("[!] Sync worker already present.")
