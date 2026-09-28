import os

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.patches import Circle, Rectangle, Wedge, FancyArrowPatch

font_manager.fontManager.addfont('/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc')
plt.rcParams['font.family'] = 'Noto Sans CJK JP'
plt.rcParams['axes.unicode_minus'] = False

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'assets', 'images', 'fluxgate-leakage-overview.png')

fig = plt.figure(figsize=(17.5, 12.4))
fig.patch.set_facecolor('white')

# ============================================================ 左侧：零磁通闭环
ax = fig.add_axes([0.030, 0.050, 0.3124, 0.860])
ax.set_xlim(0, 10)
ax.set_ylim(0, 20.6)
ax.set_aspect('equal')
ax.set_axis_off()

cx, cy = 4.30, 14.00
R, r = 1.90, 1.08

ax.add_patch(Wedge((cx, cy), R, 0, 360, width=R - r,
                   facecolor='#dfe7ef', edgecolor='#5b6b7b', lw=1.8, zorder=2))
ax.add_patch(Circle((cx, cy), r, facecolor='white', edgecolor='none', zorder=3))

# 一次导体（1 匝穿芯）
ax.plot([cx, cx], [8.90, 18.30], color='#c0392b', lw=9,
        solid_capstyle='round', zorder=6)
ax.add_patch(plt.Circle((cx, 18.55), 0.30, facecolor='#c0392b',
                        edgecolor='none', zorder=6))
ax.text(cx, 19.10, '一次导体 $I_P$（1 匝穿芯）', fontsize=13, color='#8e2a20',
        ha='center', va='center', fontweight='bold', zorder=6)
ax.text(cx, 9.45, '$N_P I_P$\n（原边安匝）', fontsize=10.5, color='#8e2a20',
        ha='center', va='center', zorder=6, linespacing=1.4)


def winding(a0_deg, a1_deg, r_mid, color):
    ts = np.linspace(np.deg2rad(a0_deg), np.deg2rad(a1_deg), 90)
    ax.plot(cx + r_mid * np.cos(ts), cy + r_mid * np.sin(ts),
            color=color, lw=1.8, zorder=5)


winding(95, 145, r + 0.20, '#1f6feb')      # 励磁
winding(185, 235, r + 0.20, '#b8860b')     # 检测
winding(315, 375, r + 0.20, '#1a7f5a')     # 补偿

ax.text(2.93, 16.80, '励磁绕组', fontsize=12.2, color='#1f6feb',
        ha='center', va='center', fontweight='bold')
ax.text(2.93, 16.05, '方波/正弦 $i_e$ @ $f_{exc}$', fontsize=10.2,
        color='#404b57', ha='center', va='center')
ax.plot([3.35, 3.66], [15.88, 15.20], color='#1f6feb', lw=0.9, zorder=4)

ax.text(1.92, 13.05, '检测绕组', fontsize=12.2, color='#a8740a',
        ha='center', va='center', fontweight='bold')
ax.text(1.92, 12.28, '感应 $2f$ 分量 → 解调', fontsize=10.2,
        color='#404b57', ha='center', va='center')
ax.plot([2.62, 3.12], [12.85, 13.25], color='#b8860b', lw=0.9, zorder=4)

ax.text(7.00, 15.95, '补偿绕组', fontsize=12.2, color='#1a7f5a',
        ha='center', va='center', fontweight='bold')
ax.text(7.00, 15.20, '回灌 $I_{fb}$ 抵消 $N_PI_P$', fontsize=10.2,
        color='#404b57', ha='center', va='center')
ax.plot([5.80, 5.58], [15.05, 14.40], color='#1a7f5a', lw=0.9, zorder=4)

# 反馈回路线：检测 -> 底部分段 -> 补偿
ax.plot([3.57, 3.57], [12.60, 3.40], color='#8894a0', lw=1.5, ls=(0, (5, 3)),
        zorder=4)
ax.plot([3.57, 9.20], [3.40, 3.40], color='#8894a0', lw=1.5, ls=(0, (5, 3)),
        zorder=4)
ax.plot([9.20, 9.20], [3.40, 15.60], color='#8894a0', lw=1.5, ls=(0, (5, 3)),
        zorder=4)
