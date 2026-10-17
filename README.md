# BadApple-Part-Edition

A Roblox Studio project that plays **Bad Apple!!** using pixel-like Parts.

The project converts video frames into data that can be loaded by Roblox scripts. The main source files in this repository are organized as shown below.

## Source structure

```text
BadApple-Part-Edition/
├── extract_frames.py
├── convert_to_luau.py
├── default.project.json
└── roblox_scripts/
    ├── BadApplePlayer.server.lua
    └── BadAppleScreen.lua
```

- `extract_frames.py` — extracts frames from the source video and saves frame data.
- `convert_to_luau.py` — converts the extracted frame data into Luau modules for Roblox.
- `default.project.json` — Rojo project configuration.
- `roblox_scripts/BadApplePlayer.server.lua` — server-side playback logic.
- `roblox_scripts/BadAppleScreen.lua` — creates and updates the Part-based screen.

Generated frame data, generated Luau modules, and the source video are separate assets created or supplied during the workflow; they are not listed as source files in the tree above.

## Requirements

- Python 3.12.7 or later
- Python packages: OpenCV and NumPy
- Roblox Studio
- Rojo, for syncing the local project into Roblox Studio

Install the Python dependencies:

```bash
python -m pip install opencv-python numpy
```

## 1. Prepare the video

Place the source video at the path expected by `extract_frames.py` (the default project workflow uses `input/BadApple.mp4`).

Make sure you have permission to use the video and audio you provide.

## 2. Extract frames

Run the extractor:

```bash
python extract_frames.py
```

The script's default settings are configured in the Python source. Check its command-line help for supported options:

```bash
python extract_frames.py --help
```

The project has been tested with a **48 × 60** frame grid at **20 FPS**, producing **4,382 frames**. Your output may differ if you change the input video or extraction settings.

## 3. Convert frames to Luau modules

Run:

```bash
python convert_to_luau.py
```

To split the generated data into modules containing 20 frames each, if supported by your script's command-line options, use:

```bash
python convert_to_luau.py --frames-per-file 20
```

For the 48 × 60, 20 FPS output described above, the generated export contains 220 modules. The exact output folder and filenames depend on the settings in the script.

## 4. Configure Rojo

`default.project.json` defines how Rojo maps local files into Roblox Studio. Open a terminal in the project directory and start Rojo:

```bash
rojo serve
```

Then open Roblox Studio, connect using the Rojo plugin, and sync the project.

If Rojo reports a missing path, check that the paths in `default.project.json` match the folders and generated files actually present on your computer. Generated Luau modules must be placed in the path configured for the frame-data modules.

## 5. Run the playback

After syncing, check that the scripts and generated frame-data modules appear in the expected Roblox services. Start a play test in Roblox Studio and use the playback controls configured in your current project.

The video is rendered using Roblox Parts, so performance depends on the number of pixels, the frame rate, and the device running the experience.

## Performance notes

- A **48 × 60** screen uses **2,880 pixel Parts**.
- Lower the frame dimensions or playback FPS if the experience runs slowly.
- Mobile devices may heat up during prolonged playback. Stop the test and let the device cool if it becomes uncomfortably hot.
- Test changes in Roblox Studio before publishing the experience.

## Troubleshooting

### Rojo does not sync the scripts

- Confirm that `default.project.json` is in the project root.
- Check the configured paths against the actual directory names.
- Make sure Rojo is running and the Roblox Studio Rojo plugin is connected.

### The screen is blank or playback does not start

- Confirm that the generated Luau frame modules exist in the configured path.
- Check the Output window in Roblox Studio for script errors.
- Verify that the playback trigger or controls configured in your project are present and running.

### Playback is slow

- Try a smaller frame grid or lower FPS.
- Avoid running multiple play-test sessions at the same time.

## Credits and rights

**Bad Apple!!** is an existing copyrighted work. This repository is a fan-made technical project and is not affiliated with or endorsed by the original rights holders. Provide your own legally obtained source media and follow Roblox's rules and the rights holders' requirements when sharing or publishing your experience.

## Use Your Own Video

This project is not limited to Bad Apple!! You can use the source code to convert and play other videos as well!

How to use another video

1. Prepare a video file supported by your installed video-processing dependencies.

2. Run the frame extraction script with your video file:
   
   python extract_frames.py your_video.mp4

3. Convert the extracted frame data into Luau modules:
   
   python convert_to_luau.py --input output --output roblox_export

4. Configure "default.project.json" to match your folder structure, then sync the project with Rojo.

5. Run the project in Roblox Studio and adjust the playback settings if needed.

Notes

- You can experiment with different videos, resolutions, frame rates, and threshold values.
- Higher resolutions and frame rates can significantly increase the amount of generated data and the workload on Roblox.
- Make sure you have the necessary rights or permission to use the video you choose.
- The scripts and configuration may need adjustments depending on your video and local setup.
- Update the paths in default.project.json to match your local folder structure.
