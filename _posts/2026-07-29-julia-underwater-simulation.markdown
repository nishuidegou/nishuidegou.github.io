---
layout: post
title:  "Coastal Acoustic Tomography Simulation with Julia"
date:   2026-07-29 14:14:48 +0800
categories: julia
---
Coastal Acoustic Tomography (CAT) uses reciprocal acoustic transmissions between multiple stations to measure ocean current velocity fields at kilometer scales. This post implements a CAT forward model and Tikhonov-regularized inversion in Julia, with simulation results and analysis.

## Principle of Operation

Multiple acoustic transceivers are deployed around a coastal region. Each pair measures the round-trip travel time difference $$\Delta t$$, which reveals the path-averaged current velocity:

$$
\Delta t_{ij} = -2 \int_{\Gamma_{ij}} \frac{\mathbf{u} \cdot d\mathbf{s}}{c^2}
$$

The sum of travel times gives the path-averaged sound speed (temperature proxy):

$$
t_{ij}^+ = 2 \int_{\Gamma_{ij}} \frac{ds}{c}
$$

## Setup and Grid Configuration

{% highlight julia %}
using LinearAlgebra, SparseArrays, Random, Statistics, Plots
gr()

const C0 = 1500.0            # reference sound speed (m/s)
const NX, NY = 10, 10         # 10×10 grid
const DX, DY = 500.0, 500.0   # 500m grid spacing
{% endhighlight %}

## Station Deployment and Ray Paths

Six acoustic stations form a 3 km radius ring around the 5 km × 5 km domain, yielding 15 reciprocal ray paths:

{% highlight julia %}
function deploy_stations(n_stations=6)
    θ = range(0, 2π, length=n_stations+1)[1:n_stations]
    radius = 3000.0
    center = [(NX*DX)/2, (NY*DY)/2]
    return [(center[1] + radius * cos(ϕ), center[2] + radius * sin(ϕ))
            for ϕ in θ]
end

function ray_path(A, B; n_pts=80)
    return collect(zip(range(A[1], B[1], length=n_pts),
                       range(A[2], B[2], length=n_pts)))
end
{% endhighlight %}

## Synthetic Ocean Current Field

We construct a test field with a positive Gaussian eddy near the center and a weaker negative eddy to the northwest, simulating realistic coastal flow structures:

{% highlight julia %}
function synthetic_current_field()
    x = range(0, (NX-1)*DX, length=NX)
    y = range(0, (NY-1)*DY, length=NY)
    X = [xi for xi in x, _ in y]
    Y = [yi for _ in x, yi in y]

    u = 0.8 * exp.(-((X .- 2500).^2 + (Y .- 2500).^2) ./ (800^2)) .-
        0.4 * exp.(-((X .- 2000).^2 + (Y .- 3500).^2) ./ (600^2))
    v = 0.3 * sin.(2π * X / (NX*DX)) .* cos.(π * Y / (NY*DY))

    return x, y, u, v
end
{% endhighlight %}

## Forward Model: Ray Integral Matrix

The observation matrix $$\mathbf{G}$$ maps the discretized grid velocity to travel time differences along each ray. Each row integrates the u-velocity component along one path:

{% highlight julia %}
function build_observation_matrix(stations, pairs)
    n_pairs = length(pairs)
    n_cells = NX * NY
    G = spzeros(n_pairs, n_cells)

    for (idx, (i, j)) in enumerate(pairs)
        pts = ray_path(stations[i], stations[j])
        cell_hits = zeros(Int, NX, NY)
        for (x, y) in pts
            ix = clamp(Int(floor(x / DX)) + 1, 1, NX)
            iy = clamp(Int(floor(y / DY)) + 1, 1, NY)
            cell_hits[ix, iy] += 1
        end

        total_hits = max(sum(cell_hits), 1)
        seg_len = norm(stations[i] .- stations[j]) / total_hits
        for ix in 1:NX, iy in 1:NY
            if cell_hits[ix, iy] > 0
                col = (iy - 1) * NX + ix
                G[idx, col] = cell_hits[ix, iy] * seg_len / (C0^2)
            end
        end
    end
    return Matrix(G)
end
{% endhighlight %}

The resulting system is severely **underdetermined**: only 15 observation equations for 100 unknown grid cells. The condition number of $$\mathbf{G}^T\mathbf{G}$$ approaches infinity, making naive inversion impossible.

## Simulating Observations

