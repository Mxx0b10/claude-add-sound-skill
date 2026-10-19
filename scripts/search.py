"""Search Openverse (open-license audio from Freesound, Jamendo, ccMixter, Wikimedia) for music/SFX.

  run search --role whoosh                          # fresh mode: varied wording, deeper pages
  run search --role music --query "synthwave tech" --min-dur 25
  run search --query "glass ping" --kind sfx --mode same
  run search --roles                                # list roles and their query words

Fresh mode (default) rotates through several wordings per role, picks a random results page
(1–3) and hides sounds used in your last 10 videos, so each video gets new sounds.
Only licenses that allow commercial use are requested (CC0 / CC BY / CC BY-SA / PDM).
Results are cached so `run fetch` can download without another API call.
"""
import argparse, json, os, random, sys, time, urllib.error, urllib.parse, urllib.request
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common  # noqa: E402

API = "https://api.openverse.org/v1"
UA = "claude-add-sound/1.0 (personal sound-design skill)"

ROLE_QUERIES = {
    "whoosh":  ["whoosh", "swoosh", "swish", "woosh transition", "air whoosh", "cinematic whoosh",
                "swipe whoosh", "transition swoosh", "deep whoosh", "fast swish"],
    "impact":  ["cinematic impact", "soft impact", "boom hit", "low thud", "trailer hit", "sub hit",
                "deep impact", "punch hit", "bass hit"],
    "riser":   ["riser", "uplifter", "build up riser", "reverse swell", "tension riser", "sweep up",
                "reverse cymbal"],
    "tick":    ["ui click", "tick", "soft click", "button click", "interface tap", "mouse click",
                "click tick", "tap"],
    "pop":     ["pop", "ui pop", "bubble pop", "plop", "blip", "pop sound effect"],
    "shimmer": ["shimmer", "sparkle", "glitter", "twinkle", "magic sparkle", "fairy dust", "chimes swell"],
    "chime":   ["chime", "crystal bell", "glass ping", "ding", "notification chime", "bell hit",
                "crystal ding", "logo sting"],
    "pluck":   ["kalimba", "marimba note", "pluck", "music box note", "soft pluck", "xylophone note",
                "celesta"],
    "typing":  ["keyboard typing", "typing", "laptop keyboard", "keyboard keys", "mechanical keyboard"],
    "glitch":  ["glitch", "digital glitch", "data transfer", "computer beep", "sci-fi interface",
                "data processing", "beep sequence"],
    "texture": ["room tone", "ambience", "drone", "pad ambient", "atmosphere"],
    "music":   ["corporate technology", "tech background music", "electronic music", "ambient electronic",
                "upbeat electronic", "inspiring", "synthwave", "future bass", "minimal techno",
                "cinematic electronic", "modern corporate", "lofi", "motivational", "presentation music",
                "promo music", "tech house", "chill electronic", "background music"],
}


# Default longest useful file per role (s); keeps field recordings out of short-SFX results.
ROLE_MAX_DUR = {"whoosh": 6, "impact": 10, "riser": 15, "tick": 2, "pop": 2, "shimmer": 12, "chime": 10,
                "pluck": 6, "typing": 30, "glitch": 15}


def _token():
    tok = os.environ.get("OPENVERSE_TOKEN")
    cid, sec = os.environ.get("OPENVERSE_CLIENT_ID"), os.environ.get("OPENVERSE_CLIENT_SECRET")
    if tok or not (cid and sec):
        return tok
    data = urllib.parse.urlencode({"client_id": cid, "client_secret": sec,
                                   "grant_type": "client_credentials"}).encode()
    r = urllib.request.urlopen(urllib.request.Request(f"{API}/auth_tokens/token/", data=data,
                                                      headers={"User-Agent": UA}), timeout=30)
    return json.load(r)["access_token"]


