import threading
import queue
import numpy as np
import logging
from image_sender import ImgSender
from models import DroneData
from geo_frame import GeorefFrame


class FrameSelector:
    def __init__(self, dir: str, send_ip: str, nth: int = 10, on_request=False): 
        logging.info(f"FrameSelector initialized with nth_frame={nth}, on_request={on_request}")
        # on_request - if True, frames are selected on external request, otherwise every nth frame is saved
        self.nth_frame: int = nth
        self.frame_count: int = 0
        self.dir = dir
        self.on_request = on_request
        self.img_sender = ImgSender(address=f"tcp://{send_ip}:5001", jpeg_quality=80)
        self.to_save_queue = queue.Queue()
        self.saving_thread = threading.Thread(target=self.__saving_worker)
        self.saving_thread.start()
        self.save_next_frame = False

    def take_frame(self, frame: np.ndarray, drone_data: DroneData) -> None:
        if drone_data is not None:
            if (not self.on_request and self.frame_count % self.nth_frame == 0) or self.save_next_frame:
                geo_frame = GeorefFrame(
                    frame.copy(), drone_data, name=f"frame_{self.frame_count}"
                )
                self.to_save_queue.put(geo_frame)
                self.img_sender.add_frame_to_send(geo_frame)
                logging.debug(
                    f"Queued frame {geo_frame.name} for saving with geodata: lat={drone_data.lat}, lon={drone_data.lon}, alt={drone_data.alt}"
                )
                self.save_next_frame = False
        self.frame_count += 1

    def __saving_worker(self):
        while True:
            item: GeorefFrame = self.to_save_queue.get()
            if item is None:
                break
            item.save(self.dir)
            self.to_save_queue.task_done()
            
    def request_saving(self):
        self.save_next_frame = True

    def finish_saving(self):
        self.to_save_queue.put(None)
        self.img_sender.stop()
        self.saving_thread.join()
