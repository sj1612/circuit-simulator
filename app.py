from flask import Flask, request, jsonify
import numpy as np
from collections import defaultdict
import os

app = Flask(__name__)

# ------------------- Union-Find to group terminals into electrical nodes -------------------
class UnionFind:
    def __init__(self):
        self.parent = {}
    def find(self, x):
        self.parent.setdefault(x, x)
        if self.parent[x] != x:
            self.parent[x] = self.find(self.parent[x])
        return self.parent[x]
    def union(self, a, b):
        ra = self.find(a)
        rb = self.find(b)
        if ra == rb:
            return
        self.parent[rb] = ra

# ------------------- Helpers to build topology from frontend data -------------------
def gather_terminal_key(comp_id, term_id):
    return f"{comp_id}:{term_id}"

def build_node_mapping(components, wires, ground_component_id):
    uf = UnionFind()
    for w in wires:
        s, e = w.get("start"), w.get("end")
        if not s or not e:
            continue
        sk = gather_terminal_key(s["componentId"], s["terminalId"])
        ek = gather_terminal_key(e["componentId"], e["terminalId"])
        uf.union(sk, ek)

    for comp in components:
        cid = comp["id"]
        terms = comp.get("terminals", []) or [{"id": 0}, {"id": 1}]
        for t in terms:
            uf.find(gather_terminal_key(cid, t["id"]))

    ground_roots = set()
    if ground_component_id is not None:
        ground_comp = next((c for c in components if c["id"] == ground_component_id), None)
        if ground_comp:
            terms = ground_comp.get("terminals", []) or [{"id": 0}]
            for t in terms:
                ground_roots.add(uf.find(gather_terminal_key(ground_component_id, t["id"])))

    root_to_node, node_roots, next_node = {}, [], 1
    for key in list(uf.parent.keys()):
        root = uf.find(key)
        if root in root_to_node:
            continue
        if root in ground_roots:
            root_to_node[root] = 0
        else:
            root_to_node[root] = next_node
            next_node += 1
        node_roots.append(root)

    term_to_node = {key: root_to_node[uf.find(key)] for key in uf.parent.keys()}
    total_nodes = next_node
    return term_to_node, total_nodes, node_roots

# ------------------- MNA steady-state solver -------------------
def solve_steady_state(components, term_to_node, total_nodes, frequency=0.0):
    omega = 2 * np.pi * frequency
    n = total_nodes - 1
    v_sources = [c for c in components if c["type"].lower().startswith("v")]
    m_vs = len(v_sources)

    G = np.zeros((n, n), dtype=complex)
    B = np.zeros((m_vs, n), dtype=complex)
    E = np.zeros((m_vs,), dtype=complex)

    def reduced(node_idx): return None if node_idx == 0 else node_idx - 1

    vs_index_by_cid = {}
    for j, vs in enumerate(v_sources):
        vs_index_by_cid[vs["id"]] = j
        E[j] = vs["value"]

    for comp in components:
        ctype, cid = comp["type"].lower(), comp["id"]
        terms = comp.get("terminals", []) or [{"id": 0}, {"id": 1}]
        t0, t1 = gather_terminal_key(cid, terms[0]["id"]), gather_terminal_key(cid, terms[1]["id"])
        node_a, node_b = term_to_node.get(t0, 0), term_to_node.get(t1, 0)
        ra, rb = reduced(node_a), reduced(node_b)

        if ctype == "resistor":
            R = float(comp["value"])
            g = 1.0 / R if R != 0 else 1e12
        elif ctype == "capacitor":
            if frequency == 0: continue
            C = float(comp["value"])
            g = 1j * omega * C
        elif ctype == "inductor":
            L = float(comp["value"])
            g = 1e12 if frequency == 0 else (1 / (1j * omega * L) if L != 0 else 0)
        else:
            continue

        if ra is not None: G[ra, ra] += g
        if rb is not None: G[rb, rb] += g
        if ra is not None and rb is not None:
            G[ra, rb] -= g
            G[rb, ra] -= g

    for comp in v_sources:
        cid = comp["id"]
        terms = comp.get("terminals", []) or [{"id": 0}, {"id": 1}]
        t0, t1 = gather_terminal_key(cid, terms[0]["id"]), gather_terminal_key(cid, terms[1]["id"])
        node_a, node_b = term_to_node.get(t0, 0), term_to_node.get(t1, 0)
        ra, rb = reduced(node_a), reduced(node_b)
        j = vs_index_by_cid[cid]
        if ra is not None: B[j, ra] = 1.0
        if rb is not None: B[j, rb] = -1.0

    top = np.hstack((G, B.T))
    bottom = np.hstack((B, np.zeros((m_vs, m_vs), dtype=complex)))
    A = np.vstack((top, bottom))
    rhs = np.concatenate((np.zeros(n, dtype=complex), E))

    try:
        sol = np.linalg.solve(A, rhs)
    except np.linalg.LinAlgError as e:
        return {"error": f"Linear solve failed: {e}"}

    V_red, I_vs = sol[:n], sol[n:]
    node_voltages = [0.0] + [V_red[i] for i in range(len(V_red))]

    branches = []
    for comp in components:
        cid, ctype = comp["id"], comp["type"].lower()
        terms = comp.get("terminals", []) or [{"id": 0}, {"id": 1}]
        t0, t1 = gather_terminal_key(cid, terms[0]["id"]), gather_terminal_key(cid, terms[1]["id"])
        na, nb = term_to_node.get(t0, 0), term_to_node.get(t1, 0)
        Va, Vb, Vab = complex(node_voltages[na]), complex(node_voltages[nb]), complex(node_voltages[na] - node_voltages[nb])
        I = 0j
        if ctype == "resistor":
            I = Vab / float(comp["value"])
        elif ctype == "capacitor":
            I = (1j * omega * float(comp["value"]) * Vab) if frequency > 0 else 0
        elif ctype == "inductor":
            L = float(comp["value"])
            I = (Vab / (1j * omega * L)) if frequency > 0 else Vab * 1e12
        elif ctype.startswith("v"):
            I = I_vs[vs_index_by_cid[cid]]
        branches.append({"componentId": cid, "type": comp["type"], "voltage": Vab, "current": I})
    return {"nodes": node_voltages, "branches": branches}

# ------------------- Flask route -------------------
@app.route("/simulate", methods=["POST"])
def simulate():
    data = request.get_json(force=True)
    components, wires = data.get("components", []), data.get("wires", [])
    ground_id = data.get("groundNodeId", None)
    frequency = float(data.get("frequency", 0.0))

    if not components:
        return jsonify({"status": "error", "error": "No components provided."}), 400

    term_to_node, total_nodes, _ = build_node_mapping(components, wires, ground_id)
    result = solve_steady_state(components, term_to_node, total_nodes, frequency)

    if "error" in result:
        return jsonify({"status": "error", "error": result["error"]}), 400

    node_map = {str(i): float(round(abs(v), 12)) for i, v in enumerate(result["nodes"])}
    branches_out = [
        {
            "componentId": b["componentId"],
            "type": b["type"],
            "voltage": float(round(abs(b["voltage"]), 12)),
            "current": float(round(abs(b["current"]), 12)),
        }
        for b in result["branches"]
    ]

    return jsonify({"status": "success", "nodes": node_map, "branches": branches_out})

# ------------------- Run for local debugging -------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
