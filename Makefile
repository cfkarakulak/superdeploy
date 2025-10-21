# =============================================================================
# SuperDeploy - All-in-One Deployment System
# =============================================================================
# Single command to deploy everything: make deploy

.PHONY: help deploy init terraform-init terraform-apply update-ips wait-vms ansible-deploy git-push clean destroy

# Paths
ENV_FILE := .env
ANSIBLE_DIR := ansible
TERRAFORM_WRAPPER := ./terraform-wrapper.sh

# Colors
RED := \033[0;31m
GREEN := \033[0;32m
YELLOW := \033[1;33m
BLUE := \033[0;34m
NC := \033[0m

# =============================================================================
# HELP
# =============================================================================

help: ## Show this help
	@echo "$(GREEN)SuperDeploy - Infrastructure + Application Deployment$(NC)"
	@echo ""
	@echo "$(YELLOW)Usage:$(NC)"
	@echo "  make deploy    - Full deployment (VM + Forgejo + Apps)"
	@echo "  make destroy   - Destroy all infrastructure"
	@echo "  make update-ips - Update IPs after VM restart"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  $(BLUE)%-15s$(NC) %s\n", $$1, $$2}'

# =============================================================================
# VALIDATION
# =============================================================================

check-env: ## Check if .env is configured
	@if [ ! -f "$(ENV_FILE)" ]; then \
		echo "$(RED)❌ ERROR: .env not found!$(NC)"; \
		echo "$(YELLOW)Run: cp ENV.example .env$(NC)"; \
		exit 1; \
	fi
	@if ! grep -q "^GCP_PROJECT_ID=" $(ENV_FILE) || grep -q "^GCP_PROJECT_ID=$$" $(ENV_FILE); then \
		echo "$(RED)❌ ERROR: GCP_PROJECT_ID not configured!$(NC)"; \
		exit 1; \
	fi
	@echo "$(GREEN)✅ Configuration looks good!$(NC)"

# =============================================================================
# TERRAFORM
# =============================================================================

setup-remote-state: check-env ## Setup GCS bucket for remote state (run once)
	@echo "$(GREEN)🪣 Creating GCS bucket for Terraform remote state...$(NC)"
	@set -a && source $(ENV_FILE) && set +a && \
		BUCKET="superdeploy-tfstate-$$GCP_PROJECT_ID" && \
		if gsutil ls gs://$$BUCKET 2>/dev/null; then \
			echo "$(YELLOW)⚠️  Bucket gs://$$BUCKET already exists$(NC)"; \
		else \
			gsutil mb gs://$$BUCKET && \
			gsutil versioning set on gs://$$BUCKET && \
			gsutil lifecycle set backend-lifecycle.json gs://$$BUCKET && \
			echo "$(GREEN)✅ Remote state bucket created: gs://$$BUCKET$(NC)"; \
		fi

terraform-init: check-env ## Initialize Terraform (with remote state)
	@echo "$(GREEN)🔧 Initializing Terraform...$(NC)"
	@$(TERRAFORM_WRAPPER) init -reconfigure

terraform-apply: terraform-init ## Create GCP VMs
	@echo "$(GREEN)🚀 Creating GCP VMs...$(NC)"
	@$(TERRAFORM_WRAPPER) apply -auto-approve
	@echo "$(GREEN)✅ VMs created!$(NC)"

update-ips: check-env ## Extract and update VM IPs in .env
	@echo "$(GREEN)📍 Extracting VM IPs...$(NC)"
	@set -a && source $(ENV_FILE) && set +a && \
		CORE_EXT=$$(terraform output -json vm_core_public_ips | jq -r '.[0]') && \
		CORE_INT=$$(terraform output -json vm_core_internal_ips | jq -r '.[0]') && \
		SCRAPE_EXT=$$(terraform output -json vm_scrape_public_ips | jq -r '.[0]') && \
		SCRAPE_INT=$$(terraform output -json vm_scrape_internal_ips | jq -r '.[0]') && \
		PROXY_EXT=$$(terraform output -json vm_proxy_public_ips | jq -r '.[0]') && \
		PROXY_INT=$$(terraform output -json vm_proxy_internal_ips | jq -r '.[0]') && \
		sed -i '' "s|^CORE_EXTERNAL_IP=.*|CORE_EXTERNAL_IP=$$CORE_EXT|" $(ENV_FILE) && \
		sed -i '' "s|^CORE_INTERNAL_IP=.*|CORE_INTERNAL_IP=$$CORE_INT|" $(ENV_FILE) && \
		sed -i '' "s|^SCRAPE_EXTERNAL_IP=.*|SCRAPE_EXTERNAL_IP=$$SCRAPE_EXT|" $(ENV_FILE) && \
		sed -i '' "s|^SCRAPE_INTERNAL_IP=.*|SCRAPE_INTERNAL_IP=$$SCRAPE_INT|" $(ENV_FILE) && \
		sed -i '' "s|^PROXY_EXTERNAL_IP=.*|PROXY_EXTERNAL_IP=$$PROXY_EXT|" $(ENV_FILE) && \
		sed -i '' "s|^PROXY_INTERNAL_IP=.*|PROXY_INTERNAL_IP=$$PROXY_INT|" $(ENV_FILE)
	@set -a && source $(ENV_FILE) && set +a && \
		echo "$(GREEN)✅ Updated $(ENV_FILE) with new IPs:$(NC)" && \
		echo "  $(BLUE)CORE:$(NC)    $$CORE_EXTERNAL_IP ($$CORE_INTERNAL_IP)" && \
		echo "  $(BLUE)SCRAPE:$(NC)  $$SCRAPE_EXTERNAL_IP ($$SCRAPE_INTERNAL_IP)" && \
		echo "  $(BLUE)PROXY:$(NC)   $$PROXY_EXTERNAL_IP ($$PROXY_INTERNAL_IP)"

generate-inventory: check-env ## Generate Ansible inventory
	@set -a && source $(ENV_FILE) && set +a && \
		printf "[core]\nvm-core-1 ansible_host=$$CORE_EXTERNAL_IP ansible_user=$$SSH_USER\n\n[scrape]\nvm-scrape-1 ansible_host=$$SCRAPE_EXTERNAL_IP ansible_user=$$SSH_USER\n\n[proxy]\nvm-proxy-1 ansible_host=$$PROXY_EXTERNAL_IP ansible_user=$$SSH_USER\n" > $(ANSIBLE_DIR)/inventories/dev.ini
	@echo "$(GREEN)✅ Ansible inventory generated$(NC)"

clean-ssh: check-env ## Clean SSH known_hosts
	@echo "$(GREEN)🔐 Cleaning SSH known_hosts...$(NC)"
	@set -a && source $(ENV_FILE) && set +a && \
		ssh-keygen -R $$CORE_EXTERNAL_IP 2>/dev/null || true && \
		ssh-keygen -R $$SCRAPE_EXTERNAL_IP 2>/dev/null || true && \
		ssh-keygen -R $$PROXY_EXTERNAL_IP 2>/dev/null || true
	@echo "$(GREEN)✅ SSH known_hosts cleaned!$(NC)"

wait-vms: ## Wait for VMs to be ready
	@echo "$(YELLOW)⏳ Waiting for VMs to complete startup scripts (120 seconds)...$(NC)"
	@echo "$(YELLOW)💡 VMs run apt-get update on first boot, this prevents dpkg lock errors$(NC)"
	@for i in $$(seq 120 -1 1); do \
		printf "\r$(YELLOW)⏳ $$i seconds remaining...$(NC)"; \
		sleep 1; \
	done
	@echo "\n$(GREEN)✅ VMs should be ready!$(NC)"

# =============================================================================
# ANSIBLE
# =============================================================================

ansible-deploy: check-env ## Deploy with Ansible
	@echo "$(GREEN)🔨 Deploying with Ansible...$(NC)"
	@set -a && source $(ENV_FILE) && set +a && \
		cd $(ANSIBLE_DIR) && \
		ansible-playbook -i inventories/dev.ini playbooks/site.yml --tags system-base,git-server \
			-e "core_external_ip=$$CORE_EXTERNAL_IP" \
			-e "core_internal_ip=$$CORE_INTERNAL_IP" \
			-e "scrape_external_ip=$$SCRAPE_EXTERNAL_IP" \
			-e "scrape_internal_ip=$$SCRAPE_INTERNAL_IP" \
			-e "proxy_external_ip=$$PROXY_EXTERNAL_IP" \
			-e "proxy_internal_ip=$$PROXY_INTERNAL_IP" \
			-e "forgejo_admin_user=$$FORGEJO_ADMIN_USER" \
			-e "forgejo_admin_password=$$FORGEJO_ADMIN_PASSWORD" \
			-e "forgejo_admin_email=$$FORGEJO_ADMIN_EMAIL" \
			-e "forgejo_org=$$FORGEJO_ORG" \
			-e "forgejo_db_name=forgejo" \
			-e "forgejo_db_user=forgejo" \
			-e "forgejo_db_password=$$POSTGRES_PASSWORD" \
			-e "postgres_password=$$POSTGRES_PASSWORD"
	@echo "$(GREEN)✅ Ansible deployment complete!$(NC)"

# =============================================================================
# GIT PUSH
# =============================================================================

git-push: check-env ## Push code to GitHub & Forgejo
	@echo "$(GREEN)📤 Pushing to GitHub...$(NC)"
	@set -a && source $(ENV_FILE) && set +a && \
		if [ -n "$$GITHUB_TOKEN" ] && [ "$$GITHUB_TOKEN" != "your-github-token" ]; then \
			git remote remove github 2>/dev/null || true && \
			git remote add github "https://$$GITHUB_TOKEN@github.com/cfkarakulak/superdeploy.git" && \
			git push -u github master 2>&1 | grep -v "$$GITHUB_TOKEN" && \
			echo "$(GREEN)✅ Pushed to GitHub!$(NC)"; \
		else \
			echo "$(YELLOW)⚠️  GITHUB_TOKEN not set, skipping GitHub push$(NC)"; \
		fi
	@echo "$(GREEN)📤 Pushing to Forgejo...$(NC)"
	@set -a && source $(ENV_FILE) && set +a && \
		ENCODED_PASS=$$(printf '%s' "$$FORGEJO_ADMIN_PASSWORD" | jq -sRr @uri) && \
		git remote remove forgejo 2>/dev/null || true && \
		git remote add forgejo "http://$$FORGEJO_ADMIN_USER:$$ENCODED_PASS@$$CORE_EXTERNAL_IP:3001/$$FORGEJO_ORG/$$REPO_SUPERDEPLOY.git" && \
		git push -u forgejo master 2>&1 | grep -v "Password" || true
	@echo "$(GREEN)✅ Code pushed to Forgejo!$(NC)"

# =============================================================================
# FULL DEPLOYMENT
# =============================================================================

deploy: check-env terraform-init terraform-apply update-ips generate-inventory clean-ssh wait-vms ansible-deploy git-push ## Full E2E deployment
	@echo ""
	@echo "$(GREEN)╔════════════════════════════════════════════════════════╗$(NC)"
	@echo "$(GREEN)║  🎉 DEPLOYMENT COMPLETE! 🎉                           ║$(NC)"
	@echo "$(GREEN)╚════════════════════════════════════════════════════════╝$(NC)"
	@echo ""
	@set -a && source $(ENV_FILE) && set +a && \
		echo "$(BLUE)🌐 Forgejo:$(NC) http://$$CORE_EXTERNAL_IP:3001" && \
		echo "$(BLUE)👤 Login:$(NC)   $$FORGEJO_ADMIN_USER / $$FORGEJO_ADMIN_PASSWORD" && \
		echo "" && \
		echo "$(YELLOW)Next: Push your app repos to GitHub to trigger builds!$(NC)"

forgejo-pat-create: check-env ## Create Forgejo Personal Access Token
	@echo "$(GREEN)🔑 Creating Forgejo PAT...$(NC)"
	@set -a && source $(ENV_FILE) && set +a && \
		PAT=$$(curl -sS -X POST "http://$$CORE_EXTERNAL_IP:3001/api/v1/users/$$FORGEJO_ADMIN_USER/tokens" \
			-u "$$FORGEJO_ADMIN_USER:$$FORGEJO_ADMIN_PASSWORD" \
			-H "Content-Type: application/json" \
			-d '{"name":"github-actions-'$$(date +%s)'","scopes":["write:repository","write:activitypub"]}' \
			| jq -r '.sha1') && \
		if [ -n "$$PAT" ] && [ "$$PAT" != "null" ]; then \
			sed -i '' "s/^FORGEJO_PAT=.*/FORGEJO_PAT=$$PAT/" $(ENV_FILE) && \
			echo "$(GREEN)✅ PAT created: $$PAT$(NC)" && \
			echo "$(YELLOW)💡 Now add this to GitHub secrets for each repo$(NC)"; \
		else \
			echo "$(RED)❌ Failed to create PAT$(NC)"; \
			exit 1; \
		fi

# =============================================================================
# MANUAL DEPLOYMENT HELPERS
# =============================================================================

deploy-service: check-env ## Deploy specific service (make deploy-service SERVICE=api TAG=abc123 ENV=prod)
	@if [ -z "$(SERVICE)" ] || [ -z "$(TAG)" ]; then \
		echo "$(RED)❌ Usage: make deploy-service SERVICE=api TAG=abc123 ENV=prod$(NC)"; \
		exit 1; \
	fi
	@echo "$(GREEN)🚀 Deploying $(SERVICE):$(TAG) to $(ENV)$(NC)"
	@set -a && source $(ENV_FILE) && set +a && \
		IMAGE_TAGS="{\"$(SERVICE)\":\"$(TAG)\"}" && \
		curl -sS -X POST "http://$$CORE_EXTERNAL_IP:3001/api/v1/repos/$$FORGEJO_ORG/superdeploy-app/actions/workflows/deploy.yml/dispatches" \
			-H "Authorization: token $$FORGEJO_PAT" \
			-H "Content-Type: application/json" \
			-d "{\"ref\":\"master\",\"inputs\":{\"environment\":\"$(ENV)\",\"services\":\"$(SERVICE)\",\"image_tags\":\"$$IMAGE_TAGS\",\"migrate\":\"false\"}}" \
			&& echo "$(GREEN)✅ Deployment triggered!$(NC)" \
			|| echo "$(RED)❌ Deployment failed!$(NC)"

rollback: check-env ## Rollback service (make rollback SERVICE=api TAG=previous-sha ENV=prod)
	@if [ -z "$(SERVICE)" ] || [ -z "$(TAG)" ]; then \
		echo "$(RED)❌ Usage: make rollback SERVICE=api TAG=def456 ENV=prod$(NC)"; \
		exit 1; \
	fi
	@echo "$(YELLOW)🔄 Rolling back $(SERVICE) to $(TAG) in $(ENV)$(NC)"
	@$(MAKE) deploy-service SERVICE=$(SERVICE) TAG=$(TAG) ENV=$(ENV)

deploy-all: check-env ## Deploy all services (make deploy-all API_TAG=abc DASH_TAG=def SVC_TAG=ghi ENV=prod)
	@if [ -z "$(API_TAG)" ] || [ -z "$(DASH_TAG)" ] || [ -z "$(SVC_TAG)" ]; then \
		echo "$(RED)❌ Usage: make deploy-all API_TAG=abc DASH_TAG=def SVC_TAG=ghi ENV=prod$(NC)"; \
		exit 1; \
	fi
	@echo "$(GREEN)🚀 Deploying all services to $(ENV)$(NC)"
	@set -a && source $(ENV_FILE) && set +a && \
		IMAGE_TAGS="{\"api\":\"$(API_TAG)\",\"dashboard\":\"$(DASH_TAG)\",\"services\":\"$(SVC_TAG)\"}" && \
		curl -sS -X POST "http://$$CORE_EXTERNAL_IP:3001/api/v1/repos/$$FORGEJO_ORG/superdeploy-app/actions/workflows/deploy.yml/dispatches" \
			-H "Authorization: token $$FORGEJO_PAT" \
			-H "Content-Type: application/json" \
			-d "{\"ref\":\"master\",\"inputs\":{\"environment\":\"$(ENV)\",\"services\":\"api,dashboard,services\",\"image_tags\":\"$$IMAGE_TAGS\",\"migrate\":\"false\"}}" \
			&& echo "$(GREEN)✅ Full deployment triggered!$(NC)" \
			|| echo "$(RED)❌ Deployment failed!$(NC)"

migrate-db: check-env ## Run DB migrations (make migrate-db ENV=prod)
	@echo "$(GREEN)🗄️  Running database migrations on $(ENV)$(NC)"
	@set -a && source $(ENV_FILE) && set +a && \
		IMAGE_TAGS="{\"api\":\"latest\"}" && \
		curl -sS -X POST "http://$$CORE_EXTERNAL_IP:3001/api/v1/repos/$$FORGEJO_ORG/superdeploy-app/actions/workflows/deploy.yml/dispatches" \
			-H "Authorization: token $$FORGEJO_PAT" \
			-H "Content-Type: application/json" \
			-d "{\"ref\":\"master\",\"inputs\":{\"environment\":\"$(ENV)\",\"services\":\"api\",\"image_tags\":\"$$IMAGE_TAGS\",\"migrate\":\"true\"}}" \
			&& echo "$(GREEN)✅ Migration triggered!$(NC)" \
			|| echo "$(RED)❌ Migration failed!$(NC)"

# =============================================================================
# CLEANUP
# =============================================================================

destroy: check-env ## Destroy all infrastructure
	@echo "$(RED)⚠️  WARNING: This will destroy all VMs!$(NC)"
	@echo "$(YELLOW)Press Ctrl+C to cancel, or Enter to continue...$(NC)"
	@read confirm
	@echo "$(RED)🗑️  Destroying infrastructure...$(NC)"
	@$(TERRAFORM_WRAPPER) destroy -auto-approve
	@echo "$(GREEN)✅ Infrastructure destroyed!$(NC)"

clean: ## Clean Terraform state
	@echo "$(YELLOW)🧹 Cleaning Terraform state...$(NC)"
	@rm -rf .terraform terraform.tfstate* envs/dev/*.tfvars
	@echo "$(GREEN)✅ Cleaned!$(NC)"

# =============================================================================
# 🎯 CLI Tools (Heroku-like UX)
# =============================================================================

cli-install: ## Install superdeploy CLI to /usr/local/bin
	@echo "$(GREEN)📦 Installing superdeploy CLI...$(NC)"
	@sudo cp bin/superdeploy /usr/local/bin/superdeploy
	@sudo chmod +x /usr/local/bin/superdeploy
	@echo "$(GREEN)✅ superdeploy CLI installed!$(NC)"
	@echo ""
	@echo "Usage:"
	@echo "  superdeploy logs -a api -f"
	@echo "  superdeploy run api \"python manage.py migrate\""
	@echo "  superdeploy scale api=3"
	@echo "  superdeploy deploy -a api -e production"

cli-test: ## Test CLI commands
	@./bin/superdeploy apps
	@./bin/superdeploy status
