# Preparing useful inputs from Logic Pro

The explorer is *workflow-aware*: the more consistently you export, the richer
and more trustworthy the resulting session graph. None of the steps below are
mandatory — stems and a mixdown alone are enough — but each one adds evidence.

Menu paths and option names below follow the official *Logic Pro User Guide*
(Apple; page references from the current Mac edition).

> The prototype never reads your `.logicx` project. Everything here is
> standard Logic export, done by you, in the DAW.

## 1. Export all tracks as audio files

**File > Export > All Tracks as Audio Files** (User Guide p. 184) exports all
audio, software-instrument, and Drummer tracks, one file per track. The
options matter for evidence quality:

- **Range** — documented for single-track and region export (p. 183): choose
  to *extend silence to the project end*, not "Trim Silence at File End" or
  the cycle range, if you want stems the explorer can sum and reconcile
  against the mixdown. The all-tracks dialog does not document a Range
  option, so verify exported stem lengths match the project before relying on
  reconciliation — full-length, aligned stems are a choice, not a guarantee.
- **Include Audio Tail** — extends files to capture instrument release and
  effect tails. Use the same setting for every stem; mixed settings break
  alignment.
- **Include Volume/Pan Automation** — when selected, volume/pan automation is
  *performed* on export (printed into the file); otherwise it is only copied.
  Note which you chose — it decides whether stem levels reflect fader rides.
- **Normalize** — `Off`, `Overload Protection Only`, or `On` (p. 183). For
  level-evidence purposes prefer `Off` (or at most Overload Protection Only)
  and note the choice; `On` destroys relative level information.
- **Bypass Effect Plug-ins** — decides dry vs printed processing. Note it.

## 2. Use consistent, role-revealing names

Filenames are the primary evidence for role inference. The export dialog
builds names from *filename elements* dragged into a Pattern field (Custom,
Project Name, Region Name, **Track Name**, **Track Number**, Increment, date
elements; p. 184-186). A pattern of `Track Number` + `Track Name` produces
exactly the kind of names the scanner reads best:

```
01_Drums.wav
02_Bass.wav
03_Electric_Guitar.wav
05_Lead_Vocal.wav
```

Worth knowing about Logic's own naming behaviour:

- Default track names look like `Audio 1` / `Inst 1`, and **a track takes the
  name of the chosen patch** (p. 129) — so stems named `Alchemy` or
  `Ultrabeat` are common; the explorer recognises documented stock instrument
  names and infers roles from them.
- Multi-renaming tracks or channel strips numbers them sequentially
  (`vox 1`, `vox 2`, `vox 3`; pp. 130, 616) — the explorer treats those
  trailing digits as identity, so notes for `vox 1` never attach to `vox 2`.

## 3. Export a stereo mixdown

**File > Bounce > Project or Section** (p. 909). By default the entire
project from start to end is bounced to a file named after the output channel
strip (e.g. `Output 1-2`) in `~/Music/Logic/Bounces` — rename it to something
unambiguous like `Stereo_Mix.wav`. Options worth noting for evidence:

- **Normalize** — same three states as export; note your choice.
- **Bounce 2nd Cycle Pass** / **Include Audio Tail** — both change effective
  length/content (p. 910); keep consistent with your stem choices.
- Only unmuted tracks routed to the bounced output are included — a muted
  track at bounce time is a real source of stem-sum residual.

## 4. Export MIDI (optional)

**File > Export > Selection as MIDI File** (p. 187) saves the selected MIDI
regions as a Format 1 MIDI file. There is no "export all MIDI tracks"
command: to export a whole project as one MIDI file, merge/join the regions
first (p. 187). The explorer summarises track names, note counts, tempo and
time signatures, and links named MIDI tracks to matching stems.

## 5. Export MusicXML (optional)

**File > Export > Score as MusicXML** (p. 930) — a main-menu command, not a
Score Editor local menu. MusicXML adds notation evidence (parts, keys, time
signatures); it describes *score* structure, **not** mix state.

## 6. Create channel-strip notes (optional but high value)

Because insert chains, sends, and buses are **not** recoverable from audio, a
short CSV is the single most valuable enrichment. Columns:

```
track_name,role,plugins,sends,bus,notes
Lead Vocal,Vocal,"Channel EQ; Compressor; DeEsser 2","Vocal Verb; Slap Delay","Vocal Bus","Main lead vocal chain"
```

Use `;` to separate multiple plug-ins or sends inside a cell. Documented
Logic stock plug-in names (Channel EQ, Compressor, DeEsser 2, Space Designer,
ChromaVerb, Amp Designer, …) are recognised and tagged with their category;
third-party names are kept verbatim as annotations. Where it matters, note
the send mode too — Logic sends are **Pre Fader**, **Post Fader**, or
**Post Pan** (p. 585-587), and none of that is recoverable from stems.

## 7. Include a reference track (optional)

For reference-aware comparison, add a track you consider a useful point of
comparison and note *why*. A reference is a comparison, never an objective
target.

## 8. Note how the stems were exported

This context is essential for honest interpretation. Record:

- Range choice (full project length vs trimmed/cycle) and Include Audio Tail
- **Include Volume/Pan Automation**: performed (printed) or not
- Normalize setting (`Off` / `Overload Protection Only` / `On`)
- Bypass Effect Plug-ins: dry or printed processing
- whether stems came from summing-stack/subgroup buses or individual tracks

You can capture this in the `notes` column of the channel-strip CSV, in the
session manifest's `notes` field, or in a `README` beside your exports.
