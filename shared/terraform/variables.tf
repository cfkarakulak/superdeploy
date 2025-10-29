variable "project_id" {
  description = "GCP Project ID"
  type        = string
}

variable "project_name" {
  description = "SuperDeploy project name (for resource naming and isolation)"
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

# Dynamic VM groups - Fully configurable per project
# Each VM is defined with all its properties
variable "vm_groups" {
  description = "Dynamic VM configuration - maps VM name to its properties"
  type = map(object({
    role         = string
    index        = number
    machine_type = string
    disk_size    = number
    tags         = list(string)
    labels       = map(string)
  }))
  default = {}
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

# Image
variable "vm_image" {
  description = "VM boot disk image"
  type        = string
  default     = "debian-cloud/debian-11"
}

# Application Ports
variable "app_ports" {
  description = "List of application ports to expose (extracted from project config)"
  type        = list(string)
  default     = []
}

