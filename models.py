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
