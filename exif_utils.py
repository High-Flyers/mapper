import cv2
from PIL import Image
import piexif
from datetime import datetime
import math


def deg_to_dms_rational(deg):
    """Convert decimal coordinates into EXIF rational format (DMS)."""
    d = int(deg)
    m = int((deg - d) * 60)
    s = round((deg - d - m / 60) * 3600 * 100)
    return ((d, 1), (m, 1), (s, 100))

def save_frame_with_gps(frame, filename, lat, lng, alt=0.0, rel_alt=None, yaw=None):
    cv2.imwrite(filename, frame)
    img = Image.open(filename)

    exif_dict = {"0th": {}, "Exif": {}, "GPS": {}, "1st": {}, "thumbnail": None}

    exif_dict["GPS"][piexif.GPSIFD.GPSLatitudeRef] = "N" if lat >= 0 else "S"
    exif_dict["GPS"][piexif.GPSIFD.GPSLatitude] = deg_to_dms_rational(abs(lat))
    exif_dict["GPS"][piexif.GPSIFD.GPSLongitudeRef] = "E" if lng >= 0 else "W"
    exif_dict["GPS"][piexif.GPSIFD.GPSLongitude] = deg_to_dms_rational(abs(lng))

    exif_dict["GPS"][piexif.GPSIFD.GPSAltitudeRef] = 0 if alt >= 0 else 1
    exif_dict["GPS"][piexif.GPSIFD.GPSAltitude] = (int(abs(alt * 100)), 100)

    # convert yaw to normalized 0-360 degrees
    yaw_deg_norm = None
    if yaw is not None:
        try:
            yaw_deg_signed = math.degrees(yaw)
            # normalize to 0-360 degrees for GPSImgDirection
            yaw_deg_norm = yaw_deg_signed if yaw_deg_signed >= 0 else yaw_deg_signed + 360
            exif_dict["GPS"][piexif.GPSIFD.GPSImgDirection] = (int(round(yaw_deg_norm * 100)), 100)
            exif_dict["GPS"][piexif.GPSIFD.GPSImgDirectionRef] = "T"
        except Exception:
            yaw_deg_norm = None

    # Store relative altitude and yaw (0-360 degrees) in a human-readable field (ImageDescription)
    desc = ""
    if rel_alt is not None:
        desc += f"rel_alt={rel_alt}, "
    if yaw_deg_norm is not None:
        desc += f"yaw_deg={round(yaw_deg_norm, 5)}, "
    exif_dict["0th"][piexif.ImageIFD.ImageDescription] = desc.strip(", ")

    exif_dict["GPS"][piexif.GPSIFD.GPSVersionID] = (2, 0, 0, 0)

    now_str = datetime.utcnow().strftime("%Y:%m:%d %H:%M:%S")
    exif_dict["0th"][piexif.ImageIFD.DateTime] = now_str
    exif_dict["Exif"][piexif.ExifIFD.DateTimeOriginal] = now_str
    exif_dict["Exif"][piexif.ExifIFD.DateTimeDigitized] = now_str

    exif_bytes = piexif.dump(exif_dict)
    img.save(filename, "jpeg", exif=exif_bytes)
