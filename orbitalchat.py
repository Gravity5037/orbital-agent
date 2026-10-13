import sys
from core.engine import process_chat

print("Orbital Nucleus AI Engine Active.")
print("Type /draw <prompt> for Nebula images or ask Nucleus anything.")
print("-------------------------------------------------------------")

while True:
    try:
        user_input = input("You: ")
        if user_input.lower() in ["exit", "quit"]:
            break
        reply = process_chat(user_input)
        print(f"Orbital: {reply}\n")
    except KeyboardInterrupt:
        break
