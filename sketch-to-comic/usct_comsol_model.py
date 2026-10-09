import os

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.tri import Triangulation
from scipy import sparse
from scipy.sparse.linalg import spsolve

font_manager.fontManager.addfont('/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc')
plt.rcParams['font.family'] = 'Noto Sans CJK JP'
plt.rcParams['axes.unicode_minus'] = False

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IMG = os.path.join(ROOT, 'assets', 'images')

# ---- shared geometry (metres) -------------------------------------------
HALF = 0.045          # half size of the 2D domain
PML_W = 0.006         # absorbing layer width
R_RING = 0.032        # transducer ring radius
R_BODY = 0.024        # tissue phantom radius
C_WATER = 1500.0


def phantom_speed(X, Y):
    c = np.full(X.shape, C_WATER)
    body = X ** 2 + Y ** 2 <= R_BODY ** 2
    c[body] = 1460.0                                   # fat
    th = np.deg2rad(25.0)
    xr = X * np.cos(th) + Y * np.sin(th)
    yr = -X * np.sin(th) + Y * np.cos(th)
    gland = ((xr - 0.006) / 0.011) ** 2 + ((yr - 0.004) / 0.007) ** 2 <= 1.0
    c[gland & body] = 1560.0                           # fibroglandular
    lesion = (X - 0.011) ** 2 + (Y + 0.007) ** 2 <= 0.004 ** 2
    c[lesion] = 1600.0                                 # lesion
    return c


# ---- panel (a): COMSOL model setup --------------------------------------
fig = plt.figure(figsize=(16, 7.2))

axa = fig.add_axes([0.03, 0.06, 0.44, 0.86])
axa.add_patch(plt.Rectangle((-HALF, -HALF), 2 * HALF, 2 * HALF,
                            facecolor='#eef3f6', edgecolor='#333', lw=1.2))
axa.add_patch(plt.Rectangle((-HALF, -HALF), 2 * HALF, 2 * HALF, fill=False,
                            edgecolor='none'))
# PML border
inner = HALF - PML_W
axa.add_patch(plt.Rectangle((-HALF, -HALF), 2 * HALF, 2 * HALF, facecolor='#cfd8dc',
                            edgecolor='none'))
axa.add_patch(plt.Rectangle((-inner, -inner), 2 * inner, 2 * inner,
                            facecolor='#d6eaf8', edgecolor='#5499c7', lw=1.0))
# body
th = np.linspace(0, 2 * np.pi, 300)
axa.fill(R_BODY * np.cos(th), R_BODY * np.sin(th), color='#f6ddc9',
         edgecolor='#c98a55', lw=1.4, zorder=3)
axa.fill(0.011 * np.cos(th) + 0.006, 0.007 * np.sin(th) + 0.004,
         color='#e8b7a0', edgecolor='#b06a4a', lw=1.0, zorder=4)
axa.plot(0.004 * np.cos(th) + 0.011, 0.004 * np.sin(th) - 0.007, color='#a93226',
         lw=1.2, zorder=4)
# ring array
ang = np.linspace(0, 2 * np.pi, 32, endpoint=False)
axa.plot(R_RING * np.cos(ang), R_RING * np.sin(ang), 'o', ms=6,
         color='#1a5276', zorder=5)
src = np.pi
axa.plot(R_RING * np.cos(src), R_RING * np.sin(src), 'o', ms=12,
         color='#c0392b', zorder=6)
axa.annotate('点源（Pressure Acoustics）', xy=(R_RING * np.cos(src), 0),
             xytext=(-0.043, -0.03), fontsize=10, color='#c0392b',
             arrowprops=dict(arrowstyle='->', color='#c0392b', lw=1.0))
axa.text(0.0, R_RING + 0.0012, '环形换能器阵（逐元激励 / 接收）',
         fontsize=10, ha='center', color='#154360')
axa.annotate('', xy=(-HALF + 0.001, HALF - 0.001), xytext=(-inner, inner),
             arrowprops=dict(arrowstyle='<-', color='#566573', lw=1.1))
