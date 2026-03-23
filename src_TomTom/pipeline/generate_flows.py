"""Generate SUMO flows.xml from TomTom flow data.

flows.xml defines vehicle demand using <flow> elements:
  <routes>
    <vType id="car" vClass="passenger"/>
    <flow id="f_0" type="car" begin="0" end="3600"
          from="edgeA" to="edgeB" vehsPerHour="120"
          departLane="best" departSpeed="max"/>
  </routes>

Vehicle counts are estimated from TomTom speed ratios
and road functional class (FRC) capacity tables.
"""
from pathlib import Path
from lxml import etree
import sumolib

# Approximate per-lane capacity (veh/h) by TomTom FRC
_FRC_CAP = {
    "FRC0": 2000, "FRC1": 1500, "FRC2": 1000,
    "FRC3": 800,  "FRC4": 600,  "FRC5": 400, "FRC6": 300,
}


def _estimate_vph(fd: dict) -> float:
    ffs = fd.get("freeFlowSpeed", 50)
    cs = fd.get("currentSpeed", ffs)
    if ffs <= 0:
        return 0.0
    ratio = cs / ffs
    if ratio > 0.9:
        usage = 0.30
    elif ratio > 0.7:
        usage = 0.55
    elif ratio > 0.4:
        usage = 0.80
    else:
        usage = 0.95
    cap = _FRC_CAP.get(fd.get("frc", "FRC3"), 600)
    return cap * usage


def _boundary_edges(net):
    """Return (entry_edges, exit_edges) at the network perimeter."""
    entries, exits = [], []
    for edge in net.getEdges():
        if edge.isSpecial():
            continue
        inc = [e for e in edge.getIncoming() if not e.isSpecial()]
        out = [e for e in edge.getOutgoing() if not e.isSpecial()]
        if not inc:
            entries.append(edge)
        if not out:
            exits.append(edge)
    return entries, exits


def generate_flows(flow_data: dict, net_path: Path, out_path: Path) -> None:
    net = sumolib.net.readNet(str(net_path))
    entries, exits = _boundary_edges(net)

    if not entries or not exits:
        print("  Warning: no boundary edges found, skipping flows.xml")
        etree.ElementTree(etree.Element("routes")).write(
            str(out_path), pretty_print=True,
            xml_declaration=True, encoding="UTF-8")
        return

    root = etree.Element("routes")
    etree.SubElement(root, "vType", id="car", vClass="passenger")

    fid = 0
    for entry in entries:
        eid = entry.getID()
        default_fd = {"freeFlowSpeed": 50, "currentSpeed": 40, "frc": "FRC3"}
        vph = _estimate_vph(flow_data.get(eid, default_fd))
        if vph < 10:
            continue

        # Try to route to each exit until we find a reachable one
        for ex in exits:
            if ex.getID() == eid:
                continue
            try:
                path, _ = net.getShortestPath(entry, ex)
                if path and len(path) >= 2:
                    distributed = vph / max(len(exits) // 3, 1)
                    if distributed < 5:
                        continue
                    el = etree.SubElement(root, "flow")
                    el.set("id", f"f_{fid}")
                    el.set("type", "car")
                    el.set("begin", "0")
                    el.set("end", "3600")
                    el.set("from", entry.getID())
                    el.set("to", ex.getID())
                    el.set("vehsPerHour", f"{distributed:.0f}")
                    el.set("departLane", "best")
                    el.set("departSpeed", "max")
                    fid += 1
                    break
            except Exception:
                continue

    tree = etree.ElementTree(root)
    tree.write(str(out_path), pretty_print=True,
               xml_declaration=True, encoding="UTF-8")
    print(f"  Saved: {out_path} ({fid} flows)")
