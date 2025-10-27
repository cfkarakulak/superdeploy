# Dynamic VM outputs - works with any VM configuration
output "vm_names" {
  description = "Map of all VM names by role"
  value = {
    for key, vm in module.vms : key => vm.name
  }
}

output "vm_public_ips" {
  description = "Map of all VM public IPs by role"
  value = {
    for key, vm in module.vms : key => vm.external_ip
  }
}

output "vm_internal_ips" {
  description = "Map of all VM internal IPs by role"
  value = {
    for key, vm in module.vms : key => vm.internal_ip
  }
}

# Grouped by role for easier access
output "vms_by_role" {
  description = "VMs grouped by role"
  value = {
    for key, config in var.vm_groups : config.role => {
      name        = module.vms[key].name
      external_ip = module.vms[key].external_ip
      internal_ip = module.vms[key].internal_ip
    }...
  }
}

# Ansible inventory preview
output "ansible_inventory_preview" {
  description = "Preview of Ansible inventory structure"
  value = join("\n\n", [
    for role in distinct([for k, v in var.vm_groups : v.role]) : format(
      "[%s]\n%s",
      role,
      join("\n", [
        for key, config in var.vm_groups :
        "${module.vms[key].name} ansible_host=${module.vms[key].external_ip} ansible_user=superdeploy"
        if config.role == role
      ])
    )
  ])
}

# Network outputs
output "network_name" {
  description = "VPC network name"
  value       = module.network.network_name
}

output "subnet_name" {
  description = "Subnet name"
  value       = module.network.subnet_name
}

