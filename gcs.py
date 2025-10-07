import cv2
import imagezmq
import simplejpeg
import json
import os
import logging
import argparse
from datetime import datetime
from geo_frame import GeorefFrame


class GCS:
    def __init__(self):
        self.output_dir = datetime.now().strftime("data/gcs_%Y-%m-%d_%H-%M-%S")
        os.makedirs(self.output_dir, exist_ok=True)

    def run(self):
        image_hub = imagezmq.ImageHub(open_port="tcp://*:5001")
        while True:
            meta_str, jpg_buffer = image_hub.recv_jpg()
            image = simplejpeg.decode_jpeg(jpg_buffer, colorspace="BGR")
            meta_dict = json.loads(meta_str)

            frame = GeorefFrame.from_dict(image, meta_dict)
            logging.info(frame.drone_data)

            frame.save(dir_path=self.output_dir)
            cv2.imshow("frame", frame.image)
            cv2.waitKey(1)
            image_hub.send_reply(b"OK")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="GCS mapper")
    parser.add_argument(
        "-l",
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="Set the logging level (default: INFO)",
    )
    args = parser.parse_args()
    logging.basicConfig(
        level=getattr(logging, args.log_level.upper()),
        format="%(asctime)s %(levelname)s: %(message)s",
    )
    gcs = GCS()
    gcs.run()
