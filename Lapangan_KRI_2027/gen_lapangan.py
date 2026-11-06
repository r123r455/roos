#!/usr/bin/env python3
"""
Generator world Gazebo (gz sim) - ABU Robocon 2027 "The Pursuit of Mustika Nusantara"
Semua satuan meter. Sumber ukuran & warna: Rulebook v1.0 (Sec. 2, 3, 4.1, 14).
Frame: x+ = sisi Biru, x- = sisi Merah, y+ = sisi Storage/Mustika Pillar, y- = sisi Start Zone/Shared Grid
(sama dengan Figure 3 pada rulebook).
"""
import math

# ======================= PARAMETER DARI RULEBOOK =======================
F = 11.0; H = F / 2                       # Game Field 11000 x 11000
L1 = 6.0; L1_H = 0.60                     # Level 1: 6000 x 6000, tinggi 600
L2 = 3.0; L2_H = 0.30                     # Level 2: 3000 x 3000, +300 dari L1
RAMP_LEN, LANE_W, TRANSFER = 3.5, 1.0, 1.0   # ramp 3500, lebar 1000, Transfer Area 1000x1000
NSTEP, STEP_D, STEP_H = 3, 0.30, 0.15     # anak tangga 300 (panjang) x 1000 (lebar) x 150 (tinggi)
GAP = L1 - RAMP_LEN - TRANSFER - NSTEP * STEP_D   # = 0.6 (label "600 mm")
BLD = 0.5                                 # Building Spot 500 x 500
PILLAR_D, RECEPT_D, RECEPT_DEPTH = 0.27, 0.18, 0.10
MUSTIKA_PILLAR_H, CENTRAL_PILLAR_H = 0.50, 0.80
EARTH, SKY, MUSTIKA_R = 0.35, 0.20, 0.105

# ======================= ASUMSI (tidak tertulis di rulebook) =======================
FIELD_WALL_H, FIELD_WALL_T = 0.10, 0.05   # dinding batas lapangan
DIVIDER_H, DIVIDER_T = 0.10, 0.02         # Center Divider Fence
BARRIER_H, BARRIER_T = 0.05, 0.02         # L1 Perimeter Barrier (0 = tanpa barrier)
INCLUDE_OBJECTS = True                    # Earth Block, Sky Block, Mustika
STORAGE_FOLLOW_TABLE = False              # False: Storage merah/biru terang seperti Figure 1-3
                                          # True : warna sama dengan Ground (sesuai tabel Sec. 14)

def c(r, g, b): return (round(r / 255, 3), round(g / 255, 3), round(b / 255, 3))
# Warna (Sec. 14)
GROUND_R, GROUND_B, SHARED = c(240,210,210), c(170,210,230), c(245,240,200)
START_R, START_B = c(223,34,34), c(50,0,255)
STAIR_R, STAIR_B = c(235,180,160), c(150,215,220)
RAMP_R, RAMP_B = c(200,150,140), c(130,180,200)
L1_R, L1_B = c(235,180,160), c(150,215,220)
SPOT = c(40,100,50)
TRANS_R, TRANS_B = c(245,170,60), c(60,170,245)
GRAY, BROWN = c(190,190,185), c(100,62,0)

prims = []
def box(name, x, y, z, sx, sy, sz, col, rpy=(0, 0, 0), collide=True):
    prims.append(dict(k='box', n=name, p=(x, y, z) + tuple(rpy), s=(sx, sy, sz), c=col, col=collide))
def cyl(name, x, y, z, r, h, col, collide=True):
    prims.append(dict(k='cyl', n=name, p=(x, y, z, 0, 0, 0), s=(r, h), c=col, col=collide))
T = 0.001
def patch(name, x, y, zb, sx, sy, col, layer=1):
    """Lapisan warna tipis (visual saja) di atas permukaan setinggi zb."""
    box(name, x, y, zb + (layer - 0.5) * T, sx, sy, T, col, collide=False)

def pillar(name, x, y, z0, h):
    """Tiang silinder dia 270 mm dengan cekungan (dia 180, dalam 100) di puncak."""
    body = h - RECEPT_DEPTH
    cyl(f"{name}_body", x, y, z0 + body / 2, PILLAR_D / 2, body, BROWN)
    n = 24; rm = (PILLAR_D + RECEPT_D) / 4; t = (PILLAR_D - RECEPT_D) / 2
    seg = 2 * (PILLAR_D / 2) * math.tan(math.pi / n) * 1.05
    for i in range(n):
        a = 2 * math.pi * i / n
        box(f"{name}_ring{i}", x + rm * math.cos(a), y + rm * math.sin(a),
            z0 + h - RECEPT_DEPTH / 2, t, seg, RECEPT_DEPTH, BROWN, rpy=(0, 0, a))

