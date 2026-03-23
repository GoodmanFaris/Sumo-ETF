"""Generate SUMO additional.xml with induction-loop detectors.

Places an inductionLoop detector at the midpoint of every edge
for which we have TomTom flow data, so SUMO can output
measurements comparable to the real-world TomTom readings.

  <additional>
    <inductionLoop id="det_edgeA" lane="edgeA_0"
                   pos="50.0" period="300" file="det_output.xml"/>
  </additional>
"""
from pathlib import Path
from lxml import etree
import sumolib


def generate_additional(
    flow_data: dict, net_path: Path, out_path: Path
) -> None:
    net = sumolib.net.readNet(str(net_path))

    root = etree.Element("additional")
    count = 0

    for edge_id in flow_data:
        try:
            edge = net.getEdge(edge_id)
        except KeyError:
            continue

        lanes = edge.getLanes()
        if not lanes:
            continue

        lane = lanes[0]
        pos = edge.getLength() / 2.0
        if pos < 1.0:
            continue

        etree.SubElement(root, "inductionLoop",
                         id=f"det_{edge_id}",
                         lane=lane.getID(),
                         pos=f"{pos:.2f}",
                         period="300",
                         file="det_output.xml")
        count += 1

    tree = etree.ElementTree(root)
    tree.write(str(out_path), pretty_print=True,
               xml_declaration=True, encoding="UTF-8")
    print(f"  Saved: {out_path} ({count} detectors)")
