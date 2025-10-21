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
  name          = "vm-core-${count.index + 1}"
  machine_type  = var.machine_types.core
  disk_size     = var.disk_sizes.core
  image         = var.vm_image
  network       = module.network.network_self_link
  subnetwork    = module.network.subnet_self_link
  tags          = var.tags.core
  ssh_pub_key   = file(pathexpand(var.ssh_pub_key_path))
  environment   = var.environment

  # Static external IP for edge/API access
  create_external_ip = true

  labels = {
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
  name          = "vm-scrape-${count.index + 1}"
  machine_type  = var.machine_types.scrape
  disk_size     = var.disk_sizes.scrape
  image         = var.vm_image
  network       = module.network.network_self_link
  subnetwork    = module.network.subnet_self_link
  tags          = var.tags.scrape
  ssh_pub_key   = file(pathexpand(var.ssh_pub_key_path))
  environment   = var.environment

  # External IP for SSH access (can be removed in prod with bastion)
  create_external_ip = true

  labels = {
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
  name          = "vm-proxy-${count.index + 1}"
  machine_type  = var.machine_types.proxy
  disk_size     = var.disk_sizes.proxy
  image         = var.vm_image
  network       = module.network.network_self_link
  subnetwork    = module.network.subnet_self_link
  tags          = var.tags.proxy
  ssh_pub_key   = file(pathexpand(var.ssh_pub_key_path))
  environment   = var.environment

  # External IP is crucial for proxy functionality
  create_external_ip = true

  labels = {
    role        = "proxy"
    environment = var.environment
    has_proxy   = "true"
  }
}

