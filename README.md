# Video frame extractor

`extract_frames.py` samples a video by its source frame rate and duration, resizes each selected frame, converts it to grayscale, and thresholds it into binary pixels. Frames are processed one at a time and written as numbered JSON records split across multiple files.

## Requirements

- Python 3.12.7 or newer (Python 3.13 and newer are also supported)
- OpenCV and NumPy

Install the dependencies on Windows:

```powershell
py -m pip install opencv-python numpy
```

Or install the versions declared in `requirements.txt`:

```powershell
py -m pip install -r requirements.txt
```

## Run

```powershell
py extract_frames.py input/BadApple.mp4 --output output
```

The default output is 24 pixels wide by 30 pixels high, sampled at 20 FPS. For every output timestamp, the extractor selects the nearest source frame based on the video's reported FPS. For videos whose output FPS exceeds the source FPS, a source frame can be used more than once.

## Command-line options

| Option | Default | Description |
| --- | --- | --- |
| `video` | Required | Source video path |
| `--output PATH` | `output` | Output directory |
| `--width N` | `24` | Output pixel width |
| `--height N` | `30` | Output pixel height |
| `--fps N` | `20` | Output sampling rate |
| `--threshold N` | `127` | Grayscale threshold from 0 to 255 |
| `--frames-per-file N` | `500` | Maximum records in each JSON file |
| `--preview` | Off | Save binary PNG previews under `output/previews` |

For example, save previews and use a different sampling rate:

```powershell
py extract_frames.py input/BadApple.mp4 --output output --fps 20 --preview
```

## Output format

Each `frames_XXXXX.json` file contains a JSON array. Every entry has a zero-based output frame number and a matrix with `height` rows and `width` columns:

```json
[
  {
    "frame": 0,
    "pixels": [
      [0, 1, 0]
    ]
  }
]
```

The example matrix is abbreviated; the default matrix has 30 rows and 24 values per row. Black pixels are `0`; white pixels are `1`. `manifest.json` records source video metadata, extraction settings, the extracted frame count, and the generated JSON filenames.

The program validates the Python version before opening the video, reports progress while decoding, handles invalid paths and decoding/writing errors, and reopens the JSON files to verify the frame numbering and pixel dimensions before writing the manifest. It does not overwrite an existing `manifest.json` or `frames_XXXXX.json`; choose a new output folder if these files already exist.

If decoding stops before the frame count reported by the video, successfully decoded frames are still sampled and saved. The manifest records the reported and decoded source frame counts, actual extracted frame count, output FPS and resolution, decoded duration, partial-decoding status, decoder status, JSON validation status, and any warnings. OpenCV reports a failed `VideoCapture.read()` as no frame; it does not always distinguish an early end-of-stream from a decoding error. Exceptions raised by the decoder are recorded separately as `decoder_error`.

## JSON frames to Luau ModuleScripts

`convert_to_luau.py` converts `manifest.json` and the `frames_XXXXX.json` files into Luau modules. It validates the manifest, consecutive frame indices, pixel matrix dimensions, and binary pixel values before writing. No additional Python packages are required.

```powershell
py -3.12 convert_to_luau.py --input output --output roblox_export
```

The converter defaults to 500 frames per module and reads the FPS from `manifest.json`. These options are also available:

```powershell
py -3.12 convert_to_luau.py --input output --output roblox_export --frames-per-file 250 --fps 20
py -3.12 convert_to_luau.py --input output --output roblox_export --force
```

`--force` explicitly allows replacing generated `Frames_XXX.lua` and `Manifest.lua` files in the destination. Without it, a collision is reported and existing files are left untouched. The generated `Manifest.lua` contains the output dimensions, pixels per frame, FPS, total frame count, module filenames, and frame ranges.

To use the files in Roblox Studio, create a `ModuleScript` for each generated `.lua` file in Explorer, open it, and paste in the corresponding file contents. Keep each script's name aligned with the generated module filename (without `.lua`) so that the module list in `Manifest.lua` can be used to locate the frame modules. The converter only generates data modules; it does not create playback or Part-generation scripts.

Run the converter tests and syntax check with:

```powershell
py -3.12 -m unittest test_convert_to_luau.py
py -3.12 -m py_compile convert_to_luau.py
```

## Roblox Studio playback

Rojo maps `roblox_export_48x60_20f/` to `ReplicatedStorage.BadAppleData`, `roblox_scripts/` to `ServerScriptService`, and `roblox_client/` to `StarterPlayer.StarterPlayerScripts`. `ReplicatedStorage.BadApplePlayback` is a `RemoteEvent` declared in `default.project.json`.

The generated data manifest describes 48×60 (2880 pixels), 4382 frames at 20 FPS, split into 220 frame modules with 20 frames per module. The server reads `modules` and `ranges` from `Manifest.lua` and loads them in order; it does not depend on a hard-coded module count.

