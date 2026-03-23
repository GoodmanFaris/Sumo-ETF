from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple, Optional

import numpy as np
import pandas as pd
from shapely.geometry import Point, Polygon, LineString


# -----------------------------
# Helpers: geometry
# -----------------------------

def bbox_center(xyxy: List[float]) -> Tuple[float, float]:
    x1, y1, x2, y2 = xyxy
    return (x1 + x2) / 2.0, (y1 + y2) / 2.0


def crosses_line(p_prev: Tuple[float, float], p_curr: Tuple[float, float], line: LineString) -> bool:
    """Return True if the segment from p_prev to p_curr intersects the count line."""
    seg = LineString([p_prev, p_curr])
    return seg.crosses(line) or seg.intersects(line)


def point_in_poly(pt: Tuple[float, float], poly: Polygon) -> bool:
    return poly.contains(Point(pt[0], pt[1]))


# -----------------------------
# Data models
# -----------------------------

@dataclass
class CountLine:
    id: str
    line: LineString
    direction_hint: str = ""  

@dataclass
class Zone:
    id: str
    poly: Polygon


# -----------------------------
# Loading configs
# -----------------------------

def load_zones(zones_path: str) -> Tuple[List[CountLine], List[Zone], List[Zone], List[Zone]]:
    """
    zones.json schema (minimal):
    {
      "count_lines":[{"id":"A_in","p1":[x,y],"p2":[x,y]}],
      "entry_zones":[{"id":"A_entry","polygon":[[x,y],...]}],
      "exit_zones":[{"id":"N_exit","polygon":[[x,y],...]}],
      "queue_zones":[{"id":"A_queue","polygon":[[x,y],...]}]
    }
    """
    data = json.loads(Path(zones_path).read_text(encoding="utf-8"))

    count_lines = []
    for cl in data.get("count_lines", []):
        p1 = cl["p1"]; p2 = cl["p2"]
        count_lines.append(
            CountLine(
                id=cl["id"],
                line=LineString([tuple(p1), tuple(p2)]),
                direction_hint=cl.get("direction_hint", "")
            )
        )

    entry_zones = [Zone(z["id"], Polygon(z["polygon"])) for z in data.get("entry_zones", [])]
    exit_zones  = [Zone(z["id"], Polygon(z["polygon"])) for z in data.get("exit_zones", [])]
    queue_zones = [Zone(z["id"], Polygon(z["polygon"])) for z in data.get("queue_zones", [])]

    return count_lines, entry_zones, exit_zones, queue_zones


def load_pseudo_tracks(pseudo_tracks_path: str) -> List[dict]:
    """
    Expected:
    { "timeline": [ { "frame_index": 0, "file":"...", "objects":[{"track_id":1,"cls":0,"xyxy":[...]}]} ... ] }
    """
    data = json.loads(Path(pseudo_tracks_path).read_text(encoding="utf-8"))
    return data["timeline"]


def load_class_map(class_map_path: Optional[str]) -> Dict[int, str]:
    """
    Optional mapping from YOLO class id -> name.
    If not provided, returns {0:"car",1:"bus",2:"truck"} as default.
    """
    if not class_map_path:
        return {0: "car", 1: "bus", 2: "truck"}

    p = Path(class_map_path)
    if not p.exists():
        raise FileNotFoundError(class_map_path)

    if p.suffix.lower() in [".json"]:
        raw = json.loads(p.read_text(encoding="utf-8"))
        return {int(k): str(v) for k, v in raw.items()}

    # simple text fallback: "0 car" per line
    mapping: Dict[int, str] = {}
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split()
        mapping[int(parts[0])] = " ".join(parts[1:])
    return mapping


# -----------------------------
# Core metric extraction
# -----------------------------

