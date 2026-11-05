"""
Generates a cinematic aerospace concept visual for CERTIS-DT.
Combines 3D CAD/FEA wireframe rendering, holographic stress gradients,
and aerospace airworthiness HUD elements.
"""

from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
import matplotlib.patches as patches

# Dark titanium aesthetic
fig = plt.figure(figsize=(16, 9), dpi=300)
fig.patch.set_facecolor("#070b14")

# Set up 3D axis in the center
ax = fig.add_axes([0.15, 0.08, 0.70, 0.84], projection="3d")
ax.set_facecolor("#070b14")
ax.grid(False)
ax.xaxis.pane.fill = False
ax.yaxis.pane.fill = False
ax.zaxis.pane.fill = False
ax.set_axis_off()

# Set isometric viewpoint
ax.view_init(elev=24, azim=-55)

# -------------------------------------------------------------
# 1. Physical UAV Geometry (Delta-wing + Boom Arm)
# -------------------------------------------------------------
# Fuselage & Wings (Delta platform)
fuselage_x = np.array([0.0, -1.8, -1.8, 0.0])
fuselage_y = np.array([0.0, -1.4, 1.4, 0.0])
fuselage_z = np.array([0.0, -0.05, -0.05, 0.0])

verts_wing = [list(zip(fuselage_x, fuselage_y, fuselage_z))]
poly_wing = Poly3DCollection(verts_wing, facecolor="#1e293b", edgecolor="#38bdf8", alpha=0.85, lw=1.5)
ax.add_collection3d(poly_wing)

# Carbon-composite boom arm spar (under active monitoring)
boom_x = np.linspace(-0.2, 1.6, 60)
boom_y_left = -0.5 * np.ones_like(boom_x)
boom_y_right = 0.5 * np.ones_like(boom_x)
boom_z = np.zeros_like(boom_x)

# High-fidelity FEA von Mises stress gradient along right boom arm (root high, tip low)
stress_vals = 350.0 * (1.0 - (boom_x + 0.2) / 1.8)**1.6 + 45.0
cmap = plt.get_cmap("turbo")
colors = cmap(stress_vals / 400.0)

for i in range(len(boom_x) - 1):
    ax.plot(
        boom_x[i:i+2], boom_y_right[i:i+2], boom_z[i:i+2],
        color=colors[i], lw=6.0, solid_capstyle="round"
    )
    # Left spar in cyan structural baseline
    ax.plot(
        boom_x[i:i+2], boom_y_left[i:i+2], boom_z[i:i+2],
        color="#0284c7", lw=4.5, alpha=0.7
    )

# FEA rib cross-sections along the sensorized boom arm
for x_station in [0.1, 0.4, 0.7, 1.0, 1.3]:
    dy = np.array([-0.06, 0.06, 0.06, -0.06, -0.06])
    dz = np.array([-0.05, -0.05, 0.05, 0.05, -0.05])
    ax.plot(np.full_like(dy, x_station), 0.5 + dy, dz, color="#f59e0b", lw=1.2, alpha=0.9)

# Strain gauge sensor station callouts (SG-01, SG-02, SG-03)
for sx, s_lbl in [(0.25, "SG-01"), (0.75, "SG-02"), (1.25, "SG-03")]:
    ax.scatter([sx], [0.5], [0.06], color="#facc15", s=90, edgecolor="#ffffff", lw=1.5, zorder=10)
    ax.text(sx, 0.55, 0.16, s_lbl, color="#facc15", fontsize=9, fontweight="bold")

# Propeller nacelles at boom tips
for nac_y in [-0.5, 0.5]:
    theta = np.linspace(0, 2*np.pi, 30)
    r = 0.35
    prop_x = 1.6 + 0.02 * np.cos(theta)
    prop_y = nac_y + r * np.sin(theta)
    prop_z = r * np.cos(theta)
    ax.plot(prop_x, prop_y, prop_z, color="#38bdf8", lw=1.2, ls="--", alpha=0.6)

# -------------------------------------------------------------
# 2. Virtual Twin Shadow (Offset in Z & Y, Holographic Wireframe)
# -------------------------------------------------------------
z_offset = 0.9
y_offset = -0.4
x_offset = -0.1

v_wing_x = fuselage_x + x_offset
v_wing_y = fuselage_y + y_offset
v_wing_z = fuselage_z + z_offset

poly_vwing = Poly3DCollection([list(zip(v_wing_x, v_wing_y, v_wing_z))],
                              facecolor="#064e3b", edgecolor="#10b981", alpha=0.35, lw=1.2)
ax.add_collection3d(poly_vwing)

# Bidirectional telemetry synchronization beams (Physical <-> Virtual)
for bx in [0.0, 0.6, 1.2]:
    ax.plot([bx, bx + x_offset], [0.5, 0.5 + y_offset], [0.0, z_offset],
            color="#10b981", lw=1.5, ls=":", alpha=0.8)

# Wingman drone in formation (Trailing port side)
wm_x = fuselage_x - 1.2
wm_y = fuselage_y - 2.0
wm_z = fuselage_z - 0.2
poly_wm = Poly3DCollection([list(zip(wm_x, wm_y, wm_z))], facecolor="#1e293b", edgecolor="#64748b", alpha=0.5, lw=1.0)
ax.add_collection3d(poly_wm)

