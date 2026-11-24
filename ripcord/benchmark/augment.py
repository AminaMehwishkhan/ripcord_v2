"""
augment.py — make clean TTS speech sound like a call: noise, babble, phone
band, reverberation. All numpy/scipy, seeded for reproducibility.
"""
from __future__ import annotations

import numpy as np
from scipy import signal

SR = 16000


def rms(x: np.ndarray) -> float:
    return float(np.sqrt(np.mean(np.square(x)) + 1e-12))


def white(n: int, rng: np.random.Generator) -> np.ndarray:
    return rng.standard_normal(n).astype(np.float32)


def pink(n: int, rng: np.random.Generator) -> np.ndarray:
    spec = np.fft.rfft(rng.standard_normal(n))
    f = np.arange(len(spec), dtype=np.float64)
    f[0] = 1.0
    out = np.fft.irfft(spec / np.sqrt(f), n)
    return (out / (np.std(out) + 1e-9)).astype(np.float32)


def hum(n: int, rng: np.random.Generator) -> np.ndarray:
    t = np.arange(n) / SR
    f0 = rng.choice([50.0, 60.0])
    out = sum(np.sin(2 * np.pi * f0 * k * t + rng.uniform(0, 6.28)) / k for k in range(1, 6))
    return (out / (np.std(out) + 1e-9) * 0.7 + 0.3 * white(n, rng)).astype(np.float32)


def babble(n: int, rng: np.random.Generator, pool: list[np.ndarray]) -> np.ndarray:
    k = int(rng.integers(3, 6))
    out = np.zeros(n, dtype=np.float32)
    for _ in range(k):
        s = pool[int(rng.integers(0, len(pool)))]
        reps = int(np.ceil(n / len(s))) + 1
        s = np.tile(s, reps)
        off = int(rng.integers(0, len(s) - n)) if len(s) > n else 0
        out += s[off:off + n]
    return out / (np.std(out) + 1e-9)


def add_noise(clean: np.ndarray, kind: str, snr_db: float, rng: np.random.Generator,
              pool: list[np.ndarray]) -> np.ndarray:
    n = len(clean)
    gens = {"white": lambda: white(n, rng), "pink": lambda: pink(n, rng),
            "hum": lambda: hum(n, rng), "babble": lambda: babble(n, rng, pool)}
    noise = gens[kind]()
    noise = noise * (rms(clean) / (rms(noise) * (10 ** (snr_db / 20))))
    return (clean + noise).astype(np.float32)


def phone_band(x: np.ndarray) -> np.ndarray:
    """Narrow-band telephone: 300-3400 Hz, 8 kHz sampling, mu-law 8-bit round trip."""
    sos = signal.butter(4, [300, 3400], btype="band", fs=SR, output="sos")
    y = signal.sosfilt(sos, x)
    y = signal.resample_poly(y, 8000, SR)
    mu = 255.0
    y = np.clip(y / (np.max(np.abs(y)) + 1e-9), -1, 1)
    comp = np.sign(y) * np.log1p(mu * np.abs(y)) / np.log1p(mu)
    comp = np.round(comp * 127) / 127
    y = np.sign(comp) * ((1 + mu) ** np.abs(comp) - 1) / mu
    return signal.resample_poly(y, SR, 8000).astype(np.float32)


def reverb(x: np.ndarray, rt60: float, rng: np.random.Generator) -> np.ndarray:
    n = int(SR * rt60)
    t = np.arange(n) / SR
    rir = rng.standard_normal(n) * np.exp(-6.9 * t / rt60)
    rir[0] = 1.0
    rir = rir / np.sqrt(np.sum(rir ** 2))
    y = signal.fftconvolve(x, rir)[: len(x)]
    return (y * (rms(x) / (rms(y) + 1e-9))).astype(np.float32)


def resample_to_16k(x: np.ndarray, sr: int) -> np.ndarray:
    if sr == SR:
        return x.astype(np.float32)
    return signal.resample_poly(x, SR, sr).astype(np.float32)


CONDITIONS = [
    # (name, weight)
    ("clean", 0.16),
    ("snr25", 0.10),
    ("snr15", 0.17),
    ("snr10", 0.17),
    ("snr5", 0.16),
    ("snr0", 0.08),
    ("phone", 0.10),
    ("reverb", 0.06),
]


def apply_condition(clean: np.ndarray, condition: str, rng: np.random.Generator,
                    pool: list[np.ndarray]) -> tuple[np.ndarray, dict]:
    """Return (audio, details). `pool` is a list of other clean utterances for babble."""
    kinds = ["white", "pink", "babble", "hum"]
    info: dict = {"condition": condition}
    x = clean
    if condition == "clean":
        pass
    elif condition.startswith("snr"):
        snr = float(condition[3:])
        kind = str(rng.choice(kinds, p=[0.2, 0.25, 0.4, 0.15]))
        x = add_noise(clean, kind, snr, rng, pool)
        info.update(snr_db=snr, noise=kind)
    elif condition == "phone":
        x = phone_band(clean)
        if rng.random() < 0.6:
            x = add_noise(x, str(rng.choice(["white", "pink", "babble"])), 18.0, rng, pool)
            info.update(snr_db=18.0)
    elif condition == "reverb":
        rt = float(rng.uniform(0.35, 0.8))
        x = reverb(clean, rt, rng)
        x = add_noise(x, "pink", 20.0, rng, pool)
        info.update(rt60=round(rt, 2), snr_db=20.0)
    else:
        raise ValueError(condition)
    gain = 10 ** (rng.uniform(-9, -1) / 20)
    peak = np.max(np.abs(x)) + 1e-9
    x = (x / peak * gain).astype(np.float32)
    info["gain_db"] = round(20 * np.log10(gain), 1)
    return x, info
