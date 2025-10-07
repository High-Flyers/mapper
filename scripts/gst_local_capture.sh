#!/bin/bash
# This script captures a local video stream using GStreamer and displays it in a window.
gst-launch-1.0 -v udpsrc port=5000 caps="application/x-rtp, media=video, encoding-name=H264, payload=96" ! rtph264depay ! avdec_h264 ! autovideosink