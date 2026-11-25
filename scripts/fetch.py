"""Download sounds into the local library and measure them.

  run fetch --role whoosh  <openverse_id> [<openverse_id> ...]
  run fetch --role music   <openverse_id> ...      # music gets tempo, key and energy-profile analysis

Files land in ~/Music/ClaudeSoundLibrary/sounds/ with license metadata in index.json, so the
same sound is never downloaded twice and credits can be generated later. Downloaded audio is
treated as data only (decoded by ffmpeg, never executed).

Before downloading, each Freesound sound's license is checked on its own Freesound page (Openverse
metadata can be stale, and authors delete sounds). Deleted sounds and sounds whose page shows a
non-commercial license are refused. Other sources are marked "unverified" in the index and credits.
CC BY-SA is refused unless --allow-by-sa is given.
"""
import argparse, concurrent.futures as cf, os, sys, urllib.request
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common  # noqa: E402
import search  # noqa: E402


def meta_for(ov_id, cache):
    if ov_id in cache:
        return cache[ov_id]
    r = search.get(f"/audio/{ov_id}/", {})
    m = {k: r.get(k) for k in ("id", "title", "creator", "creator_url", "license", "license_version",
                               "license_url", "url", "filetype", "foreign_landing_url", "source",
                               "duration", "attribution")}
    m["tags"] = [t["name"] for t in (r.get("tags") or [])][:20]
    return m


def download(m, role):
    sid = common.sound_id_from(m.get("source"), m.get("url"), m.get("foreign_landing_url"), m["id"])
    ext = (m.get("filetype") or os.path.splitext(m["url"].split("?")[0])[1].lstrip(".") or "mp3").lower()
    if "jamendo" in (m.get("url") or ""):
        ext = "mp3"
    fname = f"{sid}.{ext}"
    path = os.path.join(common.SOUNDS, fname)
    if not os.path.exists(path) or os.path.getsize(path) == 0:
        req = urllib.request.Request(m["url"], headers={"User-Agent": common.UA})
        with urllib.request.urlopen(req, timeout=120) as r, open(path + ".part", "wb") as f:
            while chunk := r.read(1 << 16):
                f.write(chunk)
        os.replace(path + ".part", path)
    return sid, fname, path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("ids", nargs="+", help="openverse ids from `run search`")
    ap.add_argument("--allow-by-sa", action="store_true", help="accept CC BY-SA (share-alike) sounds")
    ap.add_argument("--no-verify", action="store_true", help="skip the source-page license check (offline)")
    ap.add_argument("--role", required=True, help="whoosh, impact, riser, tick, pop, shimmer, chime, pluck, "
                                                  "typing, glitch, texture, music …")
    a = ap.parse_args()
    common.ensure_lib()
    cache = common.read_json(common.SEARCH_CACHE, {})
    metas = [meta_for(i, cache) for i in a.ids]
    ok = []
    for m in metas:
        if m.get("license") not in common.OK_LICENSES:
            print(f"skip {m.get('title')}: license {m.get('license')} does not allow commercial use / edits")
            continue
        chk = ({"status": "unverified", "note": "check skipped (--no-verify)", "checked": common.now()}
               if a.no_verify else common.verify_license(m.get("foreign_landing_url")))
        if chk["status"] in ("deleted", "mismatch"):
            print(f"skip {m.get('title')}: {chk['note']} ({m.get('foreign_landing_url')})")
            continue
        if chk["status"] == "ok" and (chk["license"], chk["license_version"]) != (m.get("license"), m.get("license_version")):
            print(f"note {m.get('title')}: source page says {chk['license']} {chk['license_version']} "
                  f"(Openverse said {m.get('license')} {m.get('license_version')}); using the source page")
            m = {**m, "license": chk["license"], "license_version": chk["license_version"], "license_url": None}
        if m.get("license") == "by-sa" and not a.allow_by_sa:
            print(f"skip {m.get('title')}: CC BY-SA (share-alike) needs --allow-by-sa")
            continue
        m["license_check"] = {k: chk.get(k) for k in ("status", "note", "checked")}
        ok.append(m)
    metas = ok
    with cf.ThreadPoolExecutor(6) as ex:
        got = list(ex.map(lambda m: (m, *download(m, a.role)), metas))
    idx = common.load_index()
    music = a.role == "music"
    for m, sid, fname, path in got:
        an = common.analyze_file(path, music=music)
        e = idx.get(sid, {})
        roles = sorted(set(e.get("roles", [])) | {a.role})
        idx[sid] = {**e, "file": fname, "roles": roles, "kind": "music" if music else "sfx",
                    "title": m.get("title"), "creator": m.get("creator"), "license": m.get("license"),
                    "license_version": m.get("license_version"),
                    "license_url": m.get("license_url") or common.LICENSE_URLS.get(m.get("license"), "").format(
                        v=m.get("license_version") or "4.0"),
                    "landing_url": m.get("foreign_landing_url"), "source": m.get("source"),
                    "openverse_id": m.get("id"), "tags": m.get("tags", []), "analysis": an,
                    "license_check": m.get("license_check"),
                    "added": e.get("added") or common.now()}
        line = (f"{sid:18} {an['dur']:6.2f}s peak@{an['peak_t']:.2f}s onset@{an['onset_t']:.2f}s "
                f"rms {an['rms_db']:.0f}dB bright {an['centroid_hz']}Hz pitch {an['pitch'] or '-'}")
        if music:
            line += (f"\n{'':18} tempo~{an['bpm']} bpm (beat offset {an['beat_offset']}s) key~{an['key']} "
                     f"energy up at {an['energy_up_at']} down at {an['energy_down_at']}"
                     f"\n{'':18} rms/0.25s: {' '.join(str(int(v)) for v in an['rms_quarter_s'])}")
        chk = (m.get("license_check") or {}).get("status", "unverified")
        print(f"{line}\n{'':18} {m.get('title')} — {m.get('creator')} ({m.get('license')} "
              f"{m.get('license_version') or ''}, license {'checked at source' if chk == 'ok' else chk})")
    common.save_index(idx)


if __name__ == "__main__":
    main()
