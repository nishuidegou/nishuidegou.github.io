import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.patches import Arc, Polygon

font_manager.fontManager.addfont('/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc')
plt.rcParams['font.family'] = 'Noto Sans CJK JP'
plt.rcParams['axes.unicode_minus'] = False

R = 2200.0
W = 300.0
turn = np.deg2rad(125.0)

C = np.array([-1400.0, -R])
theta = np.linspace(np.deg2rad(90), np.deg2rad(90) - turn, 200)
arc = C + R * np.array([np.cos(theta), np.sin(theta)]).T
P0, P1 = arc[0], arc[-1]

up_len, down_len = 4200.0, 2500.0
up = P0 - np.array([up_len, 0.0])
down = P1 + down_len * np.array([np.cos(-turn), np.sin(-turn)])
cl = np.vstack([up, arc, down])


def bank_normal(p):
    if p[0] < P0[0] - 1:
        return np.array([0.0, 1.0])
    if p[0] > P1[0] + 1:
        return np.array([np.sin(turn), np.cos(turn)])
    return (p - C) / R


left = np.array([p + W * bank_normal(p) for p in cl])
right = np.array([p - W * bank_normal(p) for p in cl])
river = np.vstack([left, right[::-1]])

fig = plt.figure(figsize=(16, 12))
ax = fig.add_axes([0.05, 0.40, 0.90, 0.54])
ax.add_patch(Polygon(river, closed=True, facecolor='#cfe6f7',
                     edgecolor='#2f6fb0', linewidth=2, zorder=1))

apex_i = len(arc) // 2
apex = arc[apex_i]
radial = (apex - C) / R
A = apex + W * radial
B = apex - W * radial

ax.plot([A[0], B[0]], [A[1], B[1]], '--', color='#c0392b', lw=1.6, zorder=3)
ax.plot(A[0], A[1], 'o', ms=11, color='#d2232a', zorder=6)
ax.plot(B[0], B[1], 'o', ms=11, color='#d2232a', zorder=6)
ax.annotate('A（外岸·弯顶站）', xy=A, xytext=(0.88, 0.95),
            xycoords='data', textcoords='axes fraction',
            ha='center', va='center',
            arrowprops=dict(arrowstyle='-', color='#7f1d1d', lw=0.8,
                            shrinkA=0, shrinkB=6),
            fontsize=12, color='#7f1d1d')
ax.annotate('B（内岸·弯顶站）', xy=B, xytext=(0.87, 0.62),
            xycoords='data', textcoords='axes fraction',
            ha='center', va='center',
            arrowprops=dict(arrowstyle='-', color='#7f1d1d', lw=0.8,
                            shrinkA=0, shrinkB=6),
            fontsize=12, color='#7f1d1d')

od = 760.0
A1, B1 = A + od * radial, B + od * radial
ax.annotate('', xy=A1, xytext=B1,
            arrowprops=dict(arrowstyle='<->', color='#333', lw=1.2))
for p in (A1, B1):
    ax.plot([p[0] - 60 * radial[0], p[0] + 60 * radial[0]],
            [p[1] - 60 * radial[1], p[1] + 60 * radial[1]],
            color='#333', lw=1.2)
mid_dim = (A1 + B1) / 2
ax.annotate('河宽 600 m', xy=mid_dim, xytext=(0.86, 0.16),
            xycoords='data', textcoords='axes fraction',
            ha='center', va='center',
            arrowprops=dict(arrowstyle='-', color='#333', lw=0.8,
                            shrinkA=0, shrinkB=4),
            fontsize=11, color='#333',
            bbox=dict(boxstyle='round,pad=0.2', fc='white', ec='none', alpha=0.95),
            zorder=8)

for i in range(1, len(cl) - 1, 45):
    if np.linalg.norm(cl[i] - apex) < 520:
        continue
    d = cl[i + 1] - cl[i]
    dd = np.linalg.norm(d)
    if dd < 1:
        continue
    v = d / dd
    p = cl[i]
    ax.annotate('', xy=p + 240 * v, xytext=p,
                arrowprops=dict(arrowstyle='->', color='#0b3d91', lw=1.4,
                                shrinkA=0, shrinkB=0, alpha=0.85))

a_arc = Arc(C, 1500, 1500, angle=0, theta1=90 - 125, theta2=90,
            color='#5b2c6f', lw=1.6, ls='dotted')
ax.add_patch(a_arc)
amid = C + 750 * np.array([np.cos(np.deg2rad(27.5)), np.sin(np.deg2rad(27.5))])
ax.text(amid[0] - 150, amid[1] - 265, '弯道转角 125°',
        fontsize=11.5, color='#5b2c6f')