axa.text(-HALF + 0.0005, HALF - 0.006, 'PML 吸收层\n（模拟无界水槽）',
         fontsize=10, color='#34495e', va='top')
axa.text(0.0, -0.018, '水耦合\n$c=1500$ m/s', fontsize=10, ha='center',
         color='#1a5276')
axa.text(0.0, 0.0, '被测体\n（幻影）', fontsize=10, ha='center', color='#7b3f00')
axa.set_xlim(-HALF - 0.004, HALF + 0.004)
axa.set_ylim(-HALF - 0.004, HALF + 0.004)
axa.set_aspect('equal')
axa.set_xticks([]); axa.set_yticks([])
axa.set_title('① COMSOL 模型：几何、边界与阵列', fontsize=13, color='#1b2631')

# ---- panel (b): FEM mesh -------------------------------------------------
axb = fig.add_axes([0.51, 0.06, 0.44, 0.86])
rng = np.random.default_rng(3)


def sample(n, rmax):
    u = rng.random(n)
    r = rmax * np.sqrt(u)
    t = rng.random(n) * 2 * np.pi
    return r * np.cos(t), r * np.sin(t)


bx, by = sample(3000, R_BODY)
outer = HALF - PML_W


def sample_square(n, a, b):
    return rng.uniform(a, b, n), rng.uniform(a, b, n)


wx, wy = sample_square(1500, 0, outer)
keep = np.sqrt(wx ** 2 + wy ** 2) > R_BODY
wx, wy = wx[keep], wy[keep]
px, py = sample_square(400, outer, HALF)
xs = np.concatenate([bx, wx, px])
ys = np.concatenate([by, wy, py])
tri = Triangulation(xs, ys)
pts = np.column_stack([xs, ys])
cent = pts[tri.triangles].mean(axis=1)
tri.set_mask((np.abs(cent[:, 0]) > HALF) | (np.abs(cent[:, 1]) > HALF))
axb.triplot(tri, color='#2c3e50', lw=0.18)
axb.plot(R_BODY * np.cos(th), R_BODY * np.sin(th), color='#c98a55', lw=1.6)
axb.add_patch(plt.Rectangle((-HALF, -HALF), 2 * HALF, 2 * HALF, fill=False,
                            edgecolor='#111', lw=1.4))
axb.annotate('体内网格加密\n（声速高、波长短）', xy=(0.0, 0.0),
             xytext=(0.012, -0.034), fontsize=10.5, color='#7b3f00',
             arrowprops=dict(arrowstyle='->', color='#7b3f00', lw=1.0))
axb.annotate('每波长 ≥ 6–10 单元\n（由最高频决定）', xy=(outer, HALF - 0.002),
             xytext=(-HALF + 0.002, HALF - 0.008), fontsize=10.5,
             color='#154360')
axb.set_xlim(-HALF - 0.004, HALF + 0.004)
axb.set_ylim(-HALF - 0.004, HALF + 0.004)
axb.set_aspect('equal')
axb.set_xticks([]); axb.set_yticks([])
axb.set_title('② 网格：波长决定单元尺寸，边界用 PML', fontsize=13, color='#1b2631')

fig.suptitle('用 COMSOL 仿真 USCT：二维频域声学模型（Pressure Acoustics, Frequency Domain）',
             fontsize=16, y=0.985)
fig.savefig(os.path.join(IMG, 'usct-comsol-setup.png'), dpi=150)
print('saved setup')


