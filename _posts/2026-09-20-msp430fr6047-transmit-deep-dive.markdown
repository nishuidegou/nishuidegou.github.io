---
layout: post
title:  'MSP430FR6047 发射模块拆解：一串脉冲如何变成水里的声波'
date:   2026-09-20 09:00:00 +0800
categories: embedded
---

前两篇把 MSP430FR6047 的整机架构和 LEA 接收侧算力都拆过了，但发射路径始终只有一句话带过："PPG → 4 Ω PHY → 换能器"。发射模块看起来简单，实际却是整个 ToF 计量精度链条的**出发点**——它负责"在正确的时间、用正确频率和幅度、向正确方向"轰出一个干净的声脉冲串。这篇单独把它拆开。

## 一、发射模块在芯片里的坐标

发射链路由四块组成，各自分工明确：

| 模块 | 全称 | 干的活 |
|------|------|--------|
| HSPLL | High-Speed PLL | 用片外 4~8 MHz 参考（USSXT）合成 68~80 MHz 主时钟，给发射和采样发"心跳" |
| PPG | Programmable Pulse Generator | 按程序合成激励脉冲串（频率/个数/停振等全部可编程），是波形合成器 |
| PHY | Physical Interface | 低阻驱动级 + 双通道开关（MUX），把 PPG 的 0/1 序列变成压在换能器上的电压摆动 |
| ASQ | Acquisition Sequencer | 掐表的硬件时序机，按预编程的时间标记依次拉起 TX 偏置、PPG、SDHS、采样 |

一句话串起来的信号流是：

```
USSXT(4~8MHz) → HSPLL(68~80MHz) ──┬──→ PPG ──→ PHY(CH0_OUT/CH1_OUT) ──→ 压电换能器
                                  └──→ SDHS 调制器 / ASQ 时序计数器（全部同源）
```

注意画这条线想强调的是：**发射、采样、时序三者的时钟是同一根**。后面会看到这是所有精度指标的地基。

## 二、先看目标：这串脉冲要长什么样

压电换能器是个高 Q 谐振器件。要让它有效起振并辐射声波，发射器得在**换能器谐振频率附近**喂一串方波脉冲——不是一锤子，是一串。发射波形的基本三要素：

1. **激励频率**：尽量贴近换能器中心频率（严格说，是阻抗最低、灵敏度最高的那个频率）；
2. **脉冲个数**：太少能量不足回波太弱，太多 burst 拉长、挤占接收窗口；
3. **停振脉冲**：可选的 1~15 个、相位反 180° 的脉冲，用来给换能器"刹车"。

整体时序长这样：

```
激励脉冲串(1~127) ┐ 停振脉冲(0~15)          回波
 ██ ██ ██ ██ ██ ██ ███ ██████             ∿∿∿∿∿
 |←─ burst ─→|←余振衰减→|← channel 切换与 gap →|→ ADC 接收窗口
```

每一发到下一发之间，USSLib 会让发射后的余振衰减掉，然后再开接收窗口——这个 gap 就是 Design Center 里那个"Gap between pulse start and ADC capture"。

## 三、HSPLL：为什么"激励频率"和"采样频率"必须同源

发射模块不是自己带个振荡器随便凑个频率就完事。USSXT 上挂 4~8 MHz 的晶振/谐振器（TI 固定按 8 MHz 验证性能），HSPLL 把它锁到 68~80 MHz。这颗 PLL 的输出被**同时**喂给：

- PPG 的相位周期计数器（决定发射频率）；
- SDHS 的 Σ-Δ 调制器（决定采样率）；
- ASQ 的时序计数器（决定各事件的时间刻度）。

好处是**相干性（coherence）**：采样网格相对发射相位是固定的、可复现的。每次测量采样点都落在发射波形的相同相位位置，波形才可做匹配滤波、相干平均，LEA 的次样本插值才有稳定相位参考。如果发射用独立时钟，采样率误差会随时间累积、相位漂移，后面 5 ps 级测量无从谈起。

PPG 的发射频率公式也来自这颗 PLL：

```
f_pulse = f_HSPLL / (HP + LP)
```

其中 HP/LP 分别是 SAPHPGLPER / SAPHPGHPER 里的"高/低相位周期数"（以 HSPLL 周期为单位）。比如 80 MHz 下各设 40：40 cycle = 500 ns，即 1 MHz、50% 占空比。

