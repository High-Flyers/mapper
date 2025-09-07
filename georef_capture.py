import cv2
import threading
import dataclasses
from pymavlink import mavutil


print(cv2.getBuildInformation())


@dataclasses.dataclass()
class DroneData:
    lat: float = None
    lon: float = None
    alt: float = None
    roll: float = None
    pitch: float = None
    yaw: float = None


# Connect to the PX4 autopilot (adjust the connection string as needed)
# For serial: connection_string = '/dev/ttyUSB0', baud=57600
# For UDP: connection_string = 'udp:127.0.0.1:14550'


class Capturer:
    def __init__(self):
        self.last_drone_data = DroneData()
        self.mav_listener = threading.Thread(target=self.mavlink_listener)
        self.mav_listener.start()
        self.video_capturer = threading.Thread(target=self.video_capture)
        self.video_capturer.start()

    def mavlink_listener(self):
        print("Mavlink listener started")
        connection_string = "udp:127.0.0.1:14551"
        master = mavutil.mavlink_connection(connection_string)

        print("Waiting for heartbeat...")
        master.wait_heartbeat()
        print("Heartbeat received!")
        while True:
            msg = master.recv_match(
                type=["GLOBAL_POSITION_INT", "ATTITUDE"], blocking=True
            )
            if not msg:
                continue

            if msg.get_type() == "GLOBAL_POSITION_INT":
                self.last_drone_data.lat = msg.lat / 1e7
                self.last_drone_data.lon = msg.lon / 1e7
                self.last_drone_data.alt = msg.alt / 1000.0  # in meters
                print(
                    f"Position: lat={self.last_drone_data.lat:.7f}, lon={self.last_drone_data.lon:.7f}, alt={self.last_drone_data.alt:.2f}m"
                )
            elif msg.get_type() == "ATTITUDE":
                self.last_drone_data.roll = msg.roll
                self.last_drone_data.pitch = msg.pitch
                self.last_drone_data.yaw = msg.yaw
                print(
                    f"Attitude: roll={self.last_drone_data.roll:.3f}, pitch={self.last_drone_data.pitch:.3f}, yaw={self.last_drone_data.yaw:.3f}"
                )

    def video_capture(self):
        cap = cv2.VideoCapture(
            "v4l2src device=/dev/video0 ! videoconvert ! appsink", cv2.CAP_GSTREAMER
        )

        if not cap.isOpened():
            print("Error: Unable to open camera")
            exit()
        while True:
            ret, frame = cap.read()
            if ret:
                cv2.imshow("test_capture", frame)
            else:
                print("Error: Could not read frame")
                break

            if cv2.waitKey(1) & 0xFF == ord("q"):
                break

        cap.release()


if __name__ == "__main__":
    capturer = Capturer()
