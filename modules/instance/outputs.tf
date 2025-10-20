output "name" {
  description = "Instance name"
  value       = google_compute_instance.vm.name
}

output "id" {
  description = "Instance ID"
  value       = google_compute_instance.vm.id
}

output "self_link" {
  description = "Instance self link"
  value       = google_compute_instance.vm.self_link
}

output "zone" {
  description = "Instance zone"
  value       = google_compute_instance.vm.zone
}

output "machine_type" {
  description = "Machine type"
  value       = google_compute_instance.vm.machine_type
}

output "internal_ip" {
  description = "Internal IP address"
  value       = google_compute_instance.vm.network_interface[0].network_ip
}

output "external_ip" {
  description = "External IP address"
  value       = var.create_external_ip ? google_compute_address.external_ip[0].address : null
}

output "tags" {
  description = "Network tags"
  value       = google_compute_instance.vm.tags
}

output "labels" {
  description = "Resource labels"
  value       = google_compute_instance.vm.labels
}

