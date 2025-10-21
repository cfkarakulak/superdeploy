# External IP (optional)
resource "google_compute_address" "external_ip" {
  count = var.create_external_ip ? 1 : 0

  name    = "${var.name}-ip"
  project = var.project_id
  region  = var.region
}

# Compute Instance
resource "google_compute_instance" "vm" {
  name         = var.name
  machine_type = var.machine_type
  zone         = var.zone
  project      = var.project_id

  tags   = var.tags
  labels = var.labels

  boot_disk {
    initialize_params {
      image = var.image
      size  = var.disk_size
      type  = var.disk_type
    }
  }

  network_interface {
    network    = var.network
    subnetwork = var.subnetwork

    # Attach external IP if created
    dynamic "access_config" {
      for_each = var.create_external_ip ? [1] : []
      content {
        nat_ip = google_compute_address.external_ip[0].address
      }
    }
  }

  # SSH key metadata
  metadata = {
    ssh-keys = "superdeploy:${var.ssh_pub_key}"
    user-data = var.startup_script != "" ? var.startup_script : null
  }

  # Allow stopping for maintenance
  allow_stopping_for_update = true

  # Startup script (cloud-init)
  metadata_startup_script = var.startup_script != "" ? null : <<-EOF
    #!/bin/bash
    # Basic setup for Ansible
    apt-get update
    apt-get install -y python3 python3-pip sudo
    
    # Create superdeploy user for Ansible
    if ! id superdeploy &>/dev/null; then
      useradd -m -s /bin/bash superdeploy
      echo "superdeploy ALL=(ALL) NOPASSWD:ALL" > /etc/sudoers.d/superdeploy
    fi
    
    # Add SSH key to superdeploy user
    mkdir -p /home/superdeploy/.ssh
    echo "${var.ssh_pub_key}" >> /home/superdeploy/.ssh/authorized_keys
    chown -R superdeploy:superdeploy /home/superdeploy/.ssh
    chmod 700 /home/superdeploy/.ssh
    chmod 600 /home/superdeploy/.ssh/authorized_keys
  EOF

  # Service account (use default for now, customize in prod)
  service_account {
    email  = var.service_account_email
    scopes = ["cloud-platform"]
  }

  # Lifecycle
  lifecycle {
    ignore_changes = [
      metadata_startup_script,
      metadata["ssh-keys"]
    ]
  }
}

