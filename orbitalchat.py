import os
import sys
import json
import urllib.request
import urllib.error
import subprocess
import platform

MODEL_NAME = "qwen2.5-coder:1.5b"
OLLAMA_URL = "http://localhost:11434/api/chat"

def get_system_info():
    specs = []
    specs.append("OS: " + platform.system() + " " + platform.release() + " (" + platform.version() + ")")
    specs.append("Processor: " + (platform.processor() or platform.machine()))
    try:
        import psutil
        mem = psutil.virtual_memory()
        ram_gb = round(mem.total / (1024**3), 2)
        ram_avail = round(mem.available / (1024**3), 2)
        specs.append("RAM: " + str(ram_gb) + " GB Total (" + str(ram_avail) + " GB Available)")
    except Exception:
        specs.append("RAM: psutil module not installed")
    return "\n".join(specs)

def execute_local_command(cmd_str):
    print("\n[Executing local command: " + cmd_str + "]\n")
    try:
        result = subprocess.run(cmd_str, shell=True, capture_output=True, text=True, timeout=60)
        out = result.stdout.strip() if result.stdout else ""
        err = result.stderr.strip() if result.stderr else ""
        if out:
            return out
        if err:
            return "[Stderr]:\n" + err
        return "[Command executed successfully with no output]"
    except Exception as e:
        return "[Execution Error]: " + str(e)

def check_ollama():
    try:
        req = urllib.request.Request("http://localhost:11434/api/tags")
        with urllib.request.urlopen(req, timeout=3) as resp:
            return resp.status == 200
    except Exception:
        return False

def chat_loop():
    print("============================================================")
    print("          ORBITAL ACTION-AGENT LOOP (OFFLINE)")
    print("============================================================")
    print("Model:     " + MODEL_NAME)
    print("Status:    CPU Mode + Local Execution Active")
    print("Tip:       Paste any 'python ...' or 'dir' command to execute!")
    print("------------------------------------------------------------")
    print("")

    if not check_ollama():
        print("[Error] Ollama service is not responding on http://localhost:11434.")
        print("Please ensure Ollama is running (e.g. 'start \"\" ollama serve').")
        print("")

    history = [
        {"role": "system", "content": "You are Orbital, an autonomous AI agent with local system access."}
    ]

    while True:
        try:
            user_input = input("You: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("")
            print("Exiting chat. Goodbye!")
            break

        if not user_input:
            continue
        if user_input.lower() in ["exit", "quit"]:
            print("Exiting chat room. Goodbye!")
            break

        # Check if user pasted a direct command or requested specs
        is_explicit_cmd = user_input.startswith("!") or user_input.lower().startswith(("python ", "pip ", "dir", "git ", "ollama ", "systeminfo", "powershell "))
        is_specs_req = any(word in user_input.lower() for word in ["specs", "hardware", "system info", "cpu", "ram"]) and any(v in user_input.lower() for v in ["show", "see", "check", "what"])

        if is_explicit_cmd:
            cmd = user_input[1:].strip() if user_input.startswith("!") else user_input
            out = execute_local_command(cmd)
            print("Orbita, (Command Output):")
            print(out)
            print("")
            continue

        if is_specs_req:
            specs_str = get_system_info()
            print("Orbital (System Specs):")
            print(specs_str)
            print("")
            continue

        history.append({"role": "user", "content": user_input})
        print("")
        print("[Orbital is thinking...]")
        print("")

        payload = json.dumps({
            "model": MODEL_NAME,
            "messages": history,
            "stream": False
        }).encode("utf-8")

        req = urllib.request.Request(
            OLLAMA_URL,
            data=payload,
            headers={"Content-Type": "application/json"}
        )

        try:
            with urllib.request.urlopen(req, timeout=120) as response:
                res_data = json.loads(response.read().decode("utf-8"))
                reply = res_data.get("message", {}).get("content", "").strip()
                print("Orbital:")
                print(reply)
                print("")
                history.append({"role": "assistant", "content": reply})
        except urllib.error.HTTPError as e:
            print("[Error] Ollama returned status code " + str(e.code))
            print("")
        except urllib.error.URLError as e:
            print("[Error] Connection failed: " + str(e))
            print("")
        except Exception as e:
            print("[Error] Unexpected error: " + str(e))
            print("")

if __name__ == "__main__":
    chat_loop()
