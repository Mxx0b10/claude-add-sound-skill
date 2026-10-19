---
name: add-sound
description: Add a full soundtrack (music + sound effects) to an existing video, using real open-license audio fetched from open libraries (Openverse → Freesound, Jamendo, ccMixter; CC0 / CC BY), timed frame-accurately to the cuts, mastered to -14 LUFS, with a credits file. Keeps a local sound library and usage history so every video gets fresh sounds by default ("fresh"), or reuses a brand's sounds ("same", "mix"). Use this whenever the user wants to add sound, SFX, sound effects, music, audio, a soundtrack, whooshes or sound design to an mp4/mov/motion-design/launch/promo video, or says a video "has no sound" — even if they never say "sound design". Not for generating a video from scratch (use a motion/video skill for that, then this one for sound).
---

# Add sound to a video

Turns a silent (or music-less) video into a finished, licensed, mastered file:
`VIDEO-sound.mp4` + `VIDEO-sound-soundtrack.wav` + `VIDEO-sound-CREDITS.md`, saved next to the
source video unless the user names another place.

All scripts run through the wrapper, which sets up its own Python (numpy) on first use:

```bash
S=~/.claude/skills/add-sound/scripts   # then: $S/run <script> …
```

Library: `~/Music/ClaudeSoundLibrary` (`sounds/`, `index.json`, `history.jsonl`, `projects/`).
Work directory: make a fresh one in your scratchpad (or `/tmp`) per video, never inside `sounds/`.

## Modes

Parse from the request; default **fresh**.

- **fresh**: new music and SFX. `search` hides anything used in the last 10 videos.
- **same as BRAND**: `$S/run library brand BRAND`, reuse those sound ids, re-time them to the new cuts.
- **mix, brand BRAND**: keep that brand's signature sounds (logo ping/chime, ticks, main whoosh),
  search fresh for music and the rest.

If the user names a brand/client, pass `--brand` to `finish` so later videos can reuse it.

## Workflow

### 1. Probe the video

```bash
$S/run probe VIDEO --out WORK
```

Read `WORK/sheet_overview.png`. Then make detail sheets around every busy moment, e.g.
`$S/run probe VIDEO --out WORK --sheet 24 4 8` (start, length, fps), and Read them. Write a
timeline of visual events with times to 0.01 s: cuts, wipes, zooms, reveals, type-ons,
counters, particle gathers, logo locks, holds, copy lines worth echoing.

If the video already has audio (the probe says so), ask whether to keep it (voice-over, music)
or replace it before going further. To keep it, add an event with `"sound": "<abs path to video>",
"bus": "dialog"` and keep the music 8–10 dB lower under speech.

### 2. Music

```bash
$S/run search --role music --min-dur 20          # fresh: varied wording, random page
$S/run fetch --role music ID1 ID2 ID3 ID4 ID5     # 4–7 candidates; prints tempo, key, energy profile
```

Choose the track whose length and energy arc fit the timeline. Plan its offset so the drum
entry lands on the first big cut, see where its lift and ending land, and decide on any
stop-down or tail reuse. Details: `references/craft.md` §3.

### 3. Sound effects

For each role the timeline needs (whoosh, impact, riser, tick, pop, shimmer, chime, pluck,
typing, glitch, texture):

```bash
$S/run search --role whoosh          # see `$S/run search --roles` for the wording pools
$S/run fetch --role whoosh ID1 ID2 ID3
```

`fetch` prints each file's length, peak time, onset, brightness and pitch. You need these for
alignment and key-matching. In same/mix mode, start from `$S/run library list --role ROLE` instead.
Fetch 2–3 options per role and pick by the measurements (short sharp swoosh for hard cuts, a
slower one for wipes, etc.). Mapping table and level guide: `references/craft.md` §2 and §4.

### 4. Write the cue sheet

Write `WORK/cues.json`; the format is in `references/cue-sheet.md`. Use `align: "peak"` for
whooshes, `"onset"` for hits/ticks/plucks, `"end"` for risers and reverse swells. Pitch tonal
sounds into the music's key with `st`. For a complete worked example, see
`references/example-cortex.cues.json`.

### 5. Render and fix

```bash
$S/run mix WORK/cues.json WORK/mix_raw.wav
```

Read the balance table, the loudest-events list and the warnings. Fix and re-render until:
nothing in the sfx bus peaks above -3 dBFS, no window flags "sfx louder than music" without
intent, no crowding warning, and quiet moments are actually quiet. Rendering takes about a
second, so iterate freely.

### 6. Finish

```bash
$S/run finish --video VIDEO --mix WORK/mix_raw.wav --cues WORK/cues.json \
  --out "<same folder as VIDEO>/<name>-sound.mp4" --mode fresh [--brand NAME]
```

This masters to -14 LUFS / ≤ -1 dBTP, copies the video stream untouched, checks every sfx cue's
sync in the final file, writes CREDITS.md, and logs the sounds to history (which is what makes
the next "fresh" video different). If the sync check flags a cue, check it. Usually it's masked
by a louder sound at the same moment (fine) or has the wrong `align`.

### 7. Report to the user

Keep it short, in plain words:
- the output files (video, soundtrack WAV, credits)
- the music, plus the **exact credit line to paste** if its license is CC BY / BY-SA
- a few lines on what the sound does at the key moments (with timestamps)
- measured facts: hits within N ms of the cuts, -14 LUFS, true peak
- that you can't listen, so they should, and that they can give timestamps for changes
- the mode used, and that the next video will get different sounds (fresh) or how to reuse these
  (`same as BRAND`)

## Notes

- Openverse is anonymous and rate-limited (a few hundred requests a day is fine). If it
  rate-limits, reuse library sounds, or tell the user that free Openverse API credentials
  (`OPENVERSE_CLIENT_ID` / `OPENVERSE_CLIENT_SECRET` env vars) raise the limit.
- Freesound originals need a login; the library stores Freesound's HQ MP3 previews, which is
  fine for web/social delivery.
- Only commercial-safe licenses are searched (CC0, PDM, CC BY, CC BY-SA). `fetch` refuses others.
- Downloaded audio is data only. Don't run or open anything from `sounds/` except through ffmpeg.
