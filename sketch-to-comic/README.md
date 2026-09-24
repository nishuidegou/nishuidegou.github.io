# sketch-to-comic 使用说明

手绘草图 -> 漫画风格图片 / 激光雕刻矢量文件 的两组脚本。

依赖：`python3` + `opencv-python` + `numpy`

```bash
pip install opencv-python numpy
```

## 1. sketch_to_comic.py —— 草图转漫画

把手绘草图转成彩色分块 or 线条墨稿，支持多张拼版。

### 常用命令

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

### 参数

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

### 常用命令

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

### 参数

| 参数 | 默认 | 说明 |
|------|------|------|
| `input` | 必填 | 输入草图 |
| `-o / --output` | 必填 | 输出文件，扩展名决定格式：`.dxf` / `.svg` / `.gcode` `.gco` `.nc` |
| `--scale` | `1.0` | 坐标缩放倍数（px -> mm 常用 0.1 左右） |
| `--denoise` | `2` | 中值模糊核大小，去噪 |
| `--min-area` | `0` | 丢弃小于该像素数的噪点块（0 表示全保留） |
| `--simplify` | `0.0` | 折线简化容差（px），越大路径越精简 |
| `--power` | `600` | 激光功率（仅 G-code） |
| `--feed` | `3000` | 进给 mm/min（仅 G-code） |

## 典型流程

```text
手绘草图(拍照/扫描)
  ├─ sketch_to_comic.py ──> 漫画图（社交分享）
  └─ sketch_to_laser.py ──> DXF/SVG ──> 激光软件 ──> 雕刻
```