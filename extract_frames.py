"""Extract time-sampled, binary frames from a video into JSON files."""

from __future__ import annotations

import argparse
import json
import math
import sys
from fractions import Fraction
from pathlib import Path
from typing import Any


MINIMUM_PYTHON = (3, 12, 7)
DEFAULT_WIDTH = 24
DEFAULT_HEIGHT = 30
DEFAULT_FPS = 20
DEFAULT_THRESHOLD = 127
DEFAULT_FRAMES_PER_FILE = 500


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Sample a video by time and save binary frames as JSON."
    )
    parser.add_argument("video", type=Path, help="source video path")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("output"),
        help="output folder (default: output)",
    )
    parser.add_argument("--width", type=int, default=DEFAULT_WIDTH)
    parser.add_argument("--height", type=int, default=DEFAULT_HEIGHT)
    parser.add_argument("--fps", type=float, default=DEFAULT_FPS, dest="output_fps")
    parser.add_argument(
        "--threshold",
        type=int,
        default=DEFAULT_THRESHOLD,
        help="grayscale threshold from 0 to 255 (default: 127)",
    )
    parser.add_argument(
        "--frames-per-file",
        type=int,
        default=DEFAULT_FRAMES_PER_FILE,
        help="maximum frames in each JSON file (default: 500)",
    )
    parser.add_argument(
        "--preview",
        action="store_true",
        help="also save each binary frame as a PNG in output/previews",
    )
    return parser


def validate_options(parser: argparse.ArgumentParser, args: argparse.Namespace) -> None:
    if not args.video.exists() or not args.video.is_file():
        parser.error(f"video file does not exist: {args.video}")
    if args.width <= 0 or args.height <= 0:
        parser.error("--width and --height must be positive integers")
    if not math.isfinite(args.output_fps) or args.output_fps <= 0:
        parser.error("--fps must be a finite number greater than zero")
    if not 0 <= args.threshold <= 255:
        parser.error("--threshold must be between 0 and 255")
    if args.frames_per_file <= 0:
        parser.error("--frames-per-file must be a positive integer")


def show_progress(decoded_frames: int, source_frames: int, extracted_frames: int) -> None:
    if source_frames > 0:
        percent = min(100.0, decoded_frames / source_frames * 100)
        message = (
            f"\rProgress: {percent:6.2f}% "
            f"({decoded_frames}/{source_frames} source frames; "
            f"{extracted_frames} sampled)"
        )
    else:
        message = (
            f"\rDecoded {decoded_frames} source frames; "
            f"{extracted_frames} sampled"
        )
    print(message, end="", file=sys.stderr, flush=True)


def save_chunk(
    output_dir: Path,
    chunk_number: int,
    frames: list[dict[str, Any]],
) -> str:
    filename = f"frames_{chunk_number:05d}.json"
    path = output_dir / filename
    with path.open("x", encoding="utf-8", newline="\n") as file:
        json.dump(frames, file, ensure_ascii=False, separators=(",", ":"))
        file.write("\n")
    return filename


def verify_json_files(
    output_dir: Path,
    filenames: list[str],
    expected_count: int,
    width: int,
    height: int,
) -> None:
    actual_count = 0
    for filename in filenames:
        path = output_dir / filename
        try:
            with path.open("r", encoding="utf-8") as file:
                frames = json.load(file)
        except (OSError, json.JSONDecodeError) as error:
            raise RuntimeError(f"could not verify JSON file {path}: {error}") from error

        if not isinstance(frames, list):
            raise RuntimeError(f"invalid frame data in {path}: expected a JSON array")
        for frame in frames:
            if not isinstance(frame, dict) or frame.get("frame") != actual_count:
                raise RuntimeError(
                    f"invalid frame numbering in {path}; expected frame {actual_count}"
                )
            pixels = frame.get("pixels")
            if (
                not isinstance(pixels, list)
                or len(pixels) != height
                or any(
                    not isinstance(row, list)
                    or len(row) != width
                    or any(type(pixel) is not int or pixel not in (0, 1) for pixel in row)
                    for row in pixels
                )
            ):
                raise RuntimeError(
                    f"invalid pixel array for frame {actual_count} in {path}; "
                    f"expected {height} rows by {width} columns of 0/1 values"
                )
            actual_count += 1

    if actual_count != expected_count:
        raise RuntimeError(
            f"JSON frame count mismatch: expected {expected_count}, found {actual_count}"
        )


def extract_video(args: argparse.Namespace, cv2: Any, np: Any) -> None:
    args.output.mkdir(parents=True, exist_ok=True)
    existing_outputs = [
        path.name
        for path in args.output.iterdir()
        if path.name == "manifest.json"
        or (path.name.startswith("frames_") and path.suffix == ".json")
    ]
    if existing_outputs:
        examples = ", ".join(existing_outputs[:3])
        raise RuntimeError(
            f"output folder already contains generated files ({examples}); "
            "choose a new --output folder to preserve existing data"
        )

    capture = cv2.VideoCapture(str(args.video))
    if not capture.isOpened():
        capture.release()
        raise RuntimeError(f"cannot open video (unsupported or damaged file): {args.video}")

    try:
        source_fps = float(capture.get(cv2.CAP_PROP_FPS))
        reported_frame_count = float(capture.get(cv2.CAP_PROP_FRAME_COUNT))
        if not math.isfinite(source_fps) or source_fps <= 0:
            raise RuntimeError("video does not provide a valid source FPS")
        if not math.isfinite(reported_frame_count) or reported_frame_count <= 0:
            raise RuntimeError("video does not provide a valid source frame count")
        source_frame_count = int(reported_frame_count)
        if source_frame_count <= 0:
            raise RuntimeError("video does not provide a valid source frame count")

        output_rate = Fraction(str(args.output_fps)).limit_denominator(1_000_000)
        source_rate = Fraction(str(source_fps)).limit_denominator(1_000_000)
        if output_rate <= 0 or source_rate <= 0:
            raise RuntimeError("source and output FPS must be representable as positive rates")
        preview_dir = args.output / "previews"
        if args.preview:
            preview_dir.mkdir(parents=True, exist_ok=True)

        json_files: list[str] = []
        chunk: list[dict[str, Any]] = []
        chunk_number = 0
        extracted_count = 0
        decoded_count = 0
        next_sample = 0
        last_binary: Any | None = None
        warnings: list[str] = []
        decode_status = "reported_end"
        processing_error: str | None = None

        def append_sample(binary: Any) -> None:
            nonlocal chunk, chunk_number, extracted_count
            pixels = np.where(binary > 0, 1, 0).astype(np.uint8).tolist()

            if args.preview:
                preview_path = preview_dir / f"frame_{extracted_count:06d}.png"
                if not cv2.imwrite(str(preview_path), binary):
                    raise RuntimeError(f"could not write preview image: {preview_path}")

            chunk.append({"frame": extracted_count, "pixels": pixels})
            extracted_count += 1
            if len(chunk) >= args.frames_per_file:
                json_files.append(save_chunk(args.output, chunk_number, chunk))
                chunk_number += 1
                chunk = []

        while True:
            try:
                success, frame = capture.read()
            except cv2.error as error:
                decode_status = "decoder_error"
                warnings.append(f"Video decoder raised an error: {error}")
                break
            if success and frame is None:
                decode_status = "decoder_error"
                warnings.append("VideoCapture.read() reported success but returned no frame.")
                break
            if not success:
                if decoded_count < source_frame_count:
                    decode_status = "early_end_or_decode_error"
                    warnings.append(
                        "VideoCapture.read() returned no frame before the reported "
                        f"frame count ({decoded_count} of {source_frame_count}). "
                        "OpenCV does not distinguish premature end-of-stream from "
                        "a decoder failure through this return value."
                    )
                elif decoded_count > source_frame_count:
                    decode_status = "reported_frame_count_underestimated"
                    warnings.append(
                        "Decoded more frames than the source metadata reported "
                        f"({decoded_count} vs {source_frame_count})."
                    )
                break
            source_index = decoded_count
            decoded_count += 1

            try:
                grayscale = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                resized = cv2.resize(
                    grayscale,
                    (args.width, args.height),
                    interpolation=cv2.INTER_AREA,
                )
                _, binary = cv2.threshold(
                    resized, args.threshold, 255, cv2.THRESH_BINARY
                )
                last_binary = binary

                while True:
                    # Pick the nearest source frame for each output timestamp.
                    # Repeated source frames are valid when output FPS is higher.
                    numerator = (
                        next_sample
                        * output_rate.denominator
                        * source_rate.numerator
                    )
                    denominator = (
                        output_rate.numerator * source_rate.denominator
                    )
                    nearest_source_index = (
                        2 * numerator + denominator
                    ) // (2 * denominator)
                    if nearest_source_index > source_index:
                        break
                    append_sample(binary)
                    next_sample += 1
            except (cv2.error, OSError, RuntimeError) as error:
                processing_error = str(error)
                decode_status = "frame_processing_error"
                warnings.append(f"Frame processing stopped: {error}")
                break

            show_progress(decoded_count, source_frame_count, extracted_count)

        actual_sample_count = (
            decoded_count * output_rate.numerator * source_rate.denominator
            + output_rate.denominator * source_rate.numerator
            - 1
        ) // (output_rate.denominator * source_rate.numerator)
        if last_binary is not None and processing_error is None:
            try:
                while next_sample < actual_sample_count:
                    append_sample(last_binary)
                    next_sample += 1
            except (cv2.error, OSError, RuntimeError) as error:
                processing_error = str(error)
                decode_status = "frame_processing_error"
                warnings.append(f"Could not finish writing sampled frames: {error}")

        if decoded_count < source_frame_count:
            partial_decoding = True
        else:
            partial_decoding = False
        if decoded_count == source_frame_count and decode_status == "reported_end":
            decode_status = "reported_frame_count_reached"

        if chunk:
            try:
                json_files.append(save_chunk(args.output, chunk_number, chunk))
            except OSError as error:
                processing_error = str(error)
                warnings.append(f"Could not save the final JSON chunk: {error}")

        validation_passed = False
        try:
            verify_json_files(
                args.output, json_files, extracted_count, args.width, args.height
            )
            validation_passed = True
        except RuntimeError as error:
            warnings.append(f"Saved JSON validation failed: {error}")

        source_width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
        source_height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
        actual_duration = decoded_count / source_fps
        manifest = {
            "source": {
                "path": str(args.video.resolve()),
                "filename": args.video.name,
                "width": source_width,
                "height": source_height,
                "fps": source_fps,
                "frame_count": source_frame_count,
                "expected_frame_count": source_frame_count,
                "decoded_frame_count": decoded_count,
                "expected_duration_seconds": source_frame_count / source_fps,
                "duration_seconds": actual_duration,
                "partial_decoding": partial_decoding,
                "decode_status": decode_status,
            },
            "output": {
                "width": args.width,
                "height": args.height,
                "resolution": f"{args.width}x{args.height}",
                "fps": args.output_fps,
                "threshold": args.threshold,
                "frame_count": extracted_count,
                "extracted_frame_count": extracted_count,
                "frames_per_file": args.frames_per_file,
                "json_files": json_files,
                "previews_saved": args.preview,
                "json_validation_passed": validation_passed,
            },
            "warnings": warnings,
        }
        manifest_path = args.output / "manifest.json"
        try:
            with manifest_path.open("x", encoding="utf-8", newline="\n") as file:
                json.dump(manifest, file, ensure_ascii=False, indent=2)
                file.write("\n")
        except OSError as error:
            raise RuntimeError(f"could not write manifest {manifest_path}: {error}") from error

        print(file=sys.stderr)
        print(
            f"Extracted {extracted_count} frames from {decoded_count} decoded "
            f"source frames to {args.output}"
        )
        for warning in warnings:
            print(f"Warning: {warning}", file=sys.stderr)
        if processing_error is not None:
            raise RuntimeError(
                f"frame processing stopped after writing a partial result: "
                f"{processing_error}"
            )
    finally:
        capture.release()


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
    validate_options(parser, args)

    try:
        import cv2
        import numpy as np
    except ImportError as error:
        print(
            f"Missing dependency: {error}. Install packages with "
            "'py -m pip install opencv-python numpy'.",
            file=sys.stderr,
        )
        return 2

    try:
        extract_video(args, cv2, np)
    except (OSError, RuntimeError, cv2.error) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
