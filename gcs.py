import cv2
import imagezmq
import simplejpeg
import json
import os
import logging
import argparse
from datetime import datetime
from geo_frame import GeorefFrame
from map_visualization.realtime_mapper import RealTimeMapper


class GCS:
    def __init__(self):
        self.output_dir = datetime.now().strftime("data/gcs_%Y-%m-%d_%H-%M-%S")
        os.makedirs(self.output_dir, exist_ok=True)
        self.mapper = None

    def run(self):
        image_hub = imagezmq.ImageHub(open_port="tcp://*:5001")
        logging.info("GCS receiving frames. Press Ctrl+C to stop and save orthomap.")
        try:
            while True:
                meta_str, jpg_buffer = image_hub.recv_jpg()
                image = simplejpeg.decode_jpeg(jpg_buffer, colorspace="BGR")
                meta_dict = json.loads(meta_str)

                frame = GeorefFrame.from_dict(image, meta_dict)
                logging.info(f"{frame.name}: {frame.drone_data}")

                frame.save(dir_path=self.output_dir)
                cv2.imshow("frame", frame.image)
                cv2.waitKey(1)
                image_hub.send_reply(b"OK")

                if self.mapper is None:
                    h, w = frame.image.shape[:2]
                    self.mapper = RealTimeMapper(
                        img_width=w, img_height=h, fov_x=1.74, alpha=0.5, preview=True
                    )
                try:
                    self.mapper.add_frame(frame)
                except Exception as e:
                    logging.error(f"Error adding frame to mapper: {e}")
        except KeyboardInterrupt:
            logging.info("KeyboardInterrupt received. Try to save orthomap...")
            if self.mapper is not None:
                out_path = os.path.join(self.output_dir, "orthomap.png")
                try:
                    self.mapper.save(out_path)
                    logging.info(f"Orthomap saved to {out_path}")
                except Exception as e:
                    logging.error(f"Failed to save orthomap: {e}")
                self.mapper.close()

            cv2.destroyAllWindows()
            logging.info("Shutdown complete.")


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
