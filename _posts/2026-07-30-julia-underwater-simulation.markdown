---
layout: post
title:  "Julia水下仿真"
date:   2026-07-30 14:14:48 +0800
categories: julia
---

使用Julia语言进行水下仿真模拟，结合流体力学和机器人运动控制。

## 环境配置

{% highlight julia %}
using Pkg
Pkg.add(["DifferentialEquations", "Plots", "LinearAlgebra"])

using DifferentialEquations
using Plots
using LinearAlgebra
{% endhighlight %}

## 水下动力学模型

基于Fossen模型的水下航行器动力学方程：

$$ M \dot{\nu} + C(\nu)\nu + D(\nu)\nu + g(\eta) = \tau $$

{% highlight julia %}
function underwater_dynamics!(dν, ν, p, t)
    M, D, g, τ = p
    C = coriolis_matrix(ν)
    dν .= M \ (τ - C * ν - D * ν - g)
end

function coriolis_matrix(ν)
    u, v, w, p, q, r = ν
    m = 100.0
    C = zeros(6, 6)
    C[1,2] = -m * r
    C[1,3] = m * q
    C[2,1] = m * r
    C[2,3] = -m * p
    C[3,1] = -m * q
    C[3,2] = m * p
    return C
end
{% endhighlight %}

## 推进器推力分配

{% highlight julia %}
function thrust_allocation(τ_desired)
    T = [0.707  0.707  0.707  0.707;
        -0.707  0.707  0.707 -0.707;
         0.1   -0.1    0.1   -0.1]

    u = pinv(T) * τ_desired
    return clamp.(u, -100, 100)
end

τ_cmd = [50.0, 0.0, 10.0]
thruster_forces = thrust_allocation(τ_cmd)
{% endhighlight %}

## 仿真结果可视化

{% highlight julia %}
function simulate(; T_end=10.0)
    ν0 = zeros(6)
    tspan = (0.0, T_end)
    M = diagm([100, 100, 100, 10, 10, 10])
    D = diagm([10, 10, 10, 5, 5, 5])
    g = zeros(6)
    τ = [50.0, 0.0, 0.0, 0.0, 0.0, 10.0]
    params = (M, D, g, τ)

    prob = ODEProblem(underwater_dynamics!, ν0, tspan, params)
    sol = solve(prob, Tsit5())

    plt = plot(sol, xlabel="Time (s)", ylabel="Velocity",
               title="Underwater Vehicle Velocity Response",
               legend=:topright, lw=2)
    return plt
end

simulate()
{% endhighlight %}

## 洋流扰动模型

{% highlight julia %}
function ocean_current(t)
    Vc = 0.5
    βc = π/4
    uc = Vc * cos(βc)
    vc = Vc * sin(βc)
    return [uc, vc, 0.0, 0.0, 0.0, 0.0]
end

function relative_velocity(ν, t)
    νc = ocean_current(t)
    return ν - νc
end
{% endhighlight %}

## 参考链接

- [Marine Systems Simulator (MSS)](https://github.com/cybergalactic/MSS)
- [DifferentialEquations.jl](https://docs.sciml.ai/DiffEqDocs/stable/)
- [Fossen Handbook of Marine Craft](https://www.wiley.com/en-us/Handbook+of+Marine+Craft+Hydrodynamics+and+Motion+Control)

