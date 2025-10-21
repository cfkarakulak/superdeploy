# Terraform configuration moved to backend.tf
# Providers config only here

provider "google" {
  project = var.project_id
  region  = var.region
  zone    = var.zone
  
  # Use gcloud credentials (temporary fix for local development)
  # For production, use service account key file:
  # credentials = file("path/to/service-account-key.json")
  
  # Alternative: Use access token from gcloud
  # access_token = data.google_client_config.current.access_token
}

# Get current client config for access token
data "google_client_config" "current" {}

# Future: AWS provider
# provider "aws" {
#   region = var.aws_region
# }

