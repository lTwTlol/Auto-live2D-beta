<div align="center">
  <a href="README.md">日本語</a> | 
  <a href="README.zh-CN.md">简体中文</a> | 
  <a href="README.en.md">English</a>
</div>

---

# Auto虚拟形象

> A derivative of [852wa/Anime2.5DRig](https://github.com/852wa/Anime2.5DRig).
> This repository: https://github.com/lTwTlol/Auto-live2D-beta

A 2.5D avatar tool that auto-rigs and animates a parts-separated PSD the moment you drop it into the browser.
Setup that used to be done by hand (mesh splitting, deformation, physics) is fully automated. No install required — everything runs client-side.

## Usage

1. Open `index.html` directly in your browser.
2. Drop a parts-separated PSD (or click "Load sample.psd").
3. Auto-rigging runs and it starts moving immediately, with idle motion, blinking, lip-sync and hair physics.

> Camera tracking (MediaPipe FaceMesh) and mic lip-sync only work on https or localhost (browser permission policy). Dropping and playback work even when opened directly via file://.

## Python version (desktop app)

In addition to the browser version, a Python desktop version (`main.py`) is included. Its UI and layout are identical to the browser version.

### Setup

```bash
pip install -r requirements.txt
python main.py
```

- Requirements: Python 3.10+ and Microsoft Edge WebView2 (preinstalled on Windows 11).
- A desktop window opens on launch, and you can drop a PSD exactly like in the browser version.

### OpenSeeFace tracking

The desktop app also supports OpenSeeFace tracking (alongside the webcam tracking). Enable the **OpenSeeFace** toggle in the "Auto" section; it reads the UDP stream on `127.0.0.1:11573`. Run a data source on the same machine first, e.g. the bundled `opennseeface/Binary/facetracker.exe` (or VSeeFace sending VMC to that port).

### Language switching (3 languages)

Use the language dropdown in the top-right (日本語 / English / 简体中文) to switch instantly. The choice is saved locally and kept across restarts.

## What happens automatically

- Accepts [see-through](https://github.com/shitagaki-lab/see-through) output PSDs as-is (`mouth`→`mouth_open` auto-rename)
- **Auto-generates generic closed-eye / closed-mouth diffs when they are missing** (scaled and placed against the anchors, colors auto-matched to lashes/mouth; a dedicated slider fine-tunes position and angle)
  - Prefers `eye_close.psd` (both eyes on one layer, spaced apart) / `mouth_close.psd` in the repo root; falls back to built-in data otherwise
- Low-alpha noise removal (connected-component filter)
- **Automatic left/right split** of eyes, brows, lashes and closed eyes (by connected-component centroid)
- **Automatic anchor detection** for eyelid position, iris center, mouth, neck pivot, etc.
- **Automatic hair strand detection** (peak detection on the hair-tip contour, up to 6 strands per layer)
- Pseudo-3D head turn via per-layer depth assignment (parallax + shear)
- Per-strand dual-spring physics (**stiff at the root, fluffy at the tips**), chest bounce, breathing
- **Cross-fade** between open/closed eye and mouth diffs, pupil stencil clipping (kept inside the sclera)

## Layer naming conventions

Layer names (Japanese "のコピー" and full-width characters are auto-normalized):

| Layer name | Content | Required | Notes |
|---|---|---|---|
| `face` | Face base | ◎ | Anchor reference. Always required |
| `eyewhite` | Sclera (both eyes) | ○ | Left/right auto-split |
| `irides` | Iris (both eyes) | ○ | Gaze movement / pupil scale target |
| `eyelash` | Lashes (open eye) | ○ | |
| `eye_close` | Closed eye | ○ | Cross-faded on blink |
| `eyebrow` | Brows (both sides) | ○ | Angle / up-down target |
| `mouth_open` | Open mouth | ○ | Jaw lowers with openness |
| `mouth_close` | Closed mouth | ○ | |
| `nose` | Nose | | |
| `ears` | Ears | | |
| `earwear` | Ear accessories | | |
| `neck` | Neck | | Top follows the head |
| `topwear` | Upper-body clothing | | Breathing / chest-bounce target |
| `bottomwear` | Lower-body clothing | | |
| `handwear` | Arms / hands | | Arm-height target |
| `headwear` | Hat / headband, etc. | | |
| `front hair` | Front hair | | Strand physics + 3-block control |
| `back hair` | Back hair | | Strand physics |

- **Splitting hair across layers**: suffix with a number like `front hair_1`, `front hair_2`, `back hair_1`, … so each layer becomes an independent strand group for physics (strand count is auto-determined from layer width).
- Layers with non-conventional names are still loaded (their head/body position is estimated and they just follow).
- Layer groups (folders) are not supported. Keep the structure flat.
- **About neck and topwear**: using see-through output as-is can make the neck/torso front-back relationship hard to resolve, and the seam may break when moving. If that happens, merging the neck into the torso layer (no `neck` layer, include the neck in `topwear`) tends to work better.
- A square canvas is recommended (tested from 768×768 to 2048×2048).

## Features

Expression presets (smile / surprised / half-lidded / wink L/R), independent left/right eye openness, brow angle (independent + symmetric), gaze, pupil scale, eye/mouth "close ease" thresholds, 3-block front-hair control with **front-hair-only sway and softness**, arm height/position, chest bounce (strength + position), body tilt, idle/random motion, random lip-sync, mic lip-sync, mouse tracking, **webcam tracking** (head XYZ, left/right blink, mouth, gaze), background switching (transparent / green screen), **3-language UI** (日本語/English/简体中文).

## Structure

```
index.html        App body (UI + WebGL runtime + i18n)
lib/rigger.js     Auto-rig generation (pure TypedArray implementation, testable in Node)
lib/ag-psd.min.js  PSD parser (ag-psd, MIT)
lib/genericparts.js  Generic closed-eye / closed-mouth diffs (built-in fallback)
main.py           Python desktop entry (pywebview)
requirements.txt  Python dependencies
eye_close.psd     Closed-eye diff source (optional, replaceable)
mouth_close.psd   Closed-mouth diff source (optional, replaceable)
sample.psd        Sample model (place your own)
```

The runtime is WebGL1 (mesh warp + stencil). The only external communication is the MediaPipe CDN load when camera tracking is enabled.

## Known limitations

- Single-image decomposition is not performed in-app. Drop a PSD already separated with the [see-through official demo (HuggingFace Space)](https://huggingface.co/spaces/24yearsold/see-through-demo) etc. (post-processing is fully automatic)
- Mouth openness is a simplified expression using diff switching + deformation (smoother with more intermediate diffs)
- Depth is a name-based fixed table (layer order is still respected from the PSD)

## License

MIT (bundled ag-psd is also MIT; MediaPipe is Apache-2.0, referenced via CDN).

Single-image layer decomposition assumes use of [shitagaki-lab/see-through](https://github.com/shitagaki-lab/see-through) (Apache-2.0, SIGGRAPH 2026). This tool is an independent third-party tool that handles post-processing and rigging of that project's output PSDs; it does not bundle see-through's code or models.
**The rights to the sample PSD art belong to their respective authors.** When distributing your own models, please use art you have the rights to.
