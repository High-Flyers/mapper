import cv2 as cv
import numpy as np

def align_images_orb_full(img1, img2):
    gray1 = cv.cvtColor(img1, cv.COLOR_BGR2GRAY)
    gray2 = cv.cvtColor(img2, cv.COLOR_BGR2GRAY)

    orb = cv.ORB_create(5000)
    kp1, des1 = orb.detectAndCompute(gray1, None)
    kp2, des2 = orb.detectAndCompute(gray2, None)

    bf = cv.BFMatcher(cv.NORM_HAMMING, crossCheck=True)
    matches = bf.match(des1, des2)
    matches = sorted(matches, key=lambda x: x.distance)

    if len(matches) < 10:
        H = np.eye(3)
    else:
        pts1 = np.float32([kp1[m.queryIdx].pt for m in matches]).reshape(-1,1,2)
        pts2 = np.float32([kp2[m.trainIdx].pt for m in matches]).reshape(-1,1,2)
        H, mask = cv.findHomography(pts2, pts1, cv.RANSAC, 5.0)
        if H is None:
            H = np.eye(3)

    h1, w1 = img1.shape[:2]
    h2, w2 = img2.shape[:2]

    corners_img2 = np.array([[0,0],[w2,0],[w2,h2],[0,h2]], dtype=np.float32).reshape(-1,1,2)
    transformed_corners = cv.perspectiveTransform(corners_img2, H)
    all_corners = np.vstack((
        np.array([[0,0],[w1,0],[w1,h1],[0,h1]],dtype=np.float32).reshape(-1,1,2),
        transformed_corners
    ))

    [xmin, ymin] = np.int32(all_corners.min(axis=0).ravel() - 0.5)
    [xmax, ymax] = np.int32(all_corners.max(axis=0).ravel() + 0.5)
    t = [-xmin, -ymin]

    H_translation = np.array([[1, 0, t[0]],
                              [0, 1, t[1]],
                              [0, 0, 1]])

    output_width = xmax - xmin
    output_height = ymax - ymin
    aligned_img2 = cv.warpPerspective(img2, H_translation @ H, (output_width, output_height),
                                      borderMode=cv.BORDER_CONSTANT, borderValue=(255,255,255))

    # Canvas dla img1 z białym tłem
    canvas_img1 = np.ones((output_height, output_width, 3), dtype=np.uint8) * 255
    canvas_img1[t[1]:t[1]+h1, t[0]:t[0]+w1] = img1

    return canvas_img1, aligned_img2

# --- Wczytanie obrazów ---
img1 = cv.imread("map_visualization/samples/frame_6.jpg")
img2 = cv.imread("map_visualization/samples/frame_7.jpg")
if img1 is None or img2 is None:
    raise FileNotFoundError("Nie znaleziono jednego z obrazów!")

# --- Dopasowanie ---
canvas_img1, aligned_img2 = align_images_orb_full(img1, img2)

# --- Nakładanie obrazów z 50% przezroczystością ---
overlay = cv.addWeighted(canvas_img1, 0.5, aligned_img2, 0.5, 0)

# --- Połączenie w jednym obrazie poziomo ---
combined = np.hstack([canvas_img1, aligned_img2, overlay])

# --- Zapis ---
output_path = "map_visualization/orb_method/combined_overlay_white.png"
cv.imwrite(output_path, combined)
print(f"✅ Zapisano wynik w jednym pliku: {output_path}")
