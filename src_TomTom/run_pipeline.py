"""TomTom Traffic -> SUMO pipeline.

Usage:
    python src_TomTom/run_pipeline.py

Requires TOMTOM_API_KEY in .env at project root.
Asks for a bounding box, fetches live traffic data,
and produces SUMO-ready XML files.
"""
import os
import sys
from pathlib import Path

# --------------- paths ---------------
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src_TomTom"))

from pipeline.fetch_network import fetch_network          # noqa: E402
from pipeline.fetch_traffic import fetch_traffic           # noqa: E402
from pipeline.generate_edge_data import generate_edge_data # noqa: E402
from pipeline.generate_flows import generate_flows         # noqa: E402
from pipeline.generate_routes import generate_routes       # noqa: E402
from pipeline.generate_additional import generate_additional  # noqa: E402


def _load_api_key() -> str:
    """Read TOMTOM_API_KEY from .env (simple key=value parser)."""
    env_path = ROOT / ".env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())

    key = os.environ.get("TOMTOM_API_KEY", "")
    if not key:
        print("Error: TOMTOM_API_KEY not found.")
        print("Add it to .env in project root:  TOMTOM_API_KEY=your_key_here")
        sys.exit(1)
    return key


def _ask_bbox() -> dict:
    print("Enter bounding box as:  minLat,minLon,maxLat,maxLon")
    print("Example (Sarajevo centar): 43.855,18.405,43.865,18.425")
    raw = input("bbox> ").strip()
    parts = [float(x) for x in raw.replace(" ", "").split(",")]
    if len(parts) != 4:
        print("Error: expected exactly 4 comma-separated numbers")
        sys.exit(1)
    min_lat, min_lon, max_lat, max_lon = parts
    return {
        "min_lat": min_lat, "min_lon": min_lon,
        "max_lat": max_lat, "max_lon": max_lon,
    }


def main() -> None:
    api_key = _load_api_key()
    bbox = _ask_bbox()

    # Output directories
    out = ROOT / "tomtom_output"
    raw_dir = out / "raw"
    net_dir = out / "network"
    sumo_dir = out / "sumo"
    for d in (raw_dir, net_dir, sumo_dir):
        d.mkdir(parents=True, exist_ok=True)

    # 1 - road network
    print("\n[1/6] Fetching road network from OSM...")
    net_path = fetch_network(bbox, net_dir)

    # 2 - TomTom traffic
    print("\n[2/6] Fetching TomTom traffic data...")
    flow_data, incidents = fetch_traffic(api_key, bbox, net_path, raw_dir)

    # 3 - edgeData.xml
    print("\n[3/6] Generating edgeData.xml...")
    generate_edge_data(flow_data, sumo_dir / "edgeData.xml")

    # 4 - flows.xml
    print("\n[4/6] Generating flows.xml...")
    generate_flows(flow_data, net_path, sumo_dir / "flows.xml")

    # 5 - routes.xml
    print("\n[5/6] Generating routes.xml...")
    generate_routes(flow_data, net_path, sumo_dir / "routes.xml")

    # 6 - additional.xml
    print("\n[6/6] Generating additional.xml (detectors)...")
    generate_additional(flow_data, net_path, sumo_dir / "additional.xml")

    # Summary
    print("\n" + "=" * 50)
    print("Pipeline complete!")
    print(f"  Network:    {net_dir}")
    print(f"  Raw data:   {raw_dir}")
    print(f"  SUMO files: {sumo_dir}")
    print(f"    - edgeData.xml    (speed/traveltime per edge)")
    print(f"    - flows.xml       (vehicle demand, from/to)")
    print(f"    - routes.xml      (explicit edge-sequence routes)")
    print(f"    - additional.xml  (induction loop detectors)")
    if incidents:
        print(f"  Incidents:  {len(incidents)} saved to raw/incidents.json")


if __name__ == "__main__":
    main()
