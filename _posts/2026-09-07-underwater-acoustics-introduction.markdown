---
layout: post
title:  "Underwater Acoustics: A Brief Introduction"
date:   2026-09-07 12:00:00 +0800
categories: underwater-acoustics
---

This post condenses the classic course notes *Underwater Acoustics: A Brief Introduction* by Ethem Mutlu Sözer (MIT Sea Grant College Program), together with the worked numerical examples. It is a practical companion to the earlier post on signal, PA, and transducer matching — here we look at the specifications of the transducer itself, how received levels are computed end-to-end, and how propagation software models the channel. The full original notes are available as [a PDF](/assets/pdf/underwater-acoustics-introduction.pdf).

## Decibels

The **bel** was invented as a convenient unit for signal power loss in telephone wiring, named after Alexander Graham Bell. It turned out to be too coarse, so the *deci-bel* is used instead. A ratio of power is expressed as

$$
\text{Gain (dB)} = 10 \log_{10}\left(P / P_r\right)
$$

where $$P_r$$ is the reference power. Because power is proportional to the square of the voltage, the same ratio expressed in voltage is

$$
\text{Gain (dB)} = 20 \log_{10}\left(V / V_r\right)
$$

When we want to express an **amplitude level** relative to a reference — volts instead of watts — the course notes define

$$
V\ (\text{dB}) = 10 \log_{10}\left(V / V_r\right)
$$

> **Convention note.** Standard engineering practice uses \(10\log_{10}\) for power ratios and \(20\log_{10}\) for voltage ratios (so that a voltage ratio agrees with the equivalent power ratio). The MIT notes use \(10\log_{10}\) also for absolute voltage levels, and this post keeps that convention when reproducing the numbers so they match the source. The arithmetic is internally consistent either way: a level \(L\) dB re 1 V converts back with \(V = 10^{L/10}\).

## Transducer and Hydrophone Specifications

A projector or hydrophone datasheet is built around three curves:

| Spec | Meaning | Units |
|------|---------|-------|
| **OCRR** — Open Circuit Receiving Response | Output voltage per unit sound pressure vs. frequency | dB re 1 V/µPa |
| **TVR** — Transmitting Voltage Response | Sound intensity level produced at 1 m per 1 V input vs. frequency | dB re µPa/1V@1m |
| **Directivity pattern** | SIL as a function of angle in the horizontal and vertical planes | dB |

The worked example throughout the notes is the **ITC1001** spherical transducer, resonant near 22 kHz.

### Open Circuit Receiving Response (OCRR)

The OCRR of the ITC1001 is shown below. At the center frequency \(f_c = 22\) kHz the value is \(-190\) dB re 1 V/µPa.

![OCRR of the ITC1001 spherical transducer](/assets/images/itc1001-ocrr.png)

If the received sound intensity level (SIL) at the transducer is 190 dB re µPa, the transducer output level is

$$
V_{dB} = \text{SIL} + \text{OCRR}(f_c) = 190 + (-190) = 0\ \text{dB}
$$

Since $$V_{dB}$$ is referenced to 1 V,

$$
V = 10^{V_{dB}/10} = 1\ \text{V}
$$

### Transmitting Voltage Response (TVR)

The TVR of the ITC1001 is about 144 dB re µPa/1V@1m at 22 kHz.

![TVR of the ITC1001 spherical transducer](/assets/images/itc1001-tvr.png)

The sound intensity level 1 m from the transducer when driven by an input voltage \(V\) is

$$
\text{SIL} = \text{TVR}(f_c) + V_{dB} , \qquad V_{dB} = 10 \log_{10} (V / 1)
$$

Driving the ITC1001 with \(V = 200\) V gives

$$
\text{SIL} = 144 + 10 \log_{10}(200) = 144 + 26 = 170\ \text{dB re µPa}
$$

### Directivity

The ITC1001 is spherical: its directivity pattern is essentially the same in the horizontal and vertical planes.

![Directivity pattern of the ITC1001 spherical transducer](/assets/images/itc1001-directivity.png)

A **toroidal** transducer (e.g. the ITC2010) is omnidirectional in the horizontal plane but has a donut-shaped pattern in the vertical plane — it radiates energy into a horizontal disk rather than in all directions.

![Directivity pattern of the ITC2010 toroidal transducer, vertical plane (0° is horizontal)](/assets/images/itc2010-directivity-vertical.png)

## Hydrophone Pre-Amplifiers

A hydrophone output is typically in the millivolt range. In deep water the hydrophone sits at the end of a long cable (hundreds of meters), and resistive loss in that cable can bury the signal in noise. For this reason a **pre-amplifier** is placed right after the hydrophone, under water, before the signal travels up the cable. A second amplification stage at the surface is used only if needed.

