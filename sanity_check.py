#!/usr/bin/env python3
"""Sanity check script for mapper project.

Performs a sequence of quick diagnostics:
1. Load provided YAML config.
2. Open camera (GStreamer pipeline) and grab N test frames.
3. Check telemetry (MAVLink) heartbeat + receive GLOBAL_POSITION_INT & ATTITUDE.
4. Test ImageZMQ send (blocking) to an external receiver (e.g. gcs.py) with timeout.
5. Verify EXIF written (lat/lon/alt/rel_alt/yaw) to a temp JPEG.

Exit code 0 if all selected checks pass, otherwise non‑zero.

Usage:
  python sanity_check.py -c config/local_sim.yaml --no-video  # skip camera check

Notes:
- For camera test you need a valid gst_capture_pipeline in the config.
- For telemetry test you need MAVLink source available per connection_string.
"""
import argparse
import logging
import yaml
import time
import os
import tempfile
import cv2
from pymavlink import mavutil
import json
import imagezmq
import simplejpeg
import dataclasses
import threading
import numpy as np

from models import DroneData
from exif_utils import save_frame_with_gps


def check_camera(cfg, grab_frames=5):
    pipeline = cfg.get("gst_capture_pipeline")
    cap = cv2.VideoCapture(pipeline, cv2.CAP_GSTREAMER)
    if not cap.isOpened():
        raise RuntimeError("Camera open failed")
    ok = 0
    for i in range(grab_frames):
        ret, frame = cap.read()
        if not ret:
            raise RuntimeError(f"Failed to read frame {i}")
        ok += 1
        time.sleep(0.05)
    cap.release()
    logging.info(f"Camera check OK: {ok}/{grab_frames} frames read")
    return frame  # last frame


def check_mavlink(cfg, timeout=5.0):
    master = mavutil.mavlink_connection(
        cfg.get("connection_string"), baud=cfg.get("baud_rate")
    )
    start = time.time()
    logging.info("Waiting for heartbeat...")
    res = master.wait_heartbeat(timeout=timeout)
    if res is None:
        raise RuntimeError("No heartbeat received")
    logging.info(f"Heartbeat received, result {res}")
    data = DroneData()
    got_pos = got_att = False
    while time.time() - start < timeout and (not got_pos or not got_att):
        msg = master.recv_match(
            type=["GLOBAL_POSITION_INT", "ATTITUDE"], blocking=True, timeout=timeout
        )
        if not msg:
            break
        if msg.get_type() == "GLOBAL_POSITION_INT":
            data.lat = msg.lat / 1e7
            data.lon = msg.lon / 1e7
            data.alt = msg.alt / 1000.0
            data.rel_alt = msg.relative_alt / 1000.0
            got_pos = True
        elif msg.get_type() == "ATTITUDE":
            data.roll = msg.roll
            data.pitch = msg.pitch
            data.yaw = msg.yaw
            got_att = True
    if not (got_pos and got_att):
        raise RuntimeError("Did not receive full telemetry (position+attitude)")
    logging.info(
        f"Telemetry check OK: lat={data.lat:.6f} lon={data.lon:.6f} alt={data.alt:.2f} rel_alt={data.rel_alt:.2f} yaw={data.yaw:.3f}"
    )
    return data


