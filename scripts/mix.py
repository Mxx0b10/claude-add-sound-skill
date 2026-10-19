"""Render a cue sheet (JSON) into a float WAV, plus a report to check the balance.

  run mix WORKDIR/cues.json WORKDIR/mix_raw.wav

Each event places one processed clip so that its `align` point lands on video time `at`.
`align` can be seconds into the processed clip, or "peak" / "onset" / "end" / "start"
(measured on the processed clip, so it stays right after pitch, tempo, reverse or trims).
See references/cue-sheet.md for every field.
"""
import json, os, subprocess, sys
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common  # noqa: E402

SR = common.SR
ECHO_PRESETS = {"small": "0.8:0.5:70|140:0.25|0.15", "room": "0.8:0.6:90|180:0.2|0.12",
                "hall": "0.8:0.7:120|260|420:0.3|0.2|0.1"}


def build_chain(e):
    chain = [f"aresample={SR}"]
    st = e.get("st", 0)
    if st:
        chain.append(f"asetrate={SR}*{2 ** (st / 12):.6f},aresample={SR}")   # tape-style pitch
    if e.get("tempo"):
        t = float(e["tempo"])
        while t > 2.0:
            chain.append("atempo=2.0"); t /= 2.0
        while t < 0.5:
            chain.append("atempo=0.5"); t /= 0.5
        chain.append(f"atempo={t:.4f}")
    if e.get("hp"):
        chain.append(f"highpass=f={e['hp']}")
    if e.get("lp"):
        chain.append(f"lowpass=f={e['lp']}")
    if e.get("echo"):
        ec = e["echo"]
        chain.append("aecho=" + (ECHO_PRESETS["small"] if ec is True else ECHO_PRESETS.get(ec, ec)))
    if e.get("af"):
        chain.append(e["af"])                                              # raw ffmpeg filter escape hatch
    return ",".join(chain)


def process(e):
    x = common.decode(common.resolve_sound(e["sound"]), build_chain(e))
    if e.get("reverse"):
        x = x[::-1].copy()
    a = int(e.get("src", 0) * SR)
    b = len(x) if e.get("length") is None else min(len(x), a + int(e["length"] * SR))
    x = x[a:b]
    if e.get("tail"):
        x = x[-int(e["tail"] * SR):].copy()
    n = len(x)
    if e.get("fade_in"):
        k = min(n, int(e["fade_in"] * SR))
        x[:k] *= (np.linspace(0, 1, k) ** e.get("fade_in_curve", 1.0))[:, None]
    if e.get("fade_out"):
        k = min(n, int(e["fade_out"] * SR))
        x[n - k:] *= np.linspace(1, 0, k)[:, None]
    x *= 10 ** (e.get("gain", 0) / 20)
    p = e.get("pan", 0)
    if p:
        th = (p + 1) * np.pi / 4
        x *= np.array([np.cos(th), np.sin(th)], dtype=np.float32) * np.sqrt(2)
    return x


def align_point(x, al):
    if isinstance(al, (int, float)):
        return float(al)
    env = common.envelope(x.mean(axis=1), SR, 0.005)
    if al == "peak":
        return env.argmax() * 0.005
    if al == "onset":
        return np.argmax(env > env.max() * 0.1) * 0.005
    if al == "end":
        return len(x) / SR
    return 0.0


