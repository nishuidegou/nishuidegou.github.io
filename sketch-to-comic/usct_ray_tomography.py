import os

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
from scipy import sparse

font_manager.fontManager.addfont('/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc')
plt.rcParams['font.family'] = 'Noto Sans CJK JP'
plt.rcParams['axes.unicode_minus'] = False

rng = np.random.default_rng(7)

N = 100
xs = (np.arange(N) + 0.5) / N
X, Y = np.meshgrid(xs, xs, indexing="xy")
R_RING = 0.47
R_BODY = 0.38


def disk(cx, cy, r):
    return (X - cx) ** 2 + (Y - cy) ** 2 <= r ** 2


def ellipse(cx, cy, a, b, ang_deg):
    th = np.deg2rad(ang_deg)
    xr = (X - cx) * np.cos(th) + (Y - cy) * np.sin(th)
    yr = -(X - cx) * np.sin(th) + (Y - cy) * np.cos(th)
    return (xr / a) ** 2 + (yr / b) ** 2 <= 1


c_true = np.full((N, N), 1500.0)
c_true[disk(0.50, 0.50, R_BODY)] = 1470.0
c_true[ellipse(0.44, 0.56, 0.15, 0.10, 25)] = 1565.0
c_true[disk(0.63, 0.42, 0.055)] = 1600.0
s_true = (1.0 / c_true).ravel()

# --- ring array acquisition geometry -------------------------------------
ntx = 72
ang = np.linspace(0, 2 * np.pi, ntx, endpoint=False)
tx_pos = np.column_stack([0.5 + R_RING * np.cos(ang), 0.5 + R_RING * np.sin(ang)])

rays = []
for i in range(ntx):
    for j in range(i + 1, ntx):
        sep = np.rad2deg(ang[j] - ang[i])
        if 95.0 <= sep <= 265.0:
            rays.append((i, j, tx_pos[i], tx_pos[j]))

# --- system matrix: straight-ray line integrals of slowness --------------
K = 260
rows, cols, vals = [], [], []
seg_len = np.empty(len(rays))
for ridx, (_, _, p0, p1) in enumerate(rays):
    t = np.linspace(0, 1, K)
    px = p0[0] + (p1[0] - p0[0]) * t
    py = p0[1] + (p1[1] - p0[1]) * t
    dseg = np.hypot(p1[0] - p0[0], p1[1] - p0[1]) / (K - 1)
    seg_len[ridx] = np.hypot(p1[0] - p0[0], p1[1] - p0[1])
    ii = np.clip((px * N).astype(int), 0, N - 1)
    jj = np.clip((py * N).astype(int), 0, N - 1)
    bins = ii * N + jj
    uniq, cnt = np.unique(bins, return_counts=True)
    rows.extend([ridx] * len(uniq))
    cols.extend(uniq)
    vals.extend((cnt * dseg).tolist())

A = sparse.csr_matrix((vals, (rows, cols)), shape=(len(rays), N * N))
b = A @ s_true

# row/column sums for the standard SIRT (simultaneous algebraic) update
rowsum = np.asarray(A.sum(axis=1)).ravel()
colsum = np.asarray(A.sum(axis=0)).ravel()
colsum[colsum == 0] = 1.0

x = np.full(N * N, 1.0 / 1500.0)
niter = 300
lam = 1.0
for _ in range(niter):
    resid = b - A @ x
    x = x + lam * (A.T @ (resid / rowsum)) / colsum

c_rec = (1.0 / x).reshape(N, N)

body = disk(0.50, 0.50, R_BODY)
rmse = np.sqrt(np.mean((c_rec[body] - c_true[body]) ** 2))

# --- figure ---------------------------------------------------------------
fig = plt.figure(figsize=(15.5, 10.5))
fig.suptitle('超声计算机断层成像（USCT）：环形阵透射采样 与 直射线走时层析重建',
             fontsize=17, y=0.97)

# (a) acquisition geometry
axa = fig.add_axes([0.04, 0.53, 0.42, 0.36])
th = np.linspace(0, 2 * np.pi, 400)
axa.plot(0.5 + R_RING * np.cos(th), 0.5 + R_RING * np.sin(th),
         color='#7f8c8d', lw=1.0, ls='--')
