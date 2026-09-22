import os
import json
import zipfile
import urllib.request

nucleus_dir = os.path.join(os.getcwd(), "Nucleus")
os.makedirs(nucleus_dir, exist_ok=True)

api_url = "https://api.github.com/repos/ggerganov/llama.cpp/releases/latest"
headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

print("🔍 Searching for latest llama.cpp release binaries...")
zip_url = None

try:
    req = urllib.request.Request(api_url, headers=headers)
    with urllib.request.urlopen(req) as response:
        data = json.loads(response.read().decode())
        for asset in data.get("assets", []):
            name = asset.get("name", "").lower()
            if "bin-win-avx2-x64.zip" in name or "bin-win-x64.zip" in name:
                zip_url = asset.get("browser_download_url")
                print(f"📦 Found release package: {asset.get('name')}")
                break
except Exception as e:
    print(f"⚠️ Could not reach GitHub API: {e}")

if not zip_url:
    zip_url = "https://github.com/ggerganov/llama.cpp/releases/download/b4800/llama-b4800-bin-win-avx2-x64.zip"
    print(f"📦 Using fallback package: llama-b4800-bin-win-avx2-x64.zip")

zip_path = os.path.join(nucleus_dir, "llama_engine.zip")
print(f"⬇️ Downloading engine binaries into Nucleus folder...")

req_dl = urllib.request.Request(zip_url, headers=headers)
with urllib.request.urlopen(req_dl) as resp, open(zip_path, "wb") as out_file:
    out_file.write(resp.read())

print("📦 Extracting llama-server.exe and runtime DLLs...")
with zipfile.ZipFile(zip_path, 'r') as zip_ref:
    zip_ref.extractall(nucleus_dir)

if os.path.exists(zip_path):
    os.remove(zip_path)

print("\n==================================================")
print(" [✔] llama-server.exe downloaded & unpacked successfully!")
print("==================================================")