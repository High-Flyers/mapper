import cv2
import imagezmq
import json
from geo_frame import GeorefFrame, DroneData

image_hub = imagezmq.ImageHub(open_port="tcp://*:5001")
while True:
    meta_str, image = image_hub.recv_image()
    meta_dict = json.loads(meta_str)
    frame = GeorefFrame.from_dict(image, meta_dict)
    print(frame.drone_data)

    cv2.imshow("frame", frame.image)
    cv2.waitKey(1)
    image_hub.send_reply(b"OK")
