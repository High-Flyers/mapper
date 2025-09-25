import threading
import queue
import numpy as np
import logging
from image_sender import ImgSender
from models import DroneData
from geo_frame import GeorefFrame


class FrameSelector:
    def __init__(self, dir: str, send_ip: str, nth: int = 10):
        self.nth_frame: int = nth
        self.frame_count: int = 0
        self.dir = dir
        self.img_sender = ImgSender(address=f"tcp://{send_ip}:5001")
        self.to_save_queue = queue.Queue()
        self.saving_thread = threading.Thread(target=self.__saving_worker)
        self.saving_thread.start()

    def take_frame(self, frame: np.ndarray, drone_data: DroneData) -> None:
        if self.frame_count % self.nth_frame == 0 and drone_data is not None:
            geo_frame = GeorefFrame(
                frame.copy(), drone_data, name=f"frame_{self.frame_count}"
            )
            self.to_save_queue.put(geo_frame)
            self.img_sender.add_frame_to_send(geo_frame)
            logging.debug(
                f"Queued frame {geo_frame.name} for saving with geodata: lat={drone_data.lat}, lon={drone_data.lon}, alt={drone_data.alt}"
            )
        self.frame_count += 1

    def __saving_worker(self):
        while True:
            item: GeorefFrame = self.to_save_queue.get()
            if item is None:
                break
            item.save(self.dir)
            self.to_save_queue.task_done()

    def finish_saving(self):
        self.to_save_queue.put(None)
        self.img_sender.stop()
        self.saving_thread.join()
