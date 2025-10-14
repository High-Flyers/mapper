import dataclasses


@dataclasses.dataclass()
class DroneData:
    lat: float = None
    lon: float = None
    alt: float = None
    rel_alt: float = None
    roll: float = None
    pitch: float = None
    yaw: float = None

    def is_initialized(self) -> bool:
        return None not in (
            self.lat,
            self.lon,
            self.alt,
            self.rel_alt,
            self.roll,
            self.pitch,
            self.yaw,
        )
