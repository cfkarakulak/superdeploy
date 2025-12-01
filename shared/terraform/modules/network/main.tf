# VPC Network
resource "google_compute_network" "vpc" {
  name                    = var.network_name
  auto_create_subnetworks = false
  project                 = var.project_id
  
  # Prevent accidental recreation - import existing if it exists
  lifecycle {
    ignore_changes = [
      # Ignore changes to these fields to prevent unnecessary recreations
    ]
  }
}

# Subnet
resource "google_compute_subnetwork" "subnet" {
  name          = "${var.network_name}-subnet"
  ip_cidr_range = var.subnet_cidr
  region        = var.region
  network       = google_compute_network.vpc.id
  project       = var.project_id

  # Enable private Google access for Cloud APIs
  private_ip_google_access = true
  
  # Prevent accidental recreation
  lifecycle {
    ignore_changes = [
      # Ignore changes to these fields to prevent unnecessary recreations
    ]
  }
}

# Firewall: Allow SSH from admin IPs (to all VM roles)
resource "google_compute_firewall" "allow_ssh" {
  name    = "${var.network_name}-allow-ssh"
  network = google_compute_network.vpc.name
  project = var.project_id

  allow {
    protocol = "tcp"
    ports    = ["22"]
  }

  source_ranges = var.admin_source_ranges
  # Apply to all VM roles dynamically + ssh tag
  target_tags   = concat(var.vm_roles, ["ssh"])

  description = "Allow SSH from admin IP ranges to all VMs"
}

# Firewall: Allow HTTP/HTTPS and common web ports (to all VMs)
resource "google_compute_firewall" "allow_http_https" {
  name    = "${var.network_name}-allow-http-https"
  network = google_compute_network.vpc.name
  project = var.project_id

  allow {
    protocol = "tcp"
    ports    = ["80", "443"]  # HTTP, HTTPS
  }

  source_ranges = ["0.0.0.0/0"]
  # Apply to all VM roles (any can serve web traffic)
  target_tags   = var.vm_roles

  description = "Allow HTTP/HTTPS from internet"
}

# Firewall: Allow proxy ports - PUBLIC ACCESS (for testing)
# ⚠️  SECURITY WARNING: This is open to the internet for development/debugging
# 🔒 For production, change source_ranges to var.admin_source_ranges or remove
resource "google_compute_firewall" "allow_proxy" {
  name    = "${var.network_name}-allow-proxy"
  network = google_compute_network.vpc.name
  project = var.project_id

  allow {
    protocol = "tcp"
    ports    = ["1080", "3128", "8888"]
  }

  source_ranges = ["0.0.0.0/0"]  # Public access for testing
  # For production: source_ranges = var.admin_source_ranges or disable this rule
  
  # Apply to all VMs (any can run proxy services)
  target_tags   = var.vm_roles

  description = "Allow proxy connections - PUBLIC ACCESS (DEV MODE)"
}

# Firewall: Allow internal communication between all VMs
resource "google_compute_firewall" "allow_internal" {
  name    = "${var.network_name}-allow-internal"
  network = google_compute_network.vpc.name
  project = var.project_id

  allow {
    protocol = "tcp"
    ports    = ["0-65535"]
  }

  allow {
    protocol = "udp"
    ports    = ["0-65535"]
  }

  allow {
    protocol = "icmp"
  }

  # Allow from own subnet + orchestrator subnet (for VPC peering)
  source_ranges = var.orchestrator_subnet != "" ? [var.subnet_cidr, var.orchestrator_subnet] : [var.subnet_cidr]

  description = "Allow all internal communication within VPC and from orchestrator via VPC peering"
}

# Firewall: Allow addon services (database, cache, queue) between VMs
# Cross-VM container communication works via iptables SNAT rule that converts
# Docker container IPs (172.x) to host VPC IP (10.x) for VPC traffic.
# This rule is applied by Ansible docker role during VM setup.
resource "google_compute_firewall" "allow_addon_services" {
  name    = "${var.network_name}-allow-addon-services"
  network = google_compute_network.vpc.name
  project = var.project_id

  allow {
    protocol = "tcp"
    ports    = ["5432", "5672", "6379", "27017", "9200"]  # PostgreSQL, RabbitMQ, Redis, MongoDB, Elasticsearch
  }

  # Allow from VPC subnet only (secure - no public access)
  source_ranges = [var.subnet_cidr]
  target_tags   = var.vm_roles

  description = "Allow addon services between VMs via VPC internal IPs"
}

# Firewall: RabbitMQ Management UI - PUBLIC ACCESS (for testing)
resource "google_compute_firewall" "allow_rabbitmq_management" {
  name    = "${var.network_name}-allow-rabbitmq-mgmt"
  network = google_compute_network.vpc.name
  project = var.project_id

  allow {
    protocol = "tcp"
    ports    = ["15672"]  # RabbitMQ Management UI
  }

  source_ranges = ["0.0.0.0/0"]  # Public access for testing
  # Apply to all VMs (any can run RabbitMQ)
  target_tags   = var.vm_roles

  description = "RabbitMQ Management - PUBLIC ACCESS"
}

# Firewall: Allow application ports (dynamically configured per project)
resource "google_compute_firewall" "allow_app_ports" {
  count   = length(var.app_ports) > 0 ? 1 : 0
  name    = "${var.network_name}-allow-app-ports"
  network = google_compute_network.vpc.name
  project = var.project_id

  allow {
    protocol = "tcp"
    ports    = var.app_ports
  }

  source_ranges = ["0.0.0.0/0"]
  target_tags   = var.vm_roles

  description = "Allow direct access to application ports (configured per project)"
}

