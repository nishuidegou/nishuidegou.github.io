---
layout: post
title:  'MSP430FR6047 LEA 深度拆解：16 位 MCU 上塞进 DSP 引擎'
date:   2026-09-17 11:00:00 +0800
categories: embedded
---

上一篇文章把 MSP430FR6047 的整体架构梳理了一遍，其中反复出现一个名字——**LEA（Low-Energy Accelerator，低能耗加速器）**。它被官方标榜为"让 16 位 MCU 干 40 倍于 Arm Cortex-M0+ 的 DSP 活"的关键，也是这颗表 SoC 能把 5 ps 级时间测量跑进几微安量级预算的大功臣。这篇单独把它拆开，讲清楚：它是什么、怎么工作、能干什么、为什么省电，以及用的时候有什么坑。

## 一、先回答问题：LEA 到底是什么

LEA 是一颗**32 位数据的定点硬件协处理器**，挂在 MSP430 总线上的一个外设。它和绝大多数"加速器"的本质区别在于：

> **它是"没人看着也能自己干活"的一方**——CPU 把命令参数准备好、触发之后，可以立刻去睡（进入 LPM0），LEA 自带取指、算数、DM 通路，算完用中断把 CPU 叫醒。

MSP430FR6047 的总线拓扑大致是：

```
CPU (16-bit, 16 MHz) ───────────────┐
                                    ├─ 共享总线 ─ leaRAM (4 KB, 0x2C00–0x3BFF)
LEA (32-bit datapath) ──────────────┤       └─ 数据、系数、参数块都住这里
        │                            │
        └── 接到外部中断/NVIC，算完触发 ┘
```

三件关键事实：

1. **LEA 与 CPU 共享一段 4 KB 的 RAM**（RAM 的 Sector 2，地址 0x2C00~0x3BFF）。输入数据、输出数据、滤波器系数、命令参数块全部放在这段共享 RAM 里，CPU 填进去、LEA 取出来算、结果 LEA 写进去、CPU 再读走。
2. **LEA 只认定点数**：内部理解"16 位字"和"32 位字"两种数据（Q15 / IQ31 定标）。浮点运算照旧由 CPU 软跑。
3. **它是命令驱动的**：不是"调用一个 C 函数"那么简单，而是把"参数块"填进共享 RAM、往命令寄存器写一个命令码来触发。

## 二、命令驱动：一次 LEA 运算的生命周期

LEA 的运算流程可以用四步描述：

```
1. 分配：  把输入/输出/系数放到 leaRAM，按对齐要求排好
2. 填参数块：按所选命令的格式填一个参数块（数组/结构体）到 leaRAM
3. 触发：  把参数块地址装入 LEAPMSx 寄存器，往 LEAPMCB 写命令码
4. 等待：  poll LEAPMSTAT 忙位，或睡到 LEA 中断(LEAIFG)唤醒
```

涉及的核心寄存器（LEA 挂在 0x0500 附近的模块地址空间）：

| 寄存器 | 作用 |
|--------|------|
| LEACNF0/1/2 | 模块配置：时钟使能、架构版本、命令可用性等 |
| LEAPMS0L / LEAPMS1L | 参数块起始地址指针（低 16 位），指向 leaRAM 里的参数块 |
| LEAPMCB(L/H) | 写入命令码即触发该命令 |
| LEAPMSTAT | 状态/忙标志 |
| LEAIFG / LEAIE | 中断标志与使能，LEA 完成后置位 |

关键点：**LEA 的命令不是立即执行完的"函数调用"，更像异步任务提交**。写命令码之后 LEA 独立跑，CPU 可以转身睡 LPM0。

这里有个经常被新手误解的地方：**参数块不是寄存器里的一堆字段，而是放在 leaRAM 里的一段内存**。寄存器里只存"参数块在哪"和"跑哪个命令"。参数块里放的是向量长度、步长（stride/pointer increment）、维度、系数指针这类算数配置。命令跑完参数块就没用了，同一块内存还能复用给下一条命令。

命令按用途被分成了 **14 组**（Groups 1~12 + Group A、B），其中 1~12 组共享同一套通用参数块模板，A/B 组有专属参数块结构：

| 组 | 覆盖能力 |
|----|----------|
| Group 1 | 逐点的向量/矩阵基本运算 |
| Group 2 | 向量 MAC（窗函数、缩放、通用）|
| Group 3 | MAC、逐点 FIR、相关、卷积 |
| Group 4~12 | 乘法/矩阵、IIR 双二阶节、FFT/IFFT、多项式等其余类别 |
| Group A / B | 特例命令，参数块单独处理 |