With a pre-amplifier gain \(G\) in dB,

$$
V_{out}(\text{dB}) = V_{in}(\text{dB}) + G
$$

A 10 mV signal into a 23 dB pre-amplifier:

$$
V_{in}(\text{dB}) = 10 \log_{10}(10^{-3}) = -20\ \text{dB}
$$

$$
V_{out}(\text{dB}) = -20 + 23 = 3\ \text{dB} \quad\Rightarrow\quad V_{out} = 10^{3/10} \approx 2\ \text{V}
$$

(The source text prints "+43" in one spot but applies 23 dB — the arithmetic above is the correct one.)

## Acoustic Channel Estimation

The first step in designing an acoustic link is knowing the channel. In shallow water, acoustic waves reach the receiver through multiple paths: the direct path plus paths bouncing off the surface and the bottom. With a constant sound speed and flat boundaries we can predict these paths geometrically — **ray tracing**. Any signal arriving via several rays at once is a **multipath** channel.

### The SWCH-1 shallow-water example

Consider a 100 m deep channel with the source and receiver separated by \(r = 100\) m, both at depth 20 m:

- direct path, length \(r\),
- one surface bounce and one bottom bounce,
- two-reflection combinations (surface + bottom), and so on.

Each reflection adds loss on top of the propagation loss: about **1 dB at the surface** and **3 dB at the bottom** here; sound speed \(c = 1500\) m/s.

**Step 1–2 — path lengths and arrival times** (image-method). For a path that bounces \(n\) times, unfold the boundaries and measure the straight-line distance to the mirror source:

| Path | Horizontal (m) | Vertical mirror Δ (m) | Length (m) | Arrival (ms) |
|------|---------------:|----------------------:|-----------:|-------------:|
| Direct | 100 | 0 | 100.0 | 66.7 |
| Surface (1 bounce) | 100 | 40 | 107.7 | 71.8 |
| Bottom (1 bounce) | 100 | 160 | 188.7 | 125.8 |
| Surface + bottom | 100 | 200 | 223.6 | 149.1 |

**Step 3 — transmission loss.** The total loss is propagation loss plus all reflection losses:

$$
\text{TL} = 20 \log_{10}(\text{range}) + \alpha(\text{range}) + \Sigma\ \text{reflection losses}
$$

The spherical-spreading term \(20\log_{10}(r)\) dominates at short range; the absorption term \(\alpha\) (dB per km, a strong function of the 22 kHz center frequency and of temperature) would add a few dB/km — it is set to 0 in the table below for clarity.

| Path | Spreading (dB) | Reflections (dB) | Total TL (dB) |
|------|---------------:|-----------------:|--------------:|
| Direct | 40.0 | 0 | 40.0 |
| Surface | 40.6 | 1 | 41.6 |
| Bottom | 45.5 | 3 | 48.5 |
| Surface + bottom | 47.0 | 4 | 51.0 |

**Steps 4–6 — source level and received levels.** Drive the transmitter with 400 Vrms: with the ITC1001 TVR of 144 dB at 22 kHz,

$$
\text{SIL}_{1m} = 144 + 10\log_{10}(400) = 144 + 26 = 170\ \text{dB re µPa}
$$

Then per path, \(\text{SIL}_{rx} = \text{SIL}_{1m} - \text{TL}\). Using a hydrophone OCRR of −162 dB re 1V/µPa at 22 kHz and a 40 dB pre-amplifier:

| Path | TL (dB) | SIL rx (dB re µPa) | VdB at hydrophone | Pre-amp output (V) |
|------|--------:|-------------------:|------------------:|-------------------:|
| Direct | 40.0 | 130.0 | −32 | 6.3 |
| Surface | 41.6 | 128.4 | −33.6 | 4.4 |
| Bottom | 48.5 | 121.5 | −40.5 | 0.89 |
| Surface + bottom | 51.0 | 119.0 | −43.0 | 0.50 |

**Step 7 — repeating for 1000 m.** Ranges scale the losses quickly: the direct path at 1000 m sees 60 dB of spreading, dropping the received SIL to 110 dB and the pre-amplified output to about 63 mV (before absorption). Multipath delay spread also shrinks in *seconds* but the *relative* arrival windows change — at 1000 m the direct and surface-bounce rays differ by only ~0.5 ms in travel time (666.7 ms vs 667.2 ms), whereas at 100 m they differ by ~5 ms. This is what drives the pulse-width budget in the next section.

## Determining the Range of a Source

If a target transmits a pulse

$$
p(t) = A \sin(2\pi f_c t), \qquad 0 < t < T_s
$$

the receiver sees a delayed and attenuated copy,

$$
r(t) = B \sin(2\pi f_c (t - \tau))
$$