# ======================= GROUND LEVEL =======================
box("ground_red", -H / 2, 0, -0.01, H, F, 0.02, GROUND_R)
box("ground_blue", H / 2, 0, -0.01, H, F, 0.02, GROUND_B)

wt, wh = FIELD_WALL_T, FIELD_WALL_H
box("wall_n", 0,  H + wt / 2, wh / 2, F + 2 * wt, wt, wh, BROWN)
box("wall_s", 0, -H - wt / 2, wh / 2, F + 2 * wt, wt, wh, BROWN)
box("wall_e",  H + wt / 2, 0, wh / 2, wt, F, wh, BROWN)
box("wall_w", -H - wt / 2, 0, wh / 2, wt, F, wh, BROWN)

# Storage Area 1000 x 2000 (pojok atas kiri/kanan)
patch("storage_red",  -H + 1.0, H - 0.5, 0, 2.0, 1.0, GROUND_R if STORAGE_FOLLOW_TABLE else START_R)
patch("storage_blue",  H - 1.0, H - 0.5, 0, 2.0, 1.0, GROUND_B if STORAGE_FOLLOW_TABLE else START_B)

# Start Zone / Retry Zone: 2 kotak 700 x 700 per tim (pojok bawah)
for side, col, tg in ((-1, START_R, 'r'), (1, START_B, 'b')):
    for j, xo in enumerate((0.35, 1.10)):
        patch(f"start_{tg}{j+1}", side * (H - xo), -H + 0.35, 0, 0.7, 0.7, col)

# Mustika Pillar + area bersama 1000 x 1000 (tengah, antara L1 dan tepi atas)
YM = L1 / 2 + (H - L1 / 2) / 2            # = 4.25  -> jarak 750 mm ke L1 dan ke tepi
patch("mustika_pad", 0, YM, 0, 1.0, 1.0, SHARED)
pillar("mustika_pillar", 0, YM, 0, MUSTIKA_PILLAR_H)

# Ground Shared Area 1200 x 1200, grid 5x5 sel 200 mm (jarak 650 mm ke L1 dan ke tepi)
YS = -YM
patch("shared_pad", 0, YS, 0, 1.2, 1.2, SHARED)
for r in range(1, 6):
    for cc in range(1, 6):
        if (r, cc) == (3, 3):   col = BROWN
        elif (r + cc) % 2 == 0: col = c(228, 222, 180)
        else:                   col = c(250, 247, 225)
        patch(f"grid_{r}{cc}", (cc - 3) * SKY, YS + (3 - r) * SKY, 0, SKY, SKY, col, layer=2)

# ======================= LEVEL 1 =======================
box("L1", 0, 0, L1_H / 2, L1, L1, L1_H, GRAY)            # sisi = L1 Side Wall
patch("L1_top_red",  -L1 / 4, 0, L1_H, L1 / 2, L1, L1_R)
patch("L1_top_blue",  L1 / 4, 0, L1_H, L1 / 2, L1, L1_B)
for sx in (-1, 1):
    for sy in (-1, 1):   # 4 Building Spot eksklusif di sudut L1
        patch(f"L1_spot_{'r' if sx<0 else 'b'}{'n' if sy>0 else 's'}",
              sx * (L1 / 2 - BLD / 2), sy * (L1 / 2 - BLD / 2), L1_H, BLD, BLD, SPOT, layer=2)
for sy, tg in ((1, 'n'), (-1, 's')):   # L1 Shared Area + Building Spot di garis tengah
    patch(f"L1_shared_pad_{tg}", 0, sy * (L1 / 2 - 0.5), L1_H, 1.0, 1.0, SHARED, layer=2)
    patch(f"L1_shared_spot_{tg}", 0, sy * (L1 / 2 - BLD / 2), L1_H, BLD, BLD, SPOT, layer=3)
patch("L1_retry_red",  -1.85, L1 / 2 - 0.35, L1_H, 0.7, 0.7, START_R, layer=2)
patch("L1_retry_blue",  1.85, L1 / 2 - 0.35, L1_H, 0.7, 0.7, START_B, layer=2)

# ======================= LEVEL 2 =======================
box("L2", 0, 0, L1_H + L2_H / 2, L2, L2, L2_H, GRAY)      # top & sisi abu-abu
for sx in (-1, 1):
    for sy in (-1, 1):
        patch(f"L2_spot_{'r' if sx<0 else 'b'}{'n' if sy>0 else 's'}",
              sx * (L2 / 2 - BLD / 2), sy * (L2 / 2 - BLD / 2), L1_H + L2_H, BLD, BLD, SPOT)
