from flask import Flask, request, jsonify
from flask_cors import CORS
import numpy as np
from collections import defaultdict
import os

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

class UnionFind:
    def __init__(self):
        self.parent = {}
    def find(self, x):
        self.parent.setdefault(x, x)
        if self.parent[x] != x:
            self.parent[x] = self.find(self.parent[x])
        return self.parent[x]
    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[rb] = ra

def gather_terminal_key(cid, tid):
    return f"{cid}:{tid}"

def build_node_mapping(components, wires, ground_component_id):
    uf = UnionFind()
    for w in wires:
        s, e = w.get("start"), w.get("end")
        if not s or not e: continue
        uf.union(gather_terminal_key(s["componentId"], s["terminalId"]),
                 gather_terminal_key(e["componentId"], e["terminalId"]))

    for c in components:
        for t in c.get("terminals", []):
            uf.find(gather_terminal_key(c["id"], t["id"]))

    # Ground node detection
    ground_roots = set()
    if ground_component_id:
        gcomp = next((x for x in components if x["id"] == ground_component_id), None)
        if gcomp:
            for t in gcomp.get("terminals", []) or [{"id": 0}]:
                ground_roots.add(uf.find(gather_terminal_key(ground_component_id, t["id"])))

    # Node numbering
    root_to_node, next_node = {}, 1
    for k in uf.parent.keys():
        r = uf.find(k)
        if r not in root_to_node:
            root_to_node[r] = 0 if r in ground_roots else next_node
            if r not in ground_roots:
                next_node += 1

    term_to_node = {k: root_to_node[uf.find(k)] for k in uf.parent.keys()}
    return term_to_node, next_node


def generate_spice_netlist(components, term_to_node):
    netlist = []
    rc = cc = lc = vc = 1  # counters

    for comp in components:
        cid = comp["id"]
        ctype = comp["type"]
        value = comp.get("value", 0)

        # Ground / 1-terminal components → skip
        if len(comp["terminals"]) < 2:
            continue

        t0_key = f"{cid}:{comp['terminals'][0]['id']}"
        t1_key = f"{cid}:{comp['terminals'][1]['id']}"

        n1 = term_to_node[t0_key]
        n2 = term_to_node[t1_key]

        if ctype == "resistor":
            netlist.append(f"R{rc} {n1} {n2} {value}")
            rc += 1

        elif ctype == "capacitor":
            netlist.append(f"C{cc} {n1} {n2} {value}")
            cc += 1

        elif ctype == "inductor":
            netlist.append(f"L{lc} {n1} {n2} {value}")
            lc += 1

        elif ctype == "voltage_source":
            netlist.append(f"V{vc} {n1} {n2} {value}")
            vc += 1

    return netlist

import datetime
import os

def save_netlist_to_file(netlist_lines, folder="netlists"):
    # Create folder if missing
    os.makedirs(folder, exist_ok=True)
    filename = "output.txt"
    filepath = os.path.join(folder, filename)

    # Write to file
    with open(filepath, "w") as f:
        for line in netlist_lines:
            f.write(line + "\n")

    return filepath


@app.route("/simulate", methods=["POST"])
def simulate():
    data = request.get_json(force=True)
    components, wires = data.get("components", []), data.get("wires", [])
    ground_id = data.get("groundNodeId", None)

    if not components:
        return jsonify({"status": "error", "error": "No components provided."}), 400

    term_to_node, total_nodes = build_node_mapping(components, wires, ground_id)
    netlist = generate_spice_netlist(components, term_to_node)
    filepath = save_netlist_to_file(netlist)

    # PRINTS in the Python console
    print("------------ NETLIST ------------")
    for line in netlist:
        print(line)
    print("---------------------------------")

    return jsonify({
        "status": "success",
        "netlist_path": filepath,
        "line_count": len(netlist)
    })

# ------------------- Run for local debugging -------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)