命令码是常数，例如 `LEACMD__MAC`（MAC）、`LEACMD__MPYMATRIXROW`（行矩阵乘）、`LEACMD__POLYNOMIALSCALAR`（多项式缩放）、`LEACMD__IIRBQ1/IIRBQ2`（DF1/DF2 双二阶节）等等。

## 三、能干什么：从指令集看"加速器"的边界

LEA 覆盖的运算类型，正好是 DSP 里最吃吞吐的那类：

- **变换**：FFT / IFFT（实/复，Q15/IQ31），在 4 KB 共享 RAM 内最高支持 **512 点复 FFT 或 1024 点实 FFT**；
- **滤波**：FIR（含复数 FIR、卷积），IIR 双二阶节（biquad），级联结构；
- **相关/卷积**：点积、相关、卷积（正好是匹配滤波器、tof 估计的底子）；
- **矩阵**：矩阵乘法、矩阵行乘、逐点操作；
- **标量/逐点**：窗函数、缩放、多项式、向量逐点运算。

对应到软件层，TI 的 **MSP DSP 库（DSPLib）** 把这些能力封装成了 API（`msp_fft_*`、`msp_cmplx_fir_*`、`msp_biquad_*`、`msp_max_q15` 等），开发者不需要直接碰寄存器。DSPLib 内部会：

1. 检查数据是否落在 leaRAM 且对齐（一般要求 **4 字节对齐**，FFT/FIR 要求更严格的对齐）；
2. 参数不合法直接返回 `MSP_LEA_INVALID_ADDRESS`；
3. 触发 LEA、进入 LPM0 等待、中断醒来取结果。

也就是说日常开发你看到的是一堆"看起来像普通 DSP 函数"的调用，加速器在下面替你跑。

## 四、性能：13.8 倍和 40 倍是怎么来的

TI 给的基准数字有两个口径：

- **对比纯 C 软件实现**：256 点复 FFT，LEA 快约 **13.8 倍**；
- **对比 Arm Cortex-M0+ MCU**：官方口径是 **40 倍** DSP 性能（MSP430FR59xx 数据手册）；
- **实时滤波**：能在 **20 kHz 音频采样率**下实时跑 FIR。

第一口数字好理解——16 MHz 的核软跑 512 点复 FFT 大概要数万周期，LEA 的本质工作是把"每级蝶形运算 + 位反转 + 取一绕因子"全部硬化成流水线，吞吐自然差一个数量级。

第二口"40× vs M0+"要反着理解：M0+ 是通用核，LEA 是专用算子，拿专用比通用本来就不公平。但换个角度看，这正是它的设计目的——**在 x nA 级待机的表 SoC 上，用一颗"只干 DSP"的小引擎，同时买回性能和能耗**。它不追求绝对算力，追求"够用的算力 + 极低的能耗"。

一个值得注意的边界：**4 KB 共享 RAM 是硬上限**。512 点复 FFT（1024 字节）、1024 点实 FFT，都是在这 4 KB 里装下的。

## 五、为什么省电：协处理器的功耗模型

LEA 省电的机制分三层：

### 5.1 让 CPU 睡觉才是大头

纯软件 DSP 最耗电的不是运算本身，而是 **CPU 必须全程处在 Active 态驱动它**。LEA 方案的关键收益在这里：

```
软件方案：CPU Active 跑 FFT          —— 全程 ~120 µA/MHz，跑多久耗多久
LEA 方案：CPU 触发后睡 LPM0 → LEA 算 → 中断唤醒
          —— CPU 大部分时间 0 功耗，只有"填数据/收结果"时短暂激活
```

DSPLib 默认在 LEA 运行时进入 LPM0（中断使能），由 LEA 中断叫醒，这是能耗最低的路径。

### 5.2 微操级的能耗

针对受 errata 影响的 LEA 硅版本（某些版本要求 CPU 保持清醒），DSPLib 会退回"Active 态轮询"。即便如此也不是笨轮询——它利用 FRAM 缓存优化了轮询循环的取指功耗，比"跑同样运算"仍然省得多。

### 5.3 和 FRAM 的配合

MSP430FR 系选用 FRAM 除了不丢数据的优势，还因为 LEA 这类"算得快、但不常算"的加速器非常吃**统一存储器**：系数、历史数据可以常驻非易失区，掉电不丢，不用每次开机重建。需要长期驻留的滤波器系数放 FRAM、动态缓冲放 leaRAM，两者各得其所。

