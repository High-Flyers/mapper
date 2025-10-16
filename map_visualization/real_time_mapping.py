import tkinter as tk
from PIL import Image, ImageTk, ExifTags
import os
import math
import numpy as np
import time

def get_img_param(filepath):
    """Read img file description"""
    img = Image.open(filepath)
    exif = img._getexif()
    if exif:
        if 270 in exif:
            alt = float(exif[270].split("rel_alt=")[1].split(",")[0])
        if 34853 in exif:
            gps = exif[34853]
            gps_N = gps[2]
            gps_W = gps[4]
            lat_deg = -float(gps_N[0] + gps_N[1]/60 + gps_N[2]/3600)
            lon_deg = -float(gps_W[0] + gps_W[1]/60 + gps_W[2]/3600)
            cam_direction = gps[17]
            # print(cam_direction)
        return alt, lat_deg, lon_deg, cam_direction
    return None

def gps_to_pixel_offset(lat_ref, lon_ref, lat, lon, GSD_x):
    """Convert the GPS coordinate difference into a pixel offset relative to the reference point"""
    delta_x_m = (lon - lon_ref) * 111320 * math.cos(math.radians(lat_ref))
    delta_y_m = (lat - lat_ref) * 111320
    px_offset = int(delta_x_m / GSD_x)
    py_offset = int(delta_y_m / GSD_x)
    return px_offset, py_offset

def generate_map(folder_path="map_visualization/samples", img_width=1280, img_height=720, fov_x=1.74, ortho_width = 5000, ortho_height = 5000,
                 preview_scale=.4, alpha=.5, show_preview=True):
    """Main function to generate orthophoto map"""
    fov_y = fov_x * (img_height / img_width)

    image_files = [os.path.join(folder_path, f) for f in os.listdir(folder_path)]
    images_info = []

    for filepath in image_files:
        result = get_img_param(filepath)
        if result:
            alt, lat, lon, cam_direction = result
            GSD_x = 2 * alt * math.tan(fov_x / 2) / img_width
            GSD_y = 2 * alt * math.tan(fov_y / 2) / img_height
            images_info.append({
                "path": filepath,
                "lat": lat,
                "lon": lon,
                "cam_direction": cam_direction,
                "GSD_x": GSD_x,
                "GSD_y": GSD_y
            })
        else:
            print(f"Brak EXIF w {filepath}")

    ortho_map = np.zeros((ortho_height, ortho_width, 4), dtype=np.uint8)
    ref = images_info[0]

    if show_preview:
        root = tk.Tk()
        root.title("Podgląd ortofotomapy")
        canvas = tk.Canvas(root, width=int(ortho_width * preview_scale), height=int(ortho_height * preview_scale))
        canvas.pack()
        tk_img = None

    for info in images_info:
        img = Image.open(info["path"])
        rotated_img = img.rotate(-info["cam_direction"], expand=True)
        img_np = np.array(rotated_img)
        h, w = img_np.shape[:2]
    
        px_offset, py_offset = gps_to_pixel_offset(ref["lat"], ref["lon"], info["lat"], info["lon"], ref["GSD_x"])

        x_start = ortho_width // 2 + px_offset - w // 2
        y_start = ortho_height // 2 + py_offset - h // 2
        x_end = x_start + w
        y_end = y_start + h

        x_start_clip = max(0, x_start)
        y_start_clip = max(0, y_start)
        x_end_clip = min(ortho_width, x_end)
        y_end_clip = min(ortho_height, y_end)

        img_x_start = x_start_clip - x_start
        img_y_start = y_start_clip - y_start
        img_x_end = img_x_start + (x_end_clip - x_start_clip)
        img_y_end = img_y_start + (y_end_clip - y_start_clip)

        img_region = img_np[img_y_start:img_y_end, img_x_start:img_x_end, :]

        img_rgba = np.zeros((img_region.shape[0], img_region.shape[1], 4), dtype=np.uint8)
        img_rgba[:, :, :3] = img_region
        img_rgba[:, :, 3] = 255

        ortho_region = ortho_map[y_start_clip:y_end_clip, x_start_clip:x_end_clip, :]
        ortho_map[y_start_clip:y_end_clip, x_start_clip:x_end_clip, :3] = (
            img_rgba[:, :, :3].astype(np.float32) * alpha +
            ortho_region[:, :, :3].astype(np.float32) * (1 - alpha)
        ).astype(np.uint8)

        ortho_map[y_start_clip:y_end_clip, x_start_clip:x_end_clip, 3] = 255

        if show_preview:
            preview_img = Image.fromarray(ortho_map, "RGBA").resize(
                (int(ortho_width * preview_scale), int(ortho_height * preview_scale)), Image.ANTIALIAS)
            tk_img = ImageTk.PhotoImage(preview_img)
            canvas.create_image(0, 0, anchor="nw", image=tk_img)
            root.update()

    output_folder = "map_visualization"
    output_path = os.path.join(output_folder, "orthomap_vis.png")
    Image.fromarray(ortho_map, "RGBA").save(output_path)
    print(f"Zapisano jako: {output_path}")

    if show_preview:
        root.mainloop()

if __name__ == "__main__":
    generate_map()