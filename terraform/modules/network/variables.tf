variable "project_id" {
  description = "GCP Project ID"
  type        = string
}

variable "region" {
  description = "GCP region"
  type        = string
}

variable "network_name" {
  description = "VPC network name"
  type        = string
}

variable "subnet_cidr" {
  description = "Subnet CIDR range"
  type        = string
}

variable "admin_source_ranges" {
  description = "IP ranges allowed for SSH access"
  type        = list(string)
}

variable "environment" {
  description = "Environment name"
  type        = string
}

