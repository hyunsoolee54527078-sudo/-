# BadApple-Part-Edition 🍎

A fan-made **Bad Apple!!** player built in Roblox using Parts, Luau, Python, and Rojo.

The project converts video frames into binary pixel data and displays them on a 48 × 60 grid of Roblox Parts. Playback starts only when a player presses **PLAY**.

## Features

- **48 × 60 pixel display** — 2,880 pixel Parts
- **4,382 frames** at **20 FPS**
- **PLAY button** to start playback manually
- Python tools for extracting video frames and converting JSON data into Luau ModuleScripts
- Split frame data across multiple Luau modules
- Rojo integration for syncing local files with Roblox Studio

## Built With

- [Roblox Studio](https://create.roblox.com/) — game environment
- [Luau](https://luau.org/) — playback and pixel rendering
- [Python](https://www.python.org/) — frame extraction and data conversion
- [OpenCV](https://opencv.org/) and [NumPy](https://numpy.org/) — image processing
- [Rojo](https://rojo.space/) — local project synchronization
- [Rokit](https://github.com/rojo-rbx/rokit) — toolchain management

## Project Structure

```text
.
├── default.project.json
├── rokit.toml
├── extract_frames.py
├── convert_to_luau.py
├── requirements.txt
├── input/
│   └── BadApple.mp4             # Supply your own source video
├── output_48x60_分割/            # Extracted JSON frames (generated)
├── roblox_export_48x60_20f/     # Generated Luau frame modules
├── roblox_scripts/
│   ├── BadAppleScreen.lua
│   └── BadApplePlayer.server.lua
└── roblox_client/
    └── BadApplePlayButton.client.lua
```

Names shown above describe the expected/current project layout; adjust paths to match your local checkout if they differ.

## Requirements

- Windows PowerShell examples below assume Python 3.12.7 or newer.
- Python 3.12.7 or newer
- Roblox Studio
- Rojo 7.7.1 (pinned through Rokit in this project)
- `opencv-python` and `numpy`

Install Python dependencies from the project root:

```powershell
py -3.12 -m pip install -r requirements.txt
```

If you do not use `requirements.txt`, install the packages directly:

```powershell
py -3.12 -m pip install opencv-python numpy
```

## Generate the Frame Data

Place your own source video at `input/BadApple.mp4`, then extract frames at 48 × 60 and 20 FPS:

```powershell
py -3.12 extract_frames.py input/BadApple.mp4 --output "output_48x60_분할" --width 48 --height 60 --fps 20
```

The extractor writes binary pixel matrices to numbered JSON files and creates a `manifest.json` describing the output. Black and white pixels are represented by `0` and `1`.

Convert the extracted JSON into Luau ModuleScripts, with 20 frames per module:

```powershell
py -3.12 convert_to_luau.py --input "output_48x60_분할" --output "roblox_export_48x60_20f" --frames-per-file 20
```

For 4,382 frames, this produces 220 frame modules plus `Manifest.lua`. The last module contains the remaining frames. The converter reads the dimensions, FPS, frame count, module names, and frame ranges from the generated manifest.

> **Tip:** Use a new output folder when regenerating data. The scripts intentionally avoid overwriting existing generated files unless the converter is explicitly run with `--force`.

## Set Up Rojo

This project pins Rojo 7.7.1 using `rokit.toml`.

1. Install [Rokit](https://github.com/rojo-rbx/rokit/releases/latest) using its official installation instructions.
2. Open a terminal in the project root (the folder containing `default.project.json` and `rokit.toml`).
3. Install the pinned tools:

   ```powershell
   rokit install
   rojo --version
   ```

4. Install the Rojo Studio plugin if it is not already installed:

   ```powershell
   rojo plugin install
   ```

   Alternatively, install the [Rojo plugin from Roblox Creator Marketplace](https://create.roblox.com/marketplace/asset/13916111004/Rojo).

## Sync With Roblox Studio

1. Open the intended Roblox place in Studio.
2. From the project root, start the Rojo server:

   ```powershell
   rojo serve
   ```

3. Open the Rojo plugin in Studio and connect to the local server.
4. In Explorer, verify that the project is mapped as follows:

   | Location | Expected contents |
   | --- | --- |
   | `ReplicatedStorage.BadAppleData` | `Manifest` and all frame ModuleScripts listed in the manifest |
   | `ReplicatedStorage.BadApplePlayback` | `RemoteEvent` |
   | `ServerScriptService` | `BadAppleScreen` ModuleScript and `BadApplePlayer` Script |
   | `StarterPlayer.StarterPlayerScripts` | `BadApplePlayButton` LocalScript |

The `default.project.json` file defines these mappings. Rojo syncs the data modules and scripts from the local folders; you do not need to paste each ModuleScript manually.

## Play the Video

1. In Roblox Studio, press **Play** to start the experience.
2. The screen should display the first frame and wait without automatically playing the video.
3. Click the on-screen **PLAY** button to begin playback.
4. Check the Studio Output window for playback status and diagnostic messages.

The server reads the module list and frame ranges from `Manifest.lua`, so playback should not depend on a hard-coded module count. Repeated PLAY requests are intended not to create additional playback loops.

## Performance Notes

The display uses 2,880 Parts. Performance varies by device; lower-powered or mobile devices may experience lag, increased battery use, or heating. Stop the test and let the device cool if it becomes uncomfortably hot.

## Troubleshooting

- **The PLAY button does not appear:** Confirm that `BadApplePlayButton` is under `StarterPlayer > StarterPlayerScripts` and check Output for errors.
- **Clicking PLAY does nothing:** Confirm that `BadApplePlayback` exists as a `RemoteEvent` in `ReplicatedStorage` and that the server script is running.
- **Frame modules are missing:** Check that the folder in `default.project.json` matches the generated output folder and that Rojo is connected to the correct project root.
- **Data conversion reports existing files:** Use a new output folder, or use `--force` only when you intend to replace generated files.

## Credits and Copyright

This is an independent fan-made programming project. **Bad Apple!!** and its original audiovisual content belong to their respective rights holders. This project is not affiliated with or endorsed by the original creators.

Please make sure you have the necessary rights before redistributing the original video or extracted frame data. The source video is not included; provide your own copy if you want to regenerate the frame data.

---

Made as a Roblox programming project. 🍎
