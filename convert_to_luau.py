"""Convert extracted binary JSON frames to Luau ModuleScript source files."""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
import tempfile
from pathlib import Path
from typing import Any, Iterator


MINIMUM_PYTHON = (3, 12, 7)
FRAME_FILE_PATTERN = re.compile(r"frames_(\d+)\.json\Z")


class ConversionError(Exception):
    """Raised when input data is invalid or output cannot be written safely."""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Convert extracted frame JSON files to Luau ModuleScripts."
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("output"),
        help="folder containing manifest.json and frames_*.json (default: output)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("roblox_export"),
        help="output folder (default: roblox_export)",
    )
    parser.add_argument(
        "--frames-per-file",
        type=int,
        default=500,
        help="maximum frames per Luau module (default: 500)",
    )
    parser.add_argument(
        "--fps",
        type=float,
        help="override FPS from manifest.json",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="allow replacing generated Luau files already in the output folder",
    )
    return parser


def read_json(path: Path) -> Any:
    try:
        with path.open("r", encoding="utf-8") as file:
            return json.load(file)
    except json.JSONDecodeError as error:
        raise ConversionError(
            f"{path.name}: invalid JSON at line {error.lineno}, "
            f"column {error.colno}: {error.msg}"
        ) from error
    except OSError as error:
        raise ConversionError(f"could not read {path}: {error}") from error


def positive_integer(value: Any, field: str) -> int:
    if type(value) is not int or value <= 0:
        raise ConversionError(f"manifest field {field} must be a positive integer")
    return value


def get_manifest_settings(
    manifest: Any, fps_override: float | None
) -> tuple[int, int, float, int | None]:
    if not isinstance(manifest, dict):
        raise ConversionError("manifest.json: expected a JSON object")
    output = manifest.get("output")
    if not isinstance(output, dict):
        raise ConversionError("manifest.json: missing output metadata object")

    width = positive_integer(output.get("width"), "output.width")
    height = positive_integer(output.get("height"), "output.height")
    manifest_fps = output.get("fps")
    fps = fps_override if fps_override is not None else manifest_fps
    if (
        isinstance(fps, bool)
        or not isinstance(fps, (int, float))
        or not math.isfinite(fps)
        or fps <= 0
    ):
        raise ConversionError(
            "manifest output.fps must be a finite positive number, "
            "or provide --fps"
        )

    expected_count = output.get(
        "extracted_frame_count", output.get("frame_count")
    )
    if expected_count is not None:
        if type(expected_count) is not int or expected_count < 0:
            raise ConversionError(
                "manifest output.frame_count must be a non-negative integer"
            )
    return width, height, float(fps), expected_count


def discover_frame_files(input_dir: Path, manifest: Any) -> list[Path]:
    output_metadata = manifest["output"]
    names = output_metadata.get("json_files")
    if names is None:
        names = [
            path.name
            for path in input_dir.iterdir()
            if path.is_file() and FRAME_FILE_PATTERN.fullmatch(path.name)
        ]
    if not isinstance(names, list) or not names:
        raise ConversionError(
            "manifest.json must list frame JSON files or input must contain "
            "frames_*.json files"
        )

    paths: list[tuple[int, Path]] = []
    seen_names: set[str] = set()
    for name in names:
        if not isinstance(name, str):
            raise ConversionError("manifest output.json_files must contain filenames")
        match = FRAME_FILE_PATTERN.fullmatch(name)
        if match is None or Path(name).name != name:
            raise ConversionError(
                f"manifest.json contains an invalid frame filename: {name!r}"
            )
        if name in seen_names:
            raise ConversionError(f"manifest.json lists {name} more than once")
        seen_names.add(name)
        paths.append((int(match.group(1)), input_dir / name))

    paths.sort(key=lambda item: item[0])
    if len({number for number, _ in paths}) != len(paths):
        raise ConversionError("manifest.json lists duplicate numbered frame files")
    for _, path in paths:
        if not path.is_file():
            raise ConversionError(f"frame file does not exist: {path.name}")
    return [path for _, path in paths]


