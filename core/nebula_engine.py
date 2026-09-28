import os
import sys

class NebulaEngine:
    """
    Nebula Creative Suite
    Unrestricted Image, Video & Visual Asset Generator (Diffusers / PyTorch Native)
    """
    def __init__(self):
        self.device = "cuda" if self._has_cuda() else "cpu"
        self.initialized = False

    def _has_cuda(self):
        try:
            import torch
            return torch.cuda.is_available()
        except ImportError:
            return False

    def generate_image(self, prompt, output_path=r"C:\Orbital\outputs\nebula_render.png", width=1024, height=1024, steps=30):
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        try:
            import torch
            from diffusers import StableDiffusionXLPipeline
            pipe = StableDiffusionXLPipeline.from_pretrained("stabilityai/stable-diffusion-xl-base-1.0", torch_dtype=torch.float16 if self.device=="cuda" else torch.float32)
            pipe.to(self.device)
            image = pipe(prompt=prompt, num_inference_steps=steps, width=width, height=height).images[0]
            image.save(output_path)
            return {"status": "success", "path": output_path, "engine": "Nebula Diffusers Direct"}
        except Exception as e:
            from PIL import Image, ImageDraw
            img = Image.new("RGB", (width, height), color=(18, 18, 28))
            draw = ImageDraw.Draw(img)
            draw.text((40, height // 2), f"Nebula Unrestricted Engine\nPrompt: {prompt[:50]}...", fill=(0, 230, 255))
            img.save(output_path)
            return {"status": "fallback_render", "path": output_path, "note": str(e)}

    def generate_video_sequence(self, prompt, output_dir=r"C:\Orbital\outputs\video_frames", frames=24):
        os.makedirs(output_dir, exist_ok=True)
        generated_frames = []
        for i in range(frames):
            frame_path = os.path.join(output_dir, f"frame_{i:04d}.png")
            res = self.generate_image(f"{prompt} frame {i}", output_path=frame_path, width=512, height=512, steps=10)
            generated_frames.append(res["path"])
        return {"status": "success", "frames_count": len(generated_frames), "directory": output_dir}

nebula_instance = NebulaEngine()

def generate_visual(prompt, output_path=None, is_video=False):
    if is_video:
        return nebula_instance.generate_video_sequence(prompt)
    return nebula_instance.generate_image(prompt, output_path or r"C:\Orbital\outputs\nebula_gen.png")
