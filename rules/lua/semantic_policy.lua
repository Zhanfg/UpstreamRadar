local M = {}

local function clamp(value)
  if value < 0 then return 0 end
  if value > 1 then return 1 end
  return value
end

local function bernoulli_kl(q, p)
  local eps = 1e-12
  q = math.max(eps, math.min(1 - eps, q))
  p = math.max(eps, math.min(1 - eps, p))
  return q * math.log(q / p) + (1 - q) * math.log((1 - q) / (1 - p))
end

function M.bayesian_surprise(empirical, predicted)
  return clamp(1 - math.exp(-3.4 * bernoulli_kl(empirical, predicted)))
end

function M.risk_adjusted(utility, tail_risk, reliability)
  return math.max(0, utility)
    * (1 - 0.11 * clamp(tail_risk))
    * (0.82 + 0.18 * clamp(reliability))
end

function M.classify(event)
  local impact = clamp(tonumber(event.semantic_impact) or 0)
  local security = clamp(tonumber(event.security_signal) or 0)
  local score = 0.65 * impact + 0.35 * security
  if security >= 0.90 or score >= 0.85 then return "critical", score end
  if score >= 0.60 then return "investigate", score end
  if score >= 0.30 then return "observe", score end
  return "quiet", score
end

return M