def get(path, params):
    url = f"{API}{path}?{urllib.parse.urlencode(params)}"
    hdr = {"User-Agent": UA}
    tok = _token()
    if tok:
        hdr["Authorization"] = f"Bearer {tok}"
    for attempt in range(4):
        try:
            return json.load(urllib.request.urlopen(urllib.request.Request(url, headers=hdr), timeout=40))
        except urllib.error.HTTPError as e:
            if e.code == 429:
                wait = int(e.headers.get("Retry-After") or 20 * (attempt + 1))
                if wait > 120:
                    raise SystemExit(f"[add-sound] Openverse rate limit hit (retry in {wait}s). "
                                     "Reuse library sounds (`run library list`) or set OPENVERSE_CLIENT_ID/"
                                     "OPENVERSE_CLIENT_SECRET for a higher limit.")
                print(f"[add-sound] rate limited, waiting {wait}s…", file=sys.stderr)
                time.sleep(wait)
                continue
            if e.code == 400 and params.get("page", 1) > 1:
                return {"results": [], "result_count": 0}
            raise
    raise SystemExit("[add-sound] Openverse kept rate-limiting; try again later.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--role")
    ap.add_argument("--query")
    ap.add_argument("--kind", choices=["sfx", "music"])
    ap.add_argument("--mode", choices=["fresh", "same", "mix"], default="fresh")
    ap.add_argument("--brand")
    ap.add_argument("--n", type=int, default=12, help="results to show per query")
    ap.add_argument("--queries", type=int, default=2, help="fresh mode: how many wordings to try")
    ap.add_argument("--page", type=int)
    ap.add_argument("--min-dur", type=float, default=0)
    ap.add_argument("--max-dur", type=float, default=0, help="default depends on role (whoosh 6 s, tick 2 s, …)")
    ap.add_argument("--license", help="override, e.g. cc0  (default: cc0 for sfx, cc0,by,by-sa for music)")
    ap.add_argument("--roles", action="store_true")
    a = ap.parse_args()
    if a.roles:
        for r, qs in ROLE_QUERIES.items():
            print(f"{r:8} {', '.join(qs)}")
        return
    if not (a.role or a.query):
        ap.error("give --role or --query")
    kind = a.kind or ("music" if a.role == "music" else "sfx")
    lic = a.license or ("cc0,by,by-sa,pdm" if kind == "music" else "cc0,pdm")
    rng = random.Random()
    if a.query:
        queries = [a.query]
    elif a.mode == "fresh":
        queries = rng.sample(ROLE_QUERIES[a.role], min(a.queries, len(ROLE_QUERIES[a.role])))
    else:
        queries = ROLE_QUERIES[a.role][:1]
    used = common.recent_ids(10) if a.mode == "fresh" else set()
    max_dur = a.max_dur or ROLE_MAX_DUR.get(a.role or "", 0)
    idx = common.load_index()
    common.ensure_lib()
    cache = common.read_json(common.SEARCH_CACHE, {})
    seen, shown, hidden = set(), 0, 0
    for q in queries:
        page = a.page or (rng.choice([1, 1, 2, 3]) if a.mode == "fresh" else 1)
        params = {"q": q, "license": lic, "page_size": 20, "page": page}
        d = get("/audio/", params)
        if not d.get("results") and page > 1:
            params["page"] = page = 1
            d = get("/audio/", params)
        print(f"\n# '{q}'  page {page}  ({d.get('result_count', 0)} matches, licenses {lic})")
        print(f"{'openverse_id':36}  {'sound_id':16} {'dur':>6}  {'license':9} {'creator':18} title")
        n = 0
        for r in d.get("results", []):
            sid = common.sound_id_from(r.get("source"), r.get("url"), r.get("foreign_landing_url"), r["id"])
            dur = (r.get("duration") or 0) / 1000
            licv = f"{r['license']}{r.get('license_version') or ''}"
            if r["license"] not in common.OK_LICENSES or sid in seen:
                continue
            if (a.min_dur and dur and dur < a.min_dur) or (max_dur and dur > max_dur):
                continue
            if r.get("source") == "wikimedia_audio" and kind == "sfx" and dur > 30:
                continue                       # mostly field recordings / speech
            seen.add(sid)
            cache[r["id"]] = {k: r.get(k) for k in ("id", "title", "creator", "creator_url", "license",
                                                    "license_version", "license_url", "url", "filetype",
                                                    "foreign_landing_url", "source", "duration", "attribution")}
            cache[r["id"]]["tags"] = [t["name"] for t in (r.get("tags") or [])][:20]
            if sid in used:
                hidden += 1
                continue
            flag = " [in library]" if sid in idx else ""
            print(f"{r['id']}  {sid:16} {dur:6.1f}s {licv:9} {(r.get('creator') or '')[:18]:18} "
                  f"{(r.get('title') or '')[:60]}{flag}")
            n += 1
            shown += 1
            if n >= a.n:
                break
        time.sleep(0.6)
    common.write_json(common.SEARCH_CACHE, cache)
    if hidden:
        print(f"\n({hidden} result(s) hidden because they were used in your last 10 videos)")
    if a.role == "music" or kind == "music":
        print("\nTip: fetch 4–7 candidates with --role music, then compare tempo/energy/key from the fetch output.")


if __name__ == "__main__":
    main()
