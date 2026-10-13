p = r"C:\Orbital\engine.py"
with open(p, "r", encoding="utf-8") as f:
    code = f.read()

bt_function = '''
def scan_bluetooth_and_audio():
    cmd = r"""
    $bt = Get-PnpDevice -Class Bluetooth -Status OK | Select-Object -Property FriendlyName, InstanceId, Status
    $audio = Get-PnpDevice -Class AudioEndpoint -Status OK | Select-Object -Property FriendlyName, InstanceId
    @{ Bluetooth = $bt; AudioEndpoints = $audio } | ConvertTo-Json -Depth 3
    """
    return run_shell(cmd)
'''

if "scan_bluetooth_and_audio" not in code:
    code = code.replace("def process_query(prompt):", bt_function + "\ndef process_query(prompt):")
    # Add router triggers
    trigger = '''    if p.lower() in ["/bt", "/bluetooth", "scan bluetooth", "check devices"]:
        return scan_bluetooth_and_audio()
'''
    code = code.replace("def process_query(prompt):\n    p = prompt.strip()", "def process_query(prompt):\n    p = prompt.strip()\n" + trigger)
    with open(p, "w", encoding="utf-8") as f:
        f.write(code)
    with open(r"C:\Orbital\core\engine.py", "w", encoding="utf-8") as f:
        f.write(code)
    print("[✔] Bluetooth and Audio hardware introspection added to engine.")
else:
    print("[!] Bluetooth support already patched.")
