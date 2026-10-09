---
layout: post
title:  "用 k-Wave 与自写求解器仿真 USCT：二维前向建模全流程"
date:   2026-10-09 12:00:00 +0800
categories: ultrasound
---

上一篇讲了 USCT 的原理和反演的"三层楼"。这一篇落到工程：**怎么把 USCT 的前向问题——声波在非均匀介质里怎么传播——跑出来，得到能喂给反演算法的合成数据。**

前向建模的工具箱里，最常用的就两样：**k-Wave**（社区标准，伪谱时域）和**自己写的求解器**（有限差分/有限元，想怎么改就怎么改）。这篇把两者都讲清楚：k-Wave 负责把"批量、宽频、三维"的前向跑得又快又稳，自写求解器负责"完全可控、可微、快速原型"。它们不是二选一，而是**互相验证、各干一段**。

本文按建模的自然顺序走：**定目标 → 选路线 → k-Wave 实操 → 自写求解器 → 可复现算例 → 两者互验 → 后处理 → 避坑**。

> 说明：文中的两张示意图由 Python 自写的二维 Helmholtz 有限差分解生成。本机没有 MATLAB/k-Wave 环境，所以 k-Wave 部分给的是可直接抄的代码和参数，自写求解器部分给的是能跑通的完整思路（脚本见仓库 `sketch-to-comic/usct_simulation.py`）。两者解的是同一个物理方程，结果应当一致。

## 一、前向仿真到底要产出什么

USCT 的流水线是"**采集 → 前向建模 → 反演 → 成像**"。你在电脑上做前向，产出的东西有三类用途：

| 用途 | 产出 | 为什么需要 |
|------|------|-----------|
| 造合成数据 | 各阵元接收到的波形 / 走时 | 有真值可对照，反演算法好不好一目了然 |
| 效应研究 | 单独开关衰减、密度、耦合层 | 物理量可独立控制，因果清楚 |
| 标定与验证 | 与实测或另一求解器对照 | 确认自己的代码没写错 |

一句话：**前向建模是把"已知的真值"变成"模拟出来的观测"，好让反演有靶子可打。**

## 二、两条路线：k-Wave 还是自写求解器

| | k-Wave | 自写求解器（FD/FEM） |
|---|---|---|
| 方法 | 伪谱时域（k-space 修正） | 有限差分/有限元，频域或时域 |
| 采样要求 | 每波长 **2–3 点**（建议 3–4） | FD 约 **8–10 点**；FEM 约 6–10 点 |
| 衰减 | 内置幂律吸收模型 | 自己用复声速/阻尼实现 |
| 批量 / GPU | 强（`gpuArray`、多源并行） | 看实现，通常要自己写 |
| 可微（接反演） | 否 | 可（配合自动微分） |
| 适合 | 批量前向、宽频、三维 | 快速原型、可微反演、完全可控 |

**结论**：用 k-Wave 造数据、跑效应研究；用自写求解器做快速验证和"可微"的反演。两者拿同一个算例一对照，谁写错了立刻现形。

## 三、k-Wave 上手：五步搭一个前向

k-Wave 的核心就五个对象：**网格 → 介质 → 源 → 传感器 → 求解器**。下面以二维为例。

### 3.1 安装

- MATLAB：官网下载 k-Wave Toolbox，加进路径即可。
- Python：`pip install k-wave-python`（需要对应的 C++/CUDA 后端）。

### 3.2 五步建模

**MATLAB：**

```matlab
% 1) 网格：Nx/Ny 个点，间距 dx/dy
Nx = 512; dx = 0.3e-3;
Ny = 512; dy = 0.3e-3;
kgrid = kWaveGrid(Nx, dx, Ny, dy);

% 时间步：由最大声速和 CFL 自动定
kgrid.makeTime(1600, [], 0.3);   % c_max, t_end, CFL=0.3

% 2) 介质
medium.sound_speed = c_map;        % [m/s]，每个网格一个值
medium.density     = rho_map;      % [kg/m^3]
medium.alpha_coeff = 0.5;          % 吸收 = 0.5 dB/(MHz^y · cm)
medium.alpha_power = 1.1;          % 幂律指数 y

% 3) 源：在环形阵的一个位置放一个脉冲
source.p_mask = source_mask;                 % 源掩模（哪个网格在发声）
source.p = toneBurst(1/kgrid.dt, 1e6, 3);    % 1 MHz、3 周期脉冲

% 4) 传感器：环形接收阵
sensor.mask = sensor_mask;                   % 接收网格
sensor.record = {'p'};                       % 记录声压

% 5) 求解
sensor_data = kspaceFirstOrder2D(kgrid, medium, source, sensor, ...
    'PMLInside', false, 'PMLSize', 20, ...
    'DataCast', 'single', 'PlotSim', false);
```

**Python（k-wave-python，接口名以版本为准）：**

