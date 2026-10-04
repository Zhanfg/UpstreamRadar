terraform {
  required_version = ">= 1.8.0"
}

variable "collector_name" {
  type        = string
  description = "Logical name of the collector deployment."
  default     = "upstreamradar"
}

variable "poll_interval_seconds" {
  type        = number
  description = "Collector polling interval."
  default     = 900

  validation {
    condition     = var.poll_interval_seconds >= 60
    error_message = "poll_interval_seconds must be at least 60."
  }
}

variable "sources" {
  type        = set(string)
  description = "Enabled upstream source adapters."
  default     = ["github", "gitlab"]
}

variable "harmony_v3" {
  type = object({
    surprise_weight           = number
    structural_novelty_weight = number
    tail_risk_penalty         = number
    cvar_quantile             = number
    beam_width                = number
  })

  default = {
    surprise_weight           = 0.08
    structural_novelty_weight = 0.06
    tail_risk_penalty         = 0.11
    cvar_quantile             = 0.75
    beam_width                = 128
  }

  validation {
    condition = (
      var.harmony_v3.surprise_weight >= 0 &&
      var.harmony_v3.structural_novelty_weight >= 0 &&
      var.harmony_v3.tail_risk_penalty >= 0 &&
      var.harmony_v3.cvar_quantile >= 0.5 &&
      var.harmony_v3.cvar_quantile < 1 &&
      var.harmony_v3.beam_width >= 8
    )
    error_message = "Invalid HARMONY v3 algorithm configuration."
  }
}

locals {
  deployment = {
    name          = var.collector_name
    poll_interval = var.poll_interval_seconds
    sources       = sort(tolist(var.sources))
    harmony_v3    = var.harmony_v3
  }
}

output "collector_contract" {
  value = local.deployment
}