def validate_frame(
    frame: Any,
    filename: str,
    expected_index: int,
    width: int,
    height: int,
) -> list[int]:
    if not isinstance(frame, dict):
        raise ConversionError(
            f"{filename}: frame index {expected_index}: expected an object"
        )
    frame_index = frame.get("frame")
    if type(frame_index) is not int:
        raise ConversionError(
            f"{filename}: frame index {expected_index}: "
            "field 'frame' must be an integer"
        )
    if frame_index != expected_index:
        raise ConversionError(
            f"{filename}: frame index {frame_index}: expected "
            f"consecutive index {expected_index}"
        )

    pixels = frame.get("pixels")
    if not isinstance(pixels, list) or len(pixels) != height:
        actual_rows = len(pixels) if isinstance(pixels, list) else "non-array"
        raise ConversionError(
            f"{filename}: frame index {frame_index}: expected {height} pixel rows, "
            f"found {actual_rows}"
        )

    flattened: list[int] = []
    for row_index, row in enumerate(pixels):
        if not isinstance(row, list) or len(row) != width:
            actual_columns = len(row) if isinstance(row, list) else "non-array"
            raise ConversionError(
                f"{filename}: frame index {frame_index}: pixel row {row_index} "
                f"must contain {width} values, found {actual_columns}"
            )
        for column_index, pixel in enumerate(row):
            if type(pixel) is not int or pixel not in (0, 1):
                raise ConversionError(
                    f"{filename}: frame index {frame_index}: pixel "
                    f"({row_index}, {column_index}) must be integer 0 or 1"
                )
            flattened.append(pixel)
    return flattened


def iter_validated_frames(
    input_files: list[Path], width: int, height: int
) -> Iterator[tuple[int, list[int]]]:
    expected_index = 0
    for path in input_files:
        data = read_json(path)
        if not isinstance(data, list):
            raise ConversionError(f"{path.name}: expected a JSON array of frames")
        for frame in data:
            pixels = validate_frame(
                frame, path.name, expected_index, width, height
            )
            yield expected_index, pixels
            expected_index += 1


def progress(stage: str, completed: int, total: int) -> None:
    if total:
        percent = min(100.0, completed / total * 100)
        message = f"\r{stage}: {percent:6.2f}% ({completed}/{total} frames)"
    else:
        message = f"\r{stage}: {completed} frames"
    print(message, end="", file=sys.stderr, flush=True)


def module_names(frame_count: int, frames_per_file: int) -> list[str]:
    module_count = (frame_count + frames_per_file - 1) // frames_per_file
    return [f"Frames_{index:03d}.lua" for index in range(module_count)]


def output_manifest_source(
    width: int,
    height: int,
    fps: float,
    frame_count: int,
    frames_per_file: int,
    filenames: list[str],
) -> str:
    lines = [
        "return {",
        f"    width = {width},",
        f"    height = {height},",
        f"    pixelsPerFrame = {width * height},",
        f"    fps = {fps:g},",
        f"    frameCount = {frame_count},",
        f"    framesPerFile = {frames_per_file},",
        "    modules = {",
    ]
    lines.extend(f'        "{name}",' for name in filenames)
    lines.extend(["    },", "    ranges = {"])
    for module_index, filename in enumerate(filenames):
        first_frame = module_index * frames_per_file
        last_frame = min(first_frame + frames_per_file, frame_count) - 1
        lines.append(
            f'        {{ file = "{filename}", startFrame = {first_frame}, '
            f"endFrame = {last_frame} }},"
        )
    lines.extend(["    },", "}", ""])
    return "\n".join(lines)


