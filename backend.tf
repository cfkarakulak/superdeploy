terraform {
  backend "gcs" {
    # Bucket name will be: superdeploy-tfstate-YOUR_PROJECT_ID
    # Set via: terraform init -backend-config="bucket=superdeploy-tfstate-YOUR_PROJECT_ID"
    # Or hardcode here after creating bucket
    prefix = "infra/prod"
  }
  
  required_version = ">= 1.5.0"
  
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }
}

# Note: GCS bucket must be created manually before first terraform init:
#
# gsutil mb gs://superdeploy-tfstate-YOUR_PROJECT_ID
# gsutil versioning set on gs://superdeploy-tfstate-YOUR_PROJECT_ID
# gsutil lifecycle set backend-lifecycle.json gs://superdeploy-tfstate-YOUR_PROJECT_ID

