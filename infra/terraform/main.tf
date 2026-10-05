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

variable "skopraed_v1" {
  type = object({
    surprise_weight             = number
    structural_novelty_weight   = number
    museum_weight               = number
    museum_disagreement_penalty = number
    tail_risk_penalty           = number
    cvar_quantile               = number
    beam_width                  = number
    empirical_bayes_strength    = number
    empirical_bayes_shrinkage   = number
  })

  default = {
    surprise_weight             = 0.08
    structural_novelty_weight   = 0.06
    museum_weight               = 0.12
    museum_disagreement_penalty = 0.08
    tail_risk_penalty           = 0.11
    cvar_quantile               = 0.75
    beam_width                  = 128
    empirical_bayes_strength    = 4.0
    empirical_bayes_shrinkage   = 0.35
  }

  validation {
    condition = (
      var.skopraed_v1.surprise_weight >= 0 &&
      var.skopraed_v1.structural_novelty_weight >= 0 &&
      var.skopraed_v1.tail_risk_penalty >= 0 &&
      var.skopraed_v1.museum_weight >= 0 &&
      var.skopraed_v1.museum_disagreement_penalty >= 0 &&
      var.skopraed_v1.cvar_quantile >= 0.5 &&
      var.skopraed_v1.cvar_quantile < 1 &&
      var.skopraed_v1.beam_width >= 8 &&
      var.skopraed_v1.empirical_bayes_strength > 0 &&
      var.skopraed_v1.empirical_bayes_shrinkage >= 0 &&
      var.skopraed_v1.empirical_bayes_shrinkage <= 1
    )
    error_message = "Invalid SKOPRÆD v1 algorithm configuration."
  }
}

locals {
  deployment = {
    name          = var.collector_name
    poll_interval = var.poll_interval_seconds
    sources       = sort(tolist(var.sources))
    skopraed_v1  = var.skopraed_v1
  }
}

output "collector_contract" {
  value = local.deployment
}
