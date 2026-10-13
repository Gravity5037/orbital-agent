ui_path = r"C:\Orbital\gui\cyber_organic_workstation.html"

with open(ui_path, "r", encoding="utf-8") as f:
    html = f.read()

btn_markup = """
    <div style="margin-top: 20px; padding: 12px; background: rgba(0, 240, 255, 0.05); border: 1px solid rgba(0, 240, 255, 0.2); border-radius: 12px; text-align: center;">
      <button onclick="triggerHeal()" style="background: linear-gradient(135deg, #00f0ff, #8a2be2); color: #fff; font-weight: bold; border: none; padding: 10px 18px; border-radius: 999px; cursor: pointer; box-shadow: 0 0 12px rgba(0,240,255,0.4); display: flex; align-items: center; justify-content: center; gap: 8px; width: 100%;">
        ⚡ Heal & Optimize
      </button>
      <div id="heal-status" style="font-size: 10px; color: rgba(255,255,255,0.6); margin-top: 6px;">Ralph Loop Standby</div>
    </div>
"""

script_markup = """
<script>
function triggerHeal() {
  const status = document.getElementById('heal-status');
  status.innerText = 'Scanning & Optimizing...';
  fetch('http://127.0.0.1:5000/api/chat', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({prompt: '/heal'})
  })
  .then(r => r.json())
  .then(data => {
    status.innerText = 'Heal Complete';
    const chat = document.querySelector('.chat-messages') || document.body;
    const msg = document.createElement('div');
    msg.style = 'background: rgba(0,240,255,0.1); border-left: 3px solid #00f0ff; padding: 10px; margin: 10px 0; border-radius: 6px; white-space: pre-wrap; font-family: monospace; font-size: 11px; color: #a6daff;';
    msg.innerText = data.response;
    chat.appendChild(msg);
  })
  .catch(err => {
    status.innerText = 'Engine unreachable';
  });
}
</script>
"""

if "triggerHeal" not in html:
    # Inject button right below the sidebar nav items
    html = html.replace('<!-- End Nav -->', btn_markup + '<!-- End Nav -->') if '<!-- End Nav -->' in html else html.replace('</aside>', btn_markup + '</aside>')
    html = html.replace('</body>', script_markup + '</body>')
    with open(ui_path, "w", encoding="utf-8") as f:
        f.write(html)
    print("[✔] Cyber-Organic UI updated with interactive Self-Heal button.")
else:
    print("[✔] Heal button already present in UI.")
