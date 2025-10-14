# Mapper

Lightweight toolkit for collecting, georeferencing and transmitting frames captured from a camera mounted on a drone or vehicle. Designed for quick capture of frames with embedded GPS/altitude/attitude metadata and streaming them to a ground station or processing pipeline. Includes also ground station script for receiving frames and further postprocesing.

## Features

- Capture and save frames with EXIF GPS longitude, latitude, altitude, relative altitude and image yaw.
- Attach timestamp and metadata (position, roll/pitch/yaw) to frames, which are streamed over ImageZMQ to a remote receiver.
- Simple frame selection (every Nth frame or on-request) and background saving.
- Streaming and saving video feed

## Components

- `georef_capture.py` — main companion computer script, reads telemetry and camera feed, maintains latest drone state uses other modules to for frame selection or sending
- `gcs.py` - main ground station script, for now receives frames with metadata and saves them
- `frame_selector.py` — chooses frames to save/send and queues background saves.
- `exif_utils.py` — writes EXIF GPS, altitude, relative altitude and yaw into JPEGs.
- `image_sender.py` — streams JPEGs + metadata over ImageZMQ.
- `mavlink_check.py`, `gst_check.py`, `replay.py`, `gcs.py` — helpers for telemetry, capture, replay and ground-control interaction.
- `config/` — example YAML configurations.
- `data/` — example recorded sessions and archives.

## Quickstart

1. Create a virtual environment for example with conda, then install dependencies:
   `pip install -r requirements.txt`
   Be careful, scripts need openCV build with gstreamer you may need to build it by yourself and install in created enviroment! 

2. Edit a config in `config/` to match camera and network settings.
3. Run the capture script (see `georef_capture.py`) to start streaming and saving frames.

### Example run command:
```bash
# with preview and simple local simulation config, no streaming, for companion comp  
python georef_capture.py -p -c config/local_sim.yaml

# for ground station
python gcs.py
```

## Data & Metadata

Saved JPEGs include EXIF GPS tags (latitude, longitude, altitude), ImageDescription with relative altitude and signed yaw (degrees), and GPSImgDirection normalized to 0–360°.


## Checklist before flight:
- [ ] check IPs and ports in `config/`, especially connection string and gcs_ip
- [ ] check frame selection strategy in `config/`, be careful - `select_on_request: True` overrides `select_nth_frame` option !!!
- [ ] set proper camera params and enable photos triggering in GCS!!!
- [ ] check if script is getting video and telemetry- no warning or errors in logs
- [ ] confirm camera settings like exposure/focus
- [ ] when running on companion computer, do not use -p option
- [ ] if you need video preview do not use to high bitrate, for now there is one bitrate for saving and streaming.
- [ ] run with proper config!