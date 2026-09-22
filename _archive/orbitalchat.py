import os
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
    print("------------------------------------------------------------\n")

    if not check_nucleus():
        print("[Warning] Nucleus backend engine is not detected on http://localhost:11434.")
        print("Please launch LAUNCH_ORBITAL.bat to start the engine.\n")

    history = [
        {"role": "system", "content": "You are Orbital, an autonomous AI agent running on the Nucleus microkernel engine."}
    ]

    while True:
        try:
            user_input = input("You: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nExiting chat. Goodbye!")
            break

        if not user_input:
            continue
        if user_input.lower() in ["exit", "quit"]:
            print("Exiting chat room. Goodbye!")
            break

        history.append({"role": "user", "content": user_input})
        print("\n[Orbital is thinking...]\n")

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

                print(f"Orbital: {answer}\n")
                history.append({"role": "assistant", "content": answer})

        except urllib.error.HTTPError as e:
            print(f"[Error] Nucleus returned HTTP status code {e.code}\n")
        except urllib.error.URLError as e:
            print(f"[Error] Could not connect to Nucleus engine: {e.reason}\n")
        except Exception as e:
            print(f"[Error] {str(e)}\n")

if __name__ == "__main__":
    chat_loop()
