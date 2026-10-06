import os, warnings, torch
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"
warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", category=UserWarning, module="huggingface_hub")

from diffusers import AutoPipelineForText2Image

class NebulaEngine:
    _pipe = None
    @classmethod
    def get_pipe(cls):
        if cls._pipe is None:
            print('[Nebula] Initializing real-time SD-Turbo engine...')
            device = "cuda" if torch.cuda.is_available() else "cpu"
            dtype = torch.float16 if device == "cuda" else torch.float32
            try:
                cls._pipe = AutoPipelineForText2Image.from_pretrained("stabilityai/sd-turbo", dtype=dtype)
            except (TypeError, ValueError):
                cls._pipe = AutoPipelineForText2Image.from_pretrained("stabilityai/sd-turbo", torch_dtype=dtype)

            cls._pipe.to(device)
            print(f"[Nebula] Engine active on {device.upper()}")
        return cls._pipe

    def generate_image(self, prompt, output_path=r"C:\Orbital\outputs\nebula_render.png", steps=1):
        pipe = self.get_pipe()
        img = pipe(prompt, num_inference_steps=steps, guidance_scale=0.0).images[0]
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        img.save(output_path)
        return output_path

_engine = NebulaEngine()

def generate_visual(prompt, output_path=None, is_video=False):
    out = output_path or r"C:\Orbital\outputs\nebula_render.png"
    saved = _engine.generate_image(prompt, out)
    return f"[Nebula Engine Render Complete] Image saved to {saved}"

process_nebula = generate_visual
