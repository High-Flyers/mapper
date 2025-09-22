import threading
import queue
import numpy as np
import os
import logging
from models import DroneData
from exif_utils import save_frame_with_gps


class GeorefFrame:
    def __init__(self, image: np.ndarray, drone_data: DroneData, name: str):
        self.image = image
        self.drone_data = drone_data
        self.name = name

    def save(self, dir_path=None) -> None:
        path = self.name
        if dir_path is not None:
            path = os.path.join(dir_path, self.name)
        save_frame_with_gps(
            self.image,
            f"{path}.jpg",
            lat=self.drone_data.lat,
            lng=self.drone_data.lon,
            alt=self.drone_data.alt,
        )


class FrameSelector:
    def __init__(self, dir: str, nth: int = 10):
        self.nth_frame: int = nth
        self.frame_count: int = 0
        self.dir = dir
        self.to_save_queue = queue.Queue()
        self.saving_thread = threading.Thread(target=self.__saving_worker)
        self.saving_thread.start()

    def take_frame(self, frame: np.ndarray, drone_data: DroneData) -> None:
        if self.frame_count % self.nth_frame == 0 and drone_data is not None:
            geo_frame = GeorefFrame(
                frame.copy(), drone_data, name=f"frame_{self.frame_count}"
            )
            self.to_save_queue.put(geo_frame)
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
        self.saving_thread.join()
