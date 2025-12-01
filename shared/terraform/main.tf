# Extract unique VM roles for firewall rules
locals {
  vm_roles = distinct([for k, v in var.vm_groups : v.role])
}

# Network module
module "network" {
  source = "./modules/network"

  project_id                 = var.project_id
  region                     = var.region
  network_name               = var.network_name
  subnet_cidr                = var.subnet_cidr
  admin_source_ranges        = var.admin_source_ranges
  environment                = var.environment
  vm_roles                   = local.vm_roles  # Pass dynamic VM roles
  app_ports                  = var.app_ports   # Pass app ports from project config
  orchestrator_ip            = var.orchestrator_ip  # Pass orchestrator IP for metrics (deprecated)
  orchestrator_subnet        = var.orchestrator_subnet  # Pass orchestrator subnet for VPC peering
  orchestrator_network_name  = var.orchestrator_network_name  # Pass orchestrator network for VPC peering
  allowed_client_subnets     = var.allowed_client_subnets  # For orchestrator: allow all project subnets
}

# Dynamic VM creation based on project configuration
# Each VM group is created dynamically from var.vm_groups
module "vms" {
  source   = "./modules/instance"
  for_each = var.vm_groups

  project_id    = var.project_id
  region        = var.region
  zone          = var.zone
  name          = "${var.project_name}-${each.key}"  # each.key already contains "role-index"
  machine_type  = each.value.machine_type
  disk_size     = each.value.disk_size
  image         = var.vm_image
  network       = module.network.network_self_link
  subnetwork    = module.network.subnet_self_link
  tags          = each.value.tags
  ssh_pub_key   = file(pathexpand(var.ssh_pub_key_path))
  environment   = var.environment

  # All VMs get external IP for now (can be configured per VM in future)
  create_external_ip = true

  labels = merge(
    {
      project     = var.project_name
      role        = each.value.role
      environment = var.environment
    },
    each.value.labels
  )
}

