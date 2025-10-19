#!/usr/bin/env python3
"""Demo: build an orthomap from existing geotagged JPEG files.

Loads JPEGs with EXIF GPS + custom metadata (written by exif_utils.save_frame_with_gps),
creates GeorefFrame objects and feeds them into RealTimeMapper.

Usage:
    python map_visualization/demo_from_jpegs.py \
        -d data/2025-10-13_19-54-30/frames \
        -o map_visualization/orthomap_from_jpegs.png \
        --fov-x 1.74 --preview

Notes:
- Expects EXIF GPS tags for latitude, longitude, altitude and ImageDescription with rel_alt & yaw_deg.
- If signed yaw_deg not available, derives signed yaw from GPSImgDirection (0..360) making (-180..180).
- Field of view (fov_x) must be known for GSD estimation; adjust to your camera.
"""

import time
import os
import math
import argparse
import logging
from typing import List
import cv2
from PIL import Image

from geo_frame import GeorefFrame
from models import DroneData
from map_visualization.realtime_mapper import RealTimeMapper

IMAGE_DESCRIPTION_TAG = 270  # ImageDescription
GPS_INFO_TAG = 34853  # GPSInfo


def parse_exif(path: str) -> DroneData | None:
    try:
        img = Image.open(path)
        exif = img._getexif()
    except Exception as e:
        logging.warning(f"Failed to open/read EXIF for {path}: {e}")
        return None
    if not exif:
        return None

    gps = exif.get(GPS_INFO_TAG)
    if not gps:
        return None

    rel_alt = None
    lat_deg = None
    lon_deg = None
    cam_direction = None

    def _ratio_to_float(r):
        try:
            if hasattr(r, "numerator") and hasattr(r, "denominator"):
                return float(r.numerator) / float(r.denominator)
            if isinstance(r, tuple) and len(r) == 2:
                return float(r[0]) / float(r[1]) if r[1] else 0.0
            return float(r)
        except Exception:
            return float(r)

    def _dms_to_deg(dms):
        return (
            _ratio_to_float(dms[0])
            + _ratio_to_float(dms[1]) / 60.0
            + _ratio_to_float(dms[2]) / 3600.0
        )

    if exif:
        # Relative altitude stored in ImageDescription (custom format: ... rel_alt=XX, ...)
        if IMAGE_DESCRIPTION_TAG in exif:
            try:
                rel_alt = float(
                    exif[IMAGE_DESCRIPTION_TAG].split("rel_alt=")[1].split(",")[0]
                )
            except Exception:
                rel_alt = None
        if GPS_INFO_TAG in exif:
            gps = exif[GPS_INFO_TAG]
            try:
                lat_ref = gps.get(1, "N")  # 'N' or 'S'
                lon_ref = gps.get(3, "E")  # 'E' or 'W'
                gps_lat = gps.get(2)
                gps_lon = gps.get(4)
                if gps_lat and gps_lon:
                    lat_val = _dms_to_deg(gps_lat)
                    lon_val = _dms_to_deg(gps_lon)
                    if isinstance(lat_ref, bytes):
                        lat_ref = lat_ref.decode(errors="ignore")
                    if isinstance(lon_ref, bytes):
                        lon_ref = lon_ref.decode(errors="ignore")
                    lat_deg = -lat_val if lat_ref.upper() == "S" else lat_val
                    lon_deg = -lon_val if lon_ref.upper() == "W" else lon_val
                cam_direction = gps.get(17)  # GPSImgDirection if present (0..360)
            except Exception as e:
                logging.debug(f"GPS parse error for {path}: {e}")

    yaw_rad = math.radians(cam_direction) if cam_direction is not None else None

    drone_data = DroneData(
        lat=lat_deg,
        lon=lon_deg,
        alt=None,
        rel_alt=rel_alt,
        yaw=yaw_rad,
        roll=None,
        pitch=None,
    )
    return drone_data


def build_georef_frames(paths: List[str]) -> List[GeorefFrame]:
    frames: List[GeorefFrame] = []
    for p in paths:
        dd = parse_exif(p)
        if dd is None:
            logging.info(f"Skipping (no geo) {p}")
            continue
        img = cv2.imread(p)
        if img is None:
            logging.info(f"Skipping (cannot read) {p}")
            continue
        name = os.path.splitext(os.path.basename(p))[0]
        frames.append(GeorefFrame(image=img, drone_data=dd, name=name))
    return frames


def main():
    parser = argparse.ArgumentParser(description="Orthomap demo from geotagged JPEGs")
    parser.add_argument(
        "-d", "--dir", required=True, help="Directory with geotagged JPEGs"
    )
    parser.add_argument(
        "-o",
        "--output",
        default="map_visualization/orthomap_from_jpegs.png",
        help="Output PNG path",
    )
    parser.add_argument(
        "--fov-x", type=float, default=1.74, help="Horizontal field of view (radians)"
    )
    parser.add_argument(
        "--preview", action="store_true", help="Show live preview window"
    )
    parser.add_argument(
        "--alpha", type=float, default=0.5, help="Blend factor for new frames (0..1)"
    )
    parser.add_argument("-l", "--log-level", default="INFO")
    args = parser.parse_args()
    logging.basicConfig(
        level=getattr(logging, args.log_level.upper()),
        format="%(asctime)s %(levelname)s: %(message)s",
    )

    if not os.path.isdir(args.dir):
        raise SystemExit(f"Directory not found: {args.dir}")

    all_files = [
        os.path.join(args.dir, f)
        for f in os.listdir(args.dir)
        if f.lower().endswith(".jpg")
    ]
    all_files.sort(key=lambda p: os.path.getmtime(p))
    if not all_files:
        raise SystemExit("No .jpg files found.")

    georef_frames = build_georef_frames(all_files)
    if not georef_frames:
        raise SystemExit("No georeferenced frames parsed.")

    # derive dimensions from first image
    h, w = georef_frames[0].image.shape[:2]
    mapper = RealTimeMapper(
        img_width=w,
        img_height=h,
        fov_x=args.fov_x,
        alpha=args.alpha,
        preview=args.preview,
    )

    for gf in georef_frames:
        mapper.add_frame(gf)
        time.sleep(0.1)  # simulate processing delay

    mapper.save(args.output)
    logging.info(f"Saved orthomap to {args.output}")
    if args.preview:
        mapper.wait_until_closed()
        logging.info("Closing preview window...")
        mapper.close()


if __name__ == "__main__":
    main()
