# Preparing useful inputs from Logic Pro

The explorer is *workflow-aware*: the more consistently you export, the richer
and more trustworthy the resulting session graph. None of the steps below are
mandatory — stems and a mixdown alone are enough — but each one adds evidence.

> The prototype never reads your `.logicx` project. Everything here is standard
> Logic export, done by you, in the DAW.

## 1. Export / bounce all tracks as audio

In Logic Pro use **File ▸ Export ▸ All Tracks as Audio Files…** (or bounce each
track). This gives one audio file per track or per printed stem.

## 2. Use consistent, role-revealing names

Filenames are the primary evidence for role inference. Prefer a leading index
plus a clear role word:

```
01_Drums.wav
02_Bass.wav
03_Electric_Guitar.wav
04_Synth_Pad.wav
05_Lead_Vocal.wav
06_Backing_Vocals.wav
```

The scanner reads a leading `01_`, `1 - `, or `Track 03 ` as a track index, and
matches role keywords such as `vocal`, `drums`, `bass`, `guitar`, `synth`, `pad`.

## 3. Export a stereo mixdown

Bounce the full mix (**File ▸ Bounce ▸ Project or Section…**) and name it so it
is unambiguous, e.g. `Stereo_Mix.wav` or `Full_Mix_Master.wav`. Strong mixdown
keywords (`stereo mix`, `master`, `mixdown`, `full mix`) are detected even when
individual stems are also named "…Bounce".

## 4. Export MIDI (optional)

For programmed or scored parts, **File ▸ Export ▸ Selection as MIDI File…**
lets the explorer summarise track names, note counts, tempo and time signatures,
and link named MIDI tracks to matching stems.

## 5. Export MusicXML (optional)

From the Score editor, export MusicXML to add notation evidence (parts, keys,
time signatures). MusicXML describes *score* structure, **not** mix state.

## 6. Create channel-strip notes (optional but high value)

Because plug-in chains, sends and buses are **not** recoverable from audio, a
short CSV is the single most valuable enrichment. Columns:

```
track_name,role,plugins,sends,bus,notes
Lead Vocal,Vocal,"Channel EQ; Compressor; DeEsser","Vocal Verb; Slap Delay","Vocal Bus","Main lead vocal chain"
```

Use `;` to separate multiple plug-ins or sends inside a cell. These are recorded
as *user-provided annotations*, clearly distinct from observed export data.

## 7. Include a reference track (optional)

For reference-aware comparison, add a track you consider a useful point of
comparison and note *why*. A reference is a comparison, never an objective
target.

## 8. Note how the stems were exported

This context is essential for honest interpretation. Record whether stems are:

- pre-fader or post-fader
- post-insert (printed processing) or dry
- normalized
- routed through buses / summed

You can capture this in the `notes` column of the channel-strip CSV, in the
session manifest's `notes` field, or in a `README` beside your exports.
