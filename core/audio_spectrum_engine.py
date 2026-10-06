"""
ORBITAL OS - Real-Time Audio Spectrum Processing Engine
Converts discrete time-domain audio samples into frequency magnitude distributions via FFT
for acoustic context awareness and particle visualizer telemetry.
"""

import sys
import time
import math
import numpy as np

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

class AudioSpectrumEngine:
    def __init__(self, sample_rate=44100, fft_size=1024, num_bands=16):
        self.sample_rate = sample_rate
        self.fft_size = fft_size
        self.num_bands = num_bands
        self.latest_spectrum = [0.0] * num_bands
        self.peak_energy = 0.0

    def compute_fft_spectrum(self, audio_samples):
        """
        Transforms time-domain frame x[n] to frequency domain X[k] via Fast Fourier Transform:
        X[k] = sum_{n=0}^{N-1} x[n] * e^(-j * 2*pi*k*n / N)
        """
        if len(audio_samples) < self.fft_size:
            # Zero-pad if frame is shorter than FFT window
            samples = np.pad(audio_samples, (0, self.fft_size - len(audio_samples)), mode="constant")
        else:
            samples = audio_samples[:self.fft_size]

        # Apply Hanning window to reduce spectral leakage
        windowed = samples * np.hanning(len(samples))
        fft_complex = np.fft.rfft(windowed)
        magnitudes = np.abs(fft_complex)

        # Logarithmic binning into frequency bands (sub-bass, bass, mid, high, air)
        band_size = len(magnitudes) // self.num_bands
        bands = []
        for i in range(self.num_bands):
            start = i * band_size
            end = start + band_size
            band_val = float(np.mean(magnitudes[start:end])) if end > start else 0.0
            bands.append(round(band_val, 4))

        self.latest_spectrum = bands
        self.peak_energy = float(np.max(magnitudes)) if len(magnitudes) > 0 else 0.0
        return {
            "spectrum_bands": bands,
            "peak_energy": round(self.peak_energy, 4),
            "dominant_frequency_hz": float(np.argmax(magnitudes) * (self.sample_rate / self.fft_size))
        }

    def generate_simulated_acoustic_frame(self):
        """Generates realistic acoustic ambient audio frame for testing."""
        t = np.linspace(0, self.fft_size / self.sample_rate, self.fft_size, endpoint=False)
        # 440 Hz (A4) harmonic + 120 Hz room acoustic hum
        sig = 0.6 * np.sin(2 * np.pi * 440 * t) + 0.3 * np.sin(2 * np.pi * 120 * t) + 0.05 * np.random.randn(self.fft_size)
        return self.compute_fft_spectrum(sig)

if __name__ == "__main__":
    audio = AudioSpectrumEngine()
    print("Testing Audio Spectrum Engine FFT Processing...")
    frame = audio.generate_simulated_acoustic_frame()
    print("Computed 16-Band Spectral Magnitude Distribution:")
    print(frame["spectrum_bands"])
    print(f"Dominant Frequency: {frame['dominant_frequency_hz']} Hz | Peak Energy: {frame['peak_energy']}")
