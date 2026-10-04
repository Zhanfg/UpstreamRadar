module HarmonyV3

using Statistics

export bernoulli_kl, bayesian_surprise, cvar, change_ensemble

clamp01(x::Real) = clamp(Float64(x), 0.0, 1.0)

function bernoulli_kl(q::Real, p::Real)
    eps = 1e-12
    qv = clamp(Float64(q), eps, 1 - eps)
    pv = clamp(Float64(p), eps, 1 - eps)
    qv * log(qv / pv) + (1 - qv) * log((1 - qv) / (1 - pv))
end

bayesian_surprise(q::Real, p::Real) =
    clamp01(1 - exp(-3.4 * bernoulli_kl(q, p)))

function cvar(values::AbstractVector{<:Real}, quantile::Real = 0.75)
    isempty(values) && return 0.0
    xs = sort(clamp01.(values))
    q = clamp(Float64(quantile), 0.5, 0.999999)
    start = floor(Int, (length(xs) - 1) * q) + 1
    mean(@view xs[start:end])
end

function change_ensemble(values::AbstractVector{<:Real}, page_hinkley::Real = 0.0)
    length(values) < 2 && return clamp01(page_hinkley)
    xs = Float64.(values)
    prior = @view xs[1:end-1]
    center = median(prior)
    scale = max(1.4826 * median(abs.(prior .- center)), 1e-6)
    jump = clamp01(abs(xs[end] - center) / (1.35 * scale))

    n = length(xs)
    xbar = (n - 1) / 2
    ybar = mean(xs)
    denominator = sum((i - 1 - xbar)^2 for i in 1:n)
    slope = denominator == 0 ? 0.0 :
        sum((i - 1 - xbar) * (xs[i] - ybar) for i in 1:n) / denominator
    slope_signal = clamp01(abs(slope) * 4)
    clamp01(0.5 * page_hinkley + 0.3 * jump + 0.2 * slope_signal)
end

end