# Wingman drone 2 (Trailing starboard side)
wm2_x = fuselage_x - 1.2
wm2_y = fuselage_y + 2.0
wm2_z = fuselage_z - 0.2
poly_wm2 = Poly3DCollection([list(zip(wm2_x, wm2_y, wm2_z))], facecolor="#1e293b", edgecolor="#64748b", alpha=0.5, lw=1.0)
ax.add_collection3d(poly_wm2)

ax.set_xlim(-2.5, 2.2)
ax.set_ylim(-2.5, 2.5)
ax.set_zlim(-0.8, 1.8)

# -------------------------------------------------------------
# 3. Aerospace Head-Up Display (HUD) Overlays
# -------------------------------------------------------------
# Top Header Banner
fig.text(0.06, 0.93, "CERTIS-DT", fontsize=24, fontweight="heavy", color="#ffffff", family="sans-serif")
fig.text(0.18, 0.935, "// DIGITAL TWIN AIRWORTHINESS TESTBED", fontsize=14, color="#38bdf8", family="sans-serif", weight="bold")
fig.text(0.06, 0.895, "INTELLIGENT STRUCTURAL-SWARM CO-VALIDATION ENVIRONMENT | TRL 5 FLIGHT-LOOP", fontsize=9.5, color="#94a3b8")

# Left HUD Telemetry Box
hud_left_text = (
    "--- LAYER 1: STRUCTURAL TWIN (SCT) ---\n"
    "AIRFRAME COMPONENT : CFRP Boom Spar (0.8m)\n"
    "ESTIMATION LOOP    : 100 Hz Continuous\n"
    "SURROGATE WCET     : 24.7 us (Limit: < 2000 us)\n"
    "MAX DYNAMIC STRESS : 162.4 MPa\n"
    "MARGIN OF SAFETY   : MS = +25.07 (FAR 23.303)\n"
    "EPISTEMIC METRIC   : D_M^2 = 2.14 (< 16.27)\n"
    "STATUS             : COMPLIANT / AIRWORTHY\n\n"
    "--- LAYER 2: SWARM STATE TWIN (SST) ---\n"
    "SWARM TOPOLOGY     : 3-UAV Tactical V-Shape\n"
    "SYNC DIVERGENCE    : 0.014 m RMSE (1.4 cm)\n"
    "IEEE SOTA REF      : 0.130 m (Surpassed by 9x)\n"
    "DATALINK LATENCY   : P95 = 30.0 ms (Markov Fading)\n"
    "AUTONOMY GOVERNOR  : SASA Dynamic Lead Election\n"
    "HOTL CONCURRENCE   : Active (EASA AI Level 2)"
)
fig.text(0.05, 0.50, hud_left_text, fontsize=9.0, family="monospace", color="#38bdf8",
         bbox=dict(boxstyle="square,pad=0.8", facecolor="#0b1329", edgecolor="#1e3a8a", lw=1.5, alpha=0.85))

# Right HUD Certification Box
hud_right_text = (
    "--- LAYER 3: AIRWORTHINESS GENERATOR ---\n"
    "STANDARDS TRACEABILITY:\n"
    " [>] ARP4754B      : System Safety DAL B\n"
    " [>] DO-178C       : Airborne Software WCET\n"
    " [>] EASA AI L2    : Explainability Gating\n"
    " [>] MIL-STD-1530D : ASIP Fatigue Monitoring\n\n"
    "GSN ASSURANCE DOCKET:\n"
    " - Top Goal G1     : [SATISFIED]\n"
    " - Goal G2_STRUCT  : [SATISFIED]\n"
    " - Goal G3_SYNC    : [SATISFIED]\n"
    " - Goal G4_AI_OOD  : [SATISFIED]\n\n"
    "ASSURANCE FORMATS  : SACM 2.0 JSON + Markdown\n"
    "READINESS LEVEL    : TRL 5 IN-THE-LOOP"
)
fig.text(0.74, 0.54, hud_right_text, fontsize=9.0, family="monospace", color="#10b981",
         bbox=dict(boxstyle="square,pad=0.8", facecolor="#062016", edgecolor="#059669", lw=1.5, alpha=0.85))

# Bottom Banner Callout
fig.text(0.50, 0.04, "https://github.com/Sm-bello/CERTIS-DT  |  Open-Source Aerospace Digital Twin Testbed",
         ha="center", fontsize=11, fontweight="bold", color="#f8fafc",
         bbox=dict(boxstyle="round,pad=0.5", facecolor="#1e293b", edgecolor="#38bdf8", lw=1.2))

# Save concept image
out_concept = Path("docs/assets/certis_dt_cinematic_concept.png")
out_concept.parent.mkdir(parents=True, exist_ok=True)
plt.savefig(out_concept, dpi=300, facecolor=fig.get_facecolor(), edgecolor="none")
plt.close(fig)
print(f"Cinematic concept visual generated: {out_concept.resolve()}")
