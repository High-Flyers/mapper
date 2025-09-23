import cv2
import imagezmq
import json
from geo_frame import GeorefFrame, DroneData

image_hub = imagezmq.ImageHub(open_port="tcp://*:5001")
while True:
    meta_str, image = image_hub.recv_image()
    meta_dict = json.loads(meta_str)
    drone_data = DroneData(
        lat=meta_dict.get("lat"),
        lon=meta_dict.get("lon"),
        alt=meta_dict.get("alt"),
        roll=meta_dict.get("roll"),
        pitch=meta_dict.get("pitch"),
        yaw=meta_dict.get("yaw"),
    )
    print(drone_data)
    frame = GeorefFrame(image=image, drone_data=drone_data, name="received_frame")
    cv2.imshow("frame", frame.image)
    cv2.waitKey(1)
    image_hub.send_reply(b"OK")
