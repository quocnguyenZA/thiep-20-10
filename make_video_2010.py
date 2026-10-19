# -*- coding: utf-8 -*-
import math, os, random, subprocess, wave
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

W, H, FPS = 1080, 1920, 30
DUR = 14.0
N = int(DUR * FPS)
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "chuc_20_10.mp4")
HERE = os.path.dirname(os.path.abspath(__file__))

# ---------------- MUSIC: gentle piano-like chords I-V-vi-IV in C ----------------
SR = 44100

def note(freq, dur, amp=0.22):
    t = np.linspace(0, dur, int(SR * dur), endpoint=False)
    env = np.exp(-t * 1.1) * np.minimum(t / 0.02, 1.0)
    s = (np.sin(2 * np.pi * freq * t)
         + 0.35 * np.sin(2 * np.pi * freq * 2 * t)
         + 0.12 * np.sin(2 * np.pi * freq * 3 * t))
    return amp * env * s

def chord(freqs, dur):
    out = np.zeros(int(SR * dur))
    for i, f in enumerate(freqs):
        n = note(f, dur, amp=0.20 - 0.03 * i)
        out[:len(n)] += n
    return out

C4, D4, E4, F4, G4, A4, B4 = 261.63, 293.66, 329.63, 349.23, 392.00, 440.00, 493.88
C5, D5, E5, F5, G5, A5 = 523.25, 587.33, 659.25, 698.46, 783.99, 880.00

prog = [
    ([F4, A4, C5], [C5, A4, F4, A4]),      # F
    ([C4, E4, G4], [G4, E4, C5, E4]),      # C
    ([G4, B4, D5], [D5, B4, G4, B4]),      # G
    ([A4, C5, E5], [E5, C5, A4, C5]),      # Am
]
seg = 3.5
audio = np.zeros(int(SR * DUR) + SR)
for i, (bass, mel) in enumerate(prog):
    st = int(i * seg * SR)
    c = chord(bass, seg)
    audio[st:st + len(c)] += c
    step = seg / len(mel)
    for j, f in enumerate(mel):
        n = note(f, step * 1.6, amp=0.16)
        pos = st + int(j * step * SR)
        audio[pos:pos + len(n)] += n
audio = audio[:int(SR * DUR)]
# simple soft echo
echo = np.zeros_like(audio)
d = int(0.35 * SR)
echo[d:] = audio[:-d] * 0.28
audio = audio + echo
audio = np.tanh(audio * 1.2) * 0.85
fade = int(1.2 * SR)
audio[-fade:] *= np.linspace(1, 0, fade)
audio[:int(0.3 * SR)] *= np.linspace(0, 1, int(0.3 * SR))
stereo = np.stack([audio, audio], axis=1)
pcm = (np.clip(stereo, -1, 1) * 32767).astype(np.int16)
wav_path = os.path.join(HERE, "bgm.wav")
with wave.open(wav_path, "wb") as f:
    f.setnchannels(2); f.setsampwidth(2); f.setframerate(SR)
    f.writeframes(pcm.tobytes())

# ---------------- VISUALS ----------------
FONT = r"C:\Windows\Fonts\cambria.ttc"
FONTB = r"C:\Windows\Fonts\calibrib.ttf"
for p in (FONT, FONTB):
    if not os.path.exists(p):
        raise SystemExit("missing font " + p)

def font(sz, bold=False):
    return ImageFont.truetype(FONTB if bold else FONT, sz)

def fit_font(text, max_w, start=66):
    sz = start
    while sz > 28:
        f = font(sz)
        if f.getbbox(text)[2] - f.getbbox(text)[0] <= max_w:
            return f
        sz -= 2
    return font(28)

# background base: warm vertical gradient (deep wine -> ink)
base = Image.new("RGB", (W, H))
top = np.array([46, 18, 38], dtype=np.float64)
bot = np.array([10, 10, 26], dtype=np.float64)
grad = np.zeros((H, 1, 3))
for y in range(H):
    k = y / H
    grad[y] = top * (1 - k) + bot * k
arr = np.repeat(grad, W, axis=1)
# soft radial warm glow center
yy, xx = np.mgrid[0:H, 0:W]
cx, cy = W / 2, H * 0.46
dist = np.sqrt(((xx - cx) / (W * 0.75)) ** 2 + ((yy - cy) / (H * 0.55)) ** 2)
glow = np.clip(1 - dist, 0, 1) ** 2
glow_col = np.array([120, 62, 58], dtype=np.float64)
arr = arr + glow[..., None] * glow_col * 0.55
# vignette
vig = np.clip(1 - (((xx - W / 2) / (W * 0.72)) ** 2 + ((yy - H / 2) / (H * 0.72)) ** 2), 0, 1)
arr *= (0.55 + 0.45 * vig[..., None])
BASE = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))