ax.add_patch(FancyArrowPatch((9.20, 15.60), (8.52, 15.60),
                             arrowstyle='-|>', mutation_scale=15,
                             color='#1a7f5a', lw=1.7, zorder=5))

blocks = [
    (3.95, 5.40, '#eef4ff', '#1f6feb', '解调\n相敏检波'),
    (5.70, 7.15, '#eef4ff', '#1f6feb', '积分器\n高环路增益'),
    (7.45, 8.90, '#e9f7f0', '#1a7f5a', 'H 桥驱动\n+ 采样电阻'),
]
for x0, x1, fc, ec, txt in blocks:
    ax.add_patch(Rectangle((x0, 3.62), x1 - x0, 1.05, facecolor=fc,
                           edgecolor=ec, lw=1.6, zorder=5))
    ax.text((x0 + x1) / 2, 4.15, txt, fontsize=9.8, color='#1b2631',
            ha='center', va='center', zorder=6, linespacing=1.35)
    xm = (x0 + x1) / 2
    ax.plot([xm, xm], [3.40, 3.62], color='#3d4b5a', lw=1.4, zorder=5)
    ax.add_patch(FancyArrowPatch((xm, 3.52), (xm, 3.66), arrowstyle='-|>',
                                 mutation_scale=12, color='#3d4b5a',
                                 lw=1.4, zorder=6))
for xm in (5.55, 7.30):
    ax.add_patch(FancyArrowPatch((xm - 0.16, 3.40), (xm + 0.16, 3.40),
                                 arrowstyle='-|>', mutation_scale=12,
                                 color='#3d4b5a', lw=1.4, zorder=6))

ax.text(8.00, 3.05, '输出电压 $V_{out}$ 取自采样电阻', fontsize=9.8,
        color='#1a7f5a', ha='center', va='center')

ax.text(0.10, 2.45,
        '$N_P I_P + N_S I_{fb} \\approx 0$ ⇒ 输出严格等于原边电流÷匝数比，\n'
        '磁通恒为零 ⇒ 无剩磁、无磁滞误差，过流撤去后立刻恢复。',
        fontsize=10.6, color='#25313c', ha='left', va='top', linespacing=1.5)
ax.text(0.10, 1.45,
        '低频靠零磁通闭环；频率升高后环路增益不够、补偿电流跟不上，\n'
        '传感器"退化成"电流互感器——这才是它 DC~100 kHz 的由来。',
        fontsize=10.6, color='#7f1d1d', ha='left', va='top', linespacing=1.5)

ax.text(0.10, 19.90, '① 零磁通（fluxgate closed-loop）闭环原理', fontsize=15.5,
        color='#12232e', fontweight='bold', ha='left', va='center')

# B-H 回线平移（嵌入小图）
bh = fig.add_axes([0.199, 0.333, 0.109, 0.184])
t = np.linspace(-1, 1, 400)
bh.plot(t, np.tanh(3.2 * t), color='#9aa7b3', lw=1.5, ls='--', label='无外部场')
bh.plot(t + 0.28, np.tanh(3.2 * (t + 0.35)), color='#c0392b', lw=2.4,
        label='有 $H_{ext}$：回线平移')
bh.axhline(0, color='#c8d2da', lw=0.8)
bh.axvline(0, color='#c8d2da', lw=0.8)
bh.set_xticks([]), bh.set_yticks([])
for s in bh.spines.values():
    s.set_color('#b8c4cc')
bh.text(0.04, 0.90, 'B', fontsize=10, color='#404b57')
bh.text(0.86, 0.10, 'H', fontsize=10, color='#404b57')
ax.text(5.45, 6.15, '磁通门本质：B-H 回线被 $H_{ext}$ 平移', fontsize=10.4,
        color='#1b2631', ha='left', va='center')

# ============================================================ 右侧：频带覆盖
ax2 = fig.add_axes([0.400, 0.300, 0.565, 0.580])
ax2.set_xlim(-0.55, 7.55)
ax2.set_ylim(0, 7.15)
ax2.set_yticks([])
for sp in ax2.spines.values():
    sp.set_visible(False)