def check_imagezmq_send(frame, drone_data, dest_ip: str, port: int = 5001, attempts: int = 3, per_frame_timeout: float = 2.0):
    """Attempt to send a few frames to an external ImageZMQ receiver (gcs.py).

    Because ImageSender (REQ) waits for REP, a missing receiver will block. We protect
    each send() with a thread + timeout. If any attempt times out or errors, raise.
    """
    endpoint = f"tcp://{dest_ip}:{port}"
    sender = imagezmq.ImageSender(connect_to=endpoint)
    meta_base = dataclasses.asdict(drone_data)
    jpg_buffer = simplejpeg.encode_jpeg(frame, quality=80, colorspace="BGR")

    def send_once(meta_json, buf):
        result = {}
        def worker():
            print("worker")
            try:
                sender.send_jpg(meta_json, buf)
                result['ok'] = True
            except Exception as e:  # pragma: no cover
                result['err'] = e
        t = threading.Thread(target=worker)
        t.start()
        t.join(per_frame_timeout)
        if t.is_alive():
            return False, TimeoutError(f"send_jpg timeout after {per_frame_timeout}s")
        if 'err' in result:
            return False, result['err']
        return True, None

    for i in range(1, attempts + 1):
        meta = dict(meta_base)
        meta['name'] = f"sanity_frame_{i}"
        meta_json = json.dumps(meta)
        ok, err = send_once(meta_json, jpg_buffer)
        sender.zmq_socket.close(linger=0)
        sender.close()
        if not ok:
            sender = imagezmq.ImageSender(connect_to=endpoint)
            logging.error(f"ImageZMQ send attempt {i}/{attempts} failed: {err}")
        else:
            logging.info(f"ImageZMQ send attempt {i}/{attempts} OK")
            return True
        
    raise RuntimeError(f"ImageZMQ send failed after {attempts} attempts")


def check_exif(frame, drone_data):
    with tempfile.TemporaryDirectory() as td:
        path = os.path.join(td, "test.jpg")
        save_frame_with_gps(
            frame,
            path,
            lat=drone_data.lat,
            lng=drone_data.lon,
            alt=drone_data.alt,
            rel_alt=drone_data.rel_alt,
            yaw=drone_data.yaw,
        )
        # rudimentary: ensure file exists & size > minimal
        if not os.path.exists(path) or os.path.getsize(path) < 1000:
            raise RuntimeError("EXIF save failed (file too small)")
    logging.info("EXIF check OK")


def main():
    parser = argparse.ArgumentParser("Mapper sanity check")
    parser.add_argument("-c", "--config", required=True, help="Config YAML file")
    parser.add_argument("--skip-tele", action="store_true", help="Skip telemetry check")
    parser.add_argument("--skip-video", action="store_true", help="Skip camera check")
    parser.add_argument("--skip-send", action="store_true", help="Skip ImageZMQ send test")
    parser.add_argument("-l", "--log-level", default="INFO")
    args = parser.parse_args()
    logging.basicConfig(level=getattr(logging, args.log_level.upper()), format="%(asctime)s %(levelname)s: %(message)s")

    with open(args.config) as f:
        cfg = yaml.safe_load(f)
    logging.info("Config loaded.")

    last_frame = None
    drone_data = DroneData()

    if not args.skip_video:
        try:
            last_frame = check_camera(cfg)
        except Exception as e:
            logging.error(f"Camera check FAILED: {e}")
            return 2
    else:
        logging.info("Skipping camera check.")

    if not args.skip_tele:
        try:
            drone_data = check_mavlink(cfg)
        except Exception as e:
            logging.error(f"Telemetry check FAILED: {e}")
            return 3
    else:
        logging.info("Skipping telemetry check.")

    if last_frame is None:
        # create synthetic frame (black with text)
        last_frame = np.zeros((480, 640, 3), dtype=np.uint8)
        cv2.putText(last_frame, 'SANITY', (50,240), cv2.FONT_HERSHEY_SIMPLEX, 2, (255,255,255), 3)

    if not args.skip_send:
        try:
            if not drone_data.is_initialized():
                drone_data.lat = 0.0
                drone_data.lon = 0.0
                drone_data.alt = 0.0
                drone_data.rel_alt = 0.0
                drone_data.roll = 0.0
                drone_data.pitch = 0.0
                drone_data.yaw = 0.0
            dest_ip = cfg.get('gcs_ip')
            check_imagezmq_send(last_frame, drone_data, dest_ip=dest_ip)
        except Exception as e:
            logging.error(f"ImageZMQ send check FAILED: {e}")
            return 4
    else:
        logging.info("Skipping ImageZMQ send test.")

    try:
        if drone_data.is_initialized() and last_frame is not None:
            check_exif(last_frame, drone_data)
    except Exception as e:
        logging.error(f"EXIF check FAILED: {e}")
        return 5

    logging.info("All selected sanity checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
