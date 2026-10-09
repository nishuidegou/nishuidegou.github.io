import os

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
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
th = np.linspace(0, 2 * np.pi, 300)


def phantom_speed(X, Y):
    c = np.full(X.shape, C_WATER)
    body = X ** 2 + Y ** 2 <= R_BODY ** 2
    c[body] = 1460.0                                   # fat
    a = np.deg2rad(25.0)
    xr = X * np.cos(a) + Y * np.sin(a)
    yr = -X * np.sin(a) + Y * np.cos(a)
    gland = ((xr - 0.006) / 0.011) ** 2 + ((yr - 0.004) / 0.007) ** 2 <= 1.0
    c[gland & body] = 1560.0                           # fibroglandular
    lesion = (X - 0.011) ** 2 + (Y + 0.007) ** 2 <= 0.004 ** 2
    c[lesion] = 1600.0                                 # lesion
    return c


# ---- panel (a): model setup + panel (b): uniform grid -------------------
fig = plt.figure(figsize=(16, 7.2))

axa = fig.add_axes([0.03, 0.06, 0.44, 0.86])
axa.add_patch(plt.Rectangle((-HALF, -HALF), 2 * HALF, 2 * HALF,
                            facecolor='#cfd8dc', edgecolor='#333', lw=1.2))
inner = HALF - PML_W
axa.add_patch(plt.Rectangle((-inner, -inner), 2 * inner, 2 * inner,
                            facecolor='#d6eaf8', edgecolor='#5499c7', lw=1.0))
axa.fill(R_BODY * np.cos(th), R_BODY * np.sin(th), color='#f6ddc9',
         edgecolor='#c98a55', lw=1.4, zorder=3)
axa.fill(0.011 * np.cos(th) + 0.006, 0.007 * np.sin(th) + 0.004,
         color='#e8b7a0', edgecolor='#b06a4a', lw=1.0, zorder=4)
axa.plot(0.004 * np.cos(th) + 0.011, 0.004 * np.sin(th) - 0.007, color='#a93226',
         lw=1.2, zorder=4)
ang = np.linspace(0, 2 * np.pi, 32, endpoint=False)
axa.plot(R_RING * np.cos(ang), R_RING * np.sin(ang), 'o', ms=6,
         color='#1a5276', zorder=5)
src = np.pi
axa.plot(R_RING * np.cos(src), R_RING * np.sin(src), 'o', ms=12,
         color='#c0392b', zorder=6)
axa.annotate('声源（source mask）', xy=(R_RING * np.cos(src), 0),
             xytext=(-0.044, -0.03), fontsize=10, color='#c0392b',
             arrowprops=dict(arrowstyle='->', color='#c0392b', lw=1.0))
axa.text(0.0, R_RING + 0.0012, '环形换能器阵（source / sensor mask）',
         fontsize=10, ha='center', color='#154360')
axa.annotate('', xy=(-HALF + 0.001, HALF - 0.001), xytext=(-inner, inner),
             arrowprops=dict(arrowstyle='<-', color='#566573', lw=1.1))
axa.text(-HALF + 0.0005, HALF - 0.006, 'PML 吸收层\n（k-Wave 自带，层数可设）',
         fontsize=10, color='#34495e', va='top')
axa.text(0.0, -0.018, '水耦合\n$c=1500$ m/s', fontsize=10, ha='center',
         color='#1a5276')
axa.text(0.0, 0.0, '被测体\n（幻影）', fontsize=10, ha='center', color='#7b3f00')
axa.set_xlim(-HALF - 0.004, HALF + 0.004)
axa.set_ylim(-HALF - 0.004, HALF + 0.004)
axa.set_aspect('equal')
axa.set_xticks([]); axa.set_yticks([])
axa.set_title('① 模型：几何、边界与阵列（k-Wave / 自写求解器通用）',
              fontsize=13, color='#1b2631')

axb = fig.add_axes([0.51, 0.06, 0.44, 0.86])
ng = 40
gx = np.linspace(-inner, inner, ng)
for g in gx:
    axb.plot([g, g], [-inner, inner], color='#90a4ae', lw=0.25)
    axb.plot([-inner, inner], [g, g], color='#90a4ae', lw=0.25)