```python
import numpy as np
from kwave.kgrid import kWaveGrid
from kwave.kmedium import kWaveMedium
from kwave.ksource import kSource
from kwave.ksensor import kSensor
from kwave.kspaceFirstOrder2D import kspaceFirstOrder2D

kgrid = kWaveGrid([Nx, Ny], [dx, dy])
kgrid.makeTime(1600, cfl=0.3)

medium = kWaveMedium(sound_speed=c_map, density=rho_map,
                     alpha_coeff=0.5, alpha_power=1.1)

source = kSource()
source.p_mask = source_mask
source.p = burst          # 时域脉冲

sensor = kSensor()
sensor.mask = sensor_mask

sensor_data = kspaceFirstOrder2D(kgrid, medium, source, sensor)
```

### 3.3 环形阵怎么摆

用坐标画一个圆，把落在圆上的网格点做成掩模就行：

```matlab
[X, Y] = ndgrid(kgrid.x, kgrid.y);
R = 0.032;
ring = abs(sqrt(X.^2 + Y.^2) - R) <= dx;   % 半径 R 附近一圈
% 取 N 个角度，每个角度最近的网格点作为一个阵元
```

- **source mask** 是发射元；**sensor mask** 是所有接收元。
- 想模拟"逐元发射"，就用 LiveLink/MATLAB 循环：每次把 `source.p_mask` 设成第 $i$ 个阵元，跑一次，存一次。

### 3.4 扫一圈源

USCT 要的是"每个阵元都发一次"。两种做法：

1. **脚本循环**（推荐）：`for i = 1:N`，改 `source.p_mask` 为第 $i$ 元 → 求解 → 把 `sensor_data` 存进一个大数组。清晰、可断点续跑。
2. **一次多源**：如果只关心线性叠加，可以用多个源同时发（相位编码），但 USCT 的道集一般还是要逐源，别偷这个懒。

### 3.5 衰减

k-Wave 内置**幂律吸收**，直接给两个数：`alpha_coeff`（单位 dB/(MHz$^y$·cm)）和 `alpha_power`（指数 $y$，软组织约 1.0–1.5）。这是它相对自写求解器省事的一大块。

### 3.6 内存与 GPU

- `'DataCast','single'` 把场量降到单精度，内存直接减半；有 GPU 用 `'gpuArray-single'`，速度快数倍。
- 三维（`kspaceFirstOrder3D`）内存是"格点数 × 时间步"量级，开算前先用 2D 估一遍再放大。

## 四、自写求解器：二维频域 Helmholtz 有限差分

自写的好处是"完全可控、几十行、还能求梯度接反演"。最省事的是**频域**——它把时间导数换成 $\mathrm{i}\omega$，直接得到一个线性方程组。

### 4.1 方程

均匀密度下，时谐声压满足亥姆霍兹方程：

$$
\nabla^2 p + k^2 p = -q, \qquad k = \frac{\omega}{c} = \frac{2\pi f}{c}
$$

把 $c$ 取成复数 $c(1+\mathrm{i}\alpha)$，$k$ 就带上虚部，自然表达衰减。

### 4.2 离散：五点差分

在均匀网格 $\Delta$ 上，拉普拉斯用五点格式：

$$
\frac{p_{i+1,j}+p_{i-1,j}+p_{i,j+1}+p_{i,j-1}-4p_{ij}}{\Delta^2} + k_{ij}^2\,p_{ij} = -q_{ij}
$$

每个网格点一个方程，整体是一个**稀疏复线性系统**，用 `scipy.sparse.linalg.spsolve` 一趟解掉。因为是频域，**同一频率换源只需回代**，多源很划算。

### 4.3 边界：渐变损耗层

不想要的边界反射用一层"海绵"吸掉：在距边界 $w$ 以内，让 $k^2 \to k^2(1+\mathrm{i}\eta)$，其中 $\eta$ 从 0 平滑升到约 1.2。这层比严格 PML 简单，配合足够厚度和缓变，反射能压到很低。

### 4.4 色散：网格要比 k-Wave 密

这是和 k-Wave 最重要的差别：普通有限差分相速度会随频率偏移（数值色散），所以**每波长要 8–10 个点**；k-Wave 用 k-space 修正把色散几乎消掉，才敢用 2–3 个点。**同样精度，自写 FD 的网格通常比 k-Wave 密 3–4 倍。**

## 五、一个可复现的二维算例

参数：

| 项 | 值 |
|----|----|
| 域半宽 | 4.5 cm，四周 6 mm 吸收层 |
| 换能器 | 32 元环阵，半径 3.2 cm |
| 幻影 | 体半径 2.4 cm：脂肪 1460 + 腺体 1560 + 病灶 1600 |
| 背景 | 水 1500 m/s |
| 频率 | 0.5 MHz |
| 自写求解器网格 | $\Delta \approx 0.3$ mm（约 10 点/波长） |