## 六、在 MSP430FR6047 里的具体角色

回到芯片本体。FR6047 的 RAM 布局是 **8 KB RAM = Sector0(2KB) + Sector1(2KB) + Sector2(4KB, 与 LEA 共享)**。超声波计量的信号链在 LEA 参与下是这样的：

```
PPG 激励 → 换能器 → PGA → SDHS(Σ-Δ ADC, ≤8 Msps)
                                          │ 采样数据直接落入 leaRAM
                                          ▼
                     LEA：带通/匹配滤波 → 过零/包络估计 → 次样本插值
                                          │ 只把标量结果交回 CPU
                                          ▼
                     CPU：dToF 计算、流量累加、FRAM 日志、LCD、MTIF
```

这正是它能拿到 **<5 ps 时间分辨率**的执行基础：SDHS 以与激励同源的时钟高速采样，波形数据落在 leaRAM，LEA 就地做插值/相关，主 CPU 几乎不触碰大数据流。高速数据都流经 leaRAM、由 LEA 消化，CPU 全程保持极低活跃度——整体"每秒一测约 3 µA"的账单因此成立。

## 七、用的时候容易踩的坑

1. **对齐不理解就 index out of bounds**：DSPLib 的 `DSPLIB_DATA` 宏负责把数组放进 `.leaRAM` 段并做对齐。手写裸寄存器时最容易漏掉 FFT/FIR 的严格对齐要求，会直接拿错数据。
2. **参数块在 leaRAM 里，不是寄存器里**：忘记把参数块地址写进 `LEAPMSx` 寄存器的常见错误是"命令发了但跑的是上次的参数"。
3. **共享 RAM 仲裁与竞争**：CPU 和 LEA 同时在访问共享 RAM 的不同部分也会有仲裁延时；时序敏感时尽量减少 CPU 对 leaRAM 的并发读写。
4. **数据不持久**：leaRAM 是 SRAM，掉电就没了。中间结果若需断电保留，最终值必须先挪回 FRAM。
5. **命令异步性**：发完命令立刻读结果读到的还是旧数据。要么 poll `LEAPMSTAT` 忙位，要么等中断。
6. **版本/errata**：个别 LEA 版本有已知问题，DSPLib 会做版本检查、必要时用绕行方案（Active 轮询）。烧录时留意器件 errata 对应版本。

## 八、总结

LEA 的设计哲学可以浓缩成一句话：**在 16 位、16 MHz、微安级预算的平台上，用一块专用 32 位定点算子代替通用 CPU 去啃 DSP 负载，把 CPU 从 Active 功耗中解放出来。**

它给嵌入式设计者的启发甚至大于芯片本身：

- **低功耗不是"算得慢"，而是"算得巧"**——省电的核心机制是让 CPU 睡觉，不是让 CPU 干得少；
- **加速器要贴着数据流设计**——共享 RAM + 参数块驱动让它能无痛嵌入 DMA/采样器流水线；
- **"40 倍"不是通用计算承诺，而是场景化承诺**——它在它被造出来的场景（滤波、FFT、相关、矩阵）里就是值钱。

## 参考资料

- [MSP430FR6047 数据手册（TI datasheet，Rev. D）](https://www.ti.com/lit/gpn/MSP430FR6047)
- [MSP430FR58xx/59xx/6xx Family User's Guide（SLAU367，LEA 章节）](https://www.ti.com/lit/pdf/SLAU367)
- [Low-Energy Accelerator (LEA) Frequently Asked Questions（SLAA720）](https://www.ti.com/lit/an/slaa720/slaa720.pdf)
- [Low-Energy Accelerator (LEA) Commands Reference Guide（SLAU850）](https://www.ti.com/lit/ug/slau850/slau850.pdf)
- [Low-Energy Accelerator (LEA) Common Parameter Blocks Reference Guide（SLAU852）](https://www.ti.com/lit/pdf/SLAU852)
- [Low-Energy Accelerator (LEA) Registers Reference Guide（SLAU853）](https://www.ti.com/lit/pdf/SLAU853)
- [MSP DSP Library（DSPLib）LEA 说明](https://software-dl.ti.com/msp430/msp430_public_sw/mcu/msp430/DSPLib/1_30_00_02/exports/html/usersguide_lea.html)
- [Filtering and Signal Processing Reference Design（TIDUBI9C）](https://www.ti.com/lit/ug/tidubi9c/tidubi9c.pdf)