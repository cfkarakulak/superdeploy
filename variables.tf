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
  default     = "us-central1-c"
}

variable "environment" {
  description = "Environment name (dev, staging, prod)"
  type        = string
  default     = "dev"
}

# VM counts
variable "vm_counts" {
  description = "Number of VMs per role"
  type = object({
    core   = number
    scrape = number
    proxy  = number
  })
  default = {
    core   = 1
    scrape = 1
    proxy  = 1
  }
}

# Machine types
variable "machine_types" {
  description = "GCP machine types for each VM role"
  type = object({
    core   = string
    scrape = string
    proxy  = string
  })
  default = {
    core   = "e2-standard-2"  # 2 vCPU, 8 GB RAM
    scrape = "e2-standard-4"  # 4 vCPU, 16 GB RAM
    proxy  = "e2-small"       # 2 vCPU, 2 GB RAM
  }
}

# Disk sizes (GB)
variable "disk_sizes" {
  description = "Boot disk sizes in GB"
  type = object({
    core   = number
    scrape = number
    proxy  = number
  })
  default = {
    core   = 50
    scrape = 100
    proxy  = 20
  }
}

# Network
variable "network_name" {
  description = "VPC network name"
  type        = string
  default     = "superdeploy-network"
}

variable "subnet_cidr" {
  description = "Subnet CIDR range"
  type        = string
  default     = "10.0.0.0/24"
}

# SSH
variable "ssh_pub_key_path" {
  description = "Path to SSH public key for VM access"
  type        = string
  default     = "~/.ssh/id_rsa.pub"
}

variable "admin_source_ranges" {
  description = "IP ranges allowed to SSH into VMs"
  type        = list(string)
  default     = ["0.0.0.0/0"]  # Change this in production!
}

# Tags
variable "tags" {
  description = "Network tags for VMs"
  type = object({
    core   = list(string)
    scrape = list(string)
    proxy  = list(string)
  })
  default = {
    core   = ["core", "edge", "api", "queue", "db"]
    scrape = ["worker", "scrape"]
    proxy  = ["proxy", "socks"]
  }
}

# Image
variable "vm_image" {
  description = "VM boot disk image"
  type        = string
  default     = "debian-cloud/debian-11"
}