pillar("central_pillar", 0, 0, L1_H + L2_H, CENTRAL_PILLAR_H)
box("L2_step_red", -(L2 / 2 + 0.15), 0, L1_H + STEP_H / 2, 0.30, 1.0, STEP_H, STAIR_R)
box("L2_step_blue", (L2 / 2 + 0.15), 0, L1_H + STEP_H / 2, 0.30, 1.0, STEP_H, STAIR_B)

# ======================= JALUR LINTASAN (searah dinding, sumbu y) =======================
# Dari tepi atas L1: celah 600 -> RAMP 3500 (naik) -> TRANSFER AREA 1000 (datar, setinggi L1)
#                    -> TANGGA 3 x 300 (turun) sampai tepi bawah L1.
def lane(tag, side, c_ramp, c_stair, c_trans):
    xc = side * (L1 / 2 + LANE_W / 2)
    y_lo = L1 / 2 - GAP                    # ujung rendah ramp
    y_hi = y_lo - RAMP_LEN                 # ujung tinggi ramp = awal Transfer Area
    th = math.atan2(L1_H, RAMP_LEN); Ls = math.hypot(RAMP_LEN, L1_H); t = 0.10
    box(f"{tag}_ramp", xc, (y_lo + y_hi) / 2 - t / 2 * math.sin(th), L1_H / 2 - t / 2 * math.cos(th),
        LANE_W, Ls, t, c_ramp, rpy=(-th, 0, 0))
    seg = 0.1                               # isi di bawah ramp (visual saja)
    for k in range(int(round(RAMP_LEN / seg))):
        h = L1_H * (k + 0.5) * seg / RAMP_LEN - 0.09
        if h > 0.01:
            box(f"{tag}_fill{k}", xc, y_lo - (k + 0.5) * seg, h / 2, LANE_W, seg, h, c_ramp, collide=False)
    yt = y_hi - TRANSFER / 2
    box(f"{tag}_transfer_base", xc, yt, L1_H / 2, LANE_W, TRANSFER, L1_H, c_stair)
    patch(f"{tag}_transfer", xc, yt, L1_H, LANE_W, TRANSFER, c_trans)
    for i in range(NSTEP):
        h = L1_H - (i + 1) * STEP_H
        box(f"{tag}_step{i+1}", xc, y_hi - TRANSFER - STEP_D * (i + 0.5), h / 2, LANE_W, STEP_D, h, c_stair)

lane("red", -1, RAMP_R, STAIR_R, TRANS_R)
lane("blue", +1, RAMP_B, STAIR_B, TRANS_B)

# ======================= PAGAR / BARRIER =======================
# L1 Perimeter Barrier (dengan bukaan 1000 mm di Transfer Area agar BR bisa masuk ke L1)
if BARRIER_H > 0:
    zc, o = L1_H + BARRIER_H / 2, L1 / 2 - BARRIER_T / 2
    y_hi = L1 / 2 - GAP - RAMP_LEN
    box("L1_barrier_n", 0,  o, zc, L1, BARRIER_T, BARRIER_H, GRAY)
    box("L1_barrier_s", 0, -o, zc, L1, BARRIER_T, BARRIER_H, GRAY)
    for side, tg in ((-1, 'r'), (1, 'b')):
        a0, a1 = y_hi, L1 / 2
        b0, b1 = -L1 / 2, y_hi - TRANSFER
        box(f"L1_barrier_{tg}_a", side * o, (a0 + a1) / 2, zc, BARRIER_T, a1 - a0, BARRIER_H, GRAY)
        box(f"L1_barrier_{tg}_b", side * o, (b0 + b1) / 2, zc, BARRIER_T, b1 - b0, BARRIER_H, GRAY)

# Center Divider Fence (x=0). Terputus di area bersama agar kedua tim bisa mengaksesnya.
def divider(name, y0, y1, z0):
    box(name, 0, (y0 + y1) / 2, z0 + DIVIDER_H / 2, DIVIDER_T, y1 - y0, DIVIDER_H, BROWN)
divider("div_g1", YM + 0.5, H, 0)
divider("div_g2", L1 / 2, YM - 0.5, 0)
divider("div_g3", -(L1 / 2) - 0.0 - (YM - 0.5 - L1 / 2), -L1 / 2, 0)   # [-3.75, -3.0]
divider("div_g4", -H, YS - 0.6, 0)
divider("div_l1a", L2 / 2, L1 / 2 - 1.0, L1_H)
divider("div_l1b", -(L1 / 2 - 1.0), -L2 / 2, L1_H)

