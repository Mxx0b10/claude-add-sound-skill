"""Master the mix, put it on the video, check sync, write credits, log usage.

  run finish --video IN.mp4 --mix WORKDIR/mix_raw.wav --cues WORKDIR/cues.json \
             --out OUT.mp4 [--brand cortex] [--mode fresh] [--lufs -14] [--tp -1]

- Loudness: iterates gain + a look-ahead limiter until integrated loudness hits the target
  (-14 LUFS = YouTube/social norm) with true peak at or under the ceiling.
- Video stream is copied untouched (no re-encode, no quality loss). Audio: AAC 320 kbps 48 kHz.
- Sync check: confirms the muxed audio is not shifted vs. the master (A/V offset), and summarises
  how close each sfx cue's own attack/peak lands to its frame (measured per sound in `run mix`).
- Writes OUT-CREDITS.md and OUT-soundtrack.wav next to OUT, saves the cue sheet into the
  library's projects/ folder and appends to history.jsonl (that's what fresh/same/mix read).
"""
import argparse, json, os, shutil, subprocess, sys
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common  # noqa: E402


def measure(path):
    out = subprocess.run(["ffmpeg", "-hide_banner", "-i", path, "-map", "0:a", "-af", "ebur128=peak=true",
                          "-f", "null", "-"], capture_output=True, text=True).stderr
    s = out[out.rfind("Summary:"):]
    I = float(s.split("I:")[1].split()[0])
    P = float(s.split("Peak:")[1].split()[0])
    return I, P


def master(raw, out_wav, lufs, tp):
    I, _ = measure(raw)
    g = lufs - I
    ceiling = 10 ** ((tp - 1.0) / 20)        # 1 dB headroom for AAC overshoot
    for _ in range(4):
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", raw, "-af",
                        f"volume={g:.2f}dB,alimiter=limit={ceiling:.4f}:attack=4:release=80:level=false,"
                        "aresample=48000", "-c:a", "pcm_s24le", out_wav], check=True)
        I2, P2 = measure(out_wav)
        if abs(I2 - lufs) < 0.15:
            break
        g += lufs - I2
    # how hard the limiter worked (big numbers = squashed, lower the music or the loud sfx)
    a = common.decode(raw) * 10 ** (g / 20)
    b = common.decode(out_wav)
    n = min(len(a), len(b))
    w = int(common.SR * 0.02)
    k = n // w
    ea = np.abs(a[:k * w]).reshape(k, -1).max(1)
    eb = np.abs(b[:k * w]).reshape(k, -1).max(1)
    gr = common.db(ea / np.maximum(eb, 1e-9))[ea > 1e-3]
    return g, I2, P2, (float(np.percentile(gr, 90)) if len(gr) else 0.0, float(gr.max()) if len(gr) else 0.0)


def av_offset_ms(video_out, soundtrack):
    """Lag of the muxed audio vs. the master WAV (should be 0: proves the mux kept sync)."""
    a = common.envelope(common.decode(video_out, channels=1), common.SR, 0.001)
    b = common.envelope(common.decode(soundtrack, channels=1), common.SR, 0.001)
    n = min(len(a), len(b), 15000)
    a, b = a[:n] - a[:n].mean(), b[:n] - b[:n].mean()
    best = max(range(-100, 101), key=lambda L: float(np.dot(a[max(0, L):n + min(0, L)], b[max(0, -L):n - max(0, L)])))
    return best


