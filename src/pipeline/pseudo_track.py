from pathlib import Path
import math
import orjson
from dataclasses import dataclass

@dataclass
class Track:
    track_id: int
    cls: int
    cx: float
    cy: float
    last_frame: int

def center(xyxy):
    x1,y1,x2,y2 = xyxy
    return (x1+x2)/2.0, (y1+y2)/2.0

def dist(a, b):
    return math.hypot(a[0]-b[0], a[1]-b[1])

def pseudo_track(detections_dir: str, out_path: str, max_move_px: float = 80.0):
    files = sorted(Path(detections_dir).glob("*.json"))
    tracks = []
    next_id = 1

    # results per frame
    timeline = []

    for fi, fpath in enumerate(files):
        data = orjson.loads(fpath.read_bytes())
        dets = data["detections"]

        frame_objs = []
        used_track_ids = set()

        for det in dets:
            xyxy = det["xyxy"]
            cls = det["cls"]
            cx, cy = center(xyxy)

            # find best track of same class not already used in this frame
            best = None
            best_d = 1e9
            for t in tracks:
                if t.cls != cls:
                    continue
                if t.track_id in used_track_ids:
                    continue
                d = dist((cx, cy), (t.cx, t.cy))
                if d < best_d:
                    best_d = d
                    best = t

            if best is not None and best_d <= max_move_px:
                # assign to existing
                best.cx, best.cy = cx, cy
                best.last_frame = fi
                tid = best.track_id
                used_track_ids.add(tid)
            else:
                # new track
                tid = next_id
                next_id += 1
                t = Track(track_id=tid, cls=cls, cx=cx, cy=cy, last_frame=fi)
                tracks.append(t)
                used_track_ids.add(tid)

            frame_objs.append({"track_id": tid, "cls": cls, "xyxy": xyxy})

        timeline.append({"frame_index": fi, "file": fpath.name, "objects": frame_objs})

        # drop stale tracks (not seen in N frames)
        tracks = [t for t in tracks if (fi - t.last_frame) <= 5]

    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    Path(out_path).write_bytes(orjson.dumps({"timeline": timeline}))
    print(f"Saved pseudo-tracks to {out_path}")

if __name__ == "__main__":
    pseudo_track("inference/detections", "inference/pseudo_tracks/pseudo_tracks.json", max_move_px=80)
