# Core VM outputs
output "vm_core_names" {
  description = "Names of CORE VMs"
  value       = module.vm_core[*].name
}

output "vm_core_public_ips" {
  description = "Public IP addresses of CORE VMs (for external access)"
  value       = module.vm_core[*].external_ip
}

output "vm_core_internal_ips" {
  description = "Internal IP addresses of CORE VMs (for VPC communication)"
  value       = module.vm_core[*].internal_ip
}

# Scrape VM outputs
output "vm_scrape_names" {
  description = "Names of SCRAPE VMs"
  value       = module.vm_scrape[*].name
}

output "vm_scrape_public_ips" {
  description = "Public IP addresses of SCRAPE VMs (for SSH access)"
  value       = module.vm_scrape[*].external_ip
}

output "vm_scrape_internal_ips" {
  description = "Internal IP addresses of SCRAPE VMs (for VPC communication)"
  value       = module.vm_scrape[*].internal_ip
}

# Proxy VM outputs
output "vm_proxy_names" {
  description = "Names of PROXY VMs"
  value       = module.vm_proxy[*].name
}

output "vm_proxy_public_ips" {
  description = "Public IP addresses of PROXY VMs (used by workers for proxy connections)"
  value       = module.vm_proxy[*].external_ip
}

output "vm_proxy_internal_ips" {
  description = "Internal IP addresses of PROXY VMs (for VPC communication)"
  value       = module.vm_proxy[*].internal_ip
}

# Combined outputs
output "all_vm_ips" {
  description = "All VM public IPs in a single map"
  value = {
    core   = module.vm_core[*].external_ip
    scrape = module.vm_scrape[*].external_ip
    proxy  = module.vm_proxy[*].external_ip
  }
}

output "ansible_inventory_preview" {
  description = "Preview of Ansible inventory structure"
  value = <<-EOT
    [core]
    ${join("\n", [for idx, vm in module.vm_core : "${vm.name} ansible_host=${vm.external_ip} ansible_user=superdeploy"])}

    [scrape]
    ${join("\n", [for idx, vm in module.vm_scrape : "${vm.name} ansible_host=${vm.external_ip} ansible_user=superdeploy"])}

    [proxy]
    ${join("\n", [for idx, vm in module.vm_proxy : "${vm.name} ansible_host=${vm.external_ip} ansible_user=superdeploy"])}
  EOT
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

# Edge IP (primary core VM for external access)
output "edge_ip" {
  description = "Edge/API endpoint IP (first core VM)"
  value       = length(module.vm_core) > 0 ? module.vm_core[0].external_ip : null
}

# Proxy IPs (formatted for easy copy-paste)
output "proxy_ips_list" {
  description = "Proxy IPs as comma-separated list"
  value       = join(",", module.vm_proxy[*].external_ip)
}

