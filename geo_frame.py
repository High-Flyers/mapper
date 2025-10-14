import numpy as np
import os
from models import DroneData
from exif_utils import save_frame_with_gps


class GeorefFrame:
    def __init__(self, image: np.ndarray, drone_data: DroneData, name: str):
        self.image: np.ndarray = image
        self.drone_data: DroneData = drone_data
        self.name: str = name

    @classmethod
    def from_dict(cls, image, meta_dict):
        img_name = meta_dict.get("name")
        del meta_dict["name"]
        drone_data = DroneData(**meta_dict)
        return cls(image=image, drone_data=drone_data, name=img_name)

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
            rel_alt=self.drone_data.rel_alt,
            yaw=self.drone_data.yaw,
        )
