import re
import logging
from typing import Tuple, Optional


class BitrateCalculator:    
    STREAMING_BITRATES = {
        (1920, 1080): 3000,  # 3mbps (average SIYI Radio transfer speed)
        (4032, 3040): 4000,  # 4mbps limit (SIYI Radio transfer limit)
    }
    # This bitrates are estimated based on SIYI Air Unit transfer speed - tested via iperf3 tool that it estimates on 3-4 mbps.
    SAVING_BITRATES = {
        (1920, 1080): 8000,  # 8mbps
        (4032, 3040): 15000, # 15mbps
    }
    
    @staticmethod
    def parse_resolution_from_pipeline(pipeline: str) -> Optional[Tuple[int, int]]:
        # automatic bitrate configuration grabbed from gstreamer pipeline
        width_match = re.search(r'width=(\d+)', pipeline)
        height_match = re.search(r'height=(\d+)', pipeline)
        
        if width_match and height_match:
            width = int(width_match.group(1))
            height = int(height_match.group(1))
            return (width, height)
        
        return None
    
    @staticmethod
    def get_bitrate_for_resolution(resolution: Tuple[int, int], is_streaming: bool = False) -> int:
        # select bitrate map based on streaming or saving
        bitrate_map = BitrateCalculator.STREAMING_BITRATES if is_streaming else BitrateCalculator.SAVING_BITRATES

        for (w, h), bitrate in bitrate_map.items():
            if resolution == (w, h):
                return bitrate

        total_pixels = resolution[0] * resolution[1]
        
        if is_streaming:
            if total_pixels <= 1920 * 1080:
                return 3000
            else:
                return 4000
        else:
            if total_pixels <= 1920 * 1080:
                return 8000
            else:
                return 15000 # max sensor quality bitrate
    
    @staticmethod
    def update_pipeline_bitrate(pipeline: str, new_bitrate: int) -> str:
        bitrate_pattern = r'bitrate=\d+'
        new_bitrate_str = f'bitrate={new_bitrate}'
        
        if re.search(bitrate_pattern, pipeline):
            updated_pipeline = re.sub(bitrate_pattern, new_bitrate_str, pipeline)
        else:
            x264_pattern = r'(x264enc[^!]*?)(?=\s+[a-zA-Z]|\s*!)'
            if re.search(x264_pattern, pipeline):
                updated_pipeline = re.sub(x264_pattern, f'\\1 bitrate={new_bitrate}', pipeline)
            else:
                logging.warning("could not find bitrat in x264enc.")
                return pipeline
        
        return updated_pipeline
    
    @staticmethod
    def create_dual_bitrate_pipeline(base_pipeline: str, resolution: Tuple[int, int], 
                                   stream_ip: Optional[str] = None) -> str:
        saving_bitrate = BitrateCalculator.get_bitrate_for_resolution(resolution, is_streaming=False)
        streaming_bitrate = BitrateCalculator.get_bitrate_for_resolution(resolution, is_streaming=True)
        
        logging.info(f"setting bitrate: saving={saving_bitrate}kbps, streaming={streaming_bitrate}kbps")

        updated_pipeline = BitrateCalculator.update_pipeline_bitrate(base_pipeline, saving_bitrate)

        if stream_ip:
            address, port = stream_ip.split(":")
            streaming_pipeline = f" out. ! queue ! x264enc bitrate={streaming_bitrate} tune=zerolatency ! h264parse ! rtph264pay config-interval=1 pt=96 ! udpsink host={address} port={port} sync=false async=false"
            updated_pipeline += streaming_pipeline
        
        return updated_pipeline


def auto_configure_bitrates(config: dict, stream_ip: Optional[str] = None) -> dict:
    updated_config = config.copy()

    capture_pipeline = config.get("gst_capture_pipeline", "")
    resolution = BitrateCalculator.parse_resolution_from_pipeline(capture_pipeline)
    
    if resolution:
        logging.info(f"res detected: {resolution[0]}x{resolution[1]}")

        base_writer_pipeline = config.get("gst_writer_pipeline", "")
        new_writer_pipeline = BitrateCalculator.create_dual_bitrate_pipeline(
            base_writer_pipeline, resolution, stream_ip
        )
        
        updated_config["gst_writer_pipeline"] = new_writer_pipeline
        logging.info(f"updated pipeline: {new_writer_pipeline}")
    else:
        logging.warning("could not detect pipeline.")
    
    return updated_config