# ======================= GAME OBJECTS (dinamis) =======================
objs = []; preview_objs = []
def friction(mu): return f"<surface><friction><ode><mu>{mu}</mu><mu2>{mu}</mu2></ode></friction></surface>"
def mat(col): return f"<material><ambient>{col[0]} {col[1]} {col[2]} 1</ambient><diffuse>{col[0]} {col[1]} {col[2]} 1</diffuse></material>"

def cube(name, x, y, z, s, mass, col, extra=""):
    I = mass * s * s / 6
    return f"""
  <model name="{name}"><pose>{x:.4f} {y:.4f} {z:.4f} 0 0 0</pose>
    <link name="link">
      <inertial><mass>{mass}</mass><inertia><ixx>{I:.6f}</ixx><iyy>{I:.6f}</iyy><izz>{I:.6f}</izz></inertia></inertial>
      <collision name="c"><geometry><box><size>{s} {s} {s}</size></box></geometry>{friction(0.7)}</collision>
      <visual name="v"><geometry><box><size>{s} {s} {s}</size></box></geometry>{mat(col)}</visual>{extra}
    </link>
  </model>"""

if INCLUDE_OBJECTS:
    # 20 Earth Block per tim: 10 kolom (5 x 2) x tinggi 2 di dalam Storage Area
    for side, col, tg in ((-1, START_R, 'red'), (1, START_B, 'blue')):
        k = 0
        for i in range(5):
            for yy in (4.8, 5.2):
                x = side * (H - 0.1 - EARTH / 2 - i * 0.38)
                for lv in range(2):
                    k += 1
                    z = EARTH / 2 + 0.002 + lv * (EARTH + 0.002)
                    objs.append(cube(f"earth_{tg}_{k:02d}", x, yy, z, EARTH, 0.6, col))
                    preview_objs.append(('sq', x, yy, EARTH, col, z))
    # 12 Sky Block (pola catur 5x5, titik tengah kosong). Sisi merah & biru berhadapan; sisi lain netral.
    SKYMAP = {(1,1):('y',1),(1,3):('y',1),(1,5):('y',-1),(2,2):('x',1),(2,4):('x',-1),(3,1):('y',-1),
              (3,5):('y',1),(4,2):('x',-1),(4,4):('x',1),(5,1):('y',1),(5,3):('y',-1),(5,5):('y',-1)}
    neutral = c(230, 222, 190); e = 0.002
    for (r, cc), (ax, sg) in SKYMAP.items():
        x, y = (cc - 3) * SKY, YS + (3 - r) * SKY
        def half(nm, col, s):
            e = 0.002; L = SKY + 2 * e; d = SKY / 2 + e   # sedikit lebih besar agar menutupi kubus dasar
            o = s * (SKY / 4 + e / 2)
            if ax == 'y':
                return f'<visual name="{nm}"><pose>0 {o} 0 0 0 0</pose><geometry><box><size>{L} {d} {L}</size></box></geometry>{mat(col)}</visual>'
            return f'<visual name="{nm}"><pose>{o} 0 0 0 0 0</pose><geometry><box><size>{d} {L} {L}</size></box></geometry>{mat(col)}</visual>'
        extra = half("red_half", START_R, sg) + half("blue_half", START_B, -sg)
        objs.append(cube(f"sky_{r}{cc}", x, y, SKY / 2 + 0.002, SKY, 0.22, neutral, extra))
        preview_objs.append(('sky', x, y, SKY, (ax, sg), SKY / 2))
    # Mustika (bola voli, dia 210 mm) di atas Mustika Pillar
    m, rr = 0.27, MUSTIKA_R
    I = 2.0 / 3.0 * m * rr * rr
    zb = MUSTIKA_PILLAR_H + math.sqrt(rr**2 - (RECEPT_D / 2)**2) + 0.002
    objs.append(f"""
  <model name="mustika"><pose>0 {YM} {zb:.4f} 0 0 0</pose>
    <link name="link">
      <inertial><mass>{m}</mass><inertia><ixx>{I:.6f}</ixx><iyy>{I:.6f}</iyy><izz>{I:.6f}</izz></inertia></inertial>
      <collision name="c"><geometry><sphere><radius>{rr}</radius></sphere></geometry>{friction(0.6)}</collision>
      <visual name="v"><geometry><sphere><radius>{rr}</radius></sphere></geometry>{mat(c(240,200,30))}</visual>
    </link>
  </model>""")
    preview_objs.append(('ball', 0, YM, rr, c(240,200,30), zb))

