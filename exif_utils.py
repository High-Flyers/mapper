import cv2
from PIL import Image
import piexif
from datetime import datetime


def deg_to_dms_rational(deg):
    """Convert decimal coordinates into EXIF rational format (DMS)."""
    d = int(deg)
    m = int((deg - d) * 60)
    s = round((deg - d - m / 60) * 3600 * 100)
    return ((d, 1), (m, 1), (s, 100))


def save_frame_with_gps(frame, filename, lat, lng, alt=0.0):
    cv2.imwrite(filename, frame)
    img = Image.open(filename)

    exif_dict = {"0th": {}, "Exif": {}, "GPS": {}, "1st": {}, "thumbnail": None}

    exif_dict["GPS"][piexif.GPSIFD.GPSLatitudeRef] = "N" if lat >= 0 else "S"
    exif_dict["GPS"][piexif.GPSIFD.GPSLatitude] = deg_to_dms_rational(abs(lat))
    exif_dict["GPS"][piexif.GPSIFD.GPSLongitudeRef] = "E" if lng >= 0 else "W"
    exif_dict["GPS"][piexif.GPSIFD.GPSLongitude] = deg_to_dms_rational(abs(lng))

    exif_dict["GPS"][piexif.GPSIFD.GPSAltitudeRef] = 0 if alt >= 0 else 1
    exif_dict["GPS"][piexif.GPSIFD.GPSAltitude] = (int(abs(alt * 100)), 100)

    exif_dict["GPS"][piexif.GPSIFD.GPSVersionID] = (2, 0, 0, 0)

    now_str = datetime.utcnow().strftime("%Y:%m:%d %H:%M:%S")
    exif_dict["0th"][piexif.ImageIFD.DateTime] = now_str
    exif_dict["Exif"][piexif.ExifIFD.DateTimeOriginal] = now_str
    exif_dict["Exif"][piexif.ExifIFD.DateTimeDigitized] = now_str

    exif_bytes = piexif.dump(exif_dict)
    img.save(filename, "jpeg", exif=exif_bytes)
