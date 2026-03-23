"""Generate SUMO routes.xml with explicit edge-sequence routes.

routes.xml differs from flows.xml — it gives SUMO the full path
a vehicle takes rather than just origin/destination:

  <routes>
    <vType id="car" vClass="passenger"/>
    <route id="r_0" edges="e1 e2 e3 e4"/>
    <vehicle id="v_0" type="car" depart="0.00" route="r_0"/>
  </routes>

Routes are built as shortest paths between boundary edges,
weighted by TomTom-observed traffic volume.
"""
from pathlib import Path
from lxml import etree
import sumolib


_FRC_CAP = {
    "FRC0": 2000, "FRC1": 1500, "FRC2": 1000,
    "FRC3": 800,  "FRC4": 600,  "FRC5": 400, "FRC6": 300,
}


def _estimate_count(fd: dict, duration: int = 3600) -> int:
    """Estimate total vehicle count for the duration."""
    ffs = fd.get("freeFlowSpeed", 50)
    cs = fd.get("currentSpeed", ffs)
    if ffs <= 0:
        return 0
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
    return int(cap * usage * duration / 3600)


def generate_routes(
    flow_data: dict, net_path: Path, out_path: Path
) -> None:
    net = sumolib.net.readNet(str(net_path))

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

    if not entries or not exits:
        print("  Warning: no boundary edges, writing empty routes.xml")
        etree.ElementTree(etree.Element("routes")).write(
            str(out_path), pretty_print=True,
            xml_declaration=True, encoding="UTF-8")
        return

    root = etree.Element("routes")
    etree.SubElement(root, "vType", id="car", vClass="passenger")

    rid = 0
    vid = 0
    default_fd = {"freeFlowSpeed": 50, "currentSpeed": 40, "frc": "FRC3"}

    for entry in entries:
        fd = flow_data.get(entry.getID(), default_fd)
        count = _estimate_count(fd)
        if count < 1:
            continue

        # Find a reachable exit
        for ex in exits:
            if ex.getID() == entry.getID():
                continue
            try:
                path, _ = net.getShortestPath(entry, ex)
            except Exception:
                continue
            if not path or len(path) < 2:
                continue

            edge_ids = " ".join(e.getID() for e in path)
            route_id = f"r_{rid}"
            etree.SubElement(root, "route", id=route_id, edges=edge_ids)

            # Spread vehicles evenly over the hour
            n_vehs = max(count // max(len(exits) // 3, 1), 1)
            n_vehs = min(n_vehs, 200)  # cap per route
            interval = 3600.0 / n_vehs if n_vehs else 3600
            for k in range(n_vehs):
                etree.SubElement(root, "vehicle",
                                 id=f"v_{vid}",
                                 type="car",
                                 depart=f"{k * interval:.2f}",
                                 route=route_id)
                vid += 1

            rid += 1
            break  # one route per entry edge

    tree = etree.ElementTree(root)
    tree.write(str(out_path), pretty_print=True,
               xml_declaration=True, encoding="UTF-8")
    print(f"  Saved: {out_path} ({rid} routes, {vid} vehicles)")
