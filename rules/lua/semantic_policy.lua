local M = {}

local function clamp(value)
  if value < 0 then return 0 end
  if value > 1 then return 1 end
  return value
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
