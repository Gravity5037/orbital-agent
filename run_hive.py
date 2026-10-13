import socket
print("[*] Initializing Hive Link Node...")
hostname = socket.gethostname()
local_ip = socket.gethostbyname(hostname)
print(f"[✔] PC Node active on host: {hostname} ({local_ip})")
print("[✔] Awaiting client connections on 0.0.0.0:5000...")