# particles (golden dust)
rng = random.Random(20)
parts = []
for _ in range(70):
    parts.append({
        "x": rng.uniform(0, W), "y": rng.uniform(0, H),
        "r": rng.uniform(1.5, 5.0), "sp": rng.uniform(8, 28),
        "ph": rng.uniform(0, math.tau), "tw": rng.uniform(0.6, 1.8),
    })

def ease(k):
    k = max(0.0, min(1.0, k))
    return k * k * (3 - 2 * k)

def fade_t(t, t_in, dur_in, t_out=None, dur_out=0.8):
    if t < t_in:
        return 0.0
    if t_out is not None and t > t_out:
        return max(0.0, 1 - (t - t_out) / dur_out)
    return ease((t - t_in) / dur_in)

LABEL = "NGÀY 20 THÁNG 10"
LINES = ["Chúc em bình yên trong tim,", "tự do trong tâm hồn,", "hạnh phúc trong từng ngày."]
SIG = "Người thương của em"

label_f = font(36, True)
line_fs = [fit_font(t, 880, 72) for t in LINES]
sig_f = font(38)

def text_w(f, s):
    b = f.getbbox(s)
    return b[2] - b[0]

out_dir = os.path.join(HERE, "frames")
os.makedirs(out_dir, exist_ok=True)

for i in range(N):
    t = i / FPS
    img = BASE.copy()
    ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)

    # particles
    for p in parts:
        y = (p["y"] - p["sp"] * t) % (H + 40) - 20
        a = int(70 * (0.55 + 0.45 * math.sin(t * p["tw"] + p["ph"])))
        r = p["r"]
        d.ellipse([p["x"] - r, y - r, p["x"] + r, y + r], fill=(255, 214, 150, a))

    # label
    a1 = fade_t(t, 0.6, 1.0, 12.6)
    if a1 > 0:
        s = LABEL
        w = text_w(label_f, s)
        x = (W - w) / 2
        y = 610
        d.text((x + 4, y), s, font=label_f, fill=(0, 0, 0, int(120 * a1)))
        d.text((x, y), s, font=label_f, fill=(232, 196, 138, int(255 * a1)))
        lw = 120
        d.line([(W / 2 - lw - w / 2, y + 26), (W / 2 - w / 2 - 20, y + 26)],
               fill=(232, 196, 138, int(150 * a1)), width=2)
        d.line([(W / 2 + w / 2 + 20, y + 26), (W / 2 + w / 2 + lw, y + 26)],
               fill=(232, 196, 138, int(150 * a1)), width=2)

    # main lines
    ys = [790, 950, 1110]
    starts = [1.8, 3.3, 4.8]
    for k, (txt, f, y0, st) in enumerate(zip(LINES, line_fs, ys, starts)):
        a = fade_t(t, st, 1.1, 12.6)
        if a <= 0:
            continue
        rise = (1 - ease((t - st) / 1.1)) * 26 if t - st < 1.1 else 0
        y = y0 + rise
        w = text_w(f, txt)
        x = (W - w) / 2
        d.text((x + 3, y + 3), txt, font=f, fill=(0, 0, 0, int(130 * a)))
        col = (248, 240, 226, int(255 * a)) if k < 2 else (245, 213, 155, int(255 * a))
        d.text((x, y), txt, font=f, fill=col)

    # ornament + signature
    a3 = fade_t(t, 6.4, 1.0, 12.6)
    if a3 > 0:
        oy = 1290
        d.line([(W / 2 - 90, oy), (W / 2 - 14, oy)], fill=(232, 196, 138, int(160 * a3)), width=2)
        d.line([(W / 2 + 14, oy), (W / 2 + 90, oy)], fill=(232, 196, 138, int(160 * a3)), width=2)
        r = 5
        d.ellipse([W / 2 - r, oy - r, W / 2 + r, oy + r], fill=(232, 196, 138, int(220 * a3)))
        w = text_w(sig_f, SIG)
        d.text(((W - w) / 2, 1350), SIG, font=sig_f, fill=(232, 205, 165, int(215 * a3)))

    img = Image.alpha_composite(img.convert("RGBA"), ov).convert("RGB")
    img.save(os.path.join(out_dir, f"f{i:04d}.png"))

# ---------------- ENCODE ----------------
ff = imageio_ffmpeg_exe = __import__("imageio_ffmpeg").get_ffmpeg_exe()
cmd = [ff, "-y", "-framerate", str(FPS), "-i", os.path.join(out_dir, "f%04d.png"),
       "-i", wav_path, "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "20",
       "-c:a", "aac", "-b:a", "160k", "-shortest", "-movflags", "+faststart", OUT]
subprocess.run(cmd, check=True, capture_output=True)
print("DONE:", OUT)
