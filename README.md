# Odia Voice Clone — Piper TTS (Android-only workflow)

Clone your own voice in Odia and produce a `.onnx` + `.onnx.json` Piper voice model,
driven entirely from an Android phone. No PC required.

## Why this shape

Piper voice training needs a GPU. GitHub Actions' free runners are CPU-only, so they
can't do the actual training in reasonable time. GitHub is used here for:
- Storing your dataset + scripts (repo)
- Validating your recordings automatically (CI, runs on every push)
- Packaging the final release

**Kaggle Notebooks** (free, 30 GPU-hrs/week, works in a phone browser) does the
actual training. You trigger it manually from your phone by opening the notebook
and tapping "Run All" — no PC involved anywhere.

## Full pipeline

```
[Android: record voice] 
        │
        ▼
[Android: GitHub app / termux / mobile browser → push to repo]
        │
        ▼
[GitHub Actions: validates dataset on push] ← runs automatically
        │
        ▼
[Kaggle Notebook: pulls repo, fine-tunes Piper] ← you tap "Run All" from phone
        │
        ▼
[odia.onnx + odia.onnx.json] → download to phone
```

## Step-by-step

### 1. Record your voice (on Android)
- Use any recorder app that can save **WAV, 22050 Hz, mono, 16-bit**
  (e.g. "RecForge II", "Easy Voice Recorder" with WAV export set manually in settings).
- Record 100–300 short Odia sentences. More = better clone. 300+ is noticeably
  better than 100.
- Keep each clip to one sentence, minimal background noise, consistent mic distance.
- Name files `wav_0001.wav`, `wav_0002.wav`, ... in order (see `dataset/metadata.csv`).

### 2. Build metadata.csv
Format (pipe-separated, LJSpeech-style), one line per clip:
```
wav_0001|ଆପଣ କେମିତି ଅଛନ୍ତି
wav_0002|ମୋର ନାଁ ଅଲେକ୍ସ
```
Use any Android text editor (or Google Keep → export as .txt → rename to .csv).
See `dataset/metadata.csv` for a starter template with ~20 common Odia sentences
you can read and replace/extend.

### 3. Push to GitHub (from Android)
Options, no PC needed:
- **GitHub mobile app**: can create files/commits directly but bulk WAV upload is
  clunky through it.
- **Working Copy (iOS) / MGit or Termux+git (Android)**: better for bulk file
  upload. Termux is the most reliable:
  ```bash
  pkg install git
  git clone https://github.com/<you>/odia-voice-clone.git
  cp /sdcard/Recordings/*.wav odia-voice-clone/dataset/wavs/
  cd odia-voice-clone
  git add .
  git commit -m "Add recordings"
  git push
  ```
- Or zip the wavs on-device and upload via GitHub's web uploader (mobile Chrome
  supports drag-and-drop / file picker for repo uploads, handles zips if you
  unzip first — GitHub web UI doesn't auto-extract, so upload the individual
  wav files or use Termux instead for anything beyond a few dozen files).

### 4. Let CI validate
On every push, `.github/workflows/validate-dataset.yml` runs automatically and checks:
- Every wav in metadata.csv actually exists
- Sample rate / channel / bit depth are correct
- No empty transcripts
- Reports total recorded duration

Check the **Actions** tab in the GitHub mobile app or mobile browser after pushing.
Fix anything it flags before training — garbage in, garbage voice out.

### 5. Train on Kaggle (from phone browser)
1. Go to kaggle.com on your phone, sign in, create a new Notebook.
2. Turn on GPU: Notebook settings → Accelerator → GPU T4 x2 (or similar).
3. Copy the contents of `scripts/kaggle_train.py` into a notebook cell
   (it's written to run top-to-bottom as one script).
4. Edit the `GITHUB_REPO` variable at the top to point to your repo.
5. Tap **Run All**. Training runs in Kaggle's cloud — your phone just needs to
   stay on the page long enough to start it; Kaggle continues running the
   session even if you background the browser tab (session persists on their
   servers for a while, but don't fully close the notebook until it's done for
   the first run so you can watch for errors).
6. When done, the script zips `odia.onnx` + `odia.onnx.json` into
   `/kaggle/working/output.zip` — download it via Kaggle's Output panel.

### 6. Use your voice model
Copy `odia.onnx` + `odia.onnx.json` onto your phone (Kaggle → Download).
Load them with `sherpa-onnx` or Piper's Android runtime in your app — this
plugs directly into the TTS work you've already been doing (Piper ONNX +
`odiaToIpa()` phoneme mapping) for the Odia TTS app.

## Files in this project

- `dataset/metadata.csv` — transcript template, LJSpeech format
- `dataset/wavs/` — put your recordings here
- `scripts/kaggle_train.py` — the actual fine-tuning script, run on Kaggle
- `scripts/validate_dataset.py` — checks used by CI, also runnable manually
- `.github/workflows/validate-dataset.yml` — auto-runs validation on push

## Realistic expectations

- 100 sentences: usable but noticeably synthetic/approximate clone.
- 300+ sentences, clean audio, consistent recording conditions: good clone quality.
- 1000+: approaching very natural output.
- Training time on Kaggle T4 GPU for a fine-tune (not from scratch): roughly
  1–4 hours depending on dataset size and epochs — fits well inside Kaggle's
  free weekly GPU quota.
