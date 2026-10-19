"""Shared helpers: library paths, index/history, audio decode and analysis."""
import json
import os
import re
import subprocess
import tempfile
import time

import numpy as np

LIB = os.path.expanduser(os.environ.get("SOUND_LIBRARY", "~/Music/ClaudeSoundLibrary"))
SOUNDS = os.path.join(LIB, "sounds")
INDEX = os.path.join(LIB, "index.json")
HISTORY = os.path.join(LIB, "history.jsonl")
PROJECTS = os.path.join(LIB, "projects")
SEARCH_CACHE = os.path.join(LIB, "search_cache.json")
SR = 48000
NOTES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]

# Licenses that allow commercial use. NC (non-commercial) and ND (no derivatives) are
# excluded: a launch video is commercial and we edit/pitch the audio.
OK_LICENSES = {"cc0", "pdm", "by", "by-sa"}
LICENSE_URLS = {
    "cc0": "https://creativecommons.org/publicdomain/zero/1.0/",
    "pdm": "https://creativecommons.org/publicdomain/mark/1.0/",
    "by": "https://creativecommons.org/licenses/by/{v}/",
    "by-sa": "https://creativecommons.org/licenses/by-sa/{v}/",
}


def ensure_lib():
    for d in (LIB, SOUNDS, PROJECTS):
        os.makedirs(d, exist_ok=True)


def read_json(path, default):
    try:
        with open(path) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def write_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path), suffix=".tmp")
    with os.fdopen(fd, "w") as f:
        json.dump(data, f, indent=1, ensure_ascii=False)
    os.replace(tmp, path)


def load_index():
    return read_json(INDEX, {})


def save_index(idx):
    write_json(INDEX, idx)


def load_history():
    out = []
    try:
        with open(HISTORY) as f:
            for line in f:
                line = line.strip()
                if line:
                    out.append(json.loads(line))
    except FileNotFoundError:
        pass
    return out


def append_history(entry):
    ensure_lib()
    with open(HISTORY, "a") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def recent_ids(n_videos=10, brand=None):
    """Sound ids used in the last n videos (optionally only one brand's videos)."""
    hist = [h for h in load_history() if brand is None or h.get("brand") == brand]
    used = set()
    for h in hist[-n_videos:]:
        used.update(h.get("sounds", []))
    return used


def sound_id_from(source, url, landing, ov_id):
    for u in (landing or "", url or ""):
        m = re.search(r"freesound\.org/(?:people/[^/]+/sounds|s)/(\d+)", u) or \
            re.search(r"freesound\.org/previews/\d+/(\d+)_", u)
        if m:
            return f"freesound-{m.group(1)}"
    return f"{source or 'ov'}-{(ov_id or 'x')[:8]}"


def resolve_sound(ref):
    """Library id -> file path. Absolute/home paths pass through (e.g. the video itself)."""
    if ref.startswith(("/", "~")):
        return os.path.expanduser(ref)
    idx = load_index()
    if ref not in idx:
        raise SystemExit(f"[add-sound] '{ref}' is not in the library ({INDEX}). Fetch it first.")
    return os.path.join(SOUNDS, idx[ref]["file"])


def decode(path, af=None, sr=SR, channels=2):
    cmd = ["ffmpeg", "-v", "error", "-i", path, "-vn"]
    if af:
        cmd += ["-af", af]
    cmd += ["-ac", str(channels), "-ar", str(sr), "-f", "f32le", "-"]
    raw = subprocess.run(cmd, capture_output=True, check=True).stdout
    x = np.frombuffer(raw, dtype=np.float32)
    return x.reshape(-1, channels).copy() if channels > 1 else x.copy()


def db(v):
    return 20 * np.log10(np.maximum(v, 1e-9))


def envelope(x, sr=SR, step=0.01):
    q = max(1, int(sr * step))
    n = len(x) // q
    if n == 0:
        return np.array([np.sqrt(np.mean(x ** 2))]) if len(x) else np.zeros(1)
    return np.sqrt(np.mean(x[: n * q].reshape(n, q) ** 2, axis=1))


