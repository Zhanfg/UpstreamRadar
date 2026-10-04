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
