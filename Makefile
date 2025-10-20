# =============================================================================
# SuperDeploy - Generic Multi-Project Deployment System
# =============================================================================
# Usage: make deploy PROJECT=project-name

# Default project if not specified
PROJECT ?= cheapa

# Project-specific paths
PROJECT_DIR := projects/$(PROJECT)
PROJECT_ENV := $(PROJECT_DIR)/.env
PROJECT_COMPOSE := $(PROJECT_DIR)/compose

# Directories (generic)
INFRA_DIR := ../superdeploy-infra
ANSIBLE_DIR := $(INFRA_DIR)/ansible

# Colors
RED := \033[0;31m
GREEN := \033[0;32m
YELLOW := \033[1;33m
BLUE := \033[0;34m
NC := \033[0m # No Color

# =============================================================================
# VALIDATION
# =============================================================================

check-project: ## Check if project exists
	@if [ ! -d "$(PROJECT_DIR)" ]; then \
		echo "$(RED)❌ ERROR: Project '$(PROJECT)' not found!$(NC)"; \
		echo "$(YELLOW)Available projects:$(NC)"; \
		ls -1 projects/ | sed 's/^/  - /'; \
		exit 1; \
	fi
	@if [ ! -f "$(PROJECT_ENV)" ]; then \
		echo "$(RED)❌ ERROR: $(PROJECT_ENV) not found!$(NC)"; \
		echo "$(YELLOW)Create it: cp ENV.example $(PROJECT_ENV)$(NC)"; \
		exit 1; \
	fi
	@echo "$(GREEN)✅ Project: $(PROJECT)$(NC)"

check-env: check-project ## Check if .env is configured
	@if grep -E "^[A-Z_]+=$$" $(PROJECT_ENV) | grep -v "^#"; then \
		echo "$(RED)❌ ERROR: Empty values in $(PROJECT_ENV)!$(NC)"; \
		echo "$(YELLOW)Edit $(PROJECT_ENV) and fill all empty values$(NC)"; \
		exit 1; \
	fi
	@if ! grep -q "^GCP_PROJECT_ID=" $(PROJECT_ENV) || grep -q "^GCP_PROJECT_ID=$$" $(PROJECT_ENV); then \
		echo "$(RED)❌ ERROR: GCP_PROJECT_ID not configured!$(NC)"; \
		exit 1; \
	fi
	@echo "$(GREEN)✅ Configuration looks good!$(NC)"

# =============================================================================
# TERRAFORM
# =============================================================================

terraform-init: check-env ## Initialize Terraform
	@echo "$(GREEN)🔧 Initializing Terraform for $(PROJECT)...$(NC)"
	@set -a && source $(PROJECT_ENV) && set +a && \
		cd $(INFRA_DIR) && ./terraform-wrapper.sh init

terraform-apply: terraform-init ## Create VMs with Terraform
	@echo "$(GREEN)🚀 Creating GCP VMs for $(PROJECT)...$(NC)"
	@set -a && source $(PROJECT_ENV) && set +a && \
		cd $(INFRA_DIR) && ./terraform-wrapper.sh apply -auto-approve
	@echo "$(GREEN)✅ VMs created!$(NC)"

# =============================================================================
# IP MANAGEMENT
# =============================================================================

update-ips: check-project ## Extract IPs from Terraform and update .env
	@echo "$(GREEN)📍 Extracting VM IPs...$(NC)"
	@cd $(INFRA_DIR) && \
		CORE_EXT=$$(terraform output -json vm_core_public_ips | jq -r '.[0]') && \
		CORE_INT=$$(terraform output -json vm_core_internal_ips | jq -r '.[0]') && \
		SCRAPE_EXT=$$(terraform output -json vm_scrape_public_ips | jq -r '.[0]') && \
		SCRAPE_INT=$$(terraform output -json vm_scrape_internal_ips | jq -r '.[0]') && \
		PROXY_EXT=$$(terraform output -json vm_proxy_public_ips | jq -r '.[0]') && \
		PROXY_INT=$$(terraform output -json vm_proxy_internal_ips | jq -r '.[0]') && \
		cd - > /dev/null && \
		sed -i.bak "s|^CORE_EXTERNAL_IP=.*|CORE_EXTERNAL_IP=$$CORE_EXT|" $(PROJECT_ENV) && \
		sed -i.bak "s|^CORE_INTERNAL_IP=.*|CORE_INTERNAL_IP=$$CORE_INT|" $(PROJECT_ENV) && \
		sed -i.bak "s|^SCRAPE_EXTERNAL_IP=.*|SCRAPE_EXTERNAL_IP=$$SCRAPE_EXT|" $(PROJECT_ENV) && \
		sed -i.bak "s|^SCRAPE_INTERNAL_IP=.*|SCRAPE_INTERNAL_IP=$$SCRAPE_INT|" $(PROJECT_ENV) && \
		sed -i.bak "s|^PROXY_EXTERNAL_IP=.*|PROXY_EXTERNAL_IP=$$PROXY_EXT|" $(PROJECT_ENV) && \
		sed -i.bak "s|^PROXY_INTERNAL_IP=.*|PROXY_INTERNAL_IP=$$PROXY_INT|" $(PROJECT_ENV) && \
		rm -f $(PROJECT_ENV).bak && \
		echo "$(GREEN)✅ Updated $(PROJECT_ENV) with new IPs:$(NC)" && \
		echo "  $(BLUE)CORE:$(NC)   $$CORE_EXT ($$CORE_INT)" && \
		echo "  $(BLUE)SCRAPE:$(NC) $$SCRAPE_EXT ($$SCRAPE_INT)" && \
		echo "  $(BLUE)PROXY:$(NC)  $$PROXY_EXT ($$PROXY_INT)"

clean-ssh: check-project ## Clean SSH known_hosts for VMs
	@echo "$(GREEN)🔐 Cleaning SSH known_hosts...$(NC)"
	@set -a && source $(PROJECT_ENV) && set +a && \
		cd $(INFRA_DIR) && \
		CORE_EXT=$$(terraform output -json vm_core_public_ips | jq -r '.[0]') && \
		SCRAPE_EXT=$$(terraform output -json vm_scrape_public_ips | jq -r '.[0]') && \
		PROXY_EXT=$$(terraform output -json vm_proxy_public_ips | jq -r '.[0]') && \
		ssh-keygen -R $$CORE_EXT 2>/dev/null || true && \
		ssh-keygen -R $$SCRAPE_EXT 2>/dev/null || true && \
		ssh-keygen -R $$PROXY_EXT 2>/dev/null || true
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
	@echo "$(GREEN)🔨 Deploying $(PROJECT) with Ansible...$(NC)"
	@set -a && source $(PROJECT_ENV) && set +a && \
		cd $(ANSIBLE_DIR) && \
		ansible-playbook -i inventories/dev.ini playbooks/site.yml --tags system-base,git-server
	@echo "$(GREEN)✅ Ansible deployment complete!$(NC)"

# =============================================================================
# GIT PUSH
# =============================================================================

git-push: check-env ## Push code to Forgejo
	@echo "$(GREEN)📤 Pushing $(PROJECT) to Forgejo...$(NC)"
	@set -a && source $(PROJECT_ENV) && set +a && \
		CORE_EXT=$$CORE_EXTERNAL_IP && \
		FORGEJO_ORG=$$FORGEJO_ORG && \
		REPO_SUPERDEPLOY=$$REPO_SUPERDEPLOY && \
		ADMIN_USER=$$FORGEJO_ADMIN_USER && \
		ADMIN_PASS=$$FORGEJO_ADMIN_PASSWORD && \
		ENCODED_PASS=$$(printf '%s' "$$ADMIN_PASS" | jq -sRr @uri) && \
		echo "  📦 Pushing superdeploy-app..." && \
		if [ -d "../../app-repos/$$REPO_SUPERDEPLOY" ]; then \
			cd ../../app-repos/$$REPO_SUPERDEPLOY && \
			git remote remove forgejo 2>/dev/null || true && \
			git remote add forgejo "http://$$ADMIN_USER:$$ENCODED_PASS@$$CORE_EXT:3001/$$FORGEJO_ORG/$$REPO_SUPERDEPLOY.git" && \
			git push -u forgejo master 2>&1 | grep -v "Password" || true; \
		fi
	@echo "$(GREEN)✅ All repositories pushed!$(NC)"

# =============================================================================
# FULL DEPLOYMENT
# =============================================================================

deploy: check-env terraform-apply update-ips clean-ssh wait-vms ansible-deploy git-push ## 🚀 Full deployment
	@echo ""
	@echo "$(GREEN)╔══════════════════════════════════════════════════════════════════════════╗$(NC)"
	@echo "$(GREEN)║                  🎉 $(PROJECT) DEPLOYED! 🎉$(NC)"
	@echo "$(GREEN)╚══════════════════════════════════════════════════════════════════════════╝$(NC)"
	@echo ""
	@set -a && source $(PROJECT_ENV) && set +a && \
		CORE_EXT=$$CORE_EXTERNAL_IP && \
		echo "$(BLUE)📍 Access Points:$(NC)" && \
		echo "  $(YELLOW)Forgejo:$(NC)   http://$$CORE_EXT:3001" && \
		echo "  $(YELLOW)API:$(NC)       http://$$CORE_EXT:8000" && \
		echo "  $(YELLOW)Dashboard:$(NC) http://$$CORE_EXT:8001" && \
		echo "" && \
		echo "$(BLUE)🔐 Credentials:$(NC)" && \
		ADMIN_USER=$$FORGEJO_ADMIN_USER && \
		ADMIN_PASS=$$FORGEJO_ADMIN_PASSWORD && \
		echo "  $(YELLOW)Admin:$(NC) $$ADMIN_USER / $$ADMIN_PASS"

# =============================================================================
# UTILITIES
# =============================================================================

list-projects: ## List all available projects
	@echo "$(GREEN)📦 Available projects:$(NC)"
	@ls -1 projects/ | sed 's/^/  - /'

create-project: ## Create new project (PROJECT=name)
	@if [ -z "$(PROJECT)" ]; then \
		echo "$(RED)❌ ERROR: PROJECT not specified!$(NC)"; \
		echo "Usage: make create-project PROJECT=myapp"; \
		exit 1; \
	fi
	@if [ -d "$(PROJECT_DIR)" ]; then \
		echo "$(RED)❌ ERROR: Project '$(PROJECT)' already exists!$(NC)"; \
		exit 1; \
	fi
	@echo "$(GREEN)📦 Creating project: $(PROJECT)...$(NC)"
	@mkdir -p $(PROJECT_DIR)/compose
	@cp ENV.example $(PROJECT_ENV)
	@echo "$(GREEN)✅ Project created: $(PROJECT_DIR)$(NC)"
	@echo "$(YELLOW)Next steps:$(NC)"
	@echo "  1. Edit $(PROJECT_ENV)"
	@echo "  2. Add docker-compose.yml to $(PROJECT_COMPOSE)/"
	@echo "  3. make deploy PROJECT=$(PROJECT)"

destroy: check-project ## Destroy infrastructure
	@echo "$(RED)⚠️  This will DESTROY all VMs for project $(PROJECT)!$(NC)"
	@read -p "Are you sure? (yes/no): " confirm && [ "$$confirm" = "yes" ] || exit 1
	@echo "$(RED)🗑️  Destroying infrastructure...$(NC)"
	@set -a && source $(PROJECT_ENV) && set +a && \
		cd $(INFRA_DIR) && ./terraform-wrapper.sh destroy -auto-approve
	@echo "$(GREEN)✅ Infrastructure destroyed!$(NC)"

help: ## Show this help
	@echo "$(GREEN)╔══════════════════════════════════════════════════════════════════╗$(NC)"
	@echo "$(GREEN)║       SuperDeploy - Generic Multi-Project System                 ║$(NC)"
	@echo "$(GREEN)╚══════════════════════════════════════════════════════════════════╝$(NC)"
	@echo ""
	@echo "$(YELLOW)Usage:$(NC) make [command] PROJECT=project-name"
	@echo ""
	@echo "$(YELLOW)Available commands:$(NC)"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  $(BLUE)%-20s$(NC) %s\n", $$1, $$2}'
	@echo ""
	@echo "$(YELLOW)Examples:$(NC)"
	@echo "  make deploy PROJECT=cheapa"
	@echo "  make create-project PROJECT=myapp"
	@echo "  make list-projects"

.PHONY: check-project check-env terraform-init terraform-apply update-ips clean-ssh wait-vms ansible-deploy git-push deploy list-projects create-project destroy help
.DEFAULT_GOAL := help