def _stft(x, sr, n=2048, hop=512):
    w = np.hanning(n)
    frames = np.lib.stride_tricks.sliding_window_view(np.pad(x, (n // 2, n // 2)), n)[::hop]
    return np.abs(np.fft.rfft(frames * w, axis=1)), hop / sr, np.fft.rfftfreq(n, 1 / sr)


def chroma(x, sr):
    n = 1 << 15
    seg = x[:n] if len(x) >= n else np.pad(x, (0, n - len(x)))
    S = np.abs(np.fft.rfft(seg * np.hanning(n))) ** 2
    f = np.fft.rfftfreq(n, 1 / sr)
    m = (f > 80) & (f < 3000)
    bins = np.round(12 * np.log2(f[m] / 261.63)).astype(int) % 12
    c = np.bincount(bins, weights=S[m], minlength=12)
    return c / (c.sum() + 1e-12)


MAJOR = np.array([6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88])
MINOR = np.array([6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17])


def estimate_key(c):
    best = None
    for i in range(12):
        for prof, name in ((MAJOR, "major"), (MINOR, "minor")):
            r = np.corrcoef(c, np.roll(prof, i))[0, 1]
            if best is None or r > best[0]:
                best = (r, f"{NOTES[i]} {name}")
    return best[1]


def analyze_file(path, music=False):
    """Timing/level/pitch facts used to place a sound: where its peak and onset are, how loud,
    how bright, what pitch. For music: tempo, beat phase, loudness profile, key, section jumps."""
    sr = 22050
    x = decode(path, sr=sr, channels=1)
    dur = len(x) / sr
    env = envelope(x, sr, 0.01)
    mx = env.max() if len(env) else 0
    out = {
        "dur": round(dur, 3),
        "peak_db": round(float(db(np.abs(x).max() if len(x) else 0)), 1),
        "peak_t": round(float(env.argmax() * 0.01), 3),
        "onset_t": round(float(np.argmax(env > mx * 0.1) * 0.01), 3),
        "rms_db": round(float(db(np.sqrt(np.mean(x[x != 0] ** 2)) if np.any(x) else 0)), 1),
    }
    M, dt, freqs = _stft(x, sr)
    out["centroid_hz"] = int(np.median((M * freqs).sum(1) / (M.sum(1) + 1e-9)))
    c = chroma(x[int(out["onset_t"] * sr):], sr)
    top = np.argsort(c)[::-1]
    out["pitch"] = NOTES[top[0]] if c[top[0]] > 0.35 else None   # only clearly tonal sounds
    if music or dur > 12:
        flux = np.maximum(np.diff(M, axis=0), 0).sum(1)
        lflux = np.maximum(np.diff(M[:, freqs < 150], axis=0), 0).sum(1)
        f = flux - flux.mean()
        ac = np.correlate(f, f, "full")[len(f) - 1:]
        lags = np.arange(len(ac)) * dt
        bpm_all = 60 / np.maximum(lags, 1e-9)
        i = np.argmax(ac * ((bpm_all > 70) & (bpm_all < 180)))
        bpm = 60 / lags[i]
        per = 60 / bpm
        best = max(((lflux[(np.arange(o, len(lflux) * dt, per) / dt).astype(int)].sum(), o)
                    for o in np.arange(0, per, 0.01)))
        out["bpm"] = round(float(bpm), 1)
        out["beat_offset"] = round(float(best[1]), 2)
        q = int(sr * 0.25)
        prof = [round(float(db(np.sqrt(np.mean(x[k:k + q] ** 2)))), 0) for k in range(0, len(x), q)]
        out["rms_quarter_s"] = prof
        sm = np.convolve(prof, np.ones(4) / 4, "same")
        jumps = [round(k * 0.25, 2) for k in range(4, len(sm) - 4) if sm[k + 2] - sm[k - 2] > 5]
        drops = [round(k * 0.25, 2) for k in range(4, len(sm) - 4) if sm[k - 2] - sm[k + 2] > 8]
        out["energy_up_at"] = _dedupe(jumps)
        out["energy_down_at"] = _dedupe(drops)
        cs = np.mean([chroma(x[int(t * sr):], sr) for t in np.arange(0, max(dur - 1, 0.5), 1.0)], axis=0)
        out["key"] = estimate_key(cs)
    return out


def _dedupe(ts, gap=1.0):
    out = []
    for t in ts:
        if not out or t - out[-1] > gap:
            out.append(t)
    return out


def now():
    return time.strftime("%Y-%m-%d %H:%M")