axb.add_patch(plt.Rectangle((-inner, -inner), 2 * inner, 2 * inner, fill=False,
                            edgecolor='#111', lw=1.3))
axb.plot(R_BODY * np.cos(th), R_BODY * np.sin(th), color='#c98a55', lw=1.6)
axb.plot(R_RING * np.cos(ang), R_RING * np.sin(ang), 'o', ms=5,
         color='#1a5276', alpha=0.8)
axb.plot(R_RING * np.cos(src), R_RING * np.sin(src), 'o', ms=10,
         color='#c0392b', zorder=6)
dxv = gx[1] - gx[0]
yc = 0.004
axb.annotate('', xy=(-dxv, yc), xytext=(0.0, yc),
             arrowprops=dict(arrowstyle='<->', color='#c0392b', lw=1.1))
axb.text(-dxv / 2, yc + 0.0008, '$\\Delta x$', fontsize=11, color='#c0392b',
         ha='center')
axb.annotate('源可落在网格之间（off-grid source）',
             xy=(R_RING * np.cos(src), R_RING * np.sin(src)),
             xytext=(-inner, -HALF + 0.004), fontsize=10, color='#c0392b',
             arrowprops=dict(arrowstyle='->', color='#c0392b', lw=0.9))
axb.text(0.0, 0.018, '均匀网格 + k-space 修正\n每波长 ≥ 2 点（建议 3–4）',
         fontsize=10.5, ha='center', color='#154360',
         bbox=dict(boxstyle='round,pad=0.3', fc='white', ec='#5499c7', alpha=0.95))
axb.text(0.0, -0.028, '时间步由 CFL 决定：$\\Delta t \\leq \\mathrm{CFL}\\cdot\\Delta x / c_{max}$，'
                      'CFL 取 0.3',
         fontsize=10, ha='center', color='#34495e',
         bbox=dict(boxstyle='round,pad=0.3', fc='white', ec='#90a4ae', alpha=0.95))
axb.set_xlim(-HALF - 0.004, HALF + 0.004)
axb.set_ylim(-HALF - 0.004, HALF + 0.004)
axb.set_aspect('equal')
axb.set_xticks([]); axb.set_yticks([])
axb.set_title('② 计算网格：均匀交错网格（k-Wave 用 k-space 修正）',
              fontsize=13, color='#1b2631')

fig.suptitle('用 k-Wave 与自写求解器仿真 USCT：二维声学模型',
             fontsize=16, y=0.985)
fig.savefig(os.path.join(IMG, 'usct-simulation-setup.png'), dpi=150)
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
    sel = np.zeros((n, n), bool); sel[:, :-1] = True
    rows.append(idx[sel]); cols.append(idx[np.roll(sel, -1, axis=1)])
    vals.append(np.full(sel.sum(), 1.0 / dx ** 2))
    rows.append(idx[sel]); cols.append(idx[np.roll(sel, 1, axis=1)])
    vals.append(np.full(sel.sum(), 1.0 / dx ** 2))
    sel = np.zeros((n, n), bool); sel[:-1, :] = True
    rows.append(idx[sel]); cols.append(idx[np.roll(sel, -1, axis=0)])
    vals.append(np.full(sel.sum(), 1.0 / dx ** 2))
    rows.append(idx[sel]); cols.append(idx[np.roll(sel, 1, axis=0)])
    vals.append(np.full(sel.sum(), 1.0 / dx ** 2))

    A = sparse.csr_matrix((np.concatenate(vals),
                           (np.concatenate(rows), np.concatenate(cols))),
                          shape=(N, N))
    b = np.zeros(N, dtype=complex)
    si = np.argmin((xs - src_xy[0]) ** 2)
    sj = np.argmin((xs - src_xy[1]) ** 2)
    b[idx[sj, si]] = 1.0 / dx ** 2
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

fig2.suptitle('同一个 0.5 MHz 点源：自写二维 Helmholtz 求解器复现的波场'
              '（k-Wave 可得等价的时域结果）', fontsize=15, y=0.98)
fig2.savefig(os.path.join(IMG, 'usct-simulation-wavefield.png'), dpi=150,
             bbox_inches='tight')
print('saved wavefield')
