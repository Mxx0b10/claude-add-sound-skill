"""Look at a video before scoring it.

  run probe VIDEO --out WORKDIR                     # info, cut list, motion energy, overview sheet
  run probe VIDEO --out WORKDIR --sheet 12 3 10     # detail sheet: start 12s, 3s long, 10 fps

Sheets are timestamped contact sheets (PNG) to Read, so you can see exactly which frame a
reveal, wipe, zoom or type-on starts on.
"""
import argparse, json, os, re, subprocess, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common  # noqa: E402

FONT = next((f for f in ("/System/Library/Fonts/Supplemental/Arial.ttf",
                         "/System/Library/Fonts/Helvetica.ttc",
                         "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf") if os.path.exists(f)), None)


def info(video):
    j = json.loads(subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries",
         "format=duration:stream=index,codec_type,codec_name,width,height,r_frame_rate,nb_frames",
         "-of", "json", video], capture_output=True, check=True).stdout)
    v = next((s for s in j["streams"] if s["codec_type"] == "video"), {})
    a = [s for s in j["streams"] if s["codec_type"] == "audio"]
    num, den = (v.get("r_frame_rate", "30/1").split("/") + ["1"])[:2]
    return {"duration": float(j["format"]["duration"]), "width": v.get("width"), "height": v.get("height"),
            "fps": round(float(num) / float(den or 1), 3), "video_codec": v.get("codec_name"),
            "has_audio": bool(a), "audio_codec": a[0]["codec_name"] if a else None}


def scene_scores(video, workdir):
    meta = os.path.join(workdir, "scene_scores.txt")
    subprocess.run(["ffmpeg", "-v", "error", "-i", video, "-an", "-vf",
                    f"scale=320:-2,select='gte(scene,0)',metadata=print:file={meta}", "-f", "null", "-"],
                   check=True)
    rows, t = [], None
    for line in open(meta):
        m = re.search(r"pts_time:([0-9.]+)", line)
        if m:
            t = float(m.group(1))
        m = re.search(r"scene_score=([0-9.]+)", line)
        if m and t is not None:
            rows.append((t, float(m.group(1))))
    return rows


def find_events(rows, fps):
    """Hard cuts (big single-frame change) and softer motion peaks (wipes, zooms, reveals)."""
    cuts, motion = [], []
    for i in range(1, len(rows) - 1):
        t, s = rows[i]
        if s >= rows[i - 1][1] and s >= rows[i + 1][1]:
            if s > 0.18:
                cuts.append((round(t, 3), round(s, 3)))
            elif s > 0.025:
                motion.append((round(t, 3), round(s, 3)))
    # collapse clusters within 3 frames (a wipe gives several adjacent peaks)
    def collapse(ev):
        out = []
        for t, s in ev:
            if out and t - out[-1][0] < 3 / fps:
                if s > out[-1][1]:
                    out[-1] = (t, s)
            else:
                out.append((t, s))
        return out
    return collapse(cuts), collapse(motion)


def sheet(video, out_png, start, dur, fps, cols=6, width=320):
    n = max(1, int(round(dur * fps)))
    rows_ = (n + cols - 1) // cols
    dt = f"drawtext=text='%{{pts\\:hms}}':x=6:y=6:fontsize=20:fontcolor=red:box=1:boxcolor=white@0.6"
    if FONT:
        dt += f":fontfile={FONT}"
    vf = f"fps={fps},scale={width}:-2,setpts=PTS+{start}/TB,{dt},tile={cols}x{rows_}"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", str(start), "-t", str(dur), "-i", video,
                    "-vf", vf, "-frames:v", "1", out_png], check=True)
    return out_png


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video")
    ap.add_argument("--out", required=True, help="work directory")
    ap.add_argument("--sheet", nargs=3, type=float, metavar=("START", "DUR", "FPS"))
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    if a.sheet:
        s, d, f = a.sheet
        print(sheet(a.video, os.path.join(a.out, f"sheet_{s:g}-{s + d:g}s.png"), s, d, f))
        return
    inf = info(a.video)
    rows = scene_scores(a.video, a.out)
    cuts, motion = find_events(rows, inf["fps"] or 30)
    energy = {}
    for t, s in rows:
        k = round(int(t * 2) / 2, 1)
        energy[k] = energy.get(k, 0) + s
    ov_fps = 2 if inf["duration"] <= 40 else max(0.25, 60 / inf["duration"])
    ov = sheet(a.video, os.path.join(a.out, "sheet_overview.png"), 0, inf["duration"], ov_fps)
    res = {**inf, "cuts": cuts, "motion_peaks": motion,
           "energy_per_half_s": {f"{k:.1f}": round(v, 2) for k, v in sorted(energy.items())},
           "overview_sheet": ov}
    json.dump(res, open(os.path.join(a.out, "probe.json"), "w"), indent=1)
    print(f"{inf['width']}x{inf['height']} @ {inf['fps']} fps, {inf['duration']:.2f}s, "
          f"audio: {'YES (' + inf['audio_codec'] + ') — ask before replacing it' if inf['has_audio'] else 'none'}")
    print("hard cuts (t, score):", " ".join(f"{t:.2f}({s:.2f})" for t, s in cuts) or "none")
    print("motion peaks:", " ".join(f"{t:.2f}" for t, _ in motion) or "none")
    print("energy/0.5s:", " ".join(f"{k}:{v:.2f}" for k, v in res["energy_per_half_s"].items()))
    print("overview sheet:", ov)
    print("saved:", os.path.join(a.out, "probe.json"))


if __name__ == "__main__":
    main()
