# Cue sheet format

A cue sheet is one JSON file describing every sound in the soundtrack. `run mix` renders it;
`run finish` uses it for credits and history. Keep it in the work directory as `cues.json`.

```json
{
  "video": "/Users/me/Downloads/launch.mp4",
  "duration": 30.0,
  "music_gain_db": -1.5,
  "end_fade": 0.25,
  "events": [
    {"sound": "freesound-790646", "bus": "music", "at": 1.15, "src": 0, "length": 23.05,
     "fade_in": 0.5, "fade_out": 0.02, "label": "music body (drums land on 2.65 cut)"},
    {"sound": "freesound-507466", "at": 2.20, "align": "peak", "gain": -8, "pan": -0.2,
     "label": "cyan flash swoosh"},
    {"sound": "freesound-632344", "reverse": true, "tail": 1.1, "fade_in": 1.0, "fade_in_curve": 2,
     "at": 0.92, "align": "end", "gain": -9, "label": "particles gather into logo"}
  ]
}
```

## Top-level fields

| field | meaning |
|---|---|
| `duration` | video length in seconds (from `run probe`) |
| `music_gain_db` | trim applied to the whole music bus (default -1.5) |
| `end_fade` | seconds of fade at the very end so the file never clicks (default 0.25) |

## Event fields

| field | default | meaning |
|---|---|---|
| `sound` | — | library id (`freesound-507466`) or an absolute path (e.g. the video itself, to keep its original voice-over) |
| `bus` | `sfx` | `music`, `sfx`, or `dialog`. Only `sfx` events are sync-checked |
| `at` | — | video time (s) where the `align` point lands |
| `align` | `0` | seconds into the processed clip, or `"peak"`, `"onset"`, `"end"`, `"start"` |
| `src` | `0` | start offset inside the processed clip (s) |
| `length` | whole | how much to keep from `src` (s) |
| `tail` | — | keep only the last N s (applied after `reverse`, so a reversed shimmer's swell + attack) |
| `gain` | `0` | dB |
| `pan` | `0` | -1 (left) … 1 (right) |
| `st` | `0` | pitch shift in semitones (tape-style: +12 also halves the length) |
| `tempo` | — | time-stretch without pitch change (2.0 = twice as fast). Good for fast on-screen typing |
| `reverse` | `false` | play backwards (reverse swells into a hit) |
| `hp` / `lp` | — | high-pass / low-pass cutoff in Hz |
| `echo` | — | `true`/`"small"`, `"room"`, `"hall"`, or a raw ffmpeg `aecho` string |
| `af` | — | extra raw ffmpeg audio filter, appended last |
| `fade_in` / `fade_out` | — | seconds; `fade_in_curve` 2 = exponential (swells) |
| `sync` | sfx: true | include in the final sync check |
| `label` | — | what it is for; shows in reports and credits |

Order of processing: decode → pitch → tempo → filters → echo → reverse → src/length → tail →
fades → gain → pan → place.

Because `align` keywords are measured on the processed clip, prefer `"peak"` for whooshes
(peak on the cut), `"onset"` for impacts/pops/ticks/plucks (attack on the frame), `"end"` for
risers and reverse swells (finish on the cut). Use a number only when the loudest point is not
the musically important one.

## Worked example

`references/example-cortex.cues.json` is a complete, finished 30 s launch video (55 cues):
intro logo gather, drums landing on a cut, typing, word-card montage, a stop-down on a copy
line ("No noise."), and a key-matched logo resolve. Read it when you need a pattern.