# ---- forward solve: 2D Helmholtz with a graded lossy PML -----------------
def solve_field(c, f, src_xy, dx):
    n = int(round(2 * HALF / dx))
    xs = -HALF + (np.arange(n) + 0.5) * dx
    X, Y = np.meshgrid(xs, xs, indexing='xy')
    k = 2 * np.pi * f / c
    dist = np.minimum(HALF - np.abs(X), HALF - np.abs(Y))
    eta = np.zeros_like(dist)
    m = dist < PML_W
    t = (PML_W - dist[m]) / PML_W
    eta[m] = 1.2 * t ** 2
    kc2 = (k ** 2) * (1 + 1j * eta)

    N = n * n
    main = -4.0 / dx ** 2 + kc2.ravel()
    rows = [np.arange(N)]
    cols = [np.arange(N)]
    vals = [main]
    idx = np.arange(N).reshape(n, n)
    # x+1
    sel = np.zeros((n, n), bool); sel[:, :-1] = True
    rows.append(idx[sel]); cols.append(idx[np.roll(sel, -1, axis=1)])
    vals.append(np.full(sel.sum(), 1.0 / dx ** 2))
    # x-1
    rows.append(idx[sel]); cols.append(idx[np.roll(sel, 1, axis=1)])
    vals.append(np.full(sel.sum(), 1.0 / dx ** 2))
    # y+1
    sel = np.zeros((n, n), bool); sel[:-1, :] = True
    rows.append(idx[sel]); cols.append(idx[np.roll(sel, -1, axis=0)])
    vals.append(np.full(sel.sum(), 1.0 / dx ** 2))
    # y-1
    rows.append(idx[sel]); cols.append(idx[np.roll(sel, 1, axis=0)])
    vals.append(np.full(sel.sum(), 1.0 / dx ** 2))

    A = sparse.csr_matrix((np.concatenate(vals),
                           (np.concatenate(rows), np.concatenate(cols))),
                          shape=(N, N))
    b = np.zeros(N, dtype=complex)
    si = np.argmin((xs - src_xy[0]) ** 2) 
    sj = np.argmin((xs - src_xy[1]) ** 2)
    b[idx[sj, si]] = 1.0 / dx ** 2
    # light smoothing of the source
    for ds in (-1, 1):
        b[idx[sj, min(max(si + ds, 0), n - 1)]] += 0.5 / dx ** 2
        b[idx[min(max(sj + ds, 0), n - 1), si]] += 0.5 / dx ** 2
    p = spsolve(A, b).reshape(n, n)
    return X, Y, p


f0 = 5.0e5
dx = 3.0e-4
src = (R_RING * np.cos(np.pi), 0.0)
X, Y, p_hom = solve_field(np.full((int(round(2 * HALF / dx)),) * 2, C_WATER), f0, src, dx)
print('hom solved')
X, Y, p_het = solve_field(phantom_speed(X, Y), f0, src, dx)
print('het solved')

fig2, axes = plt.subplots(1, 2, figsize=(15.5, 7.4))
for ax, p, ttl in ((axes[0], p_hom, '① 均匀水：参考波场 $\\mathrm{Re}(p)$'),
                   (axes[1], p_het, '② 放入幻影：折射 / 绕射 / 散射')):
    vmax = np.percentile(np.abs(p.real), 99.0)
    im = ax.imshow(p.real, cmap='seismic', origin='lower',
                   extent=[-HALF, HALF, -HALF, HALF], vmin=-vmax, vmax=vmax)
    ax.add_patch(plt.Circle((0, 0), R_BODY, fill=False, edgecolor='k', lw=1.2))
    ax.plot(R_RING * np.cos(ang), R_RING * np.sin(ang), 'o', ms=4,
            color='#1a5276', alpha=0.7)
    ax.plot(*src, 'o', ms=10, color='#00e5ff', markeredgecolor='k')
    ax.set_title(ttl, fontsize=13)
    ax.set_xticks([]); ax.set_yticks([])
    ax.set_xlim(-HALF, HALF); ax.set_ylim(-HALF, HALF)
    fig2.colorbar(im, ax=ax, fraction=0.046, pad=0.03).ax.tick_params(labelsize=8)

fig2.suptitle('同一个 0.5 MHz 点源：自写二维 Helmholtz 求解器复现的 COMSOL 前向波场', fontsize=15, y=0.98)
fig2.savefig(os.path.join(IMG, 'usct-comsol-wavefield.png'), dpi=150, bbox_inches='tight')
print('saved wavefield')