因为 HSPLL 周期是一格一格的，频率分辨率也有限：

```
ΔF = f_HSPLL/(HP+LP) − f_HSPLL/(HP+1+LP)
```

1 MHz 附近把某一相位加 1 cycle，频率就跳约 12.7 kHz——所以激励频率几乎不能是"任意值"，而是**在可用的 (HP,LP) 组合里挑最接近换能器频率的一组**。这正是 Design Center 里 F1 参数帮你换算成 pulseLowPhasePeriod/pulseHighPhasePeriod 的原因，手算很容易选到不工整的频率。

## 四、PPG：可编程脉冲发生器

### 4.1 PPG 是什么

PPG 是 SAPH 模块（Sequencer for Acquisition, Programmable Pulse Generator, and Physical Interface）里的数字波形合成器。官方给的能力是：

| 参数 | 范围 |
|------|------|
| 激励脉冲数 | 1 ~ 127 |
| 停振脉冲数 | 1 ~ 15（与激励脉冲相位差 180°，紧跟在同相脉冲之后）|
| 发射频率 | 约 133 kHz ~ 2.5 MHz |
| 频率步进 | 1 个 HSPLL 周期 |

USS 基线版(FR6047)是**单音**发射；多音（dual/multi/trill tone）是 USS_A（FR6043/FR5043）的增强功能，用于燃气表场景——多音激励的编码样式可以做噪声抑制，在 Hilbert 变换前先滤掉超声波上的干扰。

### 4.2 发射参数都写在哪些寄存器里

| 寄存器 | 作用 |
|--------|------|
| SAPHPGC | 激励脉冲数、停振脉冲数、空闲电平(PLEV)、脉冲极性(PPOL) |
| SAPHPGLPER | 低相位周期数（HSPLL cycle 数）|
| SAPHPGHPER | 高相位周期数（HSPLL cycle 数）|
| SAPHPGCTL | 使能(PPGEN)、输出通道选择(PPGCHSEL)、触发源(TRSEL)、寄存器/自动模式(PGSEL) |
| SAPHPPGTRIG | 软件触发，写一下就发一炮 |
| SAPHOSEL | 把 PPG 输出（PPGSE）引到 CH0_OUT 或 CH1_OUT 引脚 |

一个最小可用的"发一炮"配置（寄存器写法取自 TI 例程，示意）：

```c
SAPHKEY = KEY;                       // 解锁 SAPH 寄存器
SAPHPGC  = PLEV_0 | PPOL_0 | 0x000A; // 10 个激励脉冲，0 个停振，空闲为低、脉冲高有效
SAPHPGLPER = 40;                     // 低相位 = 40 HSPLL cycle = 500 ns
SAPHPGHPER = 40;                     // 高相位 = 40 HSPLL cycle = 500 ns → 1 MHz
SAPHPGCTL = TRSEL_2 | PPGCHSEL_0 | PGSEL_0; // 走定时器触发、输出到 CH0、寄存器模式
SAPHOSEL  = PCH0SEL__PPGSE;          // 把 PPG 序列接到 CH0_OUT
SAPHPGCTL |= PPGEN;                  // 使能 PPG
```

### 4.3 谁来扳机：软件触发 vs 硬件触发

PPG 可以：

- **软件触发**：写 SAPHPPGTRIG；
- **硬件触发**：挂在定时器（例程里是 TA2 的 CCR1，也有 TA1 CCR2 等连接方式），由定时器边沿拉起。

在计量场景里几乎总用 ASQ（自动模式）牵头：PPG 只是整条采集序列里的一个环节，由 ASQ 的时间标记在"正确时刻"触发，CPU 全程可以睡觉。PPG 本身也可以**脱离超声波用途单独当通用脉冲发生器用**（比如精确方波源）——前提是把 PHY 也配好，把脉冲引到引脚上去。

## 五、PHY：低阻驱动 + 双通道切换

### 5.1 一套驱动，两路换能器共用

PHY 只有**一个驱动级和一套接收路径**，通过内部 MUX 在两个通道间切换：发射 CH0 时接收走 CH1，下一炮反过来。这在流量计里对应顺流/逆流两发——一次"上发下收"，切一次，再"下发上收"。

