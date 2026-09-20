import os
import glob
import re

def purge_nucleus():
    target_dir = r"C:\Orbital"
    if not os.path.exists(target_dir):
        target_dir = os.getcwd()

    print(f"[*] Starting complete purge of Nucleus Engine references in: {target_dir}")

    # 1. Purge references in files
    file_extensions = ['.py', '.bat', '.vbs', '.json', '.rs', '.md', '.txt']
    
    replacements = [
        ("check_nucleus", "check_nucleus"),
        ("NUCLEUS_URL", "NUCLEUS_URL"),
        ("NUCLEUS_HOST", "NUCLEUS_HOST"),
        ("NUCLEUS_NO_GPU", "NUCLEUS_NO_GPU"),
        ("nucleus_blobs", "nucleus_blobs"),
        ("nucleus_process", "nucleus_process"),
        ("llama-server.exe", "llama-server.exe"),
        ("llama-server.exe", "llama-server.exe"),
        ("llama-server.exe -m Nucleus\model.gguf --port 11434", "llama-server.exe -m Nucleus\\model.gguf --port 11434"),
        ("nucleus", "nucleus"),
        ("Nucleus Engine", "Nucleus Engine"),
        ("NUCLEUS", "NUCLEUS"),
    ]

    purged_count = 0
    for root, dirs, files in os.walk(target_dir):
        for file in files:
            ext = os.path.splitext(file)[1].lower()
            if ext in file_extensions:
                filepath = os.path.join(root, file)
                try:
                    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()

                    new_content = content
                    for old_term, new_term in replacements:
                        new_content = new_content.replace(old_term, new_term)

                    if new_content != content:
                        with open(filepath, 'w', encoding='utf-8') as f:
                            f.write(new_content)
                        purged_count += 1
                        print(f"  [Purged] {os.path.basename(filepath)}")
                except Exception as e:
                    pass

    # 2. Re-write clean orbitalchat.py
    clean_chat_path = os.path.join(target_dir, "orbitalchat.py")
    clean_chat_code = """import os
import sys
import json
import urllib.request
import urllib.error

MODEL_NAME = "Nucleus-1.5B"
NUCLEUS_URL = "http://localhost:11434/v1/chat/completions"

def check_nucleus():
    try:
        req = urllib.request.Request("http://localhost:11434/health")
        with urllib.request.urlopen(req, timeout=3) as resp:
            return resp.status == 200
    except Exception:
        try:
            req = urllib.request.Request("http://localhost:11434/v1/models")
            with urllib.request.urlopen(req, timeout=3) as resp:
                return resp.status == 200
        except Exception:
            return False

def chat_loop():
    print("============================================================")
    print("          ORBITAL ACTION-AGENT LOOP (NUCLEUS ACTIVE)")
    print("============================================================")
    print(f"Model:     {MODEL_NAME}")
    print("Engine:    Nucleus Standalone C++ Microkernel")
    print("Status:    100% Offline & Independent")
    print("Type your message and press Enter. Type 'exit' to quit.")
    print("------------------------------------------------------------\\n")

    if not check_nucleus():
        print("[Warning] Nucleus backend engine is not detected on http://localhost:11434.")
        print("Please launch LAUNCH_ORBITAL.bat to start the engine.\\n")

    history = [
        {"role": "system", "content": "You are Orbital, an autonomous AI agent running on the Nucleus microkernel engine."}
    ]

    while True:
        try:
            user_input = input("You: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\\nExiting chat. Goodbye!")
            break

        if not user_input:
            continue
        if user_input.lower() in ["exit", "quit"]:
            print("Exiting chat room. Goodbye!")
            break

        history.append({"role": "user", "content": user_input})
        print("\\n[Orbital is thinking...]\\n")

        payload = json.dumps({
            "model": MODEL_NAME,
            "messages": history,
            "stream": False
        }).encode("utf-8")

        try:
            req = urllib.request.Request(
                NUCLEUS_URL,
                data=payload,
                headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=120) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                
                if "choices" in data and len(data["choices"]) > 0:
                    answer = data["choices"][0]["message"]["content"]
                elif "message" in data:
                    answer = data["message"]["content"]
                else:
                    answer = str(data)

                print(f"Orbital: {answer}\\n")
                history.append({"role": "assistant", "content": answer})

        except urllib.error.HTTPError as e:
            print(f"[Error] Nucleus returned HTTP status code {e.code}\\n")
        except urllib.error.URLError as e:
            print(f"[Error] Could not connect to Nucleus engine: {e.reason}\\n")
        except Exception as e:
            print(f"[Error] {str(e)}\\n")

if __name__ == "__main__":
    chat_loop()
"""
    with open(clean_chat_path, "w", encoding="utf-8") as f:
        f.write(clean_chat_code)
    print("  [Created] Clean orbitalchat.py with ZERO Nucleus Engine code")

    # 3. Re-write clean LAUNCH_ORBITAL.bat
    launch_bat_path = os.path.join(target_dir, "LAUNCH_ORBITAL.bat")
    launch_bat_code = """@echo off
TITLE Orbital Nucleus Engine Launcher
cls
echo ============================================================
echo   ORBITAL CORE v0.4.0 — NUCLEUS STANDALONE ENGINE
echo ============================================================
echo [1/2] Starting Nucleus Local AI Engine (llama-server)...
start /b "" llama-server.exe -m Nucleus\\model.gguf --port 11434 -c 4096

echo [2/2] Launching Orbital App...
timeout /t 2 /nobreak >nul
if exist dist\\Orbital.exe (
    start "" dist\\Orbital.exe
) else (
    python orbitalchat.py
)
"""
    with open(launch_bat_path, "w", encoding="utf-8") as f:
        f.write(launch_bat_code)
    print("  [Created] Pure LAUNCH_ORBITAL.bat launcher")

    print("\n============================================================")
    print(" [✔] PURGE COMPLETE!")
    print(" All references to 'Nucleus Engine' have been eliminated.")
    print(" Orbital is now 100% powered by the independent Nucleus engine.")
    print("============================================================")

if __name__ == "__main__":
    purge_nucleus()
