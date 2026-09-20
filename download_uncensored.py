import os
import json
import urllib.request

nucleus_dir = r"C:\Orbital\Nucleus"
os.makedirs(nucleus_dir, exist_ok=True)
model_path = os.path.join(nucleus_dir, "model.gguf")

# Remove broken 29-byte file if present
if os.path.exists(model_path):
    os.remove(model_path)

api_url = "https://huggingface.co/api/models/mradermacher/Qwen2.5-Coder-1.5B-Instruct-abliterated-GGUF/tree/main"
headers = {"User-Agent": "Mozilla/5.0"}

print("🔍 Resolving exact uncensored GGUF model filename from Hugging Face...")
download_url = None

try:
    req = urllib.request.Request(api_url, headers=headers)
    with urllib.request.urlopen(req) as resp:
        files = json.loads(resp.read().decode())
        for f in files:
            path = f.get("path", "")
            if path.endswith(".gguf") and ("q4" in path.lower() or "q8" in path.lower() or "q5" in path.lower()):
                download_url = f"https://huggingface.co/mradermacher/Qwen2.5-Coder-1.5B-Instruct-abliterated-GGUF/resolve/main/{path}"
                print(f"📦 Found uncensored file: {path}")
                break
except Exception as e:
    print(f"⚠️ API lookup error: {e}")

if not download_url:
    download_url = "https://huggingface.co/Qwen/Qwen2.5-Coder-1.5B-Instruct-GGUF/resolve/main/qwen2.5-coder-1.5b-instruct-q4_k_m.gguf"
    print("📦 Using fallback GGUF download link...")

print("⬇️ Streaming model weights (~1.0 GB)...")

req_dl = urllib.request.Request(download_url, headers=headers)
with urllib.request.urlopen(req_dl) as response, open(model_path, "wb") as out_file:
    total_size = int(response.headers.get('Content-Length', 0))
    block_size = 1024 * 64
    downloaded = 0
    while True:
        buffer = response.read(block_size)
        if not buffer:
            break
        out_file.write(buffer)
        downloaded += len(buffer)
        if total_size > 0:
            percent = int(downloaded * 100 / total_size)
            mb = downloaded / (1024 * 1024)
            total_mb = total_size / (1024 * 1024)
            print(f"\rDownloading: {percent}% ({mb:.1f} / {total_mb:.1f} MB)", end="")

print("\n==================================================")
print(" [✔] Uncensored model.gguf downloaded successfully!")
print("==================================================")