```
方向1： PPG → 驱动级 ──MUX──▶ CH0_OUT ──▶ 换能器A 发射
                        CH1_IN  ◀── 接收路径 ◀── 换能器B 回波
方向2： PPG → 驱动级 ──MUX──▶ CH1_OUT ──▶ 换能器B 发射
                        CH0_IN  ◀── 接收路径 ◀── 换能器A 回波
```

所以每路换能器的两个端子要分别接到对应通道的 CHn_OUT（发射）和 CHn_IN（接收），引脚在发射/接收之间时间复用。

### 5.2 4 Ω 和 120 mA 意味着什么

官方口径：输出驱动阻抗可低至 **4 Ω**、能提供最高约 **120 mA** 的瞬态驱动电流。为什么要这么"凶"？

1. **电容性负载**：压电换能器等效是"大电容 + RLC 谐振枝"，要在 1~2 MHz 下让它快速充放电，驱动源的内阻必须远小于负载阻抗，否则边沿爬不上去、脉冲幅值被负载"吃掉"。
2. **激励幅值稳定**：源阻抗小 → 幅值对负载在温度、批次间的变化不敏感，回波的幅度/相位才可预测。
3. **ZFD 的根基**：Zero-Flow Drift——零流量时顺逆两发按理测得相同的 ToF。所谓"两路 electronics 阻抗对称"，指的就是驱动源阻抗和换能器看到的电路阻抗在 CH0/CH1 两路完全一致，任何不对称都会直接折算进 dToF 变成固定偏差。

### 5.3 对称性是硅上做出来的，不是光靠 PCB

为了把两路做到可复现一致，芯片上做了两件事：

- **片上终端匹配**：换能器直接挂芯，外部"只需要一个终止电阻和一个电容"（TI 在参考设计里实测 200 Ω + 1000 pF 组合效果较好）。片子内部还有可 trim 的终端电阻/上拉结构（SAPHCH0/CH1 的 PUT/PDT/TT 系列寄存器），把每路电子阻抗修正到规格内。
- **按片校准（ATE trim）**：出厂测试时按每颗片子的实际特性把 CH0/CH1 的驱动级、终端电阻配平，偏差打进片内。这正是"为什么换能器要尽量对称布置"的另一半答案——硅上已经把能配平的部分配平了，剩下走线等长、外部元件对称就交给你。

## 六、ASQ：发射时序的国家队

发射不是"想发就发"。一次完整测量里，发射要与接收链路的供电、偏置、采样窗口精确配合。ASQ 就是这个硬件时序机，它用一套**时间标记（time mark）事件**把动作排好，全部由硬件按 HSPLL 分频后的计数器执行，CPU 发完指令就进低功耗等待。

主要的时间标记与 Design Center / 库参数对应：

| 时间标记事件 | 对应参数 | 干的事 |
|------------|----------|--------|
| 拉起 TX/RX 偏置 | Start PGA and IN Bias Count | 偏置电路就位 |
| 触发 PPG | Start PPG Count | 打第一发脉冲 |
| 给 SDHS 上电 | Turn on ADC Count | 让 Σ-Δ 调制器稳定 | 
| 开始采样 | Start ADC Sampling Count | 打开接收窗口 |
| 反向重启 | Restart Capture Count | 切到另一通道发起对向捕获 |

这些事件的时间刻度写入 SAPHATM_A/B/C/D 等寄存器（以 HSPLL 分频计数），GUI 里则以 ns 直接显示。硬件的存在让"约 3 µA"的账单成立：**测量期间 CPU 不需要 ACTIVE，全部由 ASQ + DMA + LEA 接力**。

值得注意的约束：发射打出去时 `[Gap between pulse start and ADC capture] + Start PPG − Turn on ADC` 必须大于 SDHS 的建立时间（约 40 µs），否则 ADC 还没稳就开始采样、前段全是建立期噪声——这也是几个常见配置报错的来源。

## 七、发射参数在软件里怎么配

USS 软件库的测量配置结构体里，发射侧字段一目了然：

