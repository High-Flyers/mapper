import cv2
import imagezmq
import json
import os
from datetime import datetime
from geo_frame import GeorefFrame


class GCS:
    def __init__(self):
        self.output_dir = datetime.now().strftime("data/gcs_%Y-%m-%d_%H-%M-%S")
        os.makedirs(self.output_dir, exist_ok=True)

    def run(self):
        image_hub = imagezmq.ImageHub(open_port="tcp://*:5001")
        while True:
            meta_str, image = image_hub.recv_image()
            meta_dict = json.loads(meta_str)

            frame = GeorefFrame.from_dict(image, meta_dict)
            print(frame.drone_data)

            frame.save(dir_path=self.output_dir)
            cv2.imshow("frame", frame.image)
            cv2.waitKey(1)
            image_hub.send_reply(b"OK")


if __name__ == "__main__":
    gcs = GCS()
    gcs.run()
