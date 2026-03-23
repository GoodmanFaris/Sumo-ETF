"""Generate SUMO edgeData.xml from TomTom flow data.

edgeData.xml holds per-edge speed/travel-time measurements that SUMO
tools like routeSampler or cadyts can use for calibration.

Format:
  <data>
    <interval id="tomtom" begin="0.00" end="3600.00">
      <edge id="123" speed="12.50" traveltime="8.3" .../>
    </interval>
  </data>
"""
from pathlib import Path
from lxml import etree


def generate_edge_data(flow_data: dict, out_path: Path) -> None:
    root = etree.Element("data")
    interval = etree.SubElement(
        root, "interval", id="tomtom", begin="0.00", end="3600.00"
    )

    count = 0
    for edge_id, fd in flow_data.items():
        cs = fd.get("currentSpeed", 0)
        ffs = fd.get("freeFlowSpeed", 0)
        if cs <= 0 and ffs <= 0:
            continue

        el = etree.SubElement(interval, "edge")
        el.set("id", edge_id)
        el.set("speed", f"{cs / 3.6:.2f}")               # km/h -> m/s
        el.set("freeFlowSpeed", f"{ffs / 3.6:.2f}")
        el.set("traveltime", f"{fd.get('currentTravelTime', 0):.1f}")
        el.set("freeFlowTravelTime", f"{fd.get('freeFlowTravelTime', 0):.1f}")
        if fd.get("roadClosure"):
            el.set("roadClosure", "true")
        count += 1

    tree = etree.ElementTree(root)
    tree.write(str(out_path), pretty_print=True,
               xml_declaration=True, encoding="UTF-8")
    print(f"  Saved: {out_path} ({count} edges)")
