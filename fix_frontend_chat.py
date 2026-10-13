p = r"C:\Orbital\gui\cyber_organic_workstation.html"
with open(p, "r", encoding="utf-8-sig", errors="ignore") as f:
    c = f.read()

# Fix the broken iframe source so Chrome doesn't throw a blocking DOM exception
c = c.replace('src="http://127.0.0.1:7681/"', 'src="http://127.0.0.1:7681"')

# Ensure sendMsg has robust error catching and clears the input
old_send = """        async function sendMsg() {
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
        }"""

new_send = """        async function sendMsg() {
            const input = document.getElementById('userInput');
            const chat = document.getElementById('chat');
            if (!input || !chat) return;
            const val = input.value.trim();
            if (!val) return;

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
                const elem = document.getElementById(msgId);
                if (elem) elem.innerHTML = `<strong>🛸 Orbital AI:</strong> ${data.response}`;
            } catch(err) {
                const elem = document.getElementById(msgId);
                if (elem) elem.innerHTML = `<strong>🛸 Orbital AI:</strong> [Error connecting to engine backend on port 5000: ` + err.message + `]`;
            }
            chat.scrollTop = chat.scrollHeight;
        }"""

if "if (!input || !chat) return;" not in c:
    c = c.replace(old_send, new_send)

with open(p, "w", encoding="utf-8-sig") as f:
    f.write(c)
print("[✔] Frontend chat logic and console frame fixed.")