axa.add_patch(plt.Circle((0.5, 0.5), R_RING, facecolor='#dceaf6',
                         edgecolor='none', zorder=0))
axa.add_patch(plt.Circle((0.5, 0.5), R_BODY, facecolor='#f6ddc9',
                         edgecolor='#c98a55', lw=1.2, zorder=1))
src = 0
for i, j, p0, p1 in rays:
    if i != src:
        continue
    axa.plot([p0[0], p1[0]], [p0[1], p1[1]], color='#2e86c1',
             lw=0.4, alpha=0.35, zorder=2)
axa.plot(tx_pos[:, 0], tx_pos[:, 1], 'o', ms=4.5, color='#1a5276', zorder=4)
axa.plot(*tx_pos[src], 'o', ms=11, color='#c0392b', zorder=5)
rx_ids = [j for i, j, _, _ in rays if i == src]
axa.plot(tx_pos[rx_ids, 0], tx_pos[rx_ids, 1], 'o', ms=6.5,
         mfc='none', mec='#c0392b', mew=1.4, zorder=5)
axa.text(0.5, 1.02, '① 环形换能器阵列 + 水耦合：单发多收（透射模式）',
         fontsize=12, ha='center', color='#1b2631')
axa.annotate('发射', xy=tx_pos[src], xytext=(0.02, 0.28),
             textcoords='axes fraction', fontsize=10, color='#c0392b',
             arrowprops=dict(arrowstyle='-', color='#c0392b', lw=0.9))
axa.text(0.5, 0.03, '一种扫描：1 发 × 约 36 收；共 72 发 → 约 1296 条视线',
         fontsize=9.5, ha='center', color='#566573')
axa.set_xlim(-0.02, 1.02)
axa.set_ylim(-0.05, 1.05)
axa.set_aspect('equal')
axa.set_axis_off()

# (b) ground truth
axb = fig.add_axes([0.52, 0.53, 0.34, 0.36])
im = axb.imshow(c_true, cmap='turbo', vmin=1450, vmax=1605,
                extent=[0, 1, 0, 1], origin='lower')
axb.add_patch(plt.Circle((0.5, 0.5), R_RING, fill=False,
                         edgecolor='#333', lw=1.0, ls=':'))
axb.set_title('② 真值声速分布（m/s）', fontsize=12, color='#1b2631')
axb.set_xticks([]); axb.set_yticks([])
cb = fig.colorbar(im, ax=axb, fraction=0.046, pad=0.04)
cb.ax.tick_params(labelsize=8)

# (c) reconstruction
axc = fig.add_axes([0.04, 0.08, 0.34, 0.36])
im2 = axc.imshow(c_rec, cmap='turbo', vmin=1450, vmax=1605,
                 extent=[0, 1, 0, 1], origin='lower')
axc.add_patch(plt.Circle((0.5, 0.5), R_RING, fill=False,
                         edgecolor='#333', lw=1.0, ls=':'))
axc.set_title(f'③ 直射线 SIRT 重建（{niter} 次迭代）', fontsize=12, color='#1b2631')
axc.set_xticks([]); axc.set_yticks([])
cb2 = fig.colorbar(im2, ax=axc, fraction=0.046, pad=0.04)
cb2.ax.tick_params(labelsize=8)

# (d) profile comparison
axd = fig.add_axes([0.52, 0.11, 0.44, 0.30])
yy = N // 2
prof_x = xs
axd.plot(prof_x, c_true[yy, :], color='#c0392b', lw=2.0, label='真值')
axd.plot(prof_x, c_rec[yy, :], color='#1a5276', lw=1.5, ls='--', label='SIRT 重建')
axd.set_xlim(0.08, 0.92)
axd.set_ylim(1455, 1610)
axd.set_xlabel('横向位置', fontsize=10)
axd.set_ylabel('声速 c (m/s)', fontsize=10)
axd.grid(alpha=0.25)
axd.legend(fontsize=10, loc='lower left')
axd.set_title(f'④ 中心行剖面：重建体区 RMSE ≈ {rmse:.1f} m/s',
              fontsize=12, color='#1b2631')

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'assets', 'images', 'usct-ray-tomography.png')
fig.savefig(OUT, dpi=150)
print('rays', len(rays), 'rmse', round(rmse, 2), 'saved', OUT)
