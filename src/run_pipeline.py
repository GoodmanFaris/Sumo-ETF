from pipeline.extract_frames import extract_frames
from pipeline.run_inference import run_inference
from pipeline.pseudo_track import pseudo_track
from pipeline.extract_metrics import extract_metrics
from sumo.generate_flows import generate_flows_xml

VIDEO = "raw/videos/cam01.mp4"
IMAGES_DIR = "raw/images"
DETS_DIR = "inference/detections"
TRACKS_JSON = "inference/pseudo_tracks/pseudo_tracks.json"

ZONES = "sumo/zones/zones.json"
PER_FRAME = "metrics/per_frame/observations_per_frame.csv"
AGG = "metrics/aggregated/metrics_aggregated.csv"

MAPPING = "sumo/mapping/mapping.json"
FLOWS_XML = "sumo/demand/flows.xml"


extract_frames(VIDEO, IMAGES_DIR, every_seconds=3.0)


yolo_weights = "models/cam01_yolo/weights/best.pt"
run_inference(yolo_weights, IMAGES_DIR, DETS_DIR, conf=0.25)


pseudo_track(DETS_DIR, TRACKS_JSON, max_move_px=80.0)


extract_metrics(TRACKS_JSON, ZONES, PER_FRAME, AGG, snapshot_dt_sec=3.0, agg_bin_sec=60, class_map_path="class_map.json")


generate_flows_xml(AGG, "metrics/aggregated/turning_counts_long.csv", MAPPING, FLOWS_XML, agg_bin_sec=60)
