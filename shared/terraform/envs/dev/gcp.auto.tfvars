# Auto-generated from .env - DO NOT EDIT MANUALLY
# Edit ../superdeploy/.env instead

project_id  = "galvanic-camp-475519-d6"
environment = "dev"

region = "us-central1"
zone   = "us-central1-a"

vm_counts = {
  core   = 1
  scrape = 1
  proxy  = 1
}

machine_types = {
  core   = "e2-medium"
  scrape = "e2-standard-4"
  proxy  = "e2-small"
}

disk_sizes = {
  core   = 20
  scrape = 100
  proxy  = 20
}

network_name = "superdeploy-dev-network"
subnet_cidr  = "10.0.0.0/24"

admin_source_ranges = ["0.0.0.0/0"]
ssh_pub_key_path = "/Users/cfkarakulak/.ssh/superdeploy_deploy.pub"

vm_image = "debian-cloud/debian-11"

tags = {
  core   = ["core", "edge", "api", "queue", "db", "proxy-registry"]
  scrape = ["worker", "scrape", "browser"]
  proxy  = ["proxy", "socks", "tinyproxy"]
}