The server validates and loads the data at startup and prepares the screen on frame 0, but it does not advance frames automatically. Each player sees a `PLAY` button created by `BadApplePlayButton.client.lua`. Clicking it sends a `Start` request to the server. A single server-side playback guard ensures repeated clicks cannot create additional Heartbeat connections; the same RemoteEvent also reports playback state to clients.

To test in Roblox Studio:

1. Run `rojo serve` from the project root and connect Studio using the Rojo plugin.
2. Check that `ReplicatedStorage.BadAppleData` contains `Manifest` and all listed frame ModuleScripts, `ReplicatedStorage.BadApplePlayback` is a RemoteEvent, `ServerScriptService` contains `BadApplePlayer` and `BadAppleScreen`, and `StarterPlayer.StarterPlayerScripts` contains `BadApplePlayButton`.
3. Press **Play**. The screen should remain on its first frame until a player clicks **PLAY**.
4. Click **PLAY** and check Output for `Playback started` and frame/FPS/loaded-count messages. Clicks after playback starts should not create another playback loop. Joining during playback should show the button as `PLAYING`.

The screen Part size, spacing, and placement remain configurable in `BadAppleScreen.lua`.

## Rojo 자동 동기화 설정 (한국어)

프로젝트 루트의 `default.project.json`은 Rojo 7 프로젝트 형식입니다. `roblox_export_48x60_20f/` 폴더 전체를 `ReplicatedStorage/BadAppleData`로 연결하므로 manifest의 `modules` 목록에 있는 모든 프레임 모듈이 동기화됩니다. `roblox_scripts/BadAppleScreen.lua`는 `ServerScriptService`의 ModuleScript, `BadApplePlayer.server.lua`는 같은 위치의 Script, `roblox_client/BadApplePlayButton.client.lua`는 `StarterPlayer.StarterPlayerScripts`의 LocalScript로 인식됩니다. 같은 project 설정에서 `ReplicatedStorage.BadApplePlayback` RemoteEvent도 생성됩니다.

### 설치

1. [Rokit 최신 릴리스](https://github.com/rojo-rbx/rokit/releases/latest)에서 Windows용 `rokit.exe`를 내려받아 실행하거나, PowerShell에서 Rokit 공식 설치 스크립트를 실행합니다.

   ```powershell
   Invoke-RestMethod https://raw.githubusercontent.com/rojo-rbx/rokit/main/scripts/install.ps1 | Invoke-Expression
   ```

2. 새 터미널을 열고 프로젝트 루트(`default.project.json`이 있는 폴더)에서 프로젝트에 고정된 Rojo 7.7.1을 설치합니다.

   ```powershell
   rokit install
   rojo --version
   ```

3. Roblox Studio 플러그인을 설치합니다.

   ```powershell
   rojo plugin install
   ```

   또는 [Roblox Creator Marketplace의 Rojo 플러그인](https://create.roblox.com/marketplace/asset/13916111004/Rojo)을 Studio에 설치합니다.

### Studio 연결 및 확인

1. Roblox Studio에서 작업할 place를 엽니다.
2. 프로젝트 루트에서 Rojo 서버를 시작합니다.

   ```powershell
   rojo serve
   ```

3. Studio의 Rojo 플러그인을 열고 **Connect**를 눌러 로컬 Rojo 서버에 연결합니다. 처음 연결할 때 동기화 결과를 확인하고, 원하지 않는 place에 연결하지 않았는지 확인합니다.
4. Explorer에서 `ReplicatedStorage > BadAppleData` 아래에 Manifest와 manifest에 나열된 프레임 ModuleScript가 모두 있는지 확인합니다. 현재 48×60 데이터는 `Frames_000`~`Frames_219`의 220개 파일입니다. 같은 서비스에 `BadApplePlayback` RemoteEvent가 있고, `ServerScriptService`에 `BadAppleScreen` ModuleScript와 `BadApplePlayer` Script, `StarterPlayer > StarterPlayerScripts`에 `BadApplePlayButton` LocalScript가 있는지 확인합니다.
5. Studio에서 **Play**를 누르면 영상은 자동 재생되지 않으며 `PLAY` 버튼이 표시됩니다. 클릭 후 Output에 재생 시작과 현재 프레임, FPS, 로딩 프레임 수가 표시되는지 확인합니다. 여러 번 눌러도 재생 루프는 하나만 유지됩니다.

Rojo 동기화는 `roblox_export_48x60_20f/`, `roblox_scripts/`, `roblox_client/`의 파일과 프로젝트에 선언된 RemoteEvent를 Studio 인스턴스에 반영합니다. 출력 데이터를 다시 생성하거나 수정한 뒤에는 파일 저장을 확인하고 Studio Explorer의 동기화 결과를 확인하세요.
