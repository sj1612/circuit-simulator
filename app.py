# backend_simulator.py
from flask import Flask, request, jsonify
import numpy as np
from collections import defaultdict

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
        ra = self.find(a); rb = self.find(b)
        if ra == rb: return
        self.parent[rb] = ra

# ------------------- Helpers to build topology from frontend data -------------------
def gather_terminal_key(comp_id, term_id):
    # unique key for a terminal
    return f"{comp_id}:{term_id}"

def build_node_mapping(components, wires, ground_component_id):
    """
    Returns:
      terminal_root -> node_index (0 reserved for ground)
      node_count (including ground)
      mapping for each component terminal -> node index
      node_roots: list of root keys for nodes (for debugging)
    """
    uf = UnionFind()
    # union terminals connected by wires
    for w in wires:
        s = w.get("start"); e = w.get("end")
        if not s or not e: 
            continue
        sk = gather_terminal_key(s["componentId"], s["terminalId"])
        ek = gather_terminal_key(e["componentId"], e["terminalId"])
        uf.union(sk, ek)

    # Ensure each component's terminals exist in UF parent map
    for comp in components:
        cid = comp["id"]
        terms = comp.get("terminals", [])
        # If front-end didn't include terminals array, assume two terminals with ids 0 and 1
        if not terms:
            terms = [{"id":0},{"id":1}]
        for t in terms:
            key = gather_terminal_key(cid, t["id"])
            uf.find(key)

    # Find which UF root corresponds to ground (component's terminal 0)
    ground_roots = set()
    if ground_component_id is not None:
        # find any terminal of that component (assume id 0 if present)
        # locate terminals list for that component
        ground_comp = next((c for c in components if c["id"] == ground_component_id), None)
        if ground_comp:
            terms = ground_comp.get("terminals", [])
            if len(terms)==0:
                # assume single terminal id 0
                gr_key = gather_terminal_key(ground_component_id, 0)
                ground_roots.add(uf.find(gr_key))
            else:
                # mark all terminals of that ground component as ground
                for t in terms:
                    ground_roots.add(uf.find(gather_terminal_key(ground_component_id, t["id"])))
    # Map each root to a node index. Node 0 reserved for ground.
    root_to_node = {}
    node_roots = []
    next_node = 1  # 0 is ground
    for key in list(uf.parent.keys()):
        root = uf.find(key)
        if root in root_to_node:
            continue
        if root in ground_roots:
            root_to_node[root] = 0
            node_roots.append(root)
        else:
            root_to_node[root] = next_node
            node_roots.append(root)
            next_node += 1

    # Build mapping per terminal -> node index
    term_to_node = {}
    for key in list(uf.parent.keys()):
        root = uf.find(key)
        term_to_node[key] = root_to_node[root]

    total_nodes = next_node  # includes ground as 0
    return term_to_node, total_nodes, node_roots

