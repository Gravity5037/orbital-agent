import os
import sys
import json
import urllib.request
import subprocess

def check_and_install():
    pkgs = ["torch", "diffusers", "transformers", "accelerate", "pillow"]
    for p in pkgs:
        try:
            __import__(p)
        except ImportError:
            subprocess.run([sys.executable, "-m", "pip", "install", p], check=True)

def run_sd(prompt=None):
    try:
        import torch
        from diffusers import StableDiffusionPipeline

        device = "cuda" if torch.cuda.is_available() else "cpu"
        pipe = StableDiffusionPipeline.from_pretrained(
            "runwayml/stable-diffusion-v1-5",
            torch_dtype=torch.float16 if device == "cuda" else torch.float32,
            safety_checker=None,
            requires_safety_checker=False
        ).to(device)

        prompt_str = prompt if prompt else "a detailed photo of a dog"
        image = pipe(prompt_str, num_inference_steps=25, guidance_scale=7.5).images[0]
        
        out_dir = r"C:\Orbital"
        os.makedirs(out_dir, exist_ok=True)
        out_path = os.path.join(out_dir, "orbital_sd_output.png")
        image.save(out_path)
    except Exception as e:
        print(f"SD Error: {e}")

if __name__ == "__main__":
    check_and_install()
    arg = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else None
    run_sd(arg)
