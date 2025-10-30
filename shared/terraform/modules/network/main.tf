# VPC Network
resource "google_compute_network" "vpc" {
  name                    = var.network_name
  auto_create_subnetworks = false
  project                 = var.project_id
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
    ports    = ["80", "443", "3001"]  # HTTP, HTTPS, Forgejo
  }

  source_ranges = ["0.0.0.0/0"]
  # Apply to all VM roles (any can serve web traffic)
  target_tags   = var.vm_roles

  description = "Allow HTTP/HTTPS and Forgejo (3001) from internet"
}

# Firewall: Allow proxy ports - PUBLIC ACCESS (for testing)
resource "google_compute_firewall" "allow_proxy" {
  name    = "${var.network_name}-allow-proxy"
  network = google_compute_network.vpc.name
  project = var.project_id

  allow {
    protocol = "tcp"
    ports    = ["1080", "3128", "8888"]
  }

  source_ranges = ["0.0.0.0/0"]  # Public access for testing
  # Apply to all VMs (any can run proxy services)
  target_tags   = var.vm_roles

  description = "Allow proxy connections - PUBLIC ACCESS"
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

  source_ranges = [var.subnet_cidr]

  description = "Allow all internal communication within VPC"
}

# Firewall: Allow database and queue services - already covered by allow_internal
# This rule is redundant but kept for documentation
resource "google_compute_firewall" "allow_services" {
  name    = "${var.network_name}-allow-services"
  network = google_compute_network.vpc.name
  project = var.project_id

  allow {
    protocol = "tcp"
    ports    = ["5432", "5672"]  # PostgreSQL, RabbitMQ
  }

  # Allow from any VM role to any VM role (internal network)
  source_tags = var.vm_roles
  target_tags = var.vm_roles

  description = "Allow database and queue access between VMs (covered by allow_internal)"
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
resource "google_compute_firewall" "allow_proxy_registry" {
  name    = "${var.network_name}-allow-proxy-registry"
  network = google_compute_network.vpc.name
  project = var.project_id

  allow {
    protocol = "tcp"
    ports    = ["8080"]  # Proxy Registry
  }

  source_ranges = ["0.0.0.0/0"]  # Public access for testing
  # Apply to all VMs (any can run registry)
  target_tags   = var.vm_roles

  description = "Proxy Registry - PUBLIC ACCESS"
}

# Firewall: Monitoring (Grafana & Prometheus) - PUBLIC ACCESS
resource "google_compute_firewall" "allow_monitoring" {
  name    = "${var.network_name}-allow-monitoring"
  network = google_compute_network.vpc.name
  project = var.project_id

  allow {
    protocol = "tcp"
    ports    = ["3000", "9090"]  # Grafana, Prometheus
  }

  source_ranges = ["0.0.0.0/0"]  # Public access
  # Apply to all VMs (monitoring is shared)
  target_tags   = var.vm_roles

  description = "Allow Grafana (3000) and Prometheus (9090) - PUBLIC ACCESS"
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

