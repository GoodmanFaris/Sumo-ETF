"""Download OSM data for bbox and convert to SUMO network."""
import subprocess
import time
import urllib.request
import urllib.parse
from pathlib import Path

OVERPASS_URL = "https://overpass-api.de/api/interpreter"
MAX_RETRIES = 3


def _download_osm(bbox: dict, osm_path: Path) -> None:
    """Use Overpass QL with explicit timeout instead of /api/map."""
    query = (
        f'[out:xml][timeout:120];'
        f'('
        f'  way["highway"]'
        f'    ({bbox["min_lat"]},{bbox["min_lon"]},'
        f'     {bbox["max_lat"]},{bbox["max_lon"]});'
        f');'
        f'(._;>;);'
        f'out body;'
    )
    data = urllib.parse.urlencode({"data": query}).encode("utf-8")

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            print(f"  Downloading OSM data (attempt {attempt}/{MAX_RETRIES})...")
            req = urllib.request.Request(OVERPASS_URL, data=data)
            with urllib.request.urlopen(req, timeout=180) as resp:
                osm_path.write_bytes(resp.read())
            print(f"  Saved: {osm_path}")
            return
        except Exception as exc:
            print(f"  Attempt {attempt} failed: {exc}")
            if attempt < MAX_RETRIES:
                wait = 10 * attempt
                print(f"  Retrying in {wait}s...")
                time.sleep(wait)
    raise RuntimeError("Could not download OSM data after retries")


def fetch_network(bbox: dict, out_dir: Path) -> Path:
    """Download OSM and run netconvert -> .net.xml."""
    osm_path = out_dir / "osm_data.xml"
    net_path = out_dir / "network.net.xml"

    _download_osm(bbox, osm_path)

    # Find netconvert binary
    try:
        import sumolib
        netconvert = sumolib.checkBinary("netconvert")
    except Exception:
        netconvert = "netconvert"

    print(f"  Running netconvert...")
    cmd = [
        netconvert,
        "--osm-files", str(osm_path),
        "-o", str(net_path),
        "--geometry.remove",
        "--ramps.guess",
        "--junctions.join",
        "--tls.guess-signals",
        "--tls.discard-simple",
        "--tls.join",
        "--output.street-names",
        "--output.original-names",
        "--keep-edges.by-vclass", "passenger",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"  netconvert stderr:\n{result.stderr}")
        raise RuntimeError("netconvert failed")

    print(f"  Saved: {net_path}")
    return net_path
