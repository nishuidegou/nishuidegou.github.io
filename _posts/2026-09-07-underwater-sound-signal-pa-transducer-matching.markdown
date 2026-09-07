---
layout: post
title:  "Underwater Sound Signals, Power Amplifiers, and Transducer Matching"
date:   2026-09-07 10:00:00 +0800
categories: underwater-acoustics
---

In underwater acoustic systems the chain from digital waveform to acoustic pressure involves three tightly coupled stages: **signal generation**, **power amplification (PA)**, and the **transducer (projector)**. Each stage imposes its own constraints, and mismatches between them produce everything from wasted bandwidth to destructive amplifier oscillation. This post collects practical lessons on driving a 15 kHz - 22 kHz band transducer with M-sequence signals, why raised-cosine (RC) shaping is preferable, and how large impulses in front of a signal excite serious PA output issues.

## The Transmission Chain

The projector is a resonant, narrow-band device. Its electrical impedance is strongly frequency dependent, dominated by the motional impedance near its resonance. The PA must deliver high voltage/current swing into this reactive and variable load, while the signal must be designed so that its spectrum actually falls inside the usable band of the transducer.

A typical chain:

```
baseband waveform → DAC → linear PA / D-class PA → matching network → transducer → water
```

Three common trouble points:

1. The **signal spectrum** lands outside the transducer band → poor power transfer, ringing.
2. The **PA load** is reactive/off-resonance → high voltage standing wave, heat, or even oscillation.
3. **Transmission-line / impulse content** drives the PA into current limiting or saturation → large output oscillation.

## M-Sequence Signals and the 15 k - 22 kHz Transducer

A maximum-length sequence (m-sequence / PRBS) has excellent autocorrelation properties, making it attractive for correlation-based sonar ranging and communication. The raw m-sequence, however, has two problems when fed directly to a band-limited resonant transducer.

### Problem 1: Spectral Spreading

A binary m-sequence clocked at bit rate $$R_b$$ has a "sinc-squared" spectrum that extends far beyond its nominal bandwidth, peaking near DC and rolling off slowly. When you send the raw sequence through a channel centered at, say 18 kHz, only a small fraction of the energy falls inside the transducer band. The result:

- **Poor energy transfer** — the transducer cannot radiate energy it never receives.
- **High frequency components** driving the amplifier at frequencies where the PA has little gain margin.
- **Inter-symbol interference** as the narrow-band transducer filters and smears the sharp transitions.

### Problem 2: Spectrum Centered at DC

The raw m-sequence is baseband, centered near 0 Hz. The 15 - 22 kHz transducer is a bandpass device. Feeding it the unmodulated code means the passband sees almost nothing useful, and the amplifier works against a load it wasn't designed for.

### Solution: Bandpass-Modulated or Shaped Signaling

There are two ways to fix this.

**Frequency translation (passband modulation):** Multiply the baseband code by a carrier at the center of the band. For the 15 - 22 kHz projector, a carrier near 18.5 kHz moves the spectrum into the band. But a simple BPSK multiplication still leaves sharp phase transitions whose sidelobes ring the transducer.

**Pulse shaping (raised cosine):** Instead of hard rectangle chips, shape each chip with a raised-cosine pulse. The raised-cosine spectrum is a smooth, strictly band-limited rolloff:

$$
H(f) = \begin{cases}
T, & |f| \le \frac{1-\beta}{2T} \\[4pt]
\dfrac{T}{2}\left[1 + \cos\left(\dfrac{\pi T}{\beta}\left(|f| - \dfrac{1-\beta}{2T}\right)\right)\right], & \frac{1-\beta}{2T} < |f| \le \frac{1+\beta}{2T} \\[4pt]
0, & |f| > \frac{1+\beta}{2T}
\end{cases}
$$

where $$T$$ is the chip duration and $$\beta \in [0,1]$$ is the rolloff factor.

The raised-cosine family:
- **Band-limited**: energy outside the band is strictly zero (for the ideal filter).
- **Zero-ISI at sampling points**: when matched, the pulse satisfies the Nyquist criterion, so correlator output peaks remain distinct.
- **Small sidelobes**: ringing at the transducer resonance is drastically reduced compared to the rectangular m-sequence chip.

Choosing $$\beta$$ trades bandwidth against time-domain overshoot. With a 15 - 22 kHz (7 kHz) channel, the bandwidth budget forces an appropriate chip rate and rolloff:

```
bandwidth        ≈ (1+β) / T      (main lobe)
usable channel   ≈ 7 kHz
```

