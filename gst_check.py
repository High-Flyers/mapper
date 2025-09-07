import cv2

print(cv2.getBuildInformation())
# # pipeline_str = (
# #     'nvarguscamerasrc sensor-id=0 tnr-mode=1 exposuretimerange="0 15000000" ! '
# #     "video/x-raw(memory:NVMM), width=1920, height=1080, framerate=30/1 ! "
# #     "nvvidconv ! video/x-raw, width=1280, height=720, format=BGRx ! "
# #     "videoconvert ! video/x-raw, format=BGR ! appsink name=appsink"
# # )

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