# ------------------- MNA steady-state solver -------------------
def solve_steady_state(components, term_to_node, total_nodes, frequency=0.0):
    """
    Uses Modified Nodal Analysis to solve steady-state (DC or AC phasor).
    - components: list of components (dicts)
    - term_to_node: map terminal-key -> node index (0 is ground)
    - total_nodes: number of nodes including ground (node indices 0..total_nodes-1)
    - frequency: Hz (0 => DC)
    Returns:
      node_voltages (list length total_nodes): floats (DC) or complex (AC) ; node 0 is ground=0
      branch_results: list of dicts {componentId, type, voltage (complex), current (complex)}
    """
    omega = 2 * np.pi * frequency
    n = total_nodes - 1  # number of non-ground nodes
    # identify voltage sources count
    v_sources = [c for c in components if c["type"].lower().startswith("v")]
    m_vs = len(v_sources)

    # Build G (n x n) from resistors + admittances of L and C (if frequency>0)
    G = np.zeros((n, n), dtype=complex)
    # Build B (m x n)
    B = np.zeros((m_vs, n), dtype=complex)
    E = np.zeros((m_vs,), dtype=complex)

    # Helper to convert node index (global) -> reduced index (0..n-1) or None for ground
    def reduced(node_idx):
        return None if node_idx == 0 else (node_idx - 1)

    # Map voltage source ordering to component index
    vs_index_by_cid = {}
    for j, vs in enumerate(v_sources):
        vs_index_by_cid[vs["id"]] = j
        E[j] = vs["value"]

    # First stamp passive component admittances into G
    for comp in components:
        ctype = comp["type"].lower()
        cid = comp["id"]
        # determine node numbers for its terminals
        terms = comp.get("terminals", [])
        if not terms:
            terms = [{"id":0},{"id":1}]
        # we'll assume terminal 0 is positive (n1), terminal 1 is negative (n2)
        # but frontend also stores n1,n2 fields — prefer those if present
        if "n1" in comp and "n2" in comp:
            # front-end sometimes included n1/n2 earlier, but in your format we determine nodes from wires/term mapping
            # So ignore comp["n1"] here
            pass
        # get terminal keys (assume two terminals 0 & 1)
        t0 = gather_terminal_key(cid, terms[0]["id"])
        t1 = gather_terminal_key(cid, terms[1]["id"]) if len(terms)>1 else None
        node_a = term_to_node.get(t0, 0)
        node_b = term_to_node.get(t1, 0) if t1 else 0
        ra = reduced(node_a)
        rb = reduced(node_b)

        if ctype == "resistor" or ctype == "r":
            R = float(comp["value"])
            if R == 0:
                g = 1e12
            else:
                g = 1.0 / R
            # stamp into G
            if ra is not None:
                G[ra, ra] += g
            if rb is not None:
                G[rb, rb] += g
            if ra is not None and rb is not None:
                G[ra, rb] -= g
                G[rb, ra] -= g

        elif ctype == "capacitor" or ctype == "c":
            C = float(comp["value"])
            if frequency == 0:
                # DC: capacitor is open -> no stamp
                continue
            else:
                Y = 1j * omega * C
                if ra is not None:
                    G[ra, ra] += Y
                if rb is not None:
                    G[rb, rb] += Y
                if ra is not None and rb is not None:
                    G[ra, rb] -= Y
                    G[rb, ra] -= Y

        elif ctype == "inductor" or ctype == "l":
            L = float(comp["value"])
            if frequency == 0:
                # DC: inductor is short -> stamp very large conductance between nodes
                g = 1e12
                if ra is not None:
                    G[ra, ra] += g
                if rb is not None:
                    G[rb, rb] += g
                if ra is not None and rb is not None:
                    G[ra, rb] -= g
                    G[rb, ra] -= g
            else:
                Z = 1j * omega * L
                if Z == 0:
                    Y = 0
                else:
                    Y = 1.0 / Z
                if ra is not None:
                    G[ra, ra] += Y
                if rb is not None:
                    G[rb, rb] += Y
                if ra is not None and rb is not None:
                    G[ra, rb] -= Y
                    G[rb, ra] -= Y

        elif ctype.startswith("v"):  # voltage sources handled later in B
            pass
        else:
            # unknown component - ignore
            pass

    # Build B (m_vs x n) using voltage source terminals
    for comp in v_sources:
        cid = comp["id"]
        terms = comp.get("terminals", [])
        if not terms:
            terms = [{"id":0},{"id":1}]
        t0 = gather_terminal_key(cid, terms[0]["id"])
        t1 = gather_terminal_key(cid, terms[1]["id"]) if len(terms)>1 else None
        node_a = term_to_node.get(t0, 0)
        node_b = term_to_node.get(t1, 0) if t1 else 0
        ra = reduced(node_a)
        rb = reduced(node_b)
        j = vs_index_by_cid[cid]
        if ra is not None:
            B[j, ra] = 1.0
        if rb is not None:
            B[j, rb] = -1.0

    # Assemble augmented MNA matrix:
    # [ G    B^T ]
    # [ B    0   ]
    if n == 0 and m_vs == 0:
        return {"error":"No nodes found (only ground) or empty circuit."}
    top = np.hstack((G, B.T if m_vs>0 else np.zeros((n,0), dtype=complex)))
    bottom = np.hstack((B if m_vs>0 else np.zeros((0,n), dtype=complex),
                        np.zeros((m_vs,m_vs), dtype=complex)))
    A = np.vstack((top, bottom))
    # RHS: [0_n; E]
    rhs_top = np.zeros((n,), dtype=complex)
    rhs_bottom = E
    rhs = np.concatenate((rhs_top, rhs_bottom))
    # Solve
    try:
        sol = np.linalg.solve(A, rhs)
    except np.linalg.LinAlgError as e:
        return {"error": f"Linear solve failed: {e}"}
    V_red = sol[:n] if n>0 else np.array([], dtype=complex)
    I_vs = sol[n:] if m_vs>0 else np.array([], dtype=complex)

    # Build full node voltages (include ground = 0)
    node_voltages = [0.0] * total_nodes
    for root_node in range(1, total_nodes):
        idx = root_node - 1
        val = V_red[idx] if idx < len(V_red) else 0.0
        node_voltages[root_node] = val

    # Compute branch voltages and currents for each component
    branches = []
    for comp in components:
        cid = comp["id"]
        ctype = comp["type"].lower()
        terms = comp.get("terminals", [])
        if not terms:
            terms = [{"id":0},{"id":1}]
        t0 = gather_terminal_key(cid, terms[0]["id"])
        t1 = gather_terminal_key(cid, terms[1]["id"]) if len(terms)>1 else None
        na = term_to_node.get(t0, 0)
        nb = term_to_node.get(t1, 0) if t1 else 0
        Va = node_voltages[na]
        Vb = node_voltages[nb]
        # ensure we have complex numbers if freq>0
        V_a = complex(Va)
        V_b = complex(Vb)
        Vab = V_a - V_b

        I = 0+0j
        if ctype == "resistor" or ctype == "r":
            R = float(comp["value"])
            I = Vab / R
        elif ctype == "capacitor" or ctype == "c":
            C = float(comp["value"])
            if frequency == 0:
                I = 0+0j
            else:
                I = 1j * omega * C * Vab
        elif ctype == "inductor" or ctype == "l":
            L = float(comp["value"])
            if frequency == 0:
                # in DC we approximated inductor as short with large conductance; current is computed from node solution indirectly.
                # compute I from node voltages divided by small impedance -> approximate
                I = Vab * 1e12
            else:
                Z = 1j * omega * L
                I = Vab / Z if Z != 0 else 0+0j
        elif ctype.startswith("v"):
            # get its solved current variable
            j = vs_index_by_cid.get(cid, None)
            I = I_vs[j] if j is not None and j < len(I_vs) else 0+0j
            # sign convention: in MNA we used +1 at positive node and -1 at negative node,
            # and I_vs is the current flowing from positive terminal into the source (depends on assembly).
        else:
            I = 0+0j

        branches.append({
            "componentId": cid,
            "type": comp["type"],
            "voltage": Vab,
            "current": I
        })

    return {"nodes": node_voltages, "branches": branches}

