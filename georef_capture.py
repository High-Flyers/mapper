import cv2
import threading
from pymavlink import mavutil
import argparse
import os
import datetime
import yaml
import copy
import dataclasses
from frame_selector import FrameSelector
from models import DroneData


STREAM_PIPELINE = " out. ! queue ! rtph264pay config-interval=1 pt=96 ! udpsink host={address} port={port} sync=false async=false"


class Capturer:
    def __init__(self, args):
        with open(args.config, "r") as f:
            self.config = yaml.safe_load(f)
        print("Loaded config:")
        print(yaml.dump(self.config, sort_keys=False))
        self.preview = args.preview
        self.no_tele = args.no_tele
        self.stream_ip = args.stream_ip
        self.last_drone_data = None
        self.telems = []
        self.cap = None
        self.writer = None
        self.mav_listener = None
        self.running = False

        self.output_dir = datetime.datetime.now().strftime("data/%Y-%m-%d_%H-%M-%S")
        os.makedirs(self.output_dir, exist_ok=True)
        base = os.path.basename("out.mp4")
        self.video_filename = os.path.join(self.output_dir, base)
        frames_dir = os.path.join(self.output_dir, "frames")
        os.makedirs(frames_dir, exist_ok=True)
        self.frame_selector = FrameSelector(frames_dir, nth=10)

    def run(self):
        self.running = True
        if not self.no_tele:
            self.mav_listener = threading.Thread(target=self.mavlink_listener)
            self.mav_listener.start()
        else:
            print(
                "Telemetry disabled, not starting MAVLink listener, georef frames will not be saved."
            )
        self.video_capture()
        self.finish()

    def finish(self):
        self.running = False
        self.frame_selector.finish_saving()
        if not self.no_tele:
            print(f"Captured {len(self.telems)} telemetry points.")
            yaml_path = os.path.join(self.output_dir, "telemetry.yaml")
            with open(yaml_path, "w") as f:
                yaml.dump([dataclasses.asdict(t) for t in self.telems], f)
            print(f"Telemetry saved to {yaml_path}")

    def mavlink_listener(self):
        print("Mavlink listener started")
        master = mavutil.mavlink_connection(
            self.config.get("connection_string"), baud=self.config.get("baud_rate")
        )

        print("Waiting for heartbeat...")
        master.wait_heartbeat()
        print("Heartbeat received!")
        while self.running:
            msg = master.recv_match(
                type=["GLOBAL_POSITION_INT", "ATTITUDE"], blocking=True
            )
            if not msg:
                continue
            if self.last_drone_data is None:
                self.last_drone_data = DroneData()

            if msg.get_type() == "GLOBAL_POSITION_INT":
                self.last_drone_data.lat = msg.lat / 1e7
                self.last_drone_data.lon = msg.lon / 1e7
                self.last_drone_data.alt = msg.alt / 1000.0  # in meters

            elif msg.get_type() == "ATTITUDE":
                self.last_drone_data.roll = msg.roll
                self.last_drone_data.pitch = msg.pitch
                self.last_drone_data.yaw = msg.yaw

    def prepare_gst_writer(self):
        ret, frame = self.cap.read()
        if not ret:
            print("Error: Could not read frame for video writer initialization")
            self.cap.release()
            return

        height, width = frame.shape[:2]
        gst_writer_pipeline = self.config.get("gst_writer_pipeline")
        gst_writer_pipeline = gst_writer_pipeline.format(
            output_file=self.video_filename
        )
        if self.stream_ip:
            address, port = self.stream_ip.split(":")
            gst_writer_pipeline += STREAM_PIPELINE.format(address=address, port=port)
        print(f"GStreamer writer pipeline: {gst_writer_pipeline}")
        self.writer = cv2.VideoWriter(
            gst_writer_pipeline,
            cv2.CAP_GSTREAMER,
            0,
            self.config.get("fps"),
            (width, height),
        )
        if self.writer is None or not self.writer.isOpened():
            print(
                f"Error: Could not open video file {self.video_filename} for writing (H264). Try .mkv"
            )
            self.writer = None

    def video_capture(self):
        self.cap = cv2.VideoCapture(
            self.config.get("gst_capture_pipeline"),
            cv2.CAP_GSTREAMER,
        )
        self.prepare_gst_writer()
        frames_num = 0
        if not self.cap.isOpened():
            print("Error: Unable to open camera")
            exit()
        try:
            while True:
                ret, frame = self.cap.read()
                if ret:
                    if self.preview:
                        cv2.imshow("Frame", frame)
                    if self.writer:
                        if self.last_drone_data or self.no_tele:
                            self.telems.append(copy.deepcopy(self.last_drone_data))
                            self.writer.write(frame)
                            self.frame_selector.take_frame(frame, self.last_drone_data)
                            frames_num += 1
                        else:
                            print("Warning: No telem, skipping frame.")
                else:
                    print("Error: Could not read frame")
                    break

                if self.preview and cv2.waitKey(1) == ord("q"):
                    break
        except KeyboardInterrupt:
            print("\nKeyboardInterrupt received in video loop. Exiting...")
        finally:
            self.cap.release()
            if self.writer:
                self.writer.release()
            print(f"Total frames written: {frames_num}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Georeferenced video capture")
    parser.add_argument(
        "--preview",
        action="store_true",
        help="Show video preview window (default: off)",
    )
    parser.add_argument(
        "--no-tele",
        action="store_true",
        help="Disable telemetry data saving (default: off)",
    )
    parser.add_argument(
        "--stream-ip",
        metavar="STREAM_IP",
        help="UDP address for video streaming",
    )
    parser.add_argument(
        "--config",
        metavar="CONFIG_FILE",
        type=str,
        required=True,
        help="YAML config file path to use (required)",
    )
    args = parser.parse_args()
    capturer = Capturer(args)
    capturer.run()