# Firewall: Proxy Registry - PUBLIC ACCESS (for testing)
# ⚠️  SECURITY WARNING: This is open to the internet for development/debugging
# 🔒 For production, change source_ranges to var.admin_source_ranges
resource "google_compute_firewall" "allow_proxy_registry" {
  name    = "${var.network_name}-allow-proxy-registry"
  network = google_compute_network.vpc.name
  project = var.project_id

  allow {
    protocol = "tcp"
    ports    = ["8080"]  # Proxy Registry
  }

  source_ranges = ["0.0.0.0/0"]  # Public access for testing
  # For production: source_ranges = var.admin_source_ranges
  
  # Apply to all VMs (any can run registry)
  target_tags   = var.vm_roles

  description = "Proxy Registry - PUBLIC ACCESS (DEV MODE)"
}

# Firewall: Monitoring (Grafana & Prometheus) - PUBLIC ACCESS
# ⚠️  SECURITY WARNING: This is open to the internet for development/debugging
# 🔒 For production, change source_ranges to var.admin_source_ranges
resource "google_compute_firewall" "allow_monitoring" {
  name    = "${var.network_name}-allow-monitoring"
  network = google_compute_network.vpc.name
  project = var.project_id

  allow {
    protocol = "tcp"
    ports    = ["3000", "9090"]  # Grafana, Prometheus
  }

  source_ranges = ["0.0.0.0/0"]  # Public access for testing
  # For production: source_ranges = var.admin_source_ranges
  
  # Apply to all VMs (monitoring is shared)
  target_tags   = var.vm_roles

  description = "Allow Grafana (3000) and Prometheus (9090) - PUBLIC ACCESS (DEV MODE)"
}

# Firewall: Allow Prometheus metrics from orchestrator
resource "google_compute_firewall" "allow_metrics_from_orchestrator" {
  count   = var.orchestrator_ip != "" ? 1 : 0
  name    = "${var.network_name}-allow-metrics-from-orchestrator"
  network = google_compute_network.vpc.name
  project = var.project_id

  allow {
    protocol = "tcp"
    ports    = ["2019"]  # Caddy metrics
  }

  source_ranges = ["${var.orchestrator_ip}/32"]
  target_tags   = var.vm_roles

  description = "Allow Prometheus metrics collection from orchestrator"
}

# Firewall: Allow node_exporter metrics (port 9100)
# Allows Prometheus (orchestrator) to scrape node metrics from project VMs
resource "google_compute_firewall" "allow_node_exporter" {
  name    = "${var.network_name}-allow-node-exporter"
  network = google_compute_network.vpc.name
  project = var.project_id

  allow {
    protocol = "tcp"
    ports    = ["9100"]  # node_exporter
  }

  # Allow from all private subnets (10.0.0.0/8) for VPC peering
  # Orchestrator is in 10.0.0.0/16, projects are in 10.x.0.0/16
  source_ranges = ["10.0.0.0/8"]
  target_tags   = var.vm_roles

  description = "Allow node_exporter metrics (9100) for Prometheus monitoring via VPC peering"
}

# Firewall: Allow cAdvisor metrics (port 8080) from orchestrator
# Allows Prometheus to scrape container metrics via VPC peering
resource "google_compute_firewall" "allow_cadvisor" {
  name    = "${var.network_name}-allow-cadvisor"
  network = google_compute_network.vpc.name
  project = var.project_id

  allow {
    protocol = "tcp"
    ports    = ["8080"]  # cAdvisor
  }

  # Allow from all private subnets (10.0.0.0/8) for VPC peering
  source_ranges = ["10.0.0.0/8"]
  target_tags   = var.vm_roles

  description = "Allow cAdvisor metrics (8080) for Prometheus monitoring via VPC peering"
}

# Firewall: Allow Loki log ingestion (port 3100)
# Allows Promtail agents on project VMs to send logs to Loki (orchestrator)
resource "google_compute_firewall" "allow_loki_ingestion" {
  name    = "${var.network_name}-allow-loki-ingestion"
  network = google_compute_network.vpc.name
  project = var.project_id

  allow {
    protocol = "tcp"
    ports    = ["3100"]  # Loki
  }

  # For orchestrator network: allow from all project subnets
  # For project networks: allow bidirectional (orchestrator + own subnet)
  source_ranges = length(var.allowed_client_subnets) > 0 ? var.allowed_client_subnets : (
    var.orchestrator_subnet != "" ? [var.orchestrator_subnet, var.subnet_cidr] : ["0.0.0.0/0"]
  )
  target_tags   = concat(var.vm_roles, ["orchestrator"])

  description = "Allow Loki log ingestion (3100) from Promtail agents via VPC peering"
}

# VPC Peering: Project VPC <-> Orchestrator VPC
# This allows Prometheus (orchestrator) to reach project VMs via internal IPs
resource "google_compute_network_peering" "project_to_orchestrator" {
  count = var.orchestrator_network_name != "" && var.network_name != "superdeploy-network" ? 1 : 0
  
  name         = "${var.network_name}-to-orchestrator"
  network      = google_compute_network.vpc.self_link
  peer_network = "projects/${var.project_id}/global/networks/${var.orchestrator_network_name}"

  export_custom_routes = false
  import_custom_routes = false
}

resource "google_compute_network_peering" "orchestrator_to_project" {
  count = var.orchestrator_network_name != "" && var.network_name != "superdeploy-network" ? 1 : 0
  
  name         = "orchestrator-to-${var.network_name}"
  network      = "projects/${var.project_id}/global/networks/${var.orchestrator_network_name}"
  peer_network = google_compute_network.vpc.self_link

  export_custom_routes = false
  import_custom_routes = false

  depends_on = [google_compute_network_peering.project_to_orchestrator]
}

