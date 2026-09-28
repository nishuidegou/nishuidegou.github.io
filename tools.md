---
layout: page
title: 绘图脚本使用说明
permalink: /sketch-to-comic/usage/
---

本博客里的技术插图都是用 Python 脚本程序化生成的，源码都在仓库
[`sketch-to-comic/`](https://github.com/nishuidegou/nishuidegou.github.io/tree/master/sketch-to-comic) 目录，
改参数重跑即可复现任意尺寸的图。

依赖：`python3` + `numpy` + `opencv-python`（前两个脚本用）+ `matplotlib`（后两个配图脚本用）

```bash
pip install numpy opencv-python matplotlib
```

脚本分两类：`sketch_to_comic.py` / `sketch_to_laser.py` 是命令行工具，处理你自己拍的草图；
`bend_site_selection.py` / `fluxgate_leakage.py` 是为博客定制的配图脚本，参数直接写在脚本开头。

## 1. sketch_to_comic.py —— 草图转漫画

把手绘草图转成彩色分块或线条墨稿，支持多张拼版。

```bash
# 单张转彩漫
python sketch_to_comic.py input.jpg -o out.png

# 只出线条墨稿（黑白）
python sketch_to_comic.py input.jpg -o out.png --style ink

# 多张拼成一张条漫（3 列）
python sketch_to_comic.py a.jpg b.png c.webp -o strip.png --cols 3

# 加粗墨线
python sketch_to_comic.py input.jpg -o out.png --style ink --ink 3
```

| 参数 | 默认 | 说明 |
|------|------|------|
| `inputs` | 必填 | 输入草图（可多个，至少 1 个） |
| `-o / --output` | 必填 | 输出文件名，按扩展名决定格式（png/jpg/webp…） |
| `--style` | `color` | 漫画风格：`color` 彩色 / `ink` 黑白墨稿 |
| `--ink` | `2` | 墨线膨胀像素数，越大线条越粗 |
| `--cols` | `1` | 多输入拼版列数 |
| `--gutter` | `24` | 拼版间隔（px） |
| `--palette` | `classic` | 配色方案，目前仅 `classic` |

## 2. sketch_to_laser.py —— 草图转激光雕刻矢量

提取草图线条并输出 DXF / SVG / G-code，可直接喂给激光雕刻机。

```bash
# 输出 DXF（激光软件通用）
python sketch_to_laser.py input.jpg -o out.dxf

# 输出 SVG，缩放 0.1 倍并简化折线
python sketch_to_laser.py input.jpg -o out.svg --scale 0.1 --simplify 0.5

# 输出 G-code，设定功率/进给
python sketch_to_laser.py input.jpg -o out.gcode --power 800 --feed 3000

# 去掉小于 50px 的噪点
python sketch_to_laser.py input.jpg -o out.dxf --min-area 50
```

| 参数 | 默认 | 说明 |
|------|------|------|
| `input` | 必填 | 输入草图 |
| `-o / --output` | 必填 | 输出文件，扩展名决定格式：`.dxf` / `.svg` / `.gcode` `.gco` `.nc` |
| `--scale` | `1.0` | 坐标缩放倍数（px → mm 常用 0.1 左右） |
| `--denoise` | `2` | 中值模糊核大小，去噪 |
| `--min-area` | `0` | 丢弃小于该像素数的噪点块（0 表示全保留） |
| `--simplify` | `0.0` | 折线简化容差（px），越大路径越精简 |
| `--power` | `600` | 激光功率（仅 G-code） |
| `--feed` | `3000` | 进给 mm/min（仅 G-code） |

## 3. bend_site_selection.py —— 弯道声学层析两站布设

没有命令行参数，参数写在脚本开头（第 12–14 行），输出到
`assets/images/river-bend-tomography-sites-125deg.png`，对应文章
《大河弯道声学层析两站布设：弯顶径向、顺直段斜交》。

| 变量 | 默认 | 说明 |
|------|------|------|
| `R` | `2200.0` | 弯道半径（与河宽同单位） |
| `W` | `300.0` | 半河宽 |
| `turn` | `125°` | 弯道转角，写成弧度 `np.deg2rad(125.0)` |

## 4. fluxgate_leakage.py —— 零磁通闭环与残流频段

同样没有命令行参数，布局常量集中在脚本里，输出到
`assets/images/fluxgate-leakage-overview.png`，对应文章
《磁通门电流传感器与漏电检测》。左栏画零磁通闭环链路（励磁/检测/补偿绕组、解调、积分器、H 桥），
右栏画残流成分在频率轴上的位置与 ZCT、霍尔、磁通门三者的覆盖范围。

中文字体依赖 Noto CJK：

```python
font_manager.fontManager.addfont('/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc')
plt.rcParams['font.family'] = 'Noto Sans CJK JP'
```

换机器时如果报字体缺失，把上面这行路径改成系统里任意一个 CJK 字体即可。

## 典型流程

```text
手绘草图(拍照/扫描)
  ├─ sketch_to_comic.py ──> 漫画图（社交分享）
  └─ sketch_to_laser.py ──> DXF/SVG ──> 激光软件 ──> 雕刻
```