ax.text(-5220, -W - 380, '上游顺直段', fontsize=11, color='#1a5276', ha='center')

ax.set_aspect('equal')
ax.set_xlim(-5600, 3200)
ax.set_ylim(-5800, 900)
ax.set_axis_off()

ax.set_title('大河弯道声学层析两站布设示意（弯道转角 125°，河宽 600 m）',
             fontsize=16, pad=6)

ins = fig.add_axes([0.04, 0.05, 0.27, 0.30])
ins.add_patch(plt.Rectangle((-3320, -W), 1250, 2 * W, facecolor='#cfe6f7',
                            edgecolor='#2f6fb0', linewidth=1.6, zorder=1))
C1 = np.array([-3000.0, W])
C2 = np.array([-3000.0 + 600.0 / np.tan(np.deg2rad(35.0)), -W])
ins.plot([C1[0], C2[0]], [C1[1], C2[1]], '--', color='#1a5276', lw=1.6, zorder=3)
ins.plot(*C1, 's', ms=10, color='#1f618d', zorder=6)
ins.plot(*C2, 's', ms=10, color='#1f618d', zorder=6)
ins.annotate('C1', xy=C1, xytext=(-3280, W + 60), fontsize=11, color='#154360')
ins.annotate('C2', xy=C2, xytext=(-3280, -W - 95), fontsize=11, color='#154360')
ins.annotate('', xy=(-3150, 0), xytext=(-3320, 0),
             arrowprops=dict(arrowstyle='->', color='#0b3d91', lw=1.4))
dir_v = np.array([np.cos(-0.61), np.sin(-0.61)])
ins.annotate('', xy=C1 + 300 * dir_v, xytext=C1,
             arrowprops=dict(arrowstyle='->', color='#154360', lw=1.1))
ins.annotate('', xy=(-2160, 0), xytext=(-2280, 0),
             arrowprops=dict(arrowstyle='->', color='#0b3d91', lw=1.1))
ins.text(-2100, 28, '流向', fontsize=10, color='#0b3d91')
a2 = Arc(C1, 460, 460, angle=0, theta1=-35, theta2=0, color='#7d3c98', lw=1.4)
ins.add_patch(a2)
ins.text(-2930, -70, '斜交角 α≈35°（连线含主流分量）', fontsize=10, color='#154360',
         ha='left', bbox=dict(boxstyle='round,pad=0.3', fc='white', ec='#1a5276', alpha=0.95))
ins.set_xlim(-3350, -2050)
ins.set_ylim(-W - 220, W + 260)
ins.set_xticks([])
ins.set_yticks([])
for s in ('top', 'right', 'left', 'bottom'):
    ins.spines[s].set_visible(False)
ins.set_title('① 顺直段：连线斜跨断面（α≈35°）', fontsize=11)

rule_box = fig.add_axes([0.40, 0.07, 0.56, 0.30], frameon=False)
rule_box.set_xlim(0, 1)
rule_box.set_ylim(0, 1)
rule_box.axis('off')
rule_box.add_patch(plt.Rectangle((0, 0), 1, 1, transform=rule_box.transAxes,
                                 facecolor='#f4f6f7', edgecolor='#b8c4cc',
                                 linewidth=1.2, zorder=1))
rule_box.text(0.03, 0.88, '选点几何规律（互易走时差只对“沿连线方向”的流分量灵敏）',
              fontsize=12.5, color='#1b2631', va='top')
rule_box.text(0.03, 0.58, '② 弯顶（本次 125°）：两站连线 ⊥ 局部流向（径向）',
              fontsize=12, color='#7f1d1d', va='top')
rule_box.text(0.03, 0.40,
              '    · 测线落在弯道横流面内，Δ t 反映横向分量与弯道环流\n'
              '    · 避免“流速垂直于固定断面”假设在弯道产生的系统偏差\n'
              '    · A（外岸）/B（内岸）间距 = 河宽 600 m',
              fontsize=10.5, color='#333', va='top')
rule_box.text(0.03, 0.10, '③ 顺直段：两站连线斜跨断面，斜交角 α 取 30°–45°，\n'
              '    使连线含沿流分量（cosα≠0）测量主流，并斜穿全断面采样',
              fontsize=10.5, color='#154360', va='top')

fig.savefig('/home/magicbean/Projects/myblog/sketch-to-comic/bend_site_selection.png',
            dpi=160)
print('saved OK')