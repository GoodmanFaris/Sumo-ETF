from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Tuple, List

import pandas as pd
from lxml import etree


def load_mapping(mapping_path: str) -> dict:
    return json.loads(Path(mapping_path).read_text(encoding="utf-8"))


def build_turn_lookup(mapping: dict) -> Dict[Tuple[str, str], str]:
    turn_map = {}
    for t in mapping.get("turns", []):
        turn_map[(t["approach_id"], t["movement"])] = t["to_edge"]
    return turn_map


def parse_turning_counts(turning_long_csv: str, mapping: dict) -> pd.DataFrame:
    df = pd.read_csv(turning_long_csv)
    if df.empty:
        return df

    cl2app = mapping.get("count_line_to_approach", {})
    exit2mov = mapping.get("exit_zone_to_movement", {})

    df["approach_id"] = df["count_line_id"].map(cl2app)
    df["movement"] = df["exit_zone"].map(exit2mov)

    df = df.dropna(subset=["approach_id", "movement"])
    return df[["bin_start_sec", "approach_id", "movement", "turn_count"]]


def load_flow_table(metrics_agg_csv: str) -> pd.DataFrame:
    df = pd.read_csv(metrics_agg_csv)
    return df


def generate_flows_xml(
    metrics_agg_csv: str,
    turning_long_csv: str,
    mapping_path: str,
    out_xml_path: str,
    agg_bin_sec: int = 60,
    default_movement: str = "T",
    depart_lane: str = "best",
    depart_speed: str = "max"
) -> None:
    mapping = load_mapping(mapping_path)
    turn_lookup = build_turn_lookup(mapping)

    flows_df = load_flow_table(metrics_agg_csv)
    if flows_df.empty:
        raise RuntimeError("metrics_aggregated.csv is empty. Run extract_metrics first.")

    flow_cols = [c for c in flows_df.columns if c.startswith("flow_")]
    if not flow_cols:
        raise RuntimeError("No flow_ columns found in metrics_aggregated.csv")


    turns_df = pd.DataFrame()
    turn_path = Path(turning_long_csv)
    if turn_path.exists():
        turns_df = parse_turning_counts(turning_long_csv, mapping)
    else:
        turns_df = pd.DataFrame()

    if not turns_df.empty:
        totals = turns_df.groupby(["bin_start_sec", "approach_id"])["turn_count"].sum().reset_index(name="total")
        turns_df = turns_df.merge(totals, on=["bin_start_sec", "approach_id"], how="left")
        turns_df["ratio"] = turns_df["turn_count"] / turns_df["total"].replace({0: pd.NA})
        turns_df = turns_df.dropna(subset=["ratio"])

    # Build XML
    routes = etree.Element("routes")

    for _, row in flows_df.iterrows():
        bin_start = int(row["bin_start_sec"])
        bin_end = bin_start + agg_bin_sec

        for fc in flow_cols:
            count_line_id = fc.replace("flow_", "")
            approach_id = mapping.get("count_line_to_approach", {}).get(count_line_id)
            if not approach_id:
                continue

            from_edge = None
            for a in mapping.get("approaches", []):
                if a["approach_id"] == approach_id:
                    from_edge = a["from_edge"]
                    break
            if not from_edge:
                continue

            flow_count = float(row[fc])
            if flow_count <= 0:
                continue

            vehs_per_hour = flow_count * (3600.0 / agg_bin_sec)

            if not turns_df.empty:
                sub = turns_df[(turns_df["bin_start_sec"] == bin_start) & (turns_df["approach_id"] == approach_id)]
                if sub.empty:
                    to_edge = turn_lookup.get((approach_id, default_movement))
                    if to_edge:
                        f = etree.SubElement(routes, "flow", attrib={
                            "id": f"flow_{approach_id}_{bin_start}_{default_movement}",
                            "begin": str(bin_start),
                            "end": str(bin_end),
                            "from": from_edge,
                            "to": to_edge,
                            "vehsPerHour": f"{vehs_per_hour:.2f}",
                            "departLane": depart_lane,
                            "departSpeed": depart_speed
                        })
                    continue

                for _, tr in sub.iterrows():
                    movement = str(tr["movement"])
                    ratio = float(tr["ratio"])
                    to_edge = turn_lookup.get((approach_id, movement))
                    if not to_edge or ratio <= 0:
                        continue

                    vph = vehs_per_hour * ratio
                    if vph <= 0:
                        continue

                    etree.SubElement(routes, "flow", attrib={
                        "id": f"flow_{approach_id}_{bin_start}_{movement}",
                        "begin": str(bin_start),
                        "end": str(bin_end),
                        "from": from_edge,
                        "to": to_edge,
                        "vehsPerHour": f"{vph:.2f}",
                        "departLane": depart_lane,
                        "departSpeed": depart_speed
                    })
            else:
                to_edge = turn_lookup.get((approach_id, default_movement))
                if not to_edge:
                    continue
                etree.SubElement(routes, "flow", attrib={
                    "id": f"flow_{approach_id}_{bin_start}_{default_movement}",
                    "begin": str(bin_start),
                    "end": str(bin_end),
                    "from": from_edge,
                    "to": to_edge,
                    "vehsPerHour": f"{vehs_per_hour:.2f}",
                    "departLane": depart_lane,
                    "departSpeed": depart_speed
                })

    outp = Path(out_xml_path)
    outp.parent.mkdir(parents=True, exist_ok=True)
    xml_bytes = etree.tostring(routes, pretty_print=True, xml_declaration=True, encoding="UTF-8")
    outp.write_bytes(xml_bytes)
    print(f"Saved flows.xml to {outp}")


if __name__ == "__main__":
    pass
     #generate_flows_xml(
     #  metrics_agg_csv="metrics/aggregated/metrics_aggregated.csv",
     #  turning_long_csv="metrics/aggregated/turning_counts_long.csv",
     #  mapping_path="sumo/mapping/mapping.json",
     #  out_xml_path="sumo/demand/flows.xml",
     #  agg_bin_sec=60
     #)
