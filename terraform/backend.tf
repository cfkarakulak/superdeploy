terraform {
  # 🔧 Toggle via USE_REMOTE_STATE in .env
  # For debug: local backend (fast, no GCS dependency)
  # For production: uncomment GCS backend below
  
  backend "local" {
    path = "terraform.tfstate"
  }
  
  # backend "gcs" {
  #   bucket = "superdeploy-tfstate-YOUR_PROJECT_ID"
  #   prefix = "infra/prod"
  # }
  
  required_version = ">= 1.5.0"
  
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }
}
