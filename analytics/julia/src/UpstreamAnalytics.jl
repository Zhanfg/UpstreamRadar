module UpstreamAnalytics

using Statistics

export ewma, robust_zscore

function ewma(values::AbstractVector{<:Real}, alpha::Real = 0.3)
    0 < alpha <= 1 || throw(ArgumentError("alpha must be in (0, 1]"))
    isempty(values) && return Float64[]
    out = Vector{Float64}(undef, length(values))
    out[1] = Float64(values[1])
    for i in 2:length(values)
        out[i] = alpha * values[i] + (1 - alpha) * out[i - 1]
    end
    out
end

function robust_zscore(values::AbstractVector{<:Real})
    isempty(values) && return Float64[]
    xs = Float64.(values)
    center = median(xs)
    deviations = abs.(xs .- center)
    scale = median(deviations)
    scale == 0 && return zeros(length(xs))
    0.67448975 .* (xs .- center) ./ scale
end

end
