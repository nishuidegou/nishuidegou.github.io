---
layout: post
title:  "Julia 三件套：UnderwaterAcoustics + AcousticsToolbox + AcousticRayTracers 建内河水下模型"
date:   2026-09-29 09:20:00 +0800
categories: julia
---

上一篇讲了 [`UnderwaterAcoustics.jl`](https://github.com/org-arl/UnderwaterAcoustics.jl) 单独用的时候有哪些坑。但内河建模真正要的是"随程水深 + 随程声速 + 淤泥床面 + 多径结构"这套组合，而**这些能力没有一个包全都有**——真正的 Bellhop / Kraken / Orca 在 [`AcousticsToolbox.jl`](https://github.com/org-arl/AcousticsToolbox.jl) 里，动态光线积分在 [`AcousticRayTracers.jl`](https://github.com/org-arl/AcousticRayTracers.jl) 里。本文把三个包装到一起，实测它们**怎么协同、每个模型到底能吃什么、以及它们之间为什么会打架**。

所有数字都是本机跑出来的：Julia 1.13 / Ubuntu 22.04，`UnderwaterAcoustics` v0.8.1、`AcousticsToolbox` v0.8.0、`AcousticRayTracers` v0.5.1。

## 一、先把三件套的分工说清楚

`UnderwaterAcoustics` 是**骨架**：它定义 `UnderwaterEnvironment`（环境）、`SampledField`（任意维度任意位置的物理场）、`AcousticSource` / `AcousticReceiver`（声源与接收点）、以及统一的 `transmission_loss` / `acoustic_field` / `arrivals` / `channel` 四个调用入口。另外两个包都只依赖它、不依赖彼此。

```
UnderwaterAcoustics v0.8.1  ←──  AcousticRayTracers v0.5.1   （RaySolver，纯 Julia，SciML 动态光线）
      ↑
      └──  AcousticsToolbox v0.8.0  （Bellhop / Kraken / Orca，走 OALIB Fortran 二进制）
```

**加载顺序有实际后果**：`models()` 返回的是"当前已加载"的所有模型。只 `using UnderwaterAcoustics` 时是五个：

```
AdiabaticExt, PekerisModeSolver, Reframe2DMode, PekerisRayTracer, Reframe2DRay
```

`using AcousticRayTracers` 多一个 `RaySolver`；`using AcousticsToolbox` 再多五个，全装齐是：

```
AdiabaticExt, PekerisModeSolver, Reframe2DMode, PekerisRayTracer, Reframe2DRay,
RaySolver, Bellhop, BellhopJL, Kraken, KrakenJL, Orca
```

所以"文档里说有 Bellhop 但我这儿 `models()` 里没有"这类问题，答案永远是**先 `using`**。

许可证也要注意：`UnderwaterAcoustics` 和 `AcousticRayTracers` 都是 MIT；但 `AcousticsToolbox` 是**按目录分别授权**的——`src/bellhopjl/` 和 `src/krakenjl/`（`BellhopJL` / `KrakenJL` 这两个纯 Julia 端口）是 GPL-3.0-or-later，因为它们是 GPL 的 Bellhop / KRAKEN 的衍生作品。作者已经明说：**只要这两个目录在源码树里，整个包的再分发就受 GPL-3.0 约束**；只要 MIT 条款，就把这两个目录删掉（其余代码不依赖它们）。内河的工程代码通常不受影响，但闭源交付前值得确认一下。

## 二、`AcousticsToolbox.jl`：把 OALIB 搬进 Julia

它做的事是把 OALIB Acoustics Toolbox 的 Fortran 内核用 `AcousticsToolbox_jll` 提供的预编译二进制包起来，**不需要你自己装 gfortran、也不需要编译**。暴露出来的模型有 5 个：

| 模型 | 算法 | 内核 | 关键参数 |
|------|------|------|---------|
| `Bellhop` | 波束（几何 / 高斯） | Fortran 可执行文件 | `nbeams`、`min_angle`、`max_angle`、`beam_type`、`beam_shift` |
| `BellhopJL` | 同上 | 纯 Julia 端口，无文件 I/O | 同上 |
| `Kraken` | 简正波（KrakenC） | Fortran | `nmodes`、`mesh_density`、`clow`、`chigh`、`rmax`、`complex_solver` |
| `KrakenJL` | 同上 | 纯 Julia 端口，多线程 | 同上 |
| `Orca` | 简正波 | Fortran | `dz`、`cphmin/cphmax`、`rmin/rmax` |

三个硬性几何约束来自 `.env` 文件格式本身，写之前就会检查：

```julia
location(tx).x == 0            # 声源必须在原点
location(tx).y == 0            # 且在 x–z 平面内
all(location(rx).x >= 0 …)     # 接收点必须在 +x 半空间
```

**所以"我的声源在河道起点 500 m 处"这类情形不能直接建模**——要么把域整体平移，要么用 `Reframe2D` 把它搬到原点（见第七节）。

Bellhop 的 `beam_type` 构造器只接受 `:geometric`（写 `'G'`）和 `:gaussian`（写 `'B'`）两个值。虽然源码里还留着 `:cartesian`（`'C'`）和 `:ray_centered`（`'R'`）的分支，**但构造器的校验会直接拒绝**，报 `Unknown beam_type type`——文档和代码在这点上不一致，知道就行，别去试。

默认 `nbeams = 0` 表示自动，按 `(max_angle - min_angle) / 0.05° + 1` 算；默认扇面 ±80°，于是**自动值是 3201 根束**。浅水波导里这个默认值既慢又没必要收这么宽，建议自己给 `min_angle=-70°`、`max_angle=70°`、`nbeams=1000`。

### 一个真正的惊喜：纯 Julia 端口复现了 Fortran 内核

`BellhopJL` / `KrakenJL` 是作者自己做的原生 Julia 移植，理论上最容易出偏差。实测同一个算例（常深 12 m，刚性底，\(c=1450\) m/s，\(T=15\) °C，\(S=0\)，300 Hz，源 \((0,-3)\)，接收点 \((200,-6)\)）：

| 模型 | TL | 到达/模态数 | 耗时 | 与 Bellhop 之差 |
|------|----|-----------|------|--------------|
| `Bellhop`（Fortran） | 32.15 dB | 190 条 | 2.17 s | — |
| `BellhopJL`（纯 Julia） | **32.15 dB** | **190 条** | 3.07 s | **0.00 dB** |
| `Kraken`（Fortran） | 32.11 dB | 4 阶 | 0.98 s | — |
| `KrakenJL`（纯 Julia） | **32.11 dB** | **4 阶** | 8.92 s | **0.00 dB** |
| `Orca` | 32.73 dB | 5 阶 | 1.10 s | +0.58 dB |

**四个模型、两对独立实现，逐位吻合。** 声场网格（51×11）上 `Bellhop` 与 `BellhopJL` 的最大偏差是峰值的 **0.019%**。

这意味着：**如果你要可微、要避免文件 I/O、要可复现（不受二进制版本影响），直接用 `BellhopJL` / `KrakenJL` 是安全的**，不用拿 Fortran 版当"标准答案"去校验。端口的谱系和每一处有意的偏离都写在仓库的 `src/bellhopjl/PORTING_NOTES.md` 里，包括"落在边界上"这个 Fortran 原版的已知不可复现问题是怎么被修掉的。

不过纯 Julia 端口**不总是更快**。实测 51×11 的声场：`Bellhop` 2.81 s，`BellhopJL` 3.82 s（慢 0.73 倍）；`Kraken` 0.98 s，`KrakenJL` 8.92 s（慢 9 倍）。小网格上是文件 I/O 开销占优，大网格、批量调用、或者要挂自动微分时，`JL` 版本的优势才会显出来。

## 三、`AcousticRayTracers.jl`：唯一能给出完整射线路径的

`RaySolver` 和 `Bellhop` 都是射线/波束法，但定位不同：

- `Bellhop` 是**波束法**——每根束代表一族射线，能高效求声场，但"到达"是波束交点反推出来的。
- `RaySolver` 是**动态光线积分**（SciML：`OrdinaryDiffEq` + `NonlinearSolve`），逐条积分带符号距离的事件方程。

结果是 `RaySolver` 给出的 `RayArrival` 带**完整路径点序列** `path`，可以画出每一条多径的折线；到达时刻也和 `Bellhop` 完全对得上。实测同一算例（常深 12 m、淤泥床、\(f_s=8\) kHz 冲激响应）：

| k | `ns` | `nb` | `RaySolver` 走时 | `Bellhop` 走时 | Δt |
|---|-----|-----|----------------|---------------|-----|
| 1 | 0 | 0 | 0.13795 s | 0.13795 s | 0.0 ms |
| 2 | 1 | 0 | 0.13807 s | 0.13807 s | 0.0 ms |
| 3 | 0 | 1 | 0.13832 s | 0.13832 s | 0.0 ms |
| 4 | 1 | 1 | 0.13869 s | 0.13869 s | 0.0 ms |
| 5 | 1 | 1 | 0.13918 s | 0.13918 s | 0.0 ms |
| 6 | 2 | 1 | 0.13980 s | 0.13980 s | 0.0 ms |
| 7 | 1 | 2 | 0.14053 s | 0.14053 s | 0.0 ms |
| 8 | 2 | 2 | 0.14138 s | 0.14138 s | 0.0 ms |

前 8 条最强多径的走时**逐位相同**（总数 22 vs 16，差别在弱路径的截断阈值上）。

**但绝对声强对不上。** 12 m 等深、\(c=1450\) m/s、淤泥床，扫频率（全部取非相干 TL）：

| 频率 | `Bellhop` | `BellhopJL` | `Kraken` | `RaySolver` | `RaySolver` 偏差 |
|------|-----------|------------|----------|------------|----------------|
| 500 Hz | 35.60 | 35.60 | 35.66 | 39.03 | +3.4 dB |
| 1 kHz | 35.60 | 35.60 | 35.69 | **51.18** | **+15.6 dB** |
| 2 kHz | 35.60 | 35.60 | 35.67 | 34.26 | −1.3 dB |
| 3 kHz | 35.60 | 35.60 | 35.65 | 34.86 | −0.7 dB |
| 5 kHz | 35.60 | 35.60 | 35.65 | 38.21 | +2.6 dB |

另外三个模型的非相干 TL 在 5 个频点上稳定在 35.6 dB（彼此差 0.09 dB 以内），`RaySolver` 却一路跳动。**结论很清楚：`RaySolver` 用来看走时和到达结构是可靠的，用来做绝对声强不可靠。** 这不奇怪——动态光线法要算严格的几何扩散和每条路径的透镜/反射系数，任何一处幅度约定不一致都会整体偏移，而到达时刻对幅度约定不敏感。

还有一个**弹性床面的行为差异**：给 `RaySolver` 配 `ElasticBoundary`（带剪切波速度）时，它会打印 `Warning: Fluid-solid reflection not implemented, ignoring shear...`，然后**丢掉剪切波继续算**；而 `Bellhop` 和 `Kraken` 是真的按弹性界面算的。实测淤泥弹性底（\(\rho=1750\)、\(c_p=1700\)、\(c_s=25\) m/s、\(\delta=0.5\)）在 200 m 处：`Bellhop` 38.39 dB、`Kraken` 38.53 dB、`RaySolver` 40.58 dB。**要严格处理弹性界面就别用 `RaySolver`。**

### `RaySolver` 的性能是个真问题

常深 12 m 等声速下，5 个接收点：

| 模型 | 耗时 |
|------|------|
| `Kraken` | 0.98 s |
| `Orca` | 1.10 s |
| `Bellhop` | 2.17 s |
| `BellhopJL` | 3.07 s |
| **`RaySolver`** | **48 s** |
| **`RaySolver`（随程 SSP）** | **965 s** |

带随程声速剖面时更夸张——5 个点跑了 **16 分钟**。原因是它的快速路径（`_gradient_discontinuities`、`_prepare_trace`）只对 `SampledFieldZ` 那样的深度单向剖面做了专门优化；换成 x–z 二维剖面就退回通用 ODE 积分，代价是两个数量级。

**实践上：批量算场用 `Bellhop`；只在需要逐条路径或精确走时时用 `RaySolver`，并且只用在少量接收点上。**

## 四、能力矩阵：每个模型到底能吃什么

这是本文最该抄走的一张表。全部来自实跑，**不是文档承诺**（很多报错只在调用时才抛）。

| 能力 | `Bellhop` | `BellhopJL` | `Kraken` | `KrakenJL` | `Orca` | `RaySolver` | `PekerisRayTracer` | `PekerisModeSolver` |
|------|-----------|------------|----------|------------|-------|------------|------------------|---------------------|
| 随程水深（`SampledFieldX`） | ✓ | ✓ | ✗ | ✗ | ✗ | ✓ | ✗ | ✗ |
| 随程 SSP（`SampledFieldXZ`） | ✓ | ✗ | ✗ | ✗ | ✗ | ✓（慢） | ✗ | ✗ |
| 深度单向 SSP（`SampledFieldZ`） | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✗ | ✗ |
| 等声速要求 | — | — | — | — | — | — | **必须等声速** | — |
| 弹性 / 多层床面 | ✓ | ✓ | ✓ | ✓ | ✓ | 忽略剪切波 | ✓ | ✗ 仅流体 |
| 返回完整路径 `path` | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | — |
| 声场（整面 TL） | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| `ForwardDiff` 可微 | **静默 0** | NaN（对源深 ✓） | **静默 0** | — | — | ✓ | ✓ | ✓ |
| 走外部二进制 | ✓ | — | ✓ | — | ✓ | — | — | — |

具体的报错原文，抄下来省得再去翻源码：

| 触发条件 | 报错 |
|---------|------|
| `Kraken` / `KrakenJL` / `Orca` + 随程水深 | `Range-dependent bathymetry not supported` |
| `Kraken` / `KrakenJL` / `Orca` + 随程 SSP | `Range-dependent soundspeed not supported` |
| `PekerisRayTracer` / `PekerisModeSolver` + 随程场 | `Environment must be range independent` |
| `PekerisRayTracer` + 非等声速 | `Environment must be iso-velocity` |
| `PekerisModeSolver` + 弹性底 | `Seabed must be a fluid boundary` |
| `BellhopJL` + 随程 SSP | `MethodError: no method matching (::SampledFieldXZ)(::Float64)` |
| `Orca` + 声场 | `SystemError: opening file "…/modes_tlc.bin": 没有那个文件或目录` |
| SSP 的 `x` 网格没盖住最远接收点 | Bellhop: `ray is outside the box where the soundspeed is defined` |
| 接收点网格里含 `x = 0` | 返回 `+Inf` dB（105 点里 5 个 `Inf`，全在源平面） |

**看清这张表，一个结论就出来了**：想同时要"随程水深 + 随程 SSP"，在实测可用的组合里**只有 `Bellhop`（和 `RaySolver` 的走时）**。`BellhopJL` 虽然在常深下复现 Fortran 逐位一致，但一遇到二维 SSP 就 `MethodError`。

## 五、三件套真正的桥梁：`AdiabaticExt`

那"模态解很准但只能处理常深"这个矛盾怎么破？答案在上表之外：**`AdiabaticExt(模型类型, env)`**。

它把环境沿程切成一段段常深子问题，每段用内层模型算一次，再把模态相位和幅度按绝热假设拼起来。**于是 `Kraken` / `Orca` 这些"不能处理随程水深"的模态解，就能吃下真实的深槽—浅滩河床了。**

注意签名是**两个参数**，第一个是模型类型：

```julia
AdiabaticExt(PekerisModeSolver, env)   # 内建模态解
AdiabaticExt(Kraken, env)              # 外部模态解
AdiabaticExt(Orca, env)
```

写成 `AdiabaticExt(env)` 会得到一个把整个环境类型展开成上千字符的 `MethodError`，看起来像环境本身有问题，其实只是少了个参数。

实测随程水深 6→10→15→12 m、接收点在 200 m（当地水深 10 m）处：

| 模型 | TL | 状态 |
|------|----|------|
| `Bellhop` | 31.98 dB | 直接可用 |
| `BellhopJL` | 31.98 dB | 直接可用 |
| `RaySolver` | 31.98 dB | 直接可用 |
| `AdiabaticExt` + `PekerisModeSolver` | 33.91 dB | 需套壳 |
| `AdiabaticExt` + `KrakenJL` | 33.91 dB | 需套壳 |
| `AdiabaticExt` + `Kraken` | 33.90 dB | 需套壳 |
| `AdiabaticExt` + `Orca` | 35.31 dB | 需套壳 |
| 裸 `Kraken` / `Orca` | — | `Range-dependent bathymetry not supported` |
| 裸 `PekerisRayTracer` / `PekerisModeSolver` | — | `Environment must be range independent` |

这里有两层信息值得记：**（1）** 三个独立实现的射线/波束模型（`Bellhop`、`BellhopJL`、`RaySolver`）在同一个随程河床上给出**完全相同的 31.98 dB**；**（2）** 模态路线内部自洽（`PekerisModeSolver` 与 `KrakenJL` 差 0.01 dB），但整体比射线路线高约 1.9 dB——绝热近似的固有偏差，量级正常，可以接受，但**做定量预算时别把两条路线的结果混着平均**。

## 六、弯河段怎么办：`Reframe2D` 的真实边界

内河平面曲率大（上文那篇急弯算例 \(R/B \approx 2.5\)），而所有这些模型都是 x–z 竖直面模型。`Reframe2D` 就是为这件事准备的：把声源平移旋转到原点、把环境一起变换，让一条弯曲测线能被 2D 模型处理。

**但它有一个文档没写清、实测才暴露的限制：接收点必须与声源共面。**

实测 \(R = 1500\) m、转角 40°、随程水深 + 随程 SSP 的弯河段：

| 做法 | 结果 |
|------|------|
| 直接 `Bellhop(env)` | `2D model requires receivers in the x-z plane` |
| 直接 `RaySolver(env)` | `RaySolver requires receivers in the x-z plane` |
| 直接 `Kraken(env)` | `Range-dependent soundspeed not supported` |
| `Reframe2D(Bellhop, env)` + 5 个弧长站 | `Scenario is not 2D: receivers deviate up to 79.2 m from the vertical plane containing the source (atol = 0.1 m)` |
| `Reframe2D(Kraken/RaySolver, env)` | 同上，报错数字完全一样（79.2 m） |

`atol` 默认只有 0.1 m，而弯河段上偏离源点所在竖直平面的距离能到 **79.2 m**——差 792 倍，所以调 `atol` 是没有意义的，正确做法只有两条：

1. **逐接收点单独跑**（库自己在报错里就是这么建议的）。每个点单独构造 `Reframe2D(Bellhop, env)` 并只传一个 `AcousticReceiver`，实测 5 个点共 **8.17 s**，得到 44.41 / 51.11 / 63.95 / 72.95 / 58.47 dB。顺带说明：**两个接收点时 `Reframe2D` 一定不会报错**（三点定面），所以只布两站的层析方案走这条路没问题，一旦布成弧形多站就会撞墙。
2. **按弧长把河段"拉直"**：以中心线弧长 \(s\) 为横坐标建环境（随程水深、随程 SSP 都按 \(s\) 索引），测线两端按各自的弧长位置放。这本来就是二维声学模型对弯曲河道的标准近似。

## 七、一套能直接抄的内河建模流程

把三件包装到一起之后，流程可以固定成这样：

1. **装三个包**，`using` 三个模块，用 `models()` 确认 11 个模型都在。注意许可证（见第一节）。
2. **建环境**：`bathymetry` 填**正水深**；随程水深用 `SampledField(h(s); x=s)`；随程 SSP 用 `SampledField(matrix; x, z)`，注意**矩阵是 x-major**（第 1 维 x、第 2 维 z），`x` 要铺到最远接收点之外，**接收点网格不要含 `x = 0`**。`salinity = 0`、`soundspeed` 显式给淡水值。**打印一次环境，确认水深是正数、采样数非零。**
3. **选模型**：需要随程水深 + 随程 SSP → `Bellhop`（要可微/免文件 I/O 就 `BellhopJL`，但常深才行）；要严格模态 → `AdiabaticExt(Kraken, env)`；要逐条多径路径和精确走时 → `RaySolver`（少量接收点）；要快速敏感性扫描 → `PekerisRayTracer`（只看趋势）。
4. **定声学量**：`transmission_loss` / `arrivals` / `acoustic_field` / `channel` 四个入口对所有模型统一，**但 TL 一律显式传 `mode=:incoherent`**（实测 500 Hz–5 kHz 稳定在 35.6 dB，而默认的相干结果在 32.7–47.1 dB 之间乱跳）。`Kraken` 的 `clow` / `chigh` 默认 1300 / 2500 是给海洋调的，浅水河里建议收紧到实际声速附近。
5. **水体吸收**：`absorption(f, 1.0, S, T, d, pH)` 返回的是**比值不是 dB**，要自己 `-20log10(...)×1000`。而且 Francois–Garrison 是海水模型，\(S=0\) 时吸收几乎全部退场（300 Hz 淡水 0.00002 dB/km vs 海水 0.0057 dB/km，差 245 倍），**内河的悬沙衰减只能外部标定后在 TL 上叠加**。这一步别省。
6. **交叉验证**（最省事也最有效的一步）：同一个算例至少跑两个模型。本文里 `Bellhop` / `BellhopJL` / `Kraken` / `Orca` 的非相干 TL 差 0.09 dB 以内，三个射线实现对随程河床差 0.00 dB——**一旦某个模型偏离十几 dB，你立刻知道该怀疑谁。**
7. **补二维限制**：柱面 → 球面展布的 3–6 dB 修正，加一次"对建模面选取的敏感性分析"。这是弥补没有三维模型唯一有效的手段。

## 八、几个值得单独记住的坑

1. **`absorption` 返回比值不是 dB。** 直接 `println(absorption(300.0))` 打出 `0.9999981`，看起来像"约 1 dB"，真实值是 0.0057 dB/km，差 200 倍。
2. **Fortran 内核的自动微分会静默返回零梯度。** 对水深求 \(\partial\mathrm{TL}/\partial h\)：`PekerisModeSolver` 给 −179.13996（差分 −179.13990，完全一致）、`PekerisRayTracer` 给 −0.70577（一致）、`RaySolver` 给 −226.11（差分 −217.99，差 3.7%），而 `Bellhop` 和 `Kraken` 都给 **精确的 0.0**。原因是 `Dual` 要写进 `.env` 文本文件，落盘前就被截成 `Float64`。**不报错，梯度下降会以为目标函数是常数而第一步就"收敛"。** 用 Fortran 版就必须上有限差分，并且每次拿中心差分验证。
3. **`BellhopJL` 的可微性只对源深成立。** \(\partial\mathrm{TL}/\partial z_{src}\)：AD 给 −2.489206549729791，中心差分给 −2.4892065551895826，9 位有效数字吻合；但对水深直接给 `NaN`。
4. **`Kraken` 在 12 m 浅水里做 5 kHz 冲激响应会崩。** `transmission_loss` 还能算（67 阶模），但 `channel` / `impulse_response` 触发 `Failure to converge in RootFinderSecant`，然后 `STOP Fatal Error`。模态根求解器在浅水高频下本来就吃力。**浅水高频河段别指望模态解的冲激响应。**
5. **接收点别放 `x = 0`。** Bellhop 在零距离返回 `+Inf` dB，会把整个统计量污染掉。
6. **`SampledField` 的矩阵是 x-major。** 和图像处理的直觉相反，写反报 `knot vectors must have the same axes as the corresponding dimension of the array`。

## References

- *UnderwaterAcoustics.jl* — MIT License. https://github.com/org-arl/UnderwaterAcoustics.jl
- *AcousticRayTracers.jl*（RaySolver）— MIT License, ARL. https://github.com/org-arl/AcousticRayTracers.jl
- *AcousticsToolbox.jl*（Bellhop / Kraken / Orca / BellhopJL / KrakenJL）— MIT + GPL-3.0 双许可，按目录划分. https://github.com/org-arl/AcousticsToolbox.jl
- Michel, H. (2024). *Acoustics Toolbox 2024_12_25* (OALIB). http://oalib.hlsresearch.com/AcousticsToolbox/
- Porter, M. B., et al. (2018). *User's Guide for BELLHOP Rev 5.2.* Naval Research Laboratory.
- Porter, M. B., & Yarger, W. J. (1987). *User's Guide for KRAKEN.* Naval Research Laboratory.
- Francois, C. M., & Garrison, C. F. (1982). An equation for absorption in water. *JASA*, 72(2), 390–395.
- 上一篇：[用 Julia UnderwaterAcoustics.jl 自建内河水下模型](/julia/2026/09/28/julia-underwater-acoustics-river-model/)