def credits(cues, out_md, video_name):
    idx = common.load_index()
    used = []
    for e in cues["events"]:
        s = e["sound"]
        if s in idx and s not in used:
            used.append(s)
    music = [s for s in used if idx[s].get("kind") == "music"]
    sfx = [s for s in used if idx[s].get("kind") != "music"]
    def link(v):
        return v.get("landing_url") or ""
    def lic(v):
        l = v.get("license", "")
        return "CC0 1.0" if l == "cc0" else (f"CC {l.upper()} {v.get('license_version') or ''}".strip())
    L = [f"# Sound credits — {video_name}", "",
         "Audio found through Openverse (openverse.org) and downloaded from its original sources.", ""]
    need = [s for s in used if idx[s].get("license") in ("by", "by-sa")]
    if need:
        L += ["## Attribution required (paste in the post / description / site footer)", ""]
        for s in need:
            v = idx[s]
            L.append(f"> \"{v.get('title')}\" by {v.get('creator')} ({link(v)}), {lic(v)}")
        L.append("")
    if music:
        L += ["## Music", ""] + [f"- \"{idx[s].get('title')}\" by {idx[s].get('creator')} — {lic(idx[s])} — {link(idx[s])}"
                                 for s in music] + [""]
    if sfx:
        L += ["## Sound effects", "", "| Used for | Sound | Author | License | Link |", "|---|---|---|---|---|"]
        for s in sfx:
            v = idx[s]
            uses = sorted({e.get("label", "").split(" (")[0] for e in cues["events"] if e["sound"] == s})
            L.append(f"| {'; '.join(uses)[:80]} | {v.get('title')} | {v.get('creator')} | {lic(v)} | {link(v)} |")
        L.append("")
    L += ["Sounds may be pitch-shifted, reversed, filtered, time-compressed or trimmed.",
          "CC0 sounds need no credit; they are listed for reference."]
    open(out_md, "w").write("\n".join(L) + "\n")
    return used, need


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", required=True)
    ap.add_argument("--mix", required=True)
    ap.add_argument("--cues", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--brand")
    ap.add_argument("--mode", default="fresh")
    ap.add_argument("--lufs", type=float, default=-14.0)
    ap.add_argument("--tp", type=float, default=-1.0)
    a = ap.parse_args()
    cues = json.load(open(a.cues))
    stem = os.path.splitext(a.out)[0]
    soundtrack = f"{stem}-soundtrack.wav"
    g, I, P, (gr90, grmax) = master(a.mix, soundtrack, a.lufs, a.tp)
    print(f"master: gain {g:+.1f} dB -> {I:.1f} LUFS, true peak {P:.1f} dBTP; "
          f"limiter 90th pct {gr90:.1f} dB, max {grmax:.1f} dB"
          + ("  (WARNING: heavy limiting — lower the loudest elements and re-mix)" if gr90 > 2.5 else ""))
    dur = str(cues["duration"])
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", a.video, "-i", soundtrack, "-map", "0:v:0", "-map", "1:a:0",
                    "-c:v", "copy", "-c:a", "aac", "-b:a", "320k", "-ar", "48000", "-t", dur,
                    "-movflags", "+faststart", a.out], check=True)
    I2, P2 = measure(a.out)
    print(f"final file: {a.out}\n  audio {I2:.1f} LUFS, true peak {P2:.1f} dBTP")
    off = av_offset_ms(a.out, soundtrack)
    print(f"  audio/video offset after mux: {off:+d} ms" + ("" if abs(off) <= 5 else "  (WARNING: mux drifted)"))
    rep_path = os.path.splitext(a.mix)[0] + ".report.json"
    if os.path.exists(rep_path):
        sy = [r for r in json.load(open(rep_path))["events"] if r.get("sync")]
        offs = [min((r["onset_off_ms"], r["peak_off_ms"]), key=abs) for r in sy]
        good = sum(abs(o) <= 60 for o in offs)
        worst = max(offs, key=abs) if offs else 0
        print(f"  sfx timing: {good}/{len(sy)} cues hit within ±60 ms of their frame (worst {worst:+d} ms)")
    used, need = credits(cues, f"{stem}-CREDITS.md", os.path.basename(a.out))
    print(f"  credits: {stem}-CREDITS.md" + (f"  ({len(need)} sound(s) need attribution)" if need else ""))
    common.ensure_lib()
    proj = os.path.join(common.PROJECTS, f"{common.now()[:10]}-{os.path.basename(stem)}.cues.json")
    shutil.copy(a.cues, proj)
    common.append_history({"date": common.now(), "video": os.path.abspath(a.video), "output": os.path.abspath(a.out),
                           "brand": a.brand, "mode": a.mode, "cues": proj, "sounds": used,
                           "lufs": round(I2, 1)})
    print(f"  logged to {common.HISTORY}")


if __name__ == "__main__":
    main()
