---
layout: post
title:  "用 Julia UnderwaterAcoustics.jl 自建内河水下模型"
date:   2026-09-28 16:40:00 +0800
categories: julia
---

内河不是海洋的小版本。把它按"浅一点、窄一点的海"来建模型，误差会出现在每一个环节：水深只有 6–15 m、床面是松散淤泥、悬沙把水体吸收抬高两个量级、平面又大角度弯曲。Julia 生态里的 [`UnderwaterAcoustics.jl`](https://github.com/org-arl/UnderwaterAcoustics.jl)（ARL @ NUS，MIT 许可，当前 v0.8.1）是少数把"环境 → 场 → 传播模型 → 信道"整条链路做成可编程对象的开源库，本文按实测结果梳理用它自建内河模型时**必须知道的事情**——包括几个在文档里查不到、只有在实跑中才会暴露的坑。

## 一、库的定位：先分清"是什么"和"不是什么"

网上（含模型自己生成的）关于这个库的 API 描述有大量失真。上手前先把边界划清楚，能省掉几天时间。

**它是**：一个水声传播建模框架。核心对象是 `UnderwaterEnvironment`（环境）、`SampledField`（任意维度、任意位置的物理场）、几个传播模型（`PekerisRayTracer`、`PekerisModeSolver`、`AdiabaticExt`）、以及一个信道层（`channel` / `transmit`）。作者把它定位成**可微分**的建模框架，于是"用实测走时反演河床参数"可以变成常规最优化问题——这也是它在学术圈被采用的主要原因（作者由此入选 OCEANS 2023 Limerick）。

不过"可微分"这件事必须按模型逐个核实，**不能想当然**：实测对水深 $h$ 求 $\partial \mathrm{TL}/\partial h$，两个内建纯 Julia 模型给出与中心差分完全一致的梯度，而走外部二进制的 `Bellhop` / `Kraken` 会**静默返回 0.0**（不报错，优化器会以为目标函数是平的直接停住），`BellhopJL` 返回 `NaN`。细节见 [姊妹篇](/julia/2026/09/29/julia-acoustics-toolbox-raytracers-river/)。

**它不是**：

- 不是全频段工具。它是**窄带**的：源只给一个标称频率，所有传播效应（吸收、反射系数）都按这个单频计算。
- 不是三维工具。它的所有模型都在 **x–z 竖直平面**里工作，没有横向 y 的声学。这对内河是硬约束，第四节专门讨论。
- 不是随机起伏介质工具。没有海浪谱（无 JONSWAP / Pierson-Moskowitz），没有随机粗糙面，没有体积散射体建模。自由面只有一个边界条件（`PressureReleaseBoundary` / `WindySurface`），要自己叠加波面起伏得在外面做。
- 不是信号处理库。频响、检测、匹配滤波这些都不在里面（作者明确把它列在 roadmap 的"out of scope"）。
- 不是一个自带计算内核的"全家桶"。真正的 Bellhop / Kraken / Orca 在独立包 [`AcousticsToolbox.jl`](https://github.com/org-arl/AcousticsToolbox.jl) 里，RayTracer 在 [`AcousticRayTracers.jl`](https://github.com/org-arl/AcousticRayTracers.jl) 里，要单独安装、单独 `using` 才会出现。

版本上要注意 0.3 → 0.4 那次大改：`IsoSSP` / `SampledSSP` / `PointSource` / `Pinger` / `SphericalReceiver` 这些类型和 `simulate` / `record` 这类函数**在 0.4 已经被移除**，声速剖面统一收敛到 `SampledField`。网上和论文里残留的旧教程基本都不能直接跑。

## 二、坐标系：最容易翻车、也最该先搞清楚的一件事

这个库用 **`z` 向上为正、水面在 `z = 0`、水下一切为负**的约定。河床位于 $z = -h$，但 `bathymetry` 这个参数本身存的是**水深 $h$（正数）**，不是高程。库内部自己会做一次取负：`AdiabaticExt` 写的是 `z0 = -value(env.bathymetry, …)`，`AcousticRayTracers` 写的是 `zmin = -maximum(env.bathymetry)`，`AcousticsToolbox` 写的是 `waterdepth = maximum(bathy)`——三处独立实现都是"收到正水深、内部取负"，所以三个包之间天然一致。

官方测试用例也全部用正数：`bathymetry = 20.0u"m"`、`bathymetry = 5000`、`SampledField([200, 150, 200]; x=[0, 2000, 5000])`。唯一默认值也是 `bathymetry = 100.0`（米）。

**传负高程进去不会立刻报错，而是会静默退化成 0 阶模、射线穿过床面之类的诡异现象**——因为下游那些 `-value(...)` 会在负水深上再做一次取负，等价于把床面放到水面之上。判断自己有没有搞反，最快的办法是运行 `UnderwaterEnvironment(bathymetry = 你的水深)` 看打印：应当显示一个正数。

> 顺带区分一个容易混的量：**OALIB 原始的 `.env` 文件里也是用正深度**（而且距离单位是千米），Julia 这一层已经帮你转换过了，不需要自己再乘除。

第二件事更隐蔽：**`bathymetry` 沿程变化时要用 `SampledField` 的一维形式按程取值**，而不是拼一个二维 x–z 场。二维形式（`SampledField(matrix; x, z)`）是给随程声速剖面 SSP 用的。

这里有四个实测踩到的格式坑：

- **矩阵是 x-major 的**：第 1 维对应 `x`、第 2 维对应 `z`，和图像处理 / `meshgrid` 的直觉相反。写反了会报 `knot vectors must have the same axes as the corresponding dimension of the array`。
- **`x` 和 `z` 都必须严格递增**。`z` 写反（`0 : 0.25 : -20`）报 `knot-vectors must be unique and sorted in increasing order`；更隐蔽的是**空区间**——步长方向反了会得到长度为 0 的向量，字段照样构造成功、照样打印，只是 `161×0 samples`，模型"能跑"但物理上完全无意义。任何时候都该看一眼环境打印里的采样数。
- **SSP 的 `x` 网格必须覆盖整条传播距离**。只给到 600 m 而接收点在 1000 m，Bellhop 会直接 `ray is outside the box where the soundspeed is defined`。实测做随程 SSP 时把 `x` 一直铺到最远接收点之外才稳定。
- **不要把 `x = 0`（源平面）放进接收点网格**。Bellhop 在零距离处返回 `+Inf` dB，实测 105 个网格点里有 5 个是 `Inf`，全在 `x = 0` 那一列。

一维场（声速剖面）可以用 `CubicSpline()`，但有两个硬性前提：`z` 必须是 `AbstractRange`（不能是 `collect` 出来的 `Vector`），而且**值的个数必须与 z 的长度严格相等**。不满足会报 `attempt to access 21-element Vector at index [22]` 这种看起来毫不相关的错。

## 三、内河的物理输入：三条与海洋截然不同的设定

### 3.1 声速：淡水在常温区几乎不随温度变

这是内河建模最反直觉、也最重要的一条。库默认的 `soundspeed` 是 **1538.92 m/s**、密度 1022.72 kg/m³——这是 27 °C 海水。内河必须显式改掉。

用 Chen & Millero (1977) 淡水公式算一遍夏季分层（底层 19 °C、表层 26 °C、水深 16 m）：

| 深度 | 温度 | 淡水声速 |
|------|------|---------|
| 0 m（表层） | 26.0 °C | 1404.1 m/s |
| 8 m | 22.5 °C | 1404.0 m/s |
| 16 m（底层） | 19.0 °C | 1403.8 m/s |

**Δc ≈ 0.32 m/s**，对应 $\mathrm{d}c/\mathrm{d}z \approx 0.02$ m/s/m，射线转弯半径

$$
\rho_{\text{ray}} \approx \frac{c}{\mathrm{d}c/\mathrm{d}z} \approx \frac{1404}{0.02} \approx 70\ \text{km}
$$

而内河一段的量程是几百米到几公里。**结论：纯淡水河段的折射效应可以忽略，Δc 的物理意义接近于零。** 这不是"精度不够"的问题，而是"这一项本来就不存在"。相应地，内河的多径结构几乎完全由**水面和床面双重反射**决定——这是一个上下都强反射的浅水波导，模态密集、径向间隔很小，但不存在海洋里那种由折射"弯折"出来的远大离轴角路径。

真正需要认真做声速剖面的是**感潮段**（河口以上几十公里的咸淡水过渡区）。用 Mackenzie (1981) 算一条表层冲淡水、底层高盐水的剖面（温度 22→26 °C、盐度 2→30 ppt）：

| 深度 | 温度 | 盐度 | 声速 |
|------|------|------|------|
| 0 m | 26 °C | 2 ppt | 1490.1 m/s |
| 8 m | 24 °C | 21 ppt | 1500.4 m/s |
| 16 m | 22 °C | 30 ppt | 1510.2 m/s |

**Δc ≈ 20 m/s**，是淡水段的两位数倍。这才是折射该起作用的地方。**所以"要不要认真建 SSP"这个问题的答案，取决于河段是否在盐度影响范围内**——对上游纯淡水段，随便给个常数 1404 就够了；对下游感潮段，SSP 是决定性的。

### 3.2 床面：内河是松散沉积物，且要给吸收

库内置了一整套 APL-UW TR 9407 的沉积物常量，映射成 `FluidBoundary`（ρ, c, δ）三元组：

| 常量 | ρ (kg/m³) | c (m/s) | δ |
|------|-----------|---------|-----|
| `Rock` | 2557.5 | 3820.0 | 0.01374 |
| `MediumSand` | 1887.4 | 1800.3 | 0.01624 |
| `MuddySand` | 1369.8 | 1650.2 | 0.01728 |
| `Clay` | 1171.3 | 1497.4 | 0.00148 |

内河主槽以淤泥质砂为主，`MuddySand` 是合理默认。**但注意这几个常量是"流体半空间"模型**：底质没有剪切波速度，反射系数按流体–流体界面算。这对"射线打到床面、算个复反射系数、继续走"的需求是够的（而且正因如此 `PekerisRayTracer` 才不挑床面类型），但如果你要讨论剪切波、横波衰减、界面波，就得上弹性边界（`ElasticBoundary` / `MultilayerElasticBoundary`），而 `PekerisModeSolver` 明确**只接受流体边界**，会直接报 `Seabed must be a fluid boundary`。

多层沉积物用 `MultilayerElasticBoundary([(h, ρ, cₚ, cₛ, δₚ, δₛ), …])`，最后一层 `h = Inf` 表示半空间。冲积河床的典型结构（表层淤泥—中层砂—下层基岩）正好对应这个形式。

### 3.3 水体吸收：内河最大的物理缺口

库的内置吸收是 **Francois & Garrison (1982)**，一个**海水**模型，输入只有温度、盐度、pH。实测同一频率下：

| 频率 | 海水 (S=35, T=27 °C) | 淡水 (S=0, T=22 °C) |
|------|---------------------|---------------------|
| 200 Hz | 0.015 dB/km | ≈ 0.0002 dB/km |
| 1 kHz | 0.053 dB/km | ≈ 0.0013 dB/km |
| 5 kHz | 0.317 dB/km | 0.0052 dB/km |
| 20 kHz | 2.004 dB/km | 0.083 dB/km |

把 `salinity` 设成 0 确实会触发库自动算淡水密度（997.77 kg/m³），但吸收机制本身在盐度为 0 时几乎全部退场，**给出的吸收低到没有物理意义**。而真实的悬沙河段，5–20 kHz 的吸收通常在 0.1–2 dB/km 量级，比上表的淡水值高一到两个数量级。

结论很直接：**内河不能用库内置的吸收值，也不能靠调温度/盐度去凑。** 环境对象里没有"水体吸收"这个可填字段，吸收是内部按公式算死的。可行的做法只有两条：一是把悬沙衰减折进床面参数（不物理，但能凑出量级）；二是**在库外做一次标定**——用同河段实测的走时/声强数据反解一个等效 $\alpha$，然后在拿到 `transmission_loss` 之后统一叠加 $\alpha \cdot R$（dB 直接加），或在拿到冲激响应之后做一次带通滤波。本文后面所有数值都按 $\alpha = 0.8$ dB/km 这个量级做了叠加。

**这是内河建模里唯一一个必须自己补的物理量**，其他都可以交给库。

## 四、二维库怎么装下三维的河：建模面的选择

库的所有模型都在 x–z 竖直平面内。一条内河有三个维度：沿程 s、横向 n、垂向 z。这个二维限制不是 bug，是设计取舍，但它决定了你必须**先选建模面**。

**（一）纵剖面 (s, z)** —— 沿主槽中心线切开的竖直切片。这个面里"程" s 就是声学"距离"，可以完整表达深槽—浅滩序列（沿程水深变化）、床面起伏、以及 SSP。**它是表达"随程变化"唯一可行的建模面。**

**（二）横断面 (n, z)** —— 垂直于主槽的切片。程是河宽，"距离"就是河宽；能表达 V 形断面、深泓偏外岸、两岸浅滩。**跨河测线（以及上一篇《大河弯道声学层析两站布设》里"顺直段连线斜跨断面"那种布设）就落在这个面上。**

**（三）库做不到的事：横向约束。** 两个建模面都没有"河岸"。二维模型的展布是柱面型（cylindrical spreading），而真实内河在短程上更接近球面型（spherical spreading）——**二维模型会系统性高估接收声压**。1.6 km 沿程、400 m 河宽这种尺度上，柱面与球面的差别在 3–6 dB 量级，工程上必须自己补一个横向扩散修正，或者用实测数据标定。**这是内河用这个库时最需要警惕的建模误差，比任何数值细节都大。**

选面的经验规则：**沿程水深变化超过最深水深的一半，就只能走纵剖面 + 距离相关模型；断面形状（深泓位置、岸坡）重要而沿程平坦，就走横断面 + 常深模型。** 弯道的横断面随里程剧变，理论上应该做三维；但既然库做不到，实际做法是"在弯顶切一个横断面、在弯顶前后各取几个断面，看结论对断面选取是否敏感"，用敏感性替代无法实现的三维性。

## 五、平面弯曲：Reframe2D 与"曲率其实不重要"

内河平面曲率很大（前面那篇急弯算例 R/B ≈ 2.5），看上去是三维效应。但实测给了一个很干净的结果。

用 `Reframe2D` 把一条**平面为圆弧**的河段（R = 1500 m、转角 40°、常深 12 m、等声速 1470 m/s、5 kHz）压回竖直建模面，两站放在弧的两端。结果：

| 量 | 弯道（R=1500 m, 40°） | 等效直段（弦长 1026.06 m） |
|----|----------------------|----------------------------|
| 到达数 | 7 | 7 |
| 到达时刻 (ms) | 698.00, 698.01, 698.11, 698.19, 698.19, 698.30, 698.97 | 完全相同 |
| 传输损失 | 49.7874 dB | 49.7874 dB |

**逐位相同。** 原因是：常深、常声速环境下，声线是直线，弯道对它的唯一影响就是把路径长度从弧长换成弦长，而这一点在"两站连线距离"里已经自动包含了。**平面曲率本身不产生任何额外的传播效应。**

这个结论的适用边界要说清楚：

- **常深 + 等声速**：可以直接用直段替代，误差为零。
- **`Reframe2D` 只对"共面"的接收点有效**。上面这个算例只有两个接收点，加上源点，三点永远确定一个平面，所以能过。但**一旦沿弧线布一串接收点就会失败**，实测 R=1500 m、转 40°、5 个弧长站时报 `Scenario is not 2D: receivers deviate up to 79.2 m from the vertical plane containing the source (atol = 0.1 m)`。可行做法就是库自己提示的那条：**逐个接收点单独跑**（每个点单独构造 `Reframe2D(Bellhop, env)` 传单个 `AcousticReceiver`），实测 5 个点共 8.17 s。或者干脆按弧长把河段"拉直"成直段、在 s 坐标下建随程场。
- **沿程水深变化**（真实的内河都是深槽—浅滩交替）：曲率会通过"哪一段的深槽对准了测线"间接起作用。这时真正需要的不是三维模型，而是**距离相关模型 + 局部坐标展开**——把弧形河道按中心线弧长"拉直"成 s 坐标，沿程水深 h(s) 作为距离相关的床面输入，测线两端按各自的弧长位置放置。
- **横向不均匀**（深泓贴外岸、横向流速切变）：曲率的影响通过横向梯度进入，而这是库表达不了的，必须靠第四节说的"横断面敏感性分析"去逼近。

`Reframe2D` 本身的使用要注意一个文档明确警告的点：**变换后的环境只保证在"包含源和接收的竖直平面"上与原环境一致**。所以它是"让一条曲线测线能被 2D 模型处理"的手段，不是"把河湾变成 3D"的手段，平面外的部分一律不要参考。

## 六、传播模型选型：一张实测出来的表

装好库之后 `models()` 会列出当前可见的模型（只有 `UnderwaterAcoustics` 时是 `PekerisRayTracer`、`PekerisModeSolver`、`AdiabaticExt`、`Reframe2DRay/2DMode` 五个；每装一个附加包就多几个）。下表是**实测结果**，不是文档承诺：

| 模型 | 来源 | 随程水深 | SSP(x,z) | 弹性床面 | 实跑状态（v0.8.1 / ART 0.5.1 / AT 0.8.0） |
|------|------|---------|---------|---------|------------------|
| `PekerisRayTracer` | 内置 | ✗ `Environment must be range independent` | ✗ 须等声速 | ✓ | 可用，但只有 7 条路径，比 Bellhop 虚高 **17 dB** |
| `PekerisModeSolver` | 内置 | ✗ 同上 | ✗ | ✗ `Seabed must be a fluid boundary` | 可用（刚性底 5 阶模） |
| `AdiabaticExt` | 内置 | ✓ | ✗ | 取决于内层模型 | **可用**，但签名是 `AdiabaticExt(模型类型, env)`，不是 `AdiabaticExt(env)` |
| `RaySolver` | `AcousticRayTracers` | ✓ | ✓ | 流体（剪切波被忽略并告警） | 可用；随程 SSP 下很慢 |
| `Bellhop` / `BellhopJL` | `AcousticsToolbox` | ✓ | ✓（`BellhopJL` ✗） | ✓ | 可用，推荐主力 |
| `Kraken` / `KrakenJL` / `Orca` | `AcousticsToolbox` | ✗ 需套 `AdiabaticExt` | ✗ 需 `SampledFieldZ` | ✓ | 可用，但必须走 `AdiabaticExt` 才能吃随程河床 |

**给内河的推荐路线**：

1. **定算主力 → `Bellhop`**（或纯 Julia 等价的 `BellhopJL`）。它是唯一能同时吃下随程水深 + 随程 SSP + 弹性床面的选项，量级也和 `RaySolver`、`Kraken` 互相印证到 0.2 dB 以内。代价是外部二进制和一条配置文件路线。细节见姊妹篇。
2. **需要严格模态解、或要压到最小依赖 → `PekerisModeSolver`**（常深）或 **`AdiabaticExt` + `Kraken`**（随程水深）。`AdiabaticExt` 把环境切成一段段常深子问题再拼起来，是让"只能处理常深"的模态模型对付真实河床的桥梁。
3. **要精确多径结构 / 冲激响应 → `RaySolver`**。它是 SciML 动态光线积分，能给出逐条到达的完整路径点序列；纯 Julia 且对水深可微（实测 $\partial\mathrm{TL}/\partial h$ 的 AD 值与差分值差 3.7%），代价是慢——常深 12 m 算 5 个接收点要 48 s，带随程 SSP 同样的活儿要 **965 s**。
4. **粗算 / 敏感性扫描 → `PekerisRayTracer`**。快、纯 Julia、完全可微，但只有 7 条路径，适合看趋势、不适合定量。
5. **内河其实很少需要的东西**：波面起伏模型、随机介质、三维场。省下这些力气，砍刀直接落在床面和吸收上。

## 七、实跑踩到的坑（这一节是本文最有用的部分）

下面几条都是我在 v0.8.1 / `AcousticRayTracers` v0.5.1 / `AcousticsToolbox` v0.8.0 上真实撞到并定位到源码行的，文档和 issue 里都没有。

### 7.1 `AdiabaticExt` 的签名是 `AdiabaticExt(模型类型, env)`

`AdiabaticExt(env)` 会直接抛 `MethodError: no method matching AdiabaticExt(::UnderwaterEnvironment{...})`，而且错误信息把整个环境类型展开成一长串，看起来像环境本身有问题。正确写法是把内层模型类型当第一个参数：

```julia
AdiabaticExt(PekerisModeSolver, env)   # 内建模态解
AdiabaticExt(Kraken, env)              # 外部模态解
```

而且它**确实能处理随程河床**：实测随程水深 6→10→15→12 m、接收点在 200 m，`AdiabaticExt` + `PekerisModeSolver` / `Kraken` / `KrakenJL` / `Orca` 分别给出 33.91 / 33.90 / 33.91 / 35.31 dB，四者内部自洽；同一场景裸调 `Kraken` 则直接 `Range-dependent bathymetry not supported`。**这就是让"只能处理常深"的模态模型对付真实河床的桥梁**，也是内河建模里最该记住的一条。

### 7.2 走外部 Fortran 二进制的模型，自动微分会**静默返回零梯度**

这一条最危险，因为它不报错。实测对水深 $h$ 求 $\partial \mathrm{TL}/\partial h$（常深 12 m，$c=1450$ m/s，300 Hz，源 $(0,-3)$，接收点 $(200,-6)$）：

| 模型 | `ForwardDiff` 梯度 | 中心差分 | 结论 |
|------|------------------|---------|------|
| `PekerisModeSolver` | −179.13996 | −179.13990 | ✓ 完全一致 |
| `PekerisRayTracer` | −0.70577 | −0.70577 | ✓ 完全一致 |
| `RaySolver` | −226.11349 | −217.99682 | ✓ 可微（差 3.7%，数值微分步长所致） |
| `BellhopJL` | **NaN** | −62.16443 | ✗ |
| `Bellhop` | **0.0** | −39.87712 | ✗ 静默零梯度 |
| `Kraken` | **0.0** | −12.02266 | ✗ 静默零梯度 |

原因很直白：`Bellhop` / `Kraken` 要把 `Dual` 写进 `.env` 文本文件，落盘前就被截成 `Float64`，导数信息丢失。梯度变成精确的 0.0，任何梯度下降/牛顿法都会认为目标函数是常数而**在第一步就"收敛"**，而且不抛异常。

`BellhopJL` 是纯 Julia 端口，按设计应该可微，实测**对源深可微**（$\partial\mathrm{TL}/\partial z_{src}$：AD 给 −2.489206549729791，中心差分给 −2.4892065551895826，9 位有效数字吻合），但**对水深给 `NaN`**。所以"用 BellhopJL 做可微反演"这条路目前只对源/接收点位置成立，对河床参数不成立。

**实践建议**：要做反演就用 `PekerisModeSolver` 或 `AdiabaticExt`（完全一致）；要用 `Bellhop` 就老老实实上有限差分或 SPSA，并且**每次都拿中心差分验证一遍梯度**，别信 AD。

### 7.3 显式给 `nbeams` 和 `ds`

`RaySolver` 的自动束数由发射角扇面宽度除以内部步长算出，扇面给太宽（比如默认 ±80°）会算出几千条束，配合反射次数上限直接卡死。**内河建模时永远显式给 `nbeams` 和 `ds`**（浅水波导建议 ±60°…±75° 扇面、1000–2000 条），顺带把接收角范围也收紧一点。

### 7.4 `absorption` 返回的是**比值**，不是 dB

`absorption(frequency, distance=1000, salinity=35, temperature=27, depth=0, pH=8.1)` 听起来像返回吸收系数，实际上返回的是**在该距离上声压的无量纲线性缩放因子**。想知道 dB/km 必须自己换算：

```julia
α_dB_per_km(f) = -20 * log10(absorption(f, 1.0, S, T, d, pH)) * 1000
```

直接 `println(absorption(300.0))` 会打出 `0.9999981`，看起来像"吸收约等于 1 dB"，实际上 300 Hz 海水的真实值是 **0.0057 dB/km**，差了近 200 倍。**这个坑很容易让人误以为吸收不重要。**

### 7.5 `RayArrival` 的字段名和排序

`RayArrival` 只有 `t`（走时）、`ϕ`（复振幅）、`ns`/`nb`（水面/床面反射次数）、`θₛ`/`θᵣ`（发射/到达角）、`path`（路径点序列）——**没有 x、y、z**。要拿接收点坐标得自己从 `path` 的末点取，用 `getfield.(arr, :t)` 做向量化时也会因为这点绕一下。另外到达是按射线路径顺序返回的，**不保证按走时排序**，自己排一次。

顺带：`AcousticReceiverGrid2D` 的两个参数必须是 `AbstractRange`，传 `collect` 出来的 `Vector` 会报 `no method matching StepRangeLen(::Vector{Float64})`。

## 八、把模型接到"数据"上：从场到信道

模型的输出不止传输损失一个数，完整链路是这样接的：

**（1）多径结构** —— `arrivals(pm, tx, rx)` 给出到达集合，`ns` / `nb` 直接就是"这个河段有多少条水面/床面反射路径"。对内河层析，**互易走时差是唯一被测的量**：

$$
\Delta t = t_{AB} - t_{BA} \approx -\frac{2}{c_0^2}\int_{\Gamma_{AB}} \mathbf{u} \cdot \hat{\mathbf e}\,\mathrm{d}s
$$

代入模型：**对同一对站，把源放 A 和放 B 各算一次 `arrivals`，按 `(ns, nb)` 分组配对（互易时反射次数必然相同），逐组相减**。内河的直达路径和浅层床面反射几乎不随水流改变（淡水折射太弱），真正对流速敏感的是**折射类路径**——而按 3.1 节的分析，纯淡水段这类路径很少。**这就是内河声学层析和海洋层析最本质的差别：灵敏度来源不一样。** 在感潮段（盐度梯度 20 m/s）折射路径丰富，层析的可行性才真正成立；纯淡水段更现实的手段是走 ADCP 走航或用悬沙浓度/温度做被动声学反演。

**（2）传输损失场** —— `AcousticReceiverGrid2D(xrange, zrange)` 生成接收点网格，`transmission_loss(pm, tx, rxg; mode=:incoherent)` 一次拿到整个竖直面上的场。**内河做传播损失评估一律显式传 `mode=:incoherent`**，理由实测很清楚：12 m 等深、$c=1450$ m/s、源 $(0,-3)$、接收点 $(200,-6)$，从 500 Hz 扫到 5 kHz——

| 频率 | 相干 TL（默认） | 非相干 TL | RaySolver TL |
|------|---------------|----------|--------------|
| 500 Hz | 32.70 dB | 35.60 dB | 39.03 dB |
| 1 kHz | 40.09 dB | 35.60 dB | 51.18 dB |
| 2 kHz | 47.08 dB | 35.60 dB | 34.26 dB |
| 3 kHz | 43.18 dB | 35.60 dB | 34.86 dB |
| 5 kHz | 39.87 dB | 35.60 dB | 38.21 dB |

非相干结果在 5 个频点上稳定在 35.6 dB（`Bellhop` / `BellhopJL` / `Kraken` 三者一致到 0.09 dB），这才是工程曲线；相干结果在浅水波导里随频率剧烈起伏（32.7→47.1 dB），纯粹是多径干涉条纹，**没有工程意义，但对束数极度敏感、收敛慢**。

顺便这张表也暴露了另一件事：**`RaySolver` 在浅水高频段的绝对声强与另外三个模型不一致，最大差 15.6 dB（1 kHz）**。但它的到达时刻与 `Bellhop` 完全一致（见姊妹篇），所以**用 `RaySolver` 做走时和多径结构、别用它做绝对 TL**。

**（3）冲激响应与信道** —— `impulse_response(pm, tx, rx, fs)` 返回复数时域序列，`channel(pm, tx, rxs, fs; noise=…)` 配 `transmit(ch, x; txs=…, rxs=…, noisy=true)` 直接生成接收信号矩阵。实测 5 kHz、12 m 河段、$f_s = 16$ kHz：`Bellhop` 526 抽头（509 个非零）、`RaySolver` 773 抽头（701 个非零），两者 `t0` 都是 0.13706 s。模态解给的短得多（`Kraken` 在 12 m 里只有 23 抽头，`t0 = 0.11925 s`）——**注意 `Kraken` 的 `t0` 是模态群延迟，不是真实到达时刻**，拿它对走时会偏。这是把模型接进信号处理链的入口——**但频响/匹配滤波这些要在库外做**（作者把信号处理明确列为 out of scope），库只负责给你信道的线性时不变部分。

## 九、一套可复用的内河建模流程

综合上面，把流程固定下来：

1. **定目标、定河段类型**。问三件事：这段是纯淡水还是感潮段（决定要不要认真做 SSP）；量程是几百米还是几公里（决定要不要距离相关模型）；要的是声强、到达结构、还是走时差（决定用相干还是非相干、要不要做互易配对）。想清楚"折射可不可忽略"，能省掉一半工作量。
2. **整理输入**：沿程水深（来自多波束或断面测量，横断面则要深泓位置和岸坡）、SSP（实测 CTD 优先，没有就用温盐公式）、床质分类、悬沙浓度与粒径（用来估 $\alpha$）。
3. **选建模面**：沿程变化大 → 纵剖面 (s, z)；断面形状关键 → 横断面 (n, z)；弯道 → 沿中心线按弧长展开，横向差异用断面敏感性分析代替。
4. **建环境**：注意 `bathymetry` 填**正水深**（不是高程）、`z` 向上为正、随程水深用 `SampledField(v; x=…)` 一维形式、随程 SSP 用 `SampledField(matrix; x, z)` 二维形式且矩阵是 **x-major**、内河显式改 `salinity = 0` 和 `soundspeed`（别用默认的 1538.92 m/s）、床面用 `MuddySand` 或 `MultilayerElasticBoundary` 描述冲积层序。**打印一次环境，确认水深是正数、采样数非零。**
5. **粗算**：`PekerisRayTracer` + 有效水深跑通，检查到达结构是否合理；记住它只有 7 条路径，绝对声强会虚高十几 dB，只看趋势。要模态解就上 `PekerisModeSolver`（常深）或 `AdiabaticExt(模型类型, env)`（随程水深）。
6. **定算**：`Bellhop` / `BellhopJL`（随程水深 + 随程 SSP + 弹性床面），或 `RaySolver`（要逐条到达路径和走时时）。产出 TL 场一律 `mode=:incoherent`。
7. **补两个库给不了的东西**：水体吸收 $\alpha$（实测反解或按悬沙浓度估），以及横向扩散修正（柱面→球面的 3–6 dB）。
8. **验证**：**用另外两个模型交叉验证同一个算例**——这是最省事也最有效的一步。同一个 12 m 等深算例，`Bellhop` / `BellhopJL` / `Kraken` / `Orca` 四者的非相干 TL 差 0.09 dB 以内；一旦某个模型偏离十几 dB，你立刻就知道该怀疑谁。再用同河段的实测走时/声强做硬对比；分层、量程、频率至少各扫一遍看趋势；最后做一次"对建模面选取的敏感性"，这是弥补二维限制的唯一有效手段。

## 十、一句话总结

内河声学建模的难点从来不在传播算法，而在**三件事**：库是二维竖直平面而河是三维的；库的内置吸收是海水模型而内河是悬沙淡水；库的内置床面是岩石而内河是松散淤泥。把前两件用"选建模面 + 外部标定"补上、把第三件用 `MuddySand` 起步，配上 `Bellhop`（定算）、`AdiabaticExt`（严格模态）、`RaySolver`（走时与多径）三条互补的路线，Julia 这条路是完全走得通的。剩下最需要克制的，是不要把二维模型的柱面展布当成真值。

## References

- Chitre, M. (2023). *Differentiable Ocean Acoustic Propagation Modeling.* OCEANS 2023 – Limerick. doi:10.1109/OCEANSLimerick52467.2023.10244307
- Porpoise, C., Meloni, G., et al. *UnderwaterAcoustics.jl* — MIT License. https://github.com/org-arl/UnderwaterAcoustics.jl
- *AcousticRayTracers.jl*（RaySolver）https://github.com/org-arl/AcousticRayTracers.jl
- *AcousticsToolbox.jl*（Bellhop / Kraken / Orca 的 Julia 封装）https://github.com/org-arl/AcousticsToolbox.jl
- Francois, C. M., & Garrison, C. F. (1982). An equation for absorption in water. *JASA*, 72(2), 390–395.
- Chen, C.-T., & Millero, F. J. (1977). The canonical sound speed in seawater. *J. Acoust. Soc. Am.*, 62(5), 1129–1135.
- Mackenzie, K. V. (1981). Nine-term equation for sound speed in the oceans. *JASA*, 70(3), 807–812.
- Heaney, J. E., & Appal, S. (1995). *APL-UW TR 9407 (Rev. 2): Short-range acoustic transmission characteristics of undersea sediments.* Applied Physics Laboratory.
- Porter, M. B., et al. (2018). *User's Guide for BELLHOP Rev 5.2.* Naval Research Laboratory.
- Acopian, A. (2020). *The Bends of the River: Turning points in the evolution of the Earth's rivers.* — 与本文大角度河湾的物理背景相衔接
