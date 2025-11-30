variable "project_id" {
  description = "GCP Project ID"
  type        = string
}

variable "region" {
  description = "GCP region"
  type        = string
  default     = "us-central1"
}

variable "zone" {
  description = "GCP zone"
  type        = string
}

variable "name" {
  description = "VM instance name"
  type        = string
}

variable "machine_type" {
  description = "GCP machine type"
  type        = string
}

variable "disk_size" {
  description = "Boot disk size in GB"
  type        = number
  default     = 50
}

variable "disk_type" {
  description = "Boot disk type"
  type        = string
  default     = "pd-standard"  # pd-ssd for better performance
}

variable "image" {
  description = "Boot disk image"
  type        = string
  default     = "debian-cloud/debian-11"
}

variable "network" {
  description = "Network self link"
  type        = string
}

variable "subnetwork" {
  description = "Subnetwork self link"
  type        = string
}

variable "tags" {
  description = "Network tags"
  type        = list(string)
  default     = []
}

variable "labels" {
  description = "Resource labels"
  type        = map(string)
  default     = {}
}

variable "ssh_pub_key" {
  description = "SSH public key content"
  type        = string
}

variable "create_external_ip" {
  description = "Whether to create and attach an external IP"
  type        = bool
  default     = true
}

variable "startup_script" {
  description = "Custom startup script"
  type        = string
  default     = ""
}

variable "service_account_email" {
  description = "Service account email for the VM"
  type        = string
  default     = "default"
}

variable "environment" {
  description = "Environment name"
  type        = string
}
