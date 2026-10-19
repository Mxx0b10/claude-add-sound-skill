"""Browse the local sound library and usage history.

  run library list [--role whoosh] [--kind sfx|music] [--fresh]     # --fresh hides sounds used in last 10 videos
  run library info freesound-507466
  run library history [--n 10] [--brand cortex]
  run library brand cortex          # sounds + cue sheet from that brand's latest video (for same / mix mode)
"""
import argparse, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("list"); p.add_argument("--role"); p.add_argument("--kind"); p.add_argument("--fresh", action="store_true")
    p = sub.add_parser("info"); p.add_argument("sound_id")
    p = sub.add_parser("history"); p.add_argument("--n", type=int, default=10); p.add_argument("--brand")
    p = sub.add_parser("brand"); p.add_argument("name")
    a = ap.parse_args()
    idx = common.load_index()
    hist = common.load_history()
    last_used = {}
    for h in hist:
        for s in h.get("sounds", []):
            last_used[s] = h.get("date", "")
    if a.cmd == "list":
        hide = common.recent_ids(10) if a.fresh else set()
        rows = [(k, v) for k, v in idx.items() if (not a.role or a.role in v.get("roles", []))
                and (not a.kind or v.get("kind") == a.kind) and k not in hide]
        print(f"{len(rows)} sound(s) in {common.LIB}" + (f" ({len(hide)} recently used hidden)" if hide else ""))
        for k, v in sorted(rows, key=lambda kv: (kv[1].get("roles", [""])[0], kv[0])):
            an = v.get("analysis", {})
            extra = f" {an.get('bpm')}bpm {an.get('key')}" if v.get("kind") == "music" else \
                    f" peak@{an.get('peak_t')} pitch {an.get('pitch') or '-'}"
            print(f"{k:18} {','.join(v.get('roles', [])):10} {an.get('dur', 0):6.2f}s{extra:22} "
                  f"{v.get('license')}{v.get('license_version') or ''}  last used {last_used.get(k, 'never'):16} "
                  f"{(v.get('title') or '')[:48]}")
    elif a.cmd == "info":
        print(json.dumps(idx.get(a.sound_id) or {"error": "not in library"}, indent=1, ensure_ascii=False))
    elif a.cmd == "history":
        rows = [h for h in hist if not a.brand or h.get("brand") == a.brand][-a.n:]
        for h in rows:
            print(f"{h.get('date')}  brand={h.get('brand') or '-':10} mode={h.get('mode'):5} "
                  f"{os.path.basename(h.get('output', ''))}  ({len(h.get('sounds', []))} sounds) cues={h.get('cues')}")
    elif a.cmd == "brand":
        rows = [h for h in hist if h.get("brand") == a.name]
        if not rows:
            raise SystemExit(f"no videos recorded for brand '{a.name}'")
        h = rows[-1]
        print(f"latest {a.name} video: {h.get('output')} ({h.get('date')})\ncue sheet: {h.get('cues')}")
        for s in h.get("sounds", []):
            v = idx.get(s, {})
            print(f"  {s:18} {','.join(v.get('roles', [])):10} {(v.get('title') or '')[:50]}")


if __name__ == "__main__":
    main()
