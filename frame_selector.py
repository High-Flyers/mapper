import cv2
import numpy as np
from typing import List
from models import DroneData
from exif_utils import save_frame_with_gps


class FrameSelector:
    def __init__(self, nth: int = 10):
        self.nth_frame: int = nth
        self.frame_count: int = 0
        self.frames: List[np.ndarray] = []
        self.telems: List[DroneData] = []

    def take_frame(self, frame: np.ndarray, drone_data: DroneData) -> None:
        if self.frame_count % self.nth_frame == 0 and drone_data is not None:
            self.frames.append(frame.copy())
            self.telems.append(drone_data)

        self.frame_count += 1

    def get_frames(self) -> List[np.ndarray]:
        return self.frames

    def get_telems(self) -> List[DroneData]:
        return self.telems

    def save_frames(self, dir: str) -> None:
        print(f"Saving {len(self.frames)} frames to {dir}")
        for idx, frame in enumerate(self.frames):
            filename = f"{dir}/frame_{idx * self.nth_frame}.jpg"
            save_frame_with_gps(
                frame,
                filename,
                lat=self.telems[idx].lat,
                lng=self.telems[idx].lon,
                alt=self.telems[idx].alt,
            )