def extract_metrics(
    pseudo_tracks_path: str,
    zones_path: str,
    out_per_frame_csv: str,
    out_agg_csv: str,
    snapshot_dt_sec: float = 3.0,
    agg_bin_sec: int = 60,
    class_map_path: Optional[str] = None
) -> None:
    count_lines, entry_zones, exit_zones, queue_zones = load_zones(zones_path)
    timeline = load_pseudo_tracks(pseudo_tracks_path)
    class_map = load_class_map(class_map_path)


    last_center: Dict[int, Tuple[float, float]] = {}
    last_entry_zone: Dict[int, Optional[str]] = {}
    last_exit_zone: Dict[int, Optional[str]] = {}
    last_seen_frame: Dict[int, int] = {}


    crossed_line: Dict[Tuple[int, str], bool] = {}

   
    rows = []

    for frame in timeline:
        fi = int(frame["frame_index"])
        t_sec = fi * snapshot_dt_sec
        objects = frame.get("objects", [])


        queue_counts = {qz.id: 0 for qz in queue_zones}

        class_counts: Dict[str, int] = {}

        for obj in objects:
            tid = int(obj["track_id"])
            cls_id = int(obj["cls"])
            cls_name = class_map.get(cls_id, f"class_{cls_id}")
            xyxy = obj["xyxy"]
            c = bbox_center(xyxy)

            class_counts[cls_name] = class_counts.get(cls_name, 0) + 1


            for qz in queue_zones:
                if point_in_poly(c, qz.poly):
                    queue_counts[qz.id] += 1


            in_entry = None
            for ez in entry_zones:
                if point_in_poly(c, ez.poly):
                    in_entry = ez.id
                    break

            in_exit = None
            for xz in exit_zones:
                if point_in_poly(c, xz.poly):
                    in_exit = xz.id
                    break


            if in_entry is not None:
                last_entry_zone[tid] = in_entry
            if in_exit is not None:
                last_exit_zone[tid] = in_exit


            if tid in last_center:
                prev = last_center[tid]
                for cl in count_lines:
                    key = (tid, cl.id)
                    if crossed_line.get(key, False):
                        continue
                    if crosses_line(prev, c, cl.line):
                        crossed_line[key] = True

                        rows.append({
                            "time_sec": t_sec,
                            "frame_index": fi,
                            "event": "flow_cross",
                            "count_line_id": cl.id,
                            "track_id": tid,
                            "class": cls_name,
                            "entry_zone": last_entry_zone.get(tid),
                            "exit_zone": last_exit_zone.get(tid),
                            "queue_zone_id": None,
                            "queue_count": None
                        })

            last_center[tid] = c
            last_seen_frame[tid] = fi

        for qz_id, qc in queue_counts.items():
            rows.append({
                "time_sec": t_sec,
                "frame_index": fi,
                "event": "queue_snapshot",
                "count_line_id": None,
                "track_id": None,
                "class": None,
                "entry_zone": None,
                "exit_zone": None,
                "queue_zone_id": qz_id,
                "queue_count": qc
            })

        for cname, cnt in class_counts.items():
            rows.append({
                "time_sec": t_sec,
                "frame_index": fi,
                "event": "class_snapshot",
                "count_line_id": None,
                "track_id": None,
                "class": cname,
                "entry_zone": None,
                "exit_zone": None,
                "queue_zone_id": None,
                "queue_count": cnt
            })

    out_per = Path(out_per_frame_csv)
    out_per.parent.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(rows)
    df.to_csv(out_per, index=False)

    # -----------------------------
    # Aggregate to bins (e.g., 60s)
    # -----------------------------
    if df.empty:
        out_agg = Path(out_agg_csv)
        out_agg.parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame().to_csv(out_agg, index=False)
        print("No rows to aggregate (empty).")
        return

    df["bin_start_sec"] = (df["time_sec"] // agg_bin_sec) * agg_bin_sec

    flow = df[df["event"] == "flow_cross"].copy()
    flow_group = flow.groupby(["bin_start_sec", "count_line_id", "class"]).size().reset_index(name="flow_count")

    turns = flow.dropna(subset=["entry_zone", "exit_zone"]).copy()
    turn_group = turns.groupby(["bin_start_sec", "count_line_id", "entry_zone", "exit_zone"]).size().reset_index(name="turn_count")

    q = df[df["event"] == "queue_snapshot"].dropna(subset=["queue_zone_id", "queue_count"]).copy()
    q_group = q.groupby(["bin_start_sec", "queue_zone_id"])["queue_count"].agg(["mean", "max"]).reset_index()
    q_group.rename(columns={"mean": "queue_mean", "max": "queue_max"}, inplace=True)


    cs = df[df["event"] == "class_snapshot"].dropna(subset=["class", "queue_count"]).copy()
    cs_group = cs.groupby(["bin_start_sec", "class"])["queue_count"].mean().reset_index()
    cs_group.rename(columns={"queue_count": "avg_count_per_frame"}, inplace=True)


    bins = sorted(df["bin_start_sec"].unique().tolist())
    base = pd.DataFrame({"bin_start_sec": bins})


    flow_total = flow_group.groupby(["bin_start_sec", "count_line_id"])["flow_count"].sum().reset_index()
    flow_wide = flow_total.pivot(index="bin_start_sec", columns="count_line_id", values="flow_count").fillna(0).reset_index()
    flow_wide.columns = ["bin_start_sec"] + [f"flow_{c}" for c in flow_wide.columns[1:]]

    out_agg = Path(out_agg_csv)
    out_agg.parent.mkdir(parents=True, exist_ok=True)


    turn_path = out_agg.parent / "turning_counts_long.csv"
    turn_group.to_csv(turn_path, index=False)


    queue_path = out_agg.parent / "queue_stats_long.csv"
    q_group.to_csv(queue_path, index=False)


    class_path = out_agg.parent / "class_composition_long.csv"
    cs_group.to_csv(class_path, index=False)

    merged = base.merge(flow_wide, on="bin_start_sec", how="left").fillna(0)

    if not q_group.empty:
        qsum = q_group.groupby("bin_start_sec")[["queue_mean", "queue_max"]].agg({"queue_mean": "mean", "queue_max": "max"}).reset_index()
        qsum.rename(columns={"queue_mean": "queue_mean_allzones", "queue_max": "queue_max_allzones"}, inplace=True)
        merged = merged.merge(qsum, on="bin_start_sec", how="left")

    merged.to_csv(out_agg, index=False)

    print(f"Saved per-frame events: {out_per}")
    print(f"Saved aggregated metrics: {out_agg}")
    print(f"Saved turning counts (long): {turn_path}")
    print(f"Saved queue stats (long): {queue_path}")
    print(f"Saved class composition (long): {class_path}")


if __name__ == "__main__":
    #pass
    extract_metrics(
        pseudo_tracks_path="inference/pseudo_tracks/pseudo_tracks.json",
        zones_path="sumo/zones/zones.json",
        out_per_frame_csv="metrics/per_frame/observations_per_frame.csv",
        out_agg_csv="metrics/aggregated/metrics_aggregated.csv",
        snapshot_dt_sec=3.0,
        agg_bin_sec=60
    )
