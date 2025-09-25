import dataclasses
import time
import cv2
import imagezmq
from threading import Thread
import logging
import queue
from geo_frame import GeorefFrame
from models import DroneData


class ImgSender:
    def __init__(
        self,
        jpeg_quality=95,
        address="tcp://0.0.0.0:5001",
        max_queue_size=100,
    ):
        self.jpeg_quality = jpeg_quality
        self.sender = imagezmq.ImageSender(connect_to=address)
        self.running = True
        self.frame_queue = queue.Queue(maxsize=max_queue_size)
        self.sending_thread = Thread(target=self.sending_loop)
        self.sending_thread.start()

    def add_frame_to_send(self, frame: GeorefFrame):
        try:
            self.frame_queue.put_nowait(frame)
        except queue.Full:
            logging.warning("ImgSender: frame queue is full, dropping frame.")

    def sending_loop(self):
        while self.running:
            try:
                frame = self.frame_queue.get(timeout=0.1)
            except queue.Empty:
                continue
            try:
                self.send_frame(frame)
            except (KeyboardInterrupt, SystemExit):
                break
            except Exception as ex:
                logging.warning("Img sender, Traceback error:", exc_info=ex)
            finally:
                self.frame_queue.task_done()

    def send_frame(self, frame: GeorefFrame):
        import json

        meta_dict = dataclasses.asdict(frame.drone_data)
        meta_dict["name"] = frame.name

        meta_str = json.dumps(meta_dict)
        self.sender.send_image(meta_str, frame.image)

    def stop(self):
        self.running = False
        self.sending_thread.join()


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    sender = ImgSender()
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        raise RuntimeError("Could not open webcam")
    time.sleep(2)  # allow camera sensor to warm up
    try:
        while True:
            ret, image = cap.read()
            if not ret:
                continue
            dummy_drone_data = DroneData(
                lat=50.0,
                lon=18.0,
                alt=0.0,
                roll=0.0,
                pitch=0.0,
                yaw=0.0,
            )
            frame = GeorefFrame(image, dummy_drone_data, name="test_frame")
            sender.add_frame_to_send(frame)
    except KeyboardInterrupt:
        logging.info("KeyboardInterrupt received, stopping sender.")
    finally:
        sender.stop()
        cap.release()
