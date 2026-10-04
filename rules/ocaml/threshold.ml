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
