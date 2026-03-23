"""Fetch TomTom traffic flow and incident data for network edges."""
import json
import time
import urllib.request
import urllib.parse
from pathlib import Path

import sumolib

MAX_FLOW_QUERIES = 200
QUERY_DELAY = 0.12  # seconds between API calls

FLOW_URL = (
    "https://api.tomtom.com/traffic/services/4/"
    "flowSegmentData/absolute/10/{lat},{lon}/json"
)
INCIDENTS_URL = (
    "https://api.tomtom.com/traffic/services/5/incidentDetails"
)


def _get_json(url: str) -> dict:
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read())


def fetch_traffic(
    api_key: str, bbox: dict, net_path: Path, out_dir: Path
) -> tuple[dict, list]:
    """Query TomTom for flow on each network edge + incidents.

    Returns (flow_data, incidents).
    """
    net = sumolib.net.readNet(str(net_path))

    # Pick edges to sample (skip internal/short edges)
    candidates = [
        e for e in net.getEdges()
        if not e.isSpecial() and e.getLength() > 20
    ]
    # Prioritise longer (more important) roads
    candidates.sort(key=lambda e: e.getLength(), reverse=True)
    candidates = candidates[:MAX_FLOW_QUERIES]

    print(f"  Querying TomTom flow for {len(candidates)} road segments...")
    flow_data: dict = {}

    for i, edge in enumerate(candidates):
        shape = edge.getShape()
        mx, my = shape[len(shape) // 2]
        lon, lat = net.convertXY2LonLat(mx, my)

        url = FLOW_URL.format(lat=lat, lon=lon) + f"?key={api_key}&unit=KMPH"
        try:
            data = _get_json(url)
            fsd = data.get("flowSegmentData", {})
            flow_data[edge.getID()] = {
                "edge_id": edge.getID(),
                "lat": lat,
                "lon": lon,
                "frc": fsd.get("frc", "FRC3"),
                "currentSpeed": fsd.get("currentSpeed", 0),
                "freeFlowSpeed": fsd.get("freeFlowSpeed", 0),
                "currentTravelTime": fsd.get("currentTravelTime", 0),
                "freeFlowTravelTime": fsd.get("freeFlowTravelTime", 0),
                "confidence": fsd.get("confidence", 0),
                "roadClosure": fsd.get("roadClosure", False),
            }
        except Exception as exc:
            print(f"    Warning: edge {edge.getID()} failed: {exc}")

        if (i + 1) % 25 == 0:
            print(f"    {i + 1}/{len(candidates)} done")
        time.sleep(QUERY_DELAY)

    # --- Incidents --------------------------------------------------------
    print(f"  Fetching incidents...")
    bbox_str = (
        f"{bbox['min_lon']},{bbox['min_lat']},"
        f"{bbox['max_lon']},{bbox['max_lat']}"
    )
    fields = (
        "{incidents{type,geometry{coordinates},"
        "properties{iconCategory,magnitudeOfDelay,"
        "events{description,code},from,to,length,delay}}}"
    )
    inc_url = (
        f"{INCIDENTS_URL}?key={api_key}&bbox={bbox_str}"
        f"&fields={urllib.parse.quote(fields)}"
        f"&language=en-GB&timeValidityFilter=present"
    )

    incidents: list = []
    try:
        data = _get_json(inc_url)
        for inc in data.get("incidents", []):
            props = inc.get("properties", {})
            events = props.get("events", [])
            incidents.append({
                "type": inc.get("type", ""),
                "iconCategory": props.get("iconCategory", 0),
                "magnitudeOfDelay": props.get("magnitudeOfDelay", 0),
                "description": (
                    events[0].get("description", "") if events else ""
                ),
                "from": props.get("from", ""),
                "to": props.get("to", ""),
                "length": props.get("length", 0),
                "delay": props.get("delay", 0),
            })
        print(f"  Found {len(incidents)} incidents")
    except Exception as exc:
        print(f"  Warning: incidents query failed: {exc}")

    # Save raw JSON
    with open(out_dir / "flow_segments.json", "w", encoding="utf-8") as f:
        json.dump(flow_data, f, indent=2, ensure_ascii=False)
    with open(out_dir / "incidents.json", "w", encoding="utf-8") as f:
        json.dump(incidents, f, indent=2, ensure_ascii=False)

    print(f"  Got flow data for {len(flow_data)} edges")
    return flow_data, incidents