{% highlight julia %}
function simulate_travel_times(G, u, v)
    u_vec = reshape(u, NX*NY)
    ray_velocities = G * u_vec
    Δt = -2.0 .* ray_velocities
    noise = 5e-4 * randn(length(Δt))    # Gaussian noise σ = 0.5ms
    return Δt + noise, noise
end
{% endhighlight %}

## Tikhonov Regularized Inversion

We stabilize the ill-posed inversion with a 2D Laplacian smoothness prior:

$$
\mathbf{u}_{\text{rec}} = (\mathbf{G}^T\mathbf{G} + \lambda \mathbf{L}^T\mathbf{L})^{-1} \mathbf{G}^T \boldsymbol{\Delta}\mathbf{t}_{\text{obs}}
$$

{% highlight julia %}
function laplacian_2d(nx, ny)
    n = nx * ny
    L = spzeros(n, n)
    for ix in 1:nx, iy in 1:ny
        k = (iy-1)*nx + ix
        L[k, k] = 4.0
        if ix > 1;  L[k, k-1]    = -1.0; end
        if ix < nx; L[k, k+1]    = -1.0; end
        if iy > 1;  L[k, k-nx]   = -1.0; end
        if iy < ny; L[k, k+nx]   = -1.0; end
    end
    return L
end

function tikhonov_inversion(G, Δt_obs, λ)
    L = laplacian_2d(NX, NY)
    A = G' * G + λ * (L' * L)
    b = G' * Δt_obs
    u_rec = A \ b
    return reshape(u_rec, NX, NY)
end
{% endhighlight %}

## Simulation Results

We ran the forward model with 6 stations around a 10×10 grid (5 km × 5 km domain), producing 15 ray paths. Gaussian noise (σ = 0.5 ms) was added to synthetic observations. The table below shows reconstruction error for different regularization strengths λ:

| λ | RMSE (m/s) |
|---|-----------|
| 10⁻⁶ | 0.3556 |
| 10⁻⁴ | 0.1730 |
| 10⁻² | 0.1553 |
| 10⁻¹ | 0.1551 |
| 10⁰ | 0.1551 |
| **10¹** | **0.1551** |

### Full Reconstruction Comparison

The grid below shows the true field alongside reconstructions for each λ. Green triangles mark acoustic station positions and thin lines show the 15 reciprocal ray paths. The gold star indicates the best-performing regularization (λ = 10):

![CAT Reconstruction Overview](/assets/images/cat_overview.png)

### True vs Best Reconstruction

The reconstructed field with λ = 10 captures the main eddy structure and spatial pattern, though the underdetermined nature (100 unknowns from 15 measurements) limits fine-scale resolution:

![CAT Comparison](/assets/images/cat_comparison.png)

### RMSE vs Regularization

The L-curve-like analysis shows RMSE stabilizes for λ ≳ 0.01, indicating the regularization adequately controls solution smoothness:

![CAT L-Curve](/assets/images/cat_lcurve.png)

### Travel Time Observations

Simulated travel time differences across the 15 ray pairs. The noise component (±0.5 ms) is shown as gray shading. Note the relatively strong signal on rays 3, 8, and 14 that cross the main eddy:

![CAT Travel Times](/assets/images/cat_traveltimes.png)

## Key Findings

1. **Underdetermination**: Only 15 observations constrain 100 unknowns — severe in coastal settings with few stations.
2. **Regularization effectiveness**: Without regularization (λ → 0), RMSE nearly doubles. The Laplacian prior reduces RMSE by 56%.
3. **Saturation**: Beyond λ ≈ 0.01, further regularization adds diminishing returns, confirming the optimal value near λ = 0.01 — 0.1.
4. **Resolution limit**: The reconstructed eddy appears smoothed; ray geometry fundamentally limits spatial resolution.

## Key Parameters for Field Deployments

| Parameter | Typical Range | This Simulation |
|-----------|--------------|-----------------|
| Frequency | 3-10 kHz | — |
| Station spacing | 500m - 10km | ~5 km (diagonal) |
| Transmission interval | 30-120s | — |
| Number of stations | 3-8 | 6 stations, 15 paths |
| Grid cells | N×N | 10×10 (100 cells) |
| Regularization λ | 0.001-10 | 10⁻⁶ — 10¹ |

## References

- [Coastal Acoustic Tomography (Kaneko et al., 2020)](https://www.cambridge.org/core/books/coastal-acoustic-tomography/)
- [Ocean Acoustic Tomography (Munk et al., 1995)](https://www.cambridge.org/core/books/ocean-acoustic-tomography/)
- [Marine Systems Simulator (Fossen)](https://github.com/cybergalactic/MSS)