# ======================= TULIS SDF =======================
SURF = friction(1.0)
def xml_prim(p):
    x, y, z, r, pi, yw = p['p']
    pose = f"<pose>{x:.4f} {y:.4f} {z:.4f} {r:.5f} {pi:.5f} {yw:.5f}</pose>"
    g = (f"<box><size>{p['s'][0]:.4f} {p['s'][1]:.4f} {p['s'][2]:.4f}</size></box>" if p['k'] == 'box'
         else f"<cylinder><radius>{p['s'][0]:.4f}</radius><length>{p['s'][1]:.4f}</length></cylinder>")
    col = f'<collision name="{p["n"]}_c">{pose}<geometry>{g}</geometry>{SURF}</collision>' if p['col'] else ""
    return f'      {col}<visual name="{p["n"]}_v">{pose}<geometry>{g}</geometry>{mat(p["c"])}</visual>\n'

body = "".join(xml_prim(p) for p in prims)
sdf = f"""<?xml version="1.0"?>
<!-- ABU Robocon 2027 - The Pursuit of Mustika Nusantara (dibuat oleh gen_lapangan.py) -->
<sdf version="1.9">
  <world name="robocon2027">
    <physics name="1ms" type="ignored"><max_step_size>0.001</max_step_size><real_time_factor>1.0</real_time_factor></physics>
    <plugin filename="gz-sim-physics-system" name="gz::sim::systems::Physics"/>
    <plugin filename="gz-sim-user-commands-system" name="gz::sim::systems::UserCommands"/>
    <plugin filename="gz-sim-scene-broadcaster-system" name="gz::sim::systems::SceneBroadcaster"/>
    <gravity>0 0 -9.8</gravity>
    <scene><ambient>0.55 0.55 0.55 1</ambient><background>0.8 0.8 0.8 1</background><shadows>true</shadows></scene>
    <light type="directional" name="sun">
      <cast_shadows>true</cast_shadows><pose>0 0 10 0 0 0</pose>
      <diffuse>0.8 0.8 0.8 1</diffuse><specular>0.2 0.2 0.2 1</specular>
      <direction>-0.4 0.3 -0.9</direction>
    </light>
    <model name="lapangan">
      <static>true</static>
      <link name="field">
{body}      </link>
    </model>{"".join(objs)}
  </world>
</sdf>
"""
open("lapangan.world", "w").write(sdf)

# ======================= PREVIEW TOP-DOWN =======================
try:
    import matplotlib; matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Rectangle, Circle
    from matplotlib.transforms import Affine2D
    fig, ax = plt.subplots(figsize=(9, 9)); ax.set_aspect('equal')
    for p in sorted(prims, key=lambda q: q['p'][2] + (q['s'][2] if q['k'] == 'box' else q['s'][1]) / 2):
        x, y, z, r, pi, yw = p['p']
        if p['k'] == 'box':
            sx, sy = p['s'][0], p['s'][1] * (math.cos(r) if abs(r) > 1e-6 else 1)
            rect = Rectangle((x - sx / 2, y - sy / 2), sx, sy, fc=p['c'], ec='none')
            rect.set_transform(Affine2D().rotate_around(x, y, yw) + ax.transData); ax.add_patch(rect)
        else:
            ax.add_patch(Circle((x, y), p['s'][0], fc=p['c'], ec='none'))
    for o in preview_objs:
        kind, x, y = o[0], o[1], o[2]
        if kind == 'sq':
            ax.add_patch(Rectangle((x - EARTH / 2, y - EARTH / 2), EARTH, EARTH, fc=o[4], ec='k', lw=0.4))
        elif kind == 'sky':
            ax_, sg = o[4]
            for col, sgn in ((START_R, sg), (START_B, -sg)):
                if ax_ == 'y': ax.add_patch(Rectangle((x - SKY / 2, y + (0 if sgn > 0 else -SKY / 2)), SKY, SKY / 2, fc=col, ec='none'))
                else:          ax.add_patch(Rectangle((x + (0 if sgn > 0 else -SKY / 2), y - SKY / 2), SKY / 2, SKY, fc=col, ec='none'))
        elif kind == 'ball':
            ax.add_patch(Circle((x, y), MUSTIKA_R, fc=o[4], ec='k', lw=0.5))
    ax.set_xlim(-H - 0.6, H + 0.6); ax.set_ylim(-H - 0.6, H + 0.6)
    ax.set_title("Top-down: x- = Merah, x+ = Biru, y+ = Storage/Mustika (Figure 3)")
    fig.savefig("preview_topdown.png", dpi=100, bbox_inches='tight')
except Exception as ex:
    print("preview dilewati:", ex)
print("OK prims:", len(prims), "objek dinamis:", len(objs), "GAP:", round(GAP, 3))