The propagation delay \(\tau\) (and hence the range) is found by **correlation**. The cross-correlation of \(a(t)\) and \(b(t)\) is

$$
R_{ab}(\lambda) = \int_{-\infty}^{\infty} a(t)\, b(t - \lambda)\, dt
$$

and is a measure of similarity at lag \(\lambda\). If \(b(t) = a(t - \tau)\) then \(R_{ab}(\lambda)\) peaks at \(\lambda = \tau\). The auto-correlation \(R_{aa}\) peaks at \(\lambda = 0\).

**Pulse-width budget.** To separate the multipath arrivals, the pulse must be short enough that the direct-path pulse finishes before the first reflected path arrives. For the 100 m example this window is about \(71.8 - 66.7 = 5.1\) ms, so \(T_s < 5\) ms. At 1000 m the direct/surface window shrinks to ~0.5 ms. If \(T_s\) is longer than the delay spread, echoes overlap and individual paths (and therefore the direct-path delay) can no longer be resolved — which is exactly why pulse-compression/wideband signals are used in practice.

**Transponder method.** A *transponder* listens for a pulse at \(f_1\) and replies with a pulse at \(f_2\) after a known delay \(\tau_t\). Measuring the round-trip delay \(\tau_m\) gives the range as

$$
R = \frac{c}{2}\left(\tau_m - \tau_t\right)
$$

## Determining the Direction of a Target

With two hydrophones separated by \(d\), the direction of arrival is recovered from the difference in arrival times. If the range is much greater than \(d\), the wavefront is approximately planar. For two hydrophones spaced by \(d\), the path difference is \(d \sin\theta\), so

$$
\sin\theta = \frac{c\, \Delta \tau}{d}
$$

With hydrophones at the four corners of the surface craft, comparing the arrival order tells which **quadrant** the target is in: the target lies in the quadrant of the corner that receives the signal first (e.g. sound arriving at H1 before H2, H3, H4 places the target in quadrant 1). Comparing the exact arrival time differences then refines the angle via the plane-wave relation above.

## Propagation Modeling Software

The notes use the **Acoustic Toolbox** written by Mike Porter — originally Fortran, with a MATLAB front-end by Alec Duncan. It numerically solves the propagation equations with several interchangeable models:

- **KRAKEN** — normal-mode code for range-varying environments (Catesian line sources or cylindrical point sources);
- **KRAKENC** — complex normal-mode version;
- **SCOOTER** — fast-field / finite-element code for range-independent environments via the spectral integral with piecewise-linear pressure and material properties;
- **BELLHOP** — ray and Gaussian-beam tracing in environments where the sound speed varies with range and depth.

The toolbox can also compute bottom reflection coefficients (Bounce) for layered media.

The typical workflow:

1. **Build the environment** — estimate the sound speed profile from depth, temperature, and salinity measured by a CTD probe (the notes use the Bermuda Atlantic Time-Series Study, BATS, November 1988 dataset).
2. **Define the bottom** — start with the program's default.
3. **Run transmission-loss and ray-trace calculations** and inspect where the sound propagates and how energy is spread by the sound-speed channel.

The front-end screenshots in the original notes step through a real CTD profile from BATS and the resulting ray traces and transmission-loss curves; the underlying workflow remains the modern de facto standard (e.g. `Bellhop` is still widely used through Acoustic Toolbox or its Python/R bindings).

## Key Takeaways

1. **dB conventions matter.** The course notes use \(10\log_{10}\) for absolute voltage levels; most datasheets use \(20\log_{10}\) for voltage ratios. Check which convention a source uses before trusting a number.
2. **OCRR + TVR close the loop.** From a receiving level and an OCRR you get a voltage; from a drive voltage and a TVR you get a source level. Together they let you budget a whole link (source level → spreading/reflection losses → received level → pre-amplified voltage).
3. **Multipath limits pulse width.** Direct and reflected arrivals force \(T_s\) to be shorter than the arrival-time separation, which shrinks rapidly with range — another argument for bandwidth-efficient, shaped, modulated signals.
4. **Correlation converts delay into range; array timing converts delay into angle.** Both rely on resolving \(c\cdot\tau\) to the required accuracy.

## References and Source

- E. M. Sözer, *Underwater Acoustics: A Brief Introduction*, MIT Sea Grant College Program.
- [Full notes (PDF download)](/assets/pdf/underwater-acoustics-introduction.pdf)
- [Acoustic Toolbox](https://oalib-acoustics.org/) — Mike Porter's propagation modeling suite (KRAKEN, SCOOTER, BELLHOP).
- M. B. Porter and H. P. Bucker, "Gaussian beam tracing for computing ocean acoustic fields," *J. Acoust. Soc. Am.*, 82, 1349–1359 (1987).