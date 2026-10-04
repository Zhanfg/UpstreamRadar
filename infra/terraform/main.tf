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

locals {
  deployment = {
    name          = var.collector_name
    poll_interval = var.poll_interval_seconds
    sources       = sort(tolist(var.sources))
  }
}

output "collector_contract" {
  value = local.deployment
}
