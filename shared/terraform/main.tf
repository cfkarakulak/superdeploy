# Network module
module "network" {
  source = "./modules/network"

  project_id          = var.project_id
  region              = var.region
  network_name        = var.network_name
  subnet_cidr         = var.subnet_cidr
  admin_source_ranges = var.admin_source_ranges
  environment         = var.environment
}

# VM-1: CORE (edge + api + rabbitmq + postgres + proxy-registry)
module "vm_core" {
  source = "./modules/instance"

  count = var.vm_counts.core

  project_id    = var.project_id
  zone          = var.zone
  name          = "${var.project_name}-core-${count.index + 1}"
  machine_type  = var.machine_types.core != "" ? var.machine_types.core : var.machine_type
  disk_size     = var.disk_sizes.core > 0 ? var.disk_sizes.core : var.disk_size
  image         = var.vm_image
  network       = module.network.network_self_link
  subnetwork    = module.network.subnet_self_link
  tags          = var.tags.core
  ssh_pub_key   = file(pathexpand(var.ssh_pub_key_path))
  environment   = var.environment

  # Static external IP for edge/API access
  create_external_ip = true

  labels = {
    project     = var.project_name
    role        = "core"
    environment = var.environment
    has_edge    = "true"
    has_api     = "true"
    has_queue   = "true"
    has_db      = "true"
  }
}

# VM-2: SCRAPE (workers with browsers)
module "vm_scrape" {
  source = "./modules/instance"

  count = var.vm_counts.scrape

  project_id    = var.project_id
  zone          = var.zone
  name          = "${var.project_name}-scrape-${count.index + 1}"
  machine_type  = var.machine_types.scrape != "" ? var.machine_types.scrape : var.machine_type
  disk_size     = var.disk_sizes.scrape > 0 ? var.disk_sizes.scrape : var.disk_size
  image         = var.vm_image
  network       = module.network.network_self_link
  subnetwork    = module.network.subnet_self_link
  tags          = var.tags.scrape
  ssh_pub_key   = file(pathexpand(var.ssh_pub_key_path))
  environment   = var.environment

  # External IP for SSH access (can be removed in prod with bastion)
  create_external_ip = true

  labels = {
    project     = var.project_name
    role        = "scrape"
    environment = var.environment
    has_worker  = "true"
  }
}

# VM-3: PROXY (dante/tinyproxy with IP rotation)
module "vm_proxy" {
  source = "./modules/instance"

  count = var.vm_counts.proxy

  project_id    = var.project_id
  zone          = var.zone
  name          = "${var.project_name}-proxy-${count.index + 1}"
  machine_type  = var.machine_types.proxy != "" ? var.machine_types.proxy : var.machine_type
  disk_size     = var.disk_sizes.proxy > 0 ? var.disk_sizes.proxy : var.disk_size
  image         = var.vm_image
  network       = module.network.network_self_link
  subnetwork    = module.network.subnet_self_link
  tags          = var.tags.proxy
  ssh_pub_key   = file(pathexpand(var.ssh_pub_key_path))
  environment   = var.environment

  # External IP is crucial for proxy functionality
  create_external_ip = true

  labels = {
    project     = var.project_name
    role        = "proxy"
    environment = var.environment
    has_proxy   = "true"
  }
}

