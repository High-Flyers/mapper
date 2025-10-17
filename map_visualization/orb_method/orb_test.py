import cv2 as cv
import numpy as np
from matplotlib import pyplot as plt
import matplotlib
matplotlib.use('Agg')

def align_images_orb(img1, img2):
    """
    Dopasuj img2 do img1 za pomocą punktów ORB
    Zwraca: (aligned_img2, H)
    """
    gray1 = cv.cvtColor(img1, cv.COLOR_BGR2GRAY)
    gray2 = cv.cvtColor(img2, cv.COLOR_BGR2GRAY)

    orb = cv.ORB_create(5000)
    kp1, des1 = orb.detectAndCompute(gray1, None)
    kp2, des2 = orb.detectAndCompute(gray2, None)

    bf = cv.BFMatcher(cv.NORM_HAMMING, crossCheck=True)
    matches = bf.match(des1, des2)
    matches = sorted(matches, key=lambda x: x.distance)

    if len(matches) < 10:
        print("⚠️ Za mało dopasowań ORB, zwracam obraz bez zmian.")
        return img2, np.eye(3)

    pts1 = np.float32([kp1[m.queryIdx].pt for m in matches]).reshape(-1,1,2)
    pts2 = np.float32([kp2[m.trainIdx].pt for m in matches]).reshape(-1,1,2)

    H, mask = cv.findHomography(pts2, pts1, cv.RANSAC, 5.0)
    if H is None:
        return img2, np.eye(3)

    aligned_img = cv.warpPerspective(img2, H, (img1.shape[1], img1.shape[0]))
    return aligned_img, H

# --- Wczytanie obrazów ---
img1 = cv.imread("map_visualization/samples/frame_1.jpg")
img2 = cv.imread("map_visualization/samples/frame_2.jpg")

if img1 is None or img2 is None:
    raise FileNotFoundError("Nie znaleziono jednego z obrazów!")

# --- Dopasowanie img2 do img1 ---
aligned_img2, H = align_images_orb(img1, img2)
print("Macierz transformacji:\n", H)

# --- Nakładanie obrazów z 50% przezroczystością ---
overlay = cv.addWeighted(img1, 0.5, aligned_img2, 0.5, 0)

# --- Zapis i wyświetlenie wyniku ---
plt.figure(figsize=(8,8))
plt.imshow(cv.cvtColor(overlay, cv.COLOR_BGR2RGB))
plt.axis("off")
plt.title("Nałożone obrazy 50%")
plt.savefig("map_visualization/overlay_orb.png")
plt.close()
print("✅ Wynik zapisano jako overlay_orb.png")
