#!/usr/bin/env python3
"""Realtime orthophoto builder based on georeferenced frames.

Instead of reading EXIF from saved JPEGs this class consumes `GeorefFrame` objects
(directly providing image ndarray + DroneData with lat, lon, alt, yaw (radians), etc.).

Usage example:

    from realtime_mapper import RealTimeMapper
    mapper = RealTimeMapper(img_width=1280, img_height=720, fov_x=1.74, preview=True)
    mapper.add_frame(geo_frame)
    # interact with window: scrollbars, mouse wheel to zoom, drag to pan.
"""
from __future__ import annotations
import os
import math
import numpy as np
from typing import Optional
from PIL import Image, ImageTk
import tkinter as tk
from geo_frame import GeorefFrame
import cv2


class RealTimeMapper:
    def __init__(
        self,
        img_width: int,
        img_height: int,
        fov_x: float,
        ortho_width: int = 5000,
        ortho_height: int = 5000,
        alpha: float = 0.5,
        preview: bool = False,
        preview_scale: float = 0.4,
    ):
        """Initialize realtime mapper.

        img_width/img_height: dimensions of source frames (needed for GSD).
        fov_x: horizontal field of view (radians).
        ortho_width/height: pixel size of orthomap canvas.
        alpha: blend factor for newly added frame (0..1).
        preview: if True show incremental Tk preview window.
        preview_scale: scale factor applied to displayed orthomap.
        """
        self.img_width = img_width
        self.img_height = img_height
        self.fov_x = fov_x
        self.fov_y = fov_x * (img_height / img_width)
        self.ortho_width = ortho_width
        self.ortho_height = ortho_height
        self.alpha = alpha
        self.preview = preview
        self.preview_scale = preview_scale

        # RGBA canvas
        self.ortho_map = np.zeros((ortho_height, ortho_width, 4), dtype=np.uint8)

        # reference frame info (set when first frame added)
        self.ref_lat: Optional[float] = None
        self.ref_lon: Optional[float] = None
        self.ref_gsd_x: Optional[float] = None  # meters per pixel horizontally
        self.frames_added = 0

        # preview setup
        self._tk_root: Optional[tk.Tk] = None
        self._tk_canvas: Optional[tk.Canvas] = None
        self._tk_img: Optional[ImageTk.PhotoImage] = None
        self.zoom: float = 1.0
        self.min_zoom: float = 0.1
        self.max_zoom: float = 5.0
        self._canvas_image_id = None
        self._hq_refresh_pending = False  # schedule high-quality refresh after fast zoom
        if self.preview:
            self._init_preview()

    def _init_preview(self):
        self._tk_root = tk.Tk()
        self._tk_root.title("Realtime Orthomap Preview")
        w = int(self.ortho_width * self.preview_scale)
        h = int(self.ortho_height * self.preview_scale)
        self._tk_canvas = tk.Canvas(self._tk_root, width=w, height=h)
        # Repack using grid to allow expansion and scrollbars always visible
        self._tk_canvas.pack_forget()
        self._tk_root.rowconfigure(0, weight=1)
        self._tk_root.columnconfigure(0, weight=1)
        self._tk_canvas.grid(row=0, column=0, sticky='nsew')
        self._h_scroll = tk.Scrollbar(self._tk_root, orient='horizontal')
        self._h_scroll.grid(row=1, column=0, sticky='ew')
        self._v_scroll = tk.Scrollbar(self._tk_root, orient='vertical')
        self._v_scroll.grid(row=0, column=1, sticky='ns')
        self._tk_canvas.config(xscrollcommand=self._h_scroll.set, yscrollcommand=self._v_scroll.set)
        self._h_scroll.config(command=self._tk_canvas.xview)
        self._v_scroll.config(command=self._tk_canvas.yview)
        # Bind zoom & pan
        self._tk_canvas.bind('<ButtonPress-1>', self._on_btn_press)
        self._tk_canvas.bind('<B1-Motion>', self._on_drag)
        self._tk_canvas.bind('<MouseWheel>', self._on_mouse_wheel)
        self._tk_canvas.bind('<Button-4>', lambda e: self._on_mouse_wheel(e, delta=120))
        self._tk_canvas.bind('<Button-5>', lambda e: self._on_mouse_wheel(e, delta=-120))

    def _on_btn_press(self, event):
        if self._tk_canvas is not None:
            self._tk_canvas.scan_mark(event.x, event.y)

    def _on_drag(self, event):
        if self._tk_canvas is not None:
            self._tk_canvas.scan_dragto(event.x, event.y, gain=1)

    def _on_mouse_wheel(self, event, delta=None):
        if delta is None:
            delta = event.delta
        prev_zoom = self.zoom
        if delta > 0:
            self.zoom *= 1.15
        else:
            self.zoom /= 1.15
        self.zoom = max(self.min_zoom, min(self.max_zoom, self.zoom))
        if abs(self.zoom - prev_zoom) < 0.001:
            return
        # Fast redraw (nearest) followed by scheduled HQ refresh
        self._update_preview(force=True, fast=True)
        if not self._hq_refresh_pending:
            self._hq_refresh_pending = True
            self._tk_root.after(150, self._delayed_hq_refresh)

    def _delayed_hq_refresh(self):
        if not self.preview:
            return
        self._update_preview(force=True, fast=False)
        self._hq_refresh_pending = False

    def _update_preview(self, force: bool = False, fast: bool = False):
        if not self.preview or self._tk_canvas is None:
            return
        preview_img = Image.fromarray(self.ortho_map, 'RGBA')
        target_w = int(self.ortho_width * self.preview_scale * self.zoom)
        target_h = int(self.ortho_height * self.preview_scale * self.zoom)
        resample = Image.Resampling.NEAREST if fast else Image.Resampling.LANCZOS
        preview_img = preview_img.resize((target_w, target_h), resample)
        self._tk_img = ImageTk.PhotoImage(preview_img)
        if self._canvas_image_id is None:
            self._canvas_image_id = self._tk_canvas.create_image(0, 0, anchor='nw', image=self._tk_img)
        else:
            self._tk_canvas.itemconfig(self._canvas_image_id, image=self._tk_img)
        self._tk_canvas.config(scrollregion=(0, 0, target_w, target_h))
        self._tk_root.update_idletasks()
        self._tk_root.update()

    def wait_until_closed(self):
        """Block until the preview window is closed by the user."""
        if self._tk_root is not None:
            self._tk_root.mainloop()

    @staticmethod
    def _gps_to_pixel_offset(lat_ref: float, lon_ref: float, lat: float, lon: float, gsd_x: float) -> tuple[int, int]:
        """Convert the GPS coordinate difference (approx planar) into pixel offset.
        Uses equirectangular approximation suitable for small areas.
        """
        delta_x_m = (lon - lon_ref) * 111320 * math.cos(math.radians(lat_ref))
        delta_y_m = (lat - lat_ref) * 111320
        px_offset = int(delta_x_m / gsd_x)
        py_offset = int(delta_y_m / gsd_x)
        return px_offset, py_offset

    def _compute_gsd_x(self, altitude_m: float) -> float:
        """Compute ground sampling distance (meters per pixel) horizontally.
        Formula: footprint_width = 2 * alt * tan(FOVx/2) ; GSD = footprint_width / img_width
        """
        return 2 * altitude_m * math.tan(self.fov_x / 2) / self.img_width

    def add_frame(self, geo_frame: GeorefFrame) -> None:
        """Blend a georeferenced frame into the orthomap.

        geo_frame.drone_data must have lat, lon, alt, yaw (radians) and rel_alt.
        If yaw unavailable, no rotation is applied.
        Transparent background preserved for rotated images (only real pixels blended).
        """
        dd = geo_frame.drone_data
        if any(v is None for v in [dd.lat, dd.lon, dd.rel_alt]):
            # insufficient geo data
            return

        # reference initialization
        if self.ref_lat is None:
            self.ref_lat = dd.lat
            self.ref_lon = dd.lon
            self.ref_gsd_x = self._compute_gsd_x(dd.rel_alt)

        # For offset we keep using reference frame's gsd_x so scale is consistent on canvas
        ref_gsd_x = self.ref_gsd_x

        # Rotation: convert yaw radians (-pi..pi) to degrees; normalize so that 0 deg = north-up if desired.
        # Original script rotated by -cam_direction (degrees). We'll mimic that with negative yaw_deg.
        yaw_deg = math.degrees(dd.yaw) if dd.yaw is not None else 0.0
        rotate_deg = -yaw_deg

        # Convert BGR (OpenCV) -> RGB before creating PIL Image to fix swapped colors
        bgr = geo_frame.image
        rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
        rgba = cv2.cvtColor(rgb, cv2.COLOR_RGB2RGBA)
        pil_rgba = Image.fromarray(rgba)
        rotated_img = pil_rgba.rotate(rotate_deg, expand=True, fillcolor=(0, 0, 0, 0))
        img_np = np.array(rotated_img)  # RGBA
        h, w = img_np.shape[:2]

        # Pixel offset from reference lat/lon
        px_offset, py_offset = self._gps_to_pixel_offset(self.ref_lat, self.ref_lon, dd.lat, dd.lon, ref_gsd_x)

        # Place frame roughly at center + offset
        x_start = self.ortho_width // 2 + px_offset - w // 2
        y_start = self.ortho_height // 2 + py_offset - h // 2
        x_end = x_start + w
        y_end = y_start + h

        # Clipping
        x_start_clip = max(0, x_start)
        y_start_clip = max(0, y_start)
        x_end_clip = min(self.ortho_width, x_end)
        y_end_clip = min(self.ortho_height, y_end)
        if x_start_clip >= x_end_clip or y_start_clip >= y_end_clip:
            return  # completely outside

        img_x_start = x_start_clip - x_start
        img_y_start = y_start_clip - y_start
        img_x_end = img_x_start + (x_end_clip - x_start_clip)
        img_y_end = img_y_start + (y_end_clip - y_start_clip)
        img_region = img_np[img_y_start:img_y_end, img_x_start:img_x_end, :]  # RGBA

        # Blend only where alpha > 0 (real pixels). Keep existing where transparent.
        target_region = self.ortho_map[y_start_clip:y_end_clip, x_start_clip:x_end_clip, :]
        mask = img_region[:, :, 3] > 0
        if np.any(mask):
            # Prepare arrays
            new_rgb = target_region[:, :, :3]
            src_rgb = img_region[:, :, :3]
            # Expand mask to 3 channels
            mask_3 = np.repeat(mask[:, :, None], 3, axis=2)
            # Alpha blending where mask True
            blended = (src_rgb.astype(np.float32) * self.alpha + new_rgb.astype(np.float32) * (1 - self.alpha)).astype(np.uint8)
            new_rgb[mask_3] = blended[mask_3]
            target_region[:, :, :3] = new_rgb
            # Set alpha to 255 where pixel written
            target_region[:, :, 3][mask] = 255
        # leave transparent background untouched

        self.frames_added += 1
        self._update_preview()

    def save(self, output_path: str) -> None:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        Image.fromarray(self.ortho_map, 'RGBA').save(output_path)

    def close(self):
        if self._tk_root is not None:
            try:
                self._tk_root.destroy()
            except Exception:
                pass


if __name__ == '__main__':
    print('RealtimeMapper standalone test placeholder. Integrate within capture pipeline.')