def render_module(
    destination: Path,
    frames: list[tuple[int, list[int]]],
) -> None:
    with destination.open("w", encoding="utf-8", newline="\n") as file:
        file.write(f"-- {destination.name}\nreturn {{\n")
        for frame_index, pixels in frames:
            pixel_values = ", ".join(str(pixel) for pixel in pixels)
            file.write(f"    [{frame_index}] = {{{pixel_values}}},\n")
        file.write("}\n")


def convert(args: argparse.Namespace) -> tuple[int, int, list[str]]:
    if not args.input.exists() or not args.input.is_dir():
        raise ConversionError(f"input folder does not exist: {args.input}")
    manifest_path = args.input / "manifest.json"
    if not manifest_path.is_file():
        raise ConversionError(f"manifest.json does not exist in {args.input}")
    if args.frames_per_file <= 0:
        raise ConversionError("--frames-per-file must be a positive integer")
    if args.fps is not None and (
        not math.isfinite(args.fps) or args.fps <= 0
    ):
        raise ConversionError("--fps must be a finite number greater than zero")
    if args.output.exists() and not args.output.is_dir():
        raise ConversionError(f"output path is not a folder: {args.output}")

    manifest = read_json(manifest_path)
    width, height, fps, expected_count = get_manifest_settings(
        manifest, args.fps
    )
    input_files = discover_frame_files(args.input, manifest)

    frame_count = 0
    for _ in iter_validated_frames(input_files, width, height):
        frame_count += 1
        if expected_count is not None and (
            frame_count % 100 == 0 or frame_count == expected_count
        ):
            progress("Validating", frame_count, expected_count)
    if expected_count is not None and frame_count != expected_count:
        raise ConversionError(
            "manifest frame count mismatch: expected "
            f"{expected_count}, found {frame_count}"
        )
    if expected_count is None:
        progress("Validated", frame_count, frame_count)
    print(file=sys.stderr)

    filenames = module_names(frame_count, args.frames_per_file)
    target_names = {"Manifest.lua", *filenames}
    if args.output.exists():
        conflicts = sorted(
            name for name in target_names if (args.output / name).exists()
        )
        if conflicts and not args.force:
            raise ConversionError(
                "output files already exist and were not modified: "
                f"{', '.join(conflicts[:5])}; use --force to replace them"
            )

    args.output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".luau-stage-", dir=args.output) as stage:
        stage_dir = Path(stage)
        module_frames: list[tuple[int, list[int]]] = []
        written_count = 0
        module_index = 0

        for frame_index, pixels in iter_validated_frames(input_files, width, height):
            module_frames.append((frame_index, pixels))
            written_count += 1
            if len(module_frames) == args.frames_per_file or frame_index == frame_count - 1:
                filename = filenames[module_index]
                render_module(stage_dir / filename, module_frames)
                module_frames = []
                module_index += 1
            if written_count % 100 == 0 or written_count == frame_count:
                progress("Converting", written_count, frame_count)

        if written_count != frame_count or module_index != len(filenames):
            raise ConversionError(
                "input changed during conversion; frame or module count differs "
                "from validation"
            )

        manifest_source = output_manifest_source(
            width, height, fps, frame_count, args.frames_per_file, filenames
        )
        (stage_dir / "Manifest.lua").write_text(
            manifest_source, encoding="utf-8", newline="\n"
        )

        for name in filenames:
            (stage_dir / name).replace(args.output / name)
        (stage_dir / "Manifest.lua").replace(args.output / "Manifest.lua")

    print(file=sys.stderr)
    return frame_count, len(filenames), filenames


def main() -> int:
    if sys.version_info < MINIMUM_PYTHON:
        print(
            "Python 3.12.7 or newer is required; "
            f"current version is {sys.version.split()[0]}",
            file=sys.stderr,
        )
        return 2

    parser = build_parser()
    args = parser.parse_args()
    try:
        frame_count, module_count, filenames = convert(args)
    except (ConversionError, OSError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1
    print(
        f"Converted {frame_count} frames into {module_count} modules "
        f"in {args.output}"
    )
    print(f"Generated: Manifest.lua, {', '.join(filenames)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
