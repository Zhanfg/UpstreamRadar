type severity = Quiet | Observe | Investigate | Critical

let classify impact security =
  let impact = Float.max 0.0 (Float.min 1.0 impact) in
  let security = Float.max 0.0 (Float.min 1.0 security) in
  let combined = (0.65 *. impact) +. (0.35 *. security) in
  if security >= 0.90 || combined >= 0.85 then Critical
  else if combined >= 0.60 then Investigate
  else if combined >= 0.30 then Observe
  else Quiet

let to_string = function
  | Quiet -> "quiet"
  | Observe -> "observe"
  | Investigate -> "investigate"
  | Critical -> "critical"


let clamp01 value = Float.max 0.0 (Float.min 1.0 value)

let bernoulli_kl q p =
  let eps = 1e-12 in
  let q = Float.max eps (Float.min (1.0 -. eps) q) in
  let p = Float.max eps (Float.min (1.0 -. eps) p) in
  q *. Float.log (q /. p)
  +. (1.0 -. q) *. Float.log ((1.0 -. q) /. (1.0 -. p))

let bayesian_surprise empirical predicted =
  clamp01 (1.0 -. Float.exp (-3.4 *. bernoulli_kl empirical predicted))

let risk_adjusted ~utility ~tail_risk ~reliability =
  Float.max 0.0 utility
  *. (1.0 -. 0.11 *. clamp01 tail_risk)
  *. (0.82 +. 0.18 *. clamp01 reliability)

let classify_v3 ~impact ~security ~surprise ~tail_risk =
  let evidence =
    0.50 *. clamp01 impact
    +. 0.25 *. clamp01 security
    +. 0.20 *. clamp01 surprise
    +. 0.05 *. clamp01 tail_risk
  in
  if security >= 0.90 || evidence >= 0.86 then Critical
  else if evidence >= 0.62 then Investigate
  else if evidence >= 0.30 then Observe
  else Quiet
