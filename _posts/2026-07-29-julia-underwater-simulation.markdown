---
layout: post
title:  "Coastal Acoustic Tomography Simulation with Julia"
date:   2026-07-29 14:14:48 +0800
categories: julia
---
Coastal Acoustic Tomography (CAT) uses reciprocal acoustic transmissions between multiple stations to measure ocean temperature and current velocity fields at kilometer scales. This post implements a CAT forward model and inversion in Julia.

## Principle of Operation

Multiple acoustic transceivers are deployed around a coastal region. Each pair measures the round-trip travel time difference $$\Delta t$$, which reveals the path-averaged current velocity:

$$
\Delta t_{ij} = -2 \int_{\Gamma_{ij}} \frac{\mathbf{u} \cdot d\mathbf{s}}{c^2}
$$

The sum of travel times gives the path-averaged sound speed (temperature proxy):

$$
t_{ij}^+ = 2 \int_{\Gamma_{ij}} \frac{ds}{c}
$$

## Setting Up the Environment

{% highlight julia %}
using LinearAlgebra, SparseArrays, Plots, Random

const C0 = 1500.0      # reference sound speed (m/s)
const NX, NY = 20, 20   # grid resolution
const DX, DY = 500.0, 500.0  # grid spacing (m)
{% endhighlight %}

## Station Deployment and Ray Paths

{% highlight julia %}
function deploy_stations(n_stations=4)
    θ = range(0, 2π, length=n_stations+1)[1:n_stations]
    radius = 2000.0
    center = [(NX*DX)/2, (NY*DY)/2]
    return [(center[1] + radius * cos(ϕ), center[2] + radius * sin(ϕ))
            for ϕ in θ]
end

function ray_path(A, B; n_pts=50)
    xs = range(A[1], B[1], length=n_pts)
    ys = range(A[2], B[2], length=n_pts)
    return collect(zip(xs, ys))
end

stations = deploy_stations(4)
pairs = [(i, j) for i in 1:4 for j in i+1:4]
{% endhighlight %}

## Synthetic Ocean Current Field

{% highlight julia %}
function synthetic_current_field()
    x = range(0, (NX-1)*DX, length=NX)
    y = range(0, (NY-1)*DY, length=NY)
    X = [xi for xi in x, _ in y]
    Y = [yi for _ in x, yi in y]

    u = 0.5 * sin.(π * X / (NX*DX)) .* cos.(π * Y / (NY*DY))
    v = 0.3 * cos.(π * X / (NX*DX)) .* sin.(π * Y / (NY*DY))

    return x, y, u, v
end
{% endhighlight %}

## Forward Model: Ray Integral Matrix

The core of CAT is constructing the observation matrix $$\mathbf{G}$$ that maps the grid velocity field to travel time differences:

{% highlight julia %}
function build_observation_matrix(stations, pairs)
    n_pairs = length(pairs)
    n_cells = NX * NY
    G = spzeros(n_pairs, n_cells)

    for (idx, (i, j)) in enumerate(pairs)
        pts = ray_path(stations[i], stations[j])
        cell_visited = zeros(Bool, NX, NY)

        for (x, y) in pts
            ix = clamp(Int(floor(x / DX)) + 1, 1, NX)
            iy = clamp(Int(floor(y / DY)) + 1, 1, NY)
            cell_visited[ix, iy] = true
        end

        seg_len = norm(stations[i] .- stations[j]) / sum(cell_visited)
        for ix in 1:NX, iy in 1:NY
            if cell_visited[ix, iy]
                col = (iy - 1) * NX + ix
                G[idx, col] = seg_len / (C0^2)
            end
        end
    end
    return G
end
{% endhighlight %}

## Simulating Observations

{% highlight julia %}
function simulate_travel_times(G, u, v)
    n_cells = NX * NY
    u_vec = reshape(u, n_cells)
    v_vec = reshape(v, n_cells)

    ray_velocities = G * u_vec

    Δt = -2.0 .* ray_velocities
    noise = 0.001 * randn(length(Δt))
    return Δt + noise
end
{% endhighlight %}

## Tikhonov Regularized Inversion

CAT inversion is ill-posed. We use Tikhonov regularization with a Laplacian smoothness prior:

{% highlight julia %}
function tikhonov_inversion(G, Δt_obs, λ=0.1)
    G_dense = Matrix(G)
    n = size(G, 2)

    L = laplacian_2d(NX, NY)

    A = G_dense' * G_dense + λ * (L' * L)
    b = G_dense' * Δt_obs

    u_rec = A \ b
    return reshape(u_rec, NX, NY)
end

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
{% endhighlight %}

## Full Simulation Pipeline

{% highlight julia %}
function run_cat_simulation(; λs=[0.01, 0.1, 1.0, 10.0])
    stations = deploy_stations(4)
    pairs = [(i, j) for i in 1:4 for j in i+1:4]

    x, y, u_true, v_true = synthetic_current_field()
    G = build_observation_matrix(stations, pairs)
    Δt_obs = simulate_travel_times(G, u_true, v_true)

    results = []
    for λ in λs
        u_rec = tikhonov_inversion(G, Δt_obs, λ)
        rmse = sqrt(mean((u_rec .- u_true).^2))
        push!(results, (λ=λ, u_rec=u_rec, rmse=rmse))
    end

    return x, y, u_true, results, stations, pairs
end

x, y, u_true, results, stations, pairs = run_cat_simulation()
{% endhighlight %}

## Visualization

{% highlight julia %}
function plot_cat_results(x, y, u_true, results, stations, pairs)
    n = length(results) + 1
    p = plot(layout=(1, n), size=(n*350, 300),
             titlefont=8, tickfont=6)

    heatmap!(p[1], x/1000, y/1000, u_true',
             title="True Field", xlabel="km", ylabel="km",
             aspect_ratio=:equal, color=:viridis)

    for (idx, res) in enumerate(results)
        heatmap!(p[idx+1], x/1000, y/1000, res.u_rec',
                 title="λ=$(res.λ), RMSE=$(round(res.rmse, digits=4))",
                 xlabel="km", aspect_ratio=:equal, color=:viridis)
    end

    for s in stations
        scatter!(p[1], [s[1]/1000], [s[2]/1000],
                 markersize=6, color=:red, label="")
    end
    return p
end

plot_cat_results(x, y, u_true, results, stations, pairs)
{% endhighlight %}

## Key Parameters for Field Deployments

| Parameter | Typical Range | Notes |
|-----------|--------------|-------|
| Frequency | 3-10 kHz | Higher frequency = better resolution, shorter range |
| Station spacing | 500m - 10km | Determined by acoustic range and bathymetry |
| Transmission interval | 30-120s | Balances temporal resolution with multipath rejection |
| Number of stations | 3-8 | More stations = better spatial coverage |
| Regularization λ | 0.001-10 | Determined by L-curve or GCV analysis |

## References

- [Coastal Acoustic Tomography (Kaneko et al., 2020)](https://www.cambridge.org/core/books/coastal-acoustic-tomography/)
- [Ocean Acoustic Tomography (Munk et al., 1995)](https://www.cambridge.org/core/books/ocean-acoustic-tomography/)
- [Julia Ocean Acoustics Tools](https://github.com/JuliaOcean/Acoustics.jl)
