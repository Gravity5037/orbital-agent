import os
import sys

def run_unconstrained_orbital_sd(prompt_arg=None):
    print("Stable Diffusion module ready.")

if __name__ == "__main__":
    arg = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else None
    run_unconstrained_orbital_sd(arg)
