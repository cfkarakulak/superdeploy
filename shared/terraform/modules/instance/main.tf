# External IP (optional)
resource "google_compute_address" "external_ip" {
  count = var.create_external_ip ? 1 : 0

  name    = "${var.name}-ip"
  project = var.project_id
  region  = var.region
  
  # Use existing IP if preserve_ip_address is provided
  address = var.preserve_ip_address
  
  # Prevent accidental deletion of static IP
  lifecycle {
    prevent_destroy = false  # Set to true in production to protect IP
  }
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
    set -e
    
    # Log everything
    exec > >(tee -a /var/log/superdeploy-startup.log)
    exec 2>&1
    
    echo "=== SuperDeploy Startup Script ==="
    echo "Started at: $(date)"
    
    # Basic setup for Ansible
    echo "Installing packages..."
    apt-get update -qq
    apt-get install -y -qq python3 python3-pip sudo
    
    # Create superdeploy user for Ansible
    echo "Creating superdeploy user..."
    if ! id superdeploy &>/dev/null; then
      useradd -m -s /bin/bash superdeploy
      echo "superdeploy ALL=(ALL) NOPASSWD:ALL" > /etc/sudoers.d/superdeploy
      chmod 0440 /etc/sudoers.d/superdeploy
      echo "User created successfully"
    else
      echo "User already exists"
    fi
    
    # Add SSH key to superdeploy user
    echo "Configuring SSH..."
    mkdir -p /home/superdeploy/.ssh
    echo "${var.ssh_pub_key}" > /home/superdeploy/.ssh/authorized_keys
    chown -R superdeploy:superdeploy /home/superdeploy/.ssh
    chmod 700 /home/superdeploy/.ssh
    chmod 600 /home/superdeploy/.ssh/authorized_keys
    echo "SSH configured successfully"
    
    # Mark setup as complete
    mkdir -p /var/lib/cloud/instance
    touch /var/lib/cloud/instance/superdeploy-ready
    
    echo "Completed at: $(date)"
    echo "=== SuperDeploy Startup Complete ==="
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
      metadata["ssh-keys"],
      service_account  # Ignore service account changes (GCP may auto-assign)
    ]
  }
}

