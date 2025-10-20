terraform {
  required_version = ">= 1.5.0"
  
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
    # AWS provider - for future multi-cloud support
    # aws = {
    #   source  = "hashicorp/aws"
    #   version = "~> 5.0"
    # }
  }

  # Local backend for now - migrate to GCS later
  backend "local" {
    path = "terraform.tfstate"
  }

  # Future: GCS backend for production
  # backend "gcs" {
  #   bucket  = "superdeploy-terraform-state"
  #   prefix  = "terraform/state"
  # }
}

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