def main():
    cues_path, out = sys.argv[1], sys.argv[2]
    cs = json.load(open(cues_path))
    dur = float(cs["duration"])
    N = int(round(dur * SR))
    bus = {}
    report, warn = [], []
    for i, e in enumerate(cs["events"]):
        b = e.get("bus", "sfx")
        bus.setdefault(b, np.zeros((N, 2), np.float32))
        x = process(e)
        if not len(x):
            warn.append(f"event {i} '{e.get('label')}' is empty (check src/length)")
            continue
        al = align_point(x, e.get("align", 0))
        start = int(round((e["at"] - al) * SR))
        s0, s1 = max(0, start), min(N, start + len(x))
        if s1 > s0:
            bus[b][s0:s1] += x[s0 - start:s1 - start]
        else:
            warn.append(f"event {i} '{e.get('label')}' falls outside the video")
        pk_i = int(np.abs(x).max(axis=1).argmax())
        pk = float(common.db(np.abs(x).max()))
        sync = e.get("sync", b == "sfx")
        # where this sound's own attack and peak land relative to its cue (measured alone,
        # so a louder neighbour can't hide it)
        on_off = (start / SR + align_point(x, "onset") - e["at"]) * 1000
        pk_off = (start / SR + align_point(x, "peak") - e["at"]) * 1000
        report.append({"i": i, "label": e.get("label", ""), "bus": b, "at": e["at"],
                       "start": round(start / SR, 3), "end": round((start + len(x)) / SR, 3),
                       "peak_db": round(pk, 1), "peak_t": round((start + pk_i) / SR, 3),
                       "onset_off_ms": round(on_off), "peak_off_ms": round(pk_off), "sync": sync})
        if b == "sfx" and pk > -3:
            warn.append(f"'{e.get('label')}' peaks at {pk:.1f} dBFS before mastering — lower its gain")
        if sync and min(abs(on_off), abs(pk_off)) > 60:
            warn.append(f"'{e.get('label')}' at {e['at']:.2f}s: attack lands {on_off:+.0f} ms, peak {pk_off:+.0f} ms "
                        f"from the cue — check `align` (or set \"sync\": false for swells/textures)")
    mg = 10 ** (cs.get("music_gain_db", -1.5) / 20)
    mix = sum((v * (mg if k == "music" else 1.0) for k, v in bus.items()), np.zeros((N, 2), np.float32))
    k = int(cs.get("end_fade", 0.25) * SR)
    if k:
        mix[-k:] *= np.linspace(1, 0, k)[:, None]
    def wav(arr, path):
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "f32le", "-ar", str(SR), "-ac", "2", "-i", "-",
                        "-c:a", "pcm_f32le", path], input=arr.astype(np.float32).tobytes(), check=True)
    wav(mix, out)
    stem = os.path.splitext(out)[0]
    for name, arr in bus.items():
        wav(arr * (mg if name == "music" else 1.0), f"{stem}.{name}.wav")
    # balance table: where SFX fight the music, or the mix goes silent
    q = int(SR * 0.5)
    m = bus.get("music", np.zeros((N, 2), np.float32)) * mg
    s = bus.get("sfx", np.zeros((N, 2), np.float32))
    print(f"{'t':>5} {'music':>6} {'sfx':>6} {'mix':>6}   (rms dBFS per 0.5s, before mastering)")
    for j in range(0, N, q):
        r = lambda a: float(common.db(np.sqrt(np.mean(a[j:j + q] ** 2))))
        rm, rs, rx = r(m), r(s), r(mix)
        note = "  <- sfx louder than music" if rs > rm + 4 and rm > -30 else ("  <- near silent" if rx < -45 else "")
        print(f"{j / SR:5.1f} {rm:6.0f} {rs:6.0f} {rx:6.0f}{note}")
    # crowding: more than 3 sfx starting within 150 ms
    starts = sorted(r_["start"] for r_ in report if r_["bus"] == "sfx")
    for a_ in range(len(starts) - 3):
        if starts[a_ + 3] - starts[a_] < 0.15:
            warn.append(f"4+ sfx start within 150 ms around {starts[a_]:.2f}s — likely muddy")
            break
    json.dump({"events": report, "warnings": warn}, open(stem + ".report.json", "w"), indent=1)
    sy = [r_ for r_ in report if r_["sync"]]
    ok = [r_ for r_ in sy if min(abs(r_["onset_off_ms"]), abs(r_["peak_off_ms"])) <= 60]
    print(f"\nwrote {out}  (peak {float(common.db(np.abs(mix).max())):.1f} dBFS, {len(report)} events)")
    print(f"timing: {len(ok)}/{len(sy)} synced cues have their attack or peak within ±60 ms of the cue time")
    print("loudest events:")
    for r_ in sorted(report, key=lambda r_: -r_["peak_db"])[:6]:
        print(f"  {r_['peak_db']:6.1f} dB @ {r_['peak_t']:6.2f}s  {r_['label']}")
    for w in warn:
        print("WARNING:", w)


if __name__ == "__main__":
    main()
