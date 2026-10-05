module UpstreamRadar.ChangePoint

let mean (values: float array) =
    if values.Length = 0 then 0.0 else Array.average values

let score (history: float array) (recent: float array) =
    if history.Length = 0 || recent.Length = 0 then 0.0
    else
        let baseline = mean history
        let current = mean recent
        let scale =
            history
            |> Array.map (fun value -> abs (value - baseline))
            |> mean
            |> max 1e-9
        abs (current - baseline) / scale


let clamp01 value = max 0.0 (min 1.0 value)

let bernoulliKl q p =
    let eps = 1e-12
    let qv = max eps (min (1.0 - eps) q)
    let pv = max eps (min (1.0 - eps) p)
    qv * log (qv / pv) + (1.0 - qv) * log ((1.0 - qv) / (1.0 - pv))

let bayesianSurprise empirical predicted =
    clamp01 (1.0 - exp (-3.4 * bernoulliKl empirical predicted))

let cvar (quantile: float) (values: float array) =
    if values.Length = 0 then 0.0
    else
        let sorted = values |> Array.map clamp01 |> Array.sort
        let q = max 0.5 (min 0.999999 quantile)
        let start = min (sorted.Length - 1) (int (floor (float sorted.Length * q)))
        sorted[start..] |> Array.average

let ensembleScore (history: float array) (recent: float array) =
    let cp = score history recent |> fun value -> 1.0 - exp(-value)
    let combined = Array.append history recent
    if combined.Length < 2 then clamp01 cp
    else
        let first = combined[0]
        let last = combined[combined.Length - 1]
        let direction = clamp01 (abs (last - first))
        clamp01 (0.72 * cp + 0.28 * direction)