- `pulseLowPhasePeriod` / `pulseHighPhasePeriod`：由 F1（激励频率）+ 采样频率/过采样率换算；
- `numOfExcitationPulses`：脉冲个数（Design Center 的 Number of Pulses）；
- `numOfStopPulses`：停振脉冲数；
- `ch0DriveStrength` / `ch1DriveStrength`：两路驱动强度，可分别调；
- `pulsePolarity`：脉冲极性；
- `startPPGCount` 等：进 ASQ 的时间参数。

Design Center 里还有一个对发射侧特别有用的工具：**Frequency Sweep（频率扫描）**。它把 F1 在一个范围内逐点扫，看哪个发射频率下 ADC 采到的回波幅度最大——那个点才是换能器的"甜蜜点"，应该作为正式 F1 写回配置。

## 八、工程落地：发射侧踩过的坑

1. **激励频率必须对准换能器阻抗最低点**：换能器规格书里的中心频率往往是"阻抗最低处"，偏离它阻抗急剧上升、回波幅度暴跌。E2E 上有用户拿 3 MHz 换能器却用 280 kHz 激发，回波小得离谱——排查下来先看激励频率是不是落在了换能器带宽里。
2. **低频换能器余振长、盲区大**：FR6047 主打 1~2 MHz 水表换能器；用 230 kHz 这类低频件体验很差——低频 Q 高、ring down 长，发射余振会压进接收窗口，收发间距必须拉长。TI 建议这种频率选 UG 路线（FR6043 + 外部 AFE）。
3. **停振脉冲该用则用**：余振直接污染接收窗口起始段，物理上"紧拍一下刹车"（180° 反相脉冲）能明显缩短衰减，等效缩短盲区、改善短流量程。
4. **发射瞬间的供电稳不稳**：~120 mA 量级的瞬态电流直接抽在 DVCC 上，供电/退耦差会让"发射能量"沿电源网络漏进接收链，形成与流量无关的固定串扰。参考设计强调用专用 LDO/DCDC 就是这个原因。
5. **两路对称到布线层面**：CH0/CH1 的走线等长、外部匹配元件同型号同厂商，芯片上的 ATE trim 只负责配平硅内侧，线上的差只能你补。
6. **别让数字侧在发射瞬间挤总线**：发射打拍、SDHS 采样的时刻尽量别让 CPU 密集访问 leaRAM，避免与 LEA/DTC 争总线引入抖动。

## 九、总结：发射模块的设计哲学

把发射侧的设计取舍拉回一句：**计量用的发射器不追求"打得响"，追求"打得确定"。**

- "确定"的三层含义：频率确定（HSPLL 同源，可复现）、相位确定（与采样相干）、时序确定（ASQ 硬件编排，不依赖软件抖动）；
- 低阻驱动 + 芯片级配平，是为了让"换能器看到的阻抗"可预测、两路对称，把误差消灭在物理层而不是靠算法补偿；
- 发射路径同样参加了"每部分都能睡"的接力：发完这一炮，模块该关就关，账单还是那 3 µA。

从架构篇到 LEA，再到今天的发射模块，MSP430FR6047 三个"为什么这么设计"的答案已经拼完整：**模拟前端负责把物理量变成可重复的相位信息，数字侧负责用最低能耗把它榨出 ps 级分辨率，而发射模块就是那条信息链的起点。**

## 参考资料

- [Ultrasonic Sensing Solution Submodules Overview（SWAY011）](https://www.ti.com/lit/wp/sway011/sway011.pdf)
- [MSP430FR58xx/59xx/6xx Family User's Guide（SLAU367，SAPH 章节 21）](https://www.ti.com/lit/pdf/SLAU367)
- [MSP430FR6047 Ultrasonic Sensing Design Center User's Guide（SLAU720）](https://www.ti.com/lit/pdf/slau720)
- [Matched-Filter Ultrasonic Sensing: Theory and Implementation（SLAA814）](https://www.ti.com/lit/pdf/SLAA814)
- [Ultrasonic Sensing FAQ（SLAA837）](https://www.ti.com/lit/pdf/slaa837)
- [MSP Ultrasonic Sensing Library User's Guide（USSLib）](https://software-dl.ti.com/msp430/msp430_public_sw/mcu/msp430/USSSWLib/latest/exports/)
- 本系列前作：[整体架构拆解]({% post_url 2026-09-17-msp430fr6047-ultrasonic-sensing %})、[LEA 深度拆解]({% post_url 2026-09-17-msp430fr6047-lea-deep-dive %})