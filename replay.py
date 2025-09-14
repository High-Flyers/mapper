import cv2
import yaml
import argparse
import os


def main():
    parser = argparse.ArgumentParser(
        description="Play video and print telemetry from a capture folder"
    )
    parser.add_argument(
        "--dir",
        type=str,
        required=True,
        help="Path to the output directory (containing video and telemetry.yaml)",
    )
    parser.add_argument(
        "--video",
        type=str,
        default=None,
        help="Video filename (if not specified, will use first .mp4/.mkv/.avi in folder)",
    )
    parser.add_argument(
        "--telemetry",
        type=str,
        default="telemetry.yaml",
        help="Telemetry YAML filename (default: telemetry.yaml)",
    )
    args = parser.parse_args()

    directory = args.dir
    video_file = args.video
    if not video_file:
        # Try to find a video file in the directory
        for ext in (".mp4", ".mkv", ".avi"):
            for f in os.listdir(directory):
                if f.endswith(ext):
                    video_file = f
                    break
            if video_file:
                break
        if not video_file:
            print("No video file found in directory.")
            return
    video_path = os.path.join(directory, video_file)
    print(f"Playing video: {video_path}")

    telemetry_path = os.path.join(directory, args.telemetry)
    telems = []
    if not os.path.exists(telemetry_path):
        print(f"Telemetry file not found: {telemetry_path}")
        return
    print(f"\nTelemetry from {telemetry_path}:")
    with open(telemetry_path, "r") as f:
        telems = yaml.safe_load(f)

    # Play video
    cap = cv2.VideoCapture(video_path)
    frame_num = 0
    if not cap.isOpened():
        print("Error: Could not open video file.")
        return
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        tele = telems[frame_num] if frame_num < len(telems) else {}
        print(f"Frame {frame_num}: {tele}")
        frame_num += 1
        cv2.imshow("Video", frame)
        if cv2.waitKey(30) & 0xFF == ord("q"):
            break
    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
