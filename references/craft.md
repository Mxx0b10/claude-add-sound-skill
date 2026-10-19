# Sound design craft for motion video

These are the rules that made the Cortex launch video work. They are defaults, not law; the
picture always wins.

## 1. Read the picture first

Build a timeline of visual events with frame-accurate times before searching anything:
hard cuts, wipes, zooms/push-ins, text reveals and type-ons, counters, particles gathering or
scattering, logo locks, holds, and any line of copy whose meaning sound can echo
("No noise.", "Silence.", "Faster."). `run probe` gives cuts and motion peaks; contact sheets at
10–20 fps around each busy moment give the exact frame. Scene-score peaks land on the first
frame of the new shot.

## 2. Map events to sounds

| visual | sound | align |
|---|---|---|
| hard cut to a new scene | swoosh or short swish; big scene change gets a soft impact | swoosh `peak`, impact `onset` on the cut frame |
| circle/slide wipe | whoosh, low woosh layered with an airy swish | `peak` at the middle of the wipe |
| zoom / push-in | deep whoosh, optionally a riser into it | `peak` where motion is fastest |
| particles gather → logo | reversed shimmer with exponential fade-in | `end` on the lock frame |
| logo locks / resolves | crystal ping or chime (+ tiny pop for transient) | `onset` on the lock frame |
| text type-on (letters) | one soft tick per letter, ±1–4 st variation, slight pan drift | `onset` per letter |
| fast UI typing | real keyboard typing, `tempo` 2.0, `hp` 300 | `onset` at first character |
| tiles / cards popping in | small pops, pitched up through the sequence | `onset` |
| counters / data / grids | short data blip or glitch, high-passed, quiet | `onset` |
| letters flying in to a wordmark | tuned plucks (kalimba/marimba) as an arpeggio in the music's key | `onset` per letter |
| copy that means quiet/pause | **stop-down**: riser into the cut, music hard-stops on it, one low thud, near silence | riser `end`, thud `onset` |
| final hold | the music's own ending chord/tail, faded | — |

One hero sound per moment. Two layers are fine when they cover different bands (low woosh +
airy swish). More than three sounds starting inside 150 ms turns to mush.

## 3. Music

- Pick by structure, not genre alone: length close to the video, an energy arc that matches
  (quiet intro → body → lift → ending), tempo that suits the cut rate. Fetch 4–7 candidates;
  `fetch --role music` prints tempo, beat offset, key, and where energy rises/falls.
- Prefer CC0; CC BY / BY-SA are fine with the credit line. Never NC (non-commercial) or ND.
- Edit by **offset first**: shift the track so its drum entry lands on the first big cut. Then
  check where its lift lands; often it lands on a mid-video transition by luck — keep it.
- Cut music only on a hard visual cut, with a 10–20 ms fade. Hard stops read as intentional
  when the picture also changes. Reuse the track's own ending tail for the resolve (fade in
  0.3 s), so the ending sounds composed.
- Tonal SFX (plucks, chimes, shimmers) should sit in the track's key: shift with `st`. Arpeggios
  from the tonic triad or the final chord of the tail sound best.

## 4. Levels (before mastering)

- Music bus around -16 to -19 dBFS RMS in the body; `music_gain_db` -1.5 is a good start.
- SFX transients may peak 6–10 dB above the music RMS; their RMS should stay a few dB under
  the music. `run mix` flags windows where SFX get louder than the music.
- Ticks and pops quiet (-4 to -14 dB gain on typical UI files); whooshes -3 to -10; impacts
  -7 to -12. Check the "loudest events" list; nothing in the sfx bus should peak above -3 dBFS.
- Silence is a sound: a stop-down should drop 15–20 dB below the body.

## 5. Mastering and delivery

- -14 LUFS integrated, ≤ -1 dBTP (the finish script does this). If the limiter's 90th
  percentile gain reduction is over ~2.5 dB, something is too loud: lower it and re-mix.
- Copy the video stream; never re-encode the picture for an audio change.
- Sync tolerance: hits within about ±2 frames. Audio more than 45 ms *early* is noticeable;
  up to ~80 ms late is forgiven.

## 6. Fresh / same / mix

- **fresh** (default): new music and new SFX; search hides anything used in the last 10 videos.
  Also vary the music style from the previous video unless the brief says otherwise.
- **same**: reuse the brand's previous sounds (`run library brand NAME`), re-timed to the new picture.
- **mix**: keep the brand's signature sounds (logo ping, ticks, main whoosh); fresh music and transitions.

## 7. What you cannot do

You cannot listen. Measurements (alignment, levels, LUFS) are verified; taste is not. Always
tell the user that, and ask for timestamps of anything that feels off.