# ------------------- Flask endpoint -------------------
@app.route("/simulate", methods=["POST"])
def simulate():
    """
    Accepts frontend JSON with 'components', 'wires', 'groundNodeId', optionally 'frequency'.
    Returns node voltages and per-component voltages/currents (steady-state).
    """
    data = request.get_json(force=True)
    components = data.get("components", [])
    wires = data.get("wires", [])
    ground_id = data.get("groundNodeId", None)
    frequency = float(data.get("frequency", 0.0))

    # Validate basic
    if len(components) == 0:
        return jsonify({"status":"error", "error":"No components provided."}), 400
    # Build node mapping
    term_to_node, total_nodes, node_roots = build_node_mapping(components, wires, ground_id)

    # Solve steady-state
    result = solve_steady_state(components, term_to_node, total_nodes, frequency=frequency)

    if "error" in result:
        return jsonify({"status":"error","error": result["error"]}), 400

    # Prepare response: convert complex to real/magnitude for frontend display
    node_map_out = {}
    for i, v in enumerate(result["nodes"]):
        if isinstance(v, complex):
            if abs(v.imag) < 1e-9:
                node_map_out[str(i)] = float(round(v.real, 12))
            else:
                # return magnitude for display
                node_map_out[str(i)] = float(round(abs(v), 12))
        else:
            node_map_out[str(i)] = float(round(v, 12))

    branches_out = []
    for b in result["branches"]:
        v = b["voltage"]
        i_ = b["current"]
        def to_num(z):
            if isinstance(z, complex):
                if abs(z.imag) < 1e-9:
                    return float(round(z.real, 12))
                else:
                    return float(round(abs(z), 12))
            else:
                return float(round(z, 12))
        branches_out.append({
            "componentId": b["componentId"],
            "type": b["type"],
            "voltage": to_num(v),
            "current": to_num(i_)
        })

    return jsonify({"status":"success","nodes": node_map_out, "branches": branches_out})

if __name__ == "__main__":
    # Run dev server
    app.run(host="127.0.0.1", port=5000, debug=True)