模型与网格长这样（左：几何、边界与阵列；右：k-Wave 那样的均匀交错网格，注意源可以落在网格之间）：

![k-Wave / 自写求解器的二维 USCT 模型与计算网格](/assets/images/usct-simulation-setup.png)

同一个 0.5 MHz 点源，在均匀水和放入幻影两种情况下的波场（复声压实部）：

![自写二维 Helmholtz 求解器复现的 USCT 前向波场](/assets/images/usct-simulation-wavefield.png)

左边均匀水里是干净的点源球面波，碰到吸收层被吃掉；右边放入幻影后，能直接看到**脂肪/腺体界面处的折射、内部结构的绕射、以及病灶后面的弱阴影区**。这正是层析反演要"逆"的物理过程。k-Wave 跑同一个算例会得到等价的时域结果。

## 六、两者互验：这是最该养成的习惯

k-Wave 和自写求解器各有一堆"隐式约定"（网格、时间步、衰减单位、时谐符号）。**拿同一个均匀算例对齐，是发现这些坑最快的方法：**

1. 先算**均匀水**：解析解是 $p \propto e^{\mathrm{i}kr}/\sqrt{r}$（2D 是柱面波）。两条路都应贴着它。
2. 再算**单点界面**：加一个平面分界面，看反射/透射系数是否符合斯涅尔定律和声阻抗公式。
3. 最后算**完整幻影**：对同一接收点比较走时，差异应小于你目标的精度。
4. 差异大时，按"**网格 → 时间步 → 边界 → 衰减 → 符号**"的顺序排查——通常前两个占九成。

## 七、从波场到反演输入

拿到接收信号后，喂给反演前还要做几件事：

1. **组道集**：把各源的接收信号排成 `source × receiver × time`（或频域）。
2. **拾取走时**：走时层析就在波形上拾初至。
3. **加噪声**：合成数据太干净会骗过算法，按目标信噪比加噪声。
4. **对齐约定**：源的时间零点、幅度量纲、时谐符号、衰减符号，全都要和反演代码一致。**这一步不做，前面全白算。**

## 八、常见坑

**k-Wave：**

1. **CFL 太大**：会直接数值发散。异质介质取 0.3 较稳。
2. **网格太粗**：每波长不足 2 点会有严重色散；建议 3–4 点起。
3. **`alpha_coeff` 单位**：是 dB/(MHz$^y$·cm)，不是 Np/m。别和文献里的衰减值直接混用。
4. **PML 太小**：边界反射会伪装成散射信号。先用均匀算例看边界回波。
5. **`source.p0` 与 `source.p` 的区别**：`p0` 是初始压力（瞬时全场分布），`p` 是随时间变化的源掩模，别用错。
6. **内存**：3D 前先估；单精度 `single` 能救命。

**自写求解器：**

1. **数值色散**：相速度随频率漂移，靠"每波长 8–10 点"压下去。
2. **稳定条件**：时域 FDTD 要满足 $\mathrm{CFL} = c\,\Delta t/\Delta x \le 1/\sqrt{2}$（二维）。
3. **衰减符号**：复声速虚部符号搞反，衰减会变成指数增长，场直接爆掉。
4. **稀疏直接法的内存**：二维还好，三维会迅速顶满内存。

## 九、小结

- 前向仿真就是"把已知真值变成模拟观测"，给反演当靶子。
- **k-Wave 负责批量、宽频、三维前向**；**自写求解器负责快速原型、可微反演**。
- k-Wave 五步：网格 → 介质 → 源 → 传感器 → 求解；环阵用掩模逐元发射；衰减用内置幂律。
- 自写求解器最省事是**频域五点差分**：一个稀疏复线性系统解掉，多源复用分解；代价是网格要比 k-Wave 密 3–4 倍。
- **两者拿同一算例互验**，是定位隐藏约定错误最有效的一招。

## References

- Treeby, B. E., & Cox, B. T. (2010). k-Wave: MATLAB toolbox for the simulation and reconstruction of photoacoustic wave fields. *Journal of Biomedical Optics*, 15(2), 021314.
- Treeby, B. E., et al. (2012). Modeling nonlinear ultrasound propagation in heterogeneous media with power law absorption using a k-space pseudospectral method. *JASA*, 131(6), 4324–4336.
- k-Wave Toolbox 官方文档与用户手册. http://www.k-wave.org/
- Tabei, M., Mast, T. D., & Waag, R. C. (2002). A k-space method for coupled first-order acoustic propagation equations. *JASA*, 111(1), 53–63.
- Kak, A. C., & Slaney, M. (1988). *Principles of Computerized Tomographic Imaging*. IEEE Press.
- 上一篇：《[超声计算机断层成像（USCT）：用声波给身体做 CT，以及反演的"三层楼"]({% post_url 2026-10-09-ultrasound-computed-tomography %})》
