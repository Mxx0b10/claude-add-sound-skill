# add-sound — a Claude Code skill for video sound design

Give Claude a silent video and it adds a full soundtrack: music and sound effects from
**open-license libraries** (Openverse → Freesound, Jamendo, ccMixter), timed to the frame of
each cut, mastered to **-14 LUFS**, with a credits file for the licenses.

```
/add-sound ~/Downloads/launch-video.mp4
```

You get, next to your video:

- `launch-video-sound.mp4`: your video with sound. The picture is copied untouched, with no re-encode.
- `launch-video-sound-soundtrack.wav`: the soundtrack on its own
- `launch-video-sound-CREDITS.md`: every sound used, its author and license, plus the credit
  line to paste when a track needs attribution

## What it does

1. **Reads the picture.** Detects hard cuts and motion peaks, then makes timestamped contact sheets so
   Claude can see every reveal, wipe, zoom, type-on and logo lock.
2. **Finds music.** Searches commercially usable licenses (CC0, CC BY, CC BY-SA) and measures each
   candidate's tempo, key and energy curve to choose one that fits the edit.
3. **Finds sound effects.** Whooshes, impacts, risers, ticks, pops, shimmers, chimes, plucks, typing,
   glitches. Each one is measured (peak time, attack, pitch) so it can be placed exactly.
4. **Writes a cue sheet.** One JSON file listing every sound, its frame, gain, pan and pitch. Tonal
   sounds are tuned to the music's key.
5. **Mixes, masters and checks.** Renders the mix, masters to -14 LUFS / -1 dBTP, puts it on the
   video, and verifies that every hit lands within ±60 ms of its frame.

## Fresh, same or mix

| mode | what happens |
|---|---|
| **fresh** (default) | New music and new sounds. Anything used in your last 10 videos is hidden from search. |
| **same as BRAND** | Reuses a brand's sounds from its last video, re-timed to the new cuts. |
| **mix, brand: BRAND** | Keeps a brand's signature sounds (logo ping, ticks, main whoosh), with fresh music and transitions. |

```
/add-sound promo.mp4
/add-sound promo-v2.mp4 same as cortex
/add-sound teaser.mp4 mix, brand: cortex
```

Every sound you use is kept in a local library (`~/Music/ClaudeSoundLibrary`) with its license
and measurements, so nothing is downloaded twice. A usage history makes "fresh" really fresh.

## Install

Requirements: [Claude Code](https://claude.com/claude-code), `ffmpeg`, and Python 3 (numpy installs itself on first run).

```bash
brew install ffmpeg
```

```bash
git clone https://github.com/Mxx0b10/claude-add-sound-skill.git ~/.claude/skills/add-sound
```

Start a new Claude Code session. The skill loads automatically: type `/add-sound` or just ask
"add sound to this video".

## Files

```
SKILL.md                         the workflow Claude follows
references/craft.md              sound-design rules: what sound goes on which visual event, levels, music editing
references/cue-sheet.md          cue sheet format
references/example-cortex.cues.json   a complete 30 s launch-video soundtrack (55 cues)
scripts/run                      wrapper: sets up a private Python venv, then runs a script
scripts/probe.py                 video info, cut detection, contact sheets
scripts/search.py                Openverse search with fresh-mode rotation and license filtering
scripts/fetch.py                 download into the library + measure (timing, pitch, tempo, key)
scripts/library.py               browse the library and history
scripts/mix.py                   render a cue sheet, with balance and timing report
scripts/finish.py                master, mux, sync check, credits, history
```

## Licenses of the sounds

This repo contains **no audio**. Sounds are downloaded on demand from their original sources, and
each keeps its own license. Only licenses that allow commercial use and editing are searched:
CC0, Public Domain Mark, CC BY and CC BY-SA. CC BY / BY-SA sounds need the credit line from
the generated CREDITS file wherever you publish the video.

Openverse's anonymous API is rate-limited. For heavy use, register free API credentials and set
`OPENVERSE_CLIENT_ID` / `OPENVERSE_CLIENT_SECRET`.

## Note

Claude can't listen to the result. Timing, levels and loudness are measured and verified; taste
is yours. Listen through, and tell Claude the timestamp of anything you want changed.
