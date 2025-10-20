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

# Firewall: Allow SSH from admin IPs
resource "google_compute_firewall" "allow_ssh" {
  name    = "${var.network_name}-allow-ssh"
  network = google_compute_network.vpc.name
  project = var.project_id

  allow {
    protocol = "tcp"
    ports    = ["22"]
  }

  source_ranges = var.admin_source_ranges
  target_tags   = ["core", "worker", "proxy"]

  description = "Allow SSH from admin IP ranges"
}

# Firewall: Allow HTTP/HTTPS and Forgejo to edge (core VMs)
resource "google_compute_firewall" "allow_http_https" {
  name    = "${var.network_name}-allow-http-https"
  network = google_compute_network.vpc.name
  project = var.project_id

  allow {
    protocol = "tcp"
    ports    = ["80", "443", "3001"]
  }

  source_ranges = ["0.0.0.0/0"]
  target_tags   = ["edge", "core"]

  description = "Allow HTTP/HTTPS and Forgejo (3001) to edge servers"
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
  target_tags   = ["proxy"]

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

# Firewall: Allow RabbitMQ (5672), PostgreSQL (5432) from worker VMs - INTERNAL ONLY
resource "google_compute_firewall" "allow_services" {
  name    = "${var.network_name}-allow-services"
  network = google_compute_network.vpc.name
  project = var.project_id

  allow {
    protocol = "tcp"
    ports    = ["5432", "5672"]  # PostgreSQL, RabbitMQ (Management UI removed from external)
  }

  source_tags = ["worker", "scrape"]
  target_tags = ["core", "queue", "db"]

  description = "Allow worker VMs to access core services (DB, Queue) - INTERNAL ONLY"
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
  target_tags   = ["core", "queue"]

  description = "RabbitMQ Management - PUBLIC ACCESS"
}

# Firewall: Allow direct API access (8000) - optional, usually via Caddy
resource "google_compute_firewall" "allow_api_direct" {
  name    = "${var.network_name}-allow-api-direct"
  network = google_compute_network.vpc.name
  project = var.project_id

  allow {
    protocol = "tcp"
    ports    = ["8000"]  # Direct API access
  }

  source_ranges = ["0.0.0.0/0"]
  target_tags   = ["api", "core"]

  description = "Allow direct API access (usually proxied via Caddy)"
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
  target_tags   = ["core"]

  description = "Proxy Registry - PUBLIC ACCESS"
}