For example, a symbol rate around 4 - 5 kchips/s with $$\beta \approx 0.2$$ - 0.5 fits comfortably inside the band while keeping the envelope smooth.

### Why This Matters for the PA

The PA and its matching network are tuned around the transducer's electrical resonance. When the driving signal has out-of-band energy:
- The PA sees a strongly **reactive** load at those frequencies.
- Reflected power raises the output voltage/current stress.
- The protection/feedback loops may not be stable because the loop bandwidth was set for the resonant frequency.

A raised-cosine shaped, properly modulated signal keeps the spectrum in-band, so the PA operates where its small-signal gain and phase margin are well defined. This is the single biggest lever for "compatibility."

## The Large Impulse Problem: PA Output Oscillation

Perhaps the most dramatic failure mode is when a **large impulse appears in front of the signal** — a sharp step, a click, or a DC jump at the start of the waveform. This happens when:

- The waveform generator clips the leading edge (e.g., a sawtooth ramp from a DC state to full amplitude).
- A large-amplitude preamble or synchronization pulse precedes the coded signal.
- The DAC slews violently from 0 to full scale in one sample.

### Mechanism

The PA's output stage (and the matching network / transducer inductance) forms a resonant system. A large, spectrally rich impulse injects energy across a huge bandwidth. The transducer coil plus PA output capacitance form an LC tank that **rings**. Even worse, the transient can momentarily push the output transistors into saturation or cutoff, temporarily opening the feedback loop. When the loop re-closes, it can hunt, and at high amplitude the power supply and output stage limitations produce sustained oscillation:

- **Voltage-limited slew**: the output can't follow the fast step, causing a non-linear "bang-bang" response.
- **Current limiting**: the PA hits its current limit into the mostly inductive transducer load, delaying the voltage build-up and injecting phase lag that destabilizes the loop.
- **Heterodyning with the carrier**: the broadband impulse interacts with the passband signal and the switching (D-class) clock, creating inter-modulation components that land right back in the band.

The classic symptom is a **large oscillating tail** at the output right where the real coded signal should begin, drowning the first several chips in ringing and corrupting the correlation peak.

### Fixes

1. **Shape the leading edge.** Ramp the envelope up smoothly (e.g., a raised-cosine / half-sine "taper" over several chips) so the waveform starts at zero and grows slowly. This removes the broadband impulse.
2. **Use a soft-start / enable ramp** on the PA power rail so the supply, not the signal, ramps up gracefully.
3. **Add a matching network tuned for the load**, with damping to limit the LC ringing (increase the load quality factor match, not the loss).
4. **Envelope shaping at the modulator**: apply a raised-cosine window to the entire burst, not just individual chips. A burst window of a few milliseconds removes both the leading impulse and the abrupt turn-off at the end.

The overall waveform then looks like:

```
envelope(t) = raised_cosine_window over the burst
              × raised_cosine_chips
              × carrier(18.5 kHz)
```

## Combining It All: A Practical Example

Consider a correlation sonar transmit burst targeting the 15 - 22 kHz band:

| Parameter | Value |
|-----------|-------|
| Carrier | 18.5 kHz |
| Chip rate | 4 kchips/s |
| Rolloff β | 0.3 |
| M-sequence length | 127 (7-bit register) |
| Burst window | 2 ms raised-cosine taper on/off |
| PA | Linear, tuned matching network |

With the raised-cosine shaping both per-chip and per-burst, the spectrum sits cleanly inside the band, the PA sees a well-behaved in-band load, and there is no impulsive leading transient to destabilize the output stage. The correlator output shows a single sharp peak with minimal ISI and no ringing precursor.

## Key Takeaways

1. **Match the signal spectrum to the transducer band.** Raw m-sequences are too wideband and DC-centered; shift them to the band with modulation and shape them with raised cosine.
2. **Raised-cosine shaping is the compatibility tool.** It is strictly band-limited and zero-ISI, keeping both the transducer and the PA in their designed operating regions.
3. **A large leading impulse is a PA stability hazard.** It rings the output LC tank, pushes the loop nonlinear, and can cause sustained oscillation before the real signal even starts. Always taper the burst envelope.
4. **Treat signal generation, PA, and transducer as one system.** Waveform design decisions (shaping, windowing, carrier placement) are the cheapest way to buy "match" and "compatibility" before touching hardware.

## References

- Proakis, *Digital Communications* — pulse shaping, matched filtering, Nyquist criterion.
- Urick, *Principles of Underwater Sound* — projector characteristics and resonance.
- [Underwater acoustics / transducer basics (intro)](https://en.wikipedia.org/wiki/Underwater_acoustics)