RAIL = 5.10
ax2.plot([0.0, 4.95], [RAIL, RAIL], color='#8a97a3', lw=1.2, zorder=2)
ax2.text(-0.35, RAIL + 0.42, '典型剩余电流成分', fontsize=11.4,
         color='#5b6b7b', ha='left', va='bottom')

marks = [
    (0.05, RAIL + 0.75, '绝缘劣化 / 漏液（缓慢直流）', '#7b4b12', 'left'),
    (1.80, RAIL + 0.20, '50/60 Hz 交流漏电', '#0b3d91', 'center'),
    (3.30, RAIL + 0.75, '整流脉动 / 充电桩 PWM 载波', '#4a235a', 'center'),
    (4.90, RAIL + 0.20, 'SiC/GaN 开关尖峰（µs 级）', '#a93226', 'center'),
]
for x, ytop, txt, col, ha in marks:
    ax2.plot([x, x], [RAIL, ytop], color=col, lw=1.1, ls=':', zorder=3)
    ax2.plot(x, RAIL, 'o', ms=8, color=col, zorder=4)
    ax2.text(x, ytop + 0.16, txt, fontsize=10.2, color=col, ha=ha,
             va='bottom', zorder=4)

bands = [
    (3.55, 4.45, 3.05, '#dbe7f3', '#5b6b7b',
     '零序互感器 ZCT：只测交流（$\\propto di_\\Delta/dt$）'),
    (2.35, 3.25, 7.30, '#e6f4ec', '#1a7f5a',
     '霍尔（开环 / 闭环 / 差分）：DC~MHz，量程大、便宜'),
    (1.15, 2.05, 5.00, '#fdeaea', '#c0392b',
     '磁通门：DC~100 kHz，残流可到 mA 级、零点极稳'),
]
for y0, y1, xend, fc, ec, lab in bands:
    ax2.add_patch(Rectangle((-0.35, y0), xend + 0.35, y1 - y0,
                            facecolor=fc, edgecolor=ec, lw=1.5, zorder=2))
    ax2.text(-0.20, (y0 + y1) / 2, lab, fontsize=11.4, color='#1b2631',
             ha='left', va='center', zorder=3)

ax2.plot([-0.35, 7.30], [0.85, 0.85], color='#8a97a3', lw=1.2, zorder=2)
ticks = {0: 'DC', 1: '1 Hz', 2: '10 Hz', 3: '100 Hz', 4: '1 kHz',
         5: '10 kHz', 6: '100 kHz', 7: '1 MHz'}
for dec, lab in ticks.items():
    ax2.plot([dec, dec], [0.68, 0.85], color='#8a97a3', lw=1.0, zorder=2)
    ax2.text(dec, 0.50, lab, fontsize=10.4, color='#404b57', ha='center',
             va='center', zorder=2)
ax2.set_xlabel('频率（对数轴）', fontsize=11.8, color='#12232e', labelpad=8)
ax2.set_title('② 残流成分与传感器频带覆盖：谁有"盲区"，谁看得见',
              fontsize=15.5, color='#12232e', fontweight='bold', pad=16)

note = fig.add_axes([0.400, 0.055, 0.565, 0.185], frameon=False)
note.set_xlim(0, 1)
note.set_ylim(0, 1)
note.axis('off')
note.add_patch(Rectangle((0, 0), 1, 1, transform=note.transAxes,
                         facecolor='#f4f6f7', edgecolor='#b8c4cc', lw=1.2,
                         zorder=1))
note.text(0.018, 0.92, '工程结论：单一传感器覆盖不全，主流做法是"分频带相加"',
          fontsize=12.6, color='#1b2631', va='top')
note.text(0.018, 0.60,
          '· 缓慢直流（绝缘劣化）→ 只有磁通门 / 低零漂霍尔能看，纯 ZCT 完全失明\n'
          '· 50 Hz 与工频谐波 → ZCT 最便宜，磁通门也够用且更稳\n'
          '· 开关尖峰（µs 级）→ 宽带差分霍尔（数百 kHz~MHz），磁通门会整段漏掉\n'
          '· 所以 RCMU 常做成"ZCT/霍尔(交流) + 霍尔/磁通门(直流)"两通道或三通道结构',
          fontsize=11.0, color='#333', va='top', linespacing=1.5)

fig.savefig(OUT, dpi=150, facecolor='white')
print('saved', OUT)
