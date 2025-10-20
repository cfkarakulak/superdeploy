.PHONY: help init deploy update-ips clean destroy test

# =============================================================================
# SuperDeploy - Full Automation Makefile
# =============================================================================

# Load .env if exists
ifneq (,$(wildcard ./.env))
    include .env
    export
endif

# Colors
RED=\033[0;31m
GREEN=\033[0;32m
YELLOW=\033[1;33m
BLUE=\033[0;34m
NC=\033[0m # No Color

# Directories (relative paths - Makefile is in superdeploy/)
INFRA_DIR=../superdeploy-infra
ANSIBLE_DIR=$(INFRA_DIR)/ansible

help: ## Show this help
	@echo "$(GREEN)╔══════════════════════════════════════════════════════════════════╗$(NC)"
	@echo "$(GREEN)║           SuperDeploy - Full Automation Commands                 ║$(NC)"
	@echo "$(GREEN)╚══════════════════════════════════════════════════════════════════╝$(NC)"
	@echo ""
	@echo "$(YELLOW)📋 Quick Start:$(NC)"
	@echo "  $(BLUE)1.$(NC) cp superdeploy/ENV.example superdeploy/.env"
	@echo "  $(BLUE)2.$(NC) nano superdeploy/.env  $(YELLOW)(fill GCP_PROJECT_ID + passwords)$(NC)"
	@echo "  $(BLUE)3.$(NC) make deploy  $(GREEN)✨ (single command!)$(NC)"
	@echo ""
	@echo "$(YELLOW)📚 Available Commands:$(NC)"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  $(BLUE)%-15s$(NC) %s\n", $$1, $$2}'

init: ## Initialize (copy ENV.example to .env)
	@echo "$(GREEN)📋 Initializing SuperDeploy...$(NC)"
	@if [ ! -f .env ]; then \
		cp ENV.example .env; \
		echo "$(GREEN)✅ Created .env$(NC)"; \
		echo "$(YELLOW)⚠️  Edit .env and fill:$(NC)"; \
		echo "  - GCP_PROJECT_ID"; \
		echo "  - All passwords (CHANGE_ME_*)"; \
		echo "$(YELLOW)💡 Generate passwords: openssl rand -base64 32$(NC)"; \
	else \
		echo "$(YELLOW)⚠️  .env already exists!$(NC)"; \
	fi

check-env: ## Check if .env exists and is configured
	@if [ ! -f .env ]; then \
		echo "$(RED)❌ ERROR: .env not found!$(NC)"; \
		echo "$(YELLOW)Run: make init$(NC)"; \
		exit 1; \
	fi
	@if grep -q "CHANGE_ME" .env; then \
		echo "$(RED)❌ ERROR: Found unconfigured values in .env!$(NC)"; \
		echo "$(YELLOW)Edit .env and replace all CHANGE_ME_* values$(NC)"; \
		exit 1; \
	fi
	@if grep -q "GCP_PROJECT_ID=your-gcp-project" .env; then \
		echo "$(RED)❌ ERROR: GCP_PROJECT_ID not configured!$(NC)"; \
		echo "$(YELLOW)Edit .env and set your GCP project ID$(NC)"; \
		exit 1; \
	fi
	@echo "$(GREEN)✅ .env configuration looks good!$(NC)"

terraform-init: check-env ## Initialize Terraform
	@echo "$(GREEN)🔧 Initializing Terraform...$(NC)"
	@cd $(INFRA_DIR) && ./terraform-wrapper.sh init

terraform-apply: terraform-init ## Create VMs with Terraform
	@echo "$(GREEN)🚀 Creating GCP VMs...$(NC)"
	@cd $(INFRA_DIR) && ./terraform-wrapper.sh apply -auto-approve
	@echo "$(GREEN)✅ VMs created!$(NC)"

update-ips: ## Extract IPs from Terraform and update .env
	@echo "$(GREEN)📍 Extracting VM IPs...$(NC)"
	@cd $(INFRA_DIR) && \
		CORE_EXT=$$(terraform output -json vm_core_public_ips | jq -r '.[0]') && \
		CORE_INT=$$(terraform output -json vm_core_internal_ips | jq -r '.[0]') && \
		SCRAPE_EXT=$$(terraform output -json vm_scrape_public_ips | jq -r '.[0]') && \
		SCRAPE_INT=$$(terraform output -json vm_scrape_internal_ips | jq -r '.[0]') && \
		PROXY_EXT=$$(terraform output -json vm_proxy_public_ips | jq -r '.[0]') && \
		PROXY_INT=$$(terraform output -json vm_proxy_internal_ips | jq -r '.[0]') && \
		cd - > /dev/null && \
		sed -i.bak "s|^CORE_EXTERNAL_IP=.*|CORE_EXTERNAL_IP=$$CORE_EXT|" .env && \
		sed -i.bak "s|^CORE_INTERNAL_IP=.*|CORE_INTERNAL_IP=$$CORE_INT|" .env && \
		sed -i.bak "s|^SCRAPE_EXTERNAL_IP=.*|SCRAPE_EXTERNAL_IP=$$SCRAPE_EXT|" .env && \
		sed -i.bak "s|^SCRAPE_INTERNAL_IP=.*|SCRAPE_INTERNAL_IP=$$SCRAPE_INT|" .env && \
		sed -i.bak "s|^PROXY_EXTERNAL_IP=.*|PROXY_EXTERNAL_IP=$$PROXY_EXT|" .env && \
		sed -i.bak "s|^PROXY_INTERNAL_IP=.*|PROXY_INTERNAL_IP=$$PROXY_INT|" .env && \
		rm -f .env.bak && \
		echo "$(GREEN)✅ Updated .env with new IPs:$(NC)" && \
		echo "  $(BLUE)CORE:$(NC)   $$CORE_EXT ($$CORE_INT)" && \
		echo "  $(BLUE)SCRAPE:$(NC) $$SCRAPE_EXT ($$SCRAPE_INT)" && \
		echo "  $(BLUE)PROXY:$(NC)  $$PROXY_EXT ($$PROXY_INT)"

clean-ssh: ## Clean SSH known_hosts for VMs
	@echo "$(GREEN)🔐 Cleaning SSH known_hosts...$(NC)"
	@cd $(INFRA_DIR) && \
		CORE_EXT=$$(terraform output -json vm_core_public_ips | jq -r '.[0]') && \
		SCRAPE_EXT=$$(terraform output -json vm_scrape_public_ips | jq -r '.[0]') && \
		PROXY_EXT=$$(terraform output -json vm_proxy_public_ips | jq -r '.[0]') && \
		ssh-keygen -R $$CORE_EXT 2>/dev/null || true && \
		ssh-keygen -R $$SCRAPE_EXT 2>/dev/null || true && \
		ssh-keygen -R $$PROXY_EXT 2>/dev/null || true
	@echo "$(GREEN)✅ SSH known_hosts cleaned!$(NC)"

wait-vms: ## Wait for VMs to be ready (120s for startup scripts)
	@echo "$(YELLOW)⏳ Waiting for VMs to complete startup scripts (120 seconds)...$(NC)"
	@echo "$(YELLOW)💡 VMs run apt-get update on first boot, this prevents dpkg lock errors$(NC)"
	@for i in $$(seq 120 -1 1); do \
		printf "\r$(YELLOW)⏳ $$i seconds remaining...$(NC)"; \
		sleep 1; \
	done
	@echo "\n$(GREEN)✅ VMs should be ready!$(NC)"

ansible-deploy: ## Deploy with Ansible
	@echo "$(GREEN)🔨 Deploying with Ansible...$(NC)"
	@set -a && source .env && set +a && \
		cd $(ANSIBLE_DIR) && \
		ansible-playbook -i inventories/dev.ini playbooks/site.yml --tags system-base,git-server
	@echo "$(GREEN)✅ Ansible deployment complete!$(NC)"

git-push: ## Push code to Forgejo
	@echo "$(GREEN)📤 Pushing code to Forgejo...$(NC)"
	@CORE_EXT=$$(grep "^CORE_EXTERNAL_IP=" .env | cut -d= -f2) && \
	ADMIN_USER=$$(grep "^FORGEJO_ADMIN_USER=" .env | cut -d= -f2) && \
	ADMIN_PASS=$$(grep "^FORGEJO_ADMIN_PASSWORD=" .env | cut -d= -f2) && \
	ENCODED_PASS=$$(printf '%s' "$$ADMIN_PASS" | jq -sRr @uri) && \
	if [ -z "$$(git remote | grep forgejo)" ]; then \
		git remote add forgejo "http://$$ADMIN_USER:$$ENCODED_PASS@$$CORE_EXT:3001/cradexco/superdeploy-app.git"; \
	else \
		git remote set-url forgejo "http://$$ADMIN_USER:$$ENCODED_PASS@$$CORE_EXT:3001/cradexco/superdeploy-app.git"; \
	fi && \
	git add .env && \
	git commit -m "config: automated deployment setup" || true && \
	git push -u forgejo master
	@echo "$(GREEN)✅ Code pushed to Forgejo!$(NC)"

deploy: check-env terraform-apply update-ips clean-ssh wait-vms ansible-deploy git-push ## 🚀 Full deployment (single command!)
	@echo ""
	@echo "$(GREEN)╔══════════════════════════════════════════════════════════════════════════╗$(NC)"
	@echo "$(GREEN)║                  🎉 DEPLOYMENT COMPLETE! 🎉                              ║$(NC)"
	@echo "$(GREEN)╚══════════════════════════════════════════════════════════════════════════╝$(NC)"
	@echo ""
	@CORE_EXT=$$(grep "^CORE_EXTERNAL_IP=" .env | cut -d= -f2) && \
		echo "$(BLUE)📍 Access Points:$(NC)" && \
		echo "  $(YELLOW)Forgejo:$(NC)  http://$$CORE_EXT:3001" && \
		echo "  $(YELLOW)Actions:$(NC)  http://$$CORE_EXT:3001/cradexco/superdeploy-app/actions" && \
		echo "  $(YELLOW)API:$(NC)      http://$$CORE_EXT:8000/health" && \
		echo "  $(YELLOW)Registry:$(NC) http://$$CORE_EXT:8080/health" && \
		echo "  $(YELLOW)Dashboard:$(NC) http://$$CORE_EXT:8001" && \
		echo "" && \
		echo "$(BLUE)🔐 Credentials:$(NC)" && \
		ADMIN_USER=$$(grep "^FORGEJO_ADMIN_USER=" .env | cut -d= -f2) && \
		ADMIN_PASS=$$(grep "^FORGEJO_ADMIN_PASSWORD=" .env | cut -d= -f2) && \
		echo "  $(YELLOW)Admin:$(NC) $$ADMIN_USER / $$ADMIN_PASS" && \
		echo "" && \
		echo "$(GREEN)✨ Watch workflows deploy automatically!$(NC)"

test: ## Test all services
	@echo "$(GREEN)🧪 Testing services...$(NC)"
	@CORE_EXT=$$(grep "^CORE_EXTERNAL_IP=" .env | cut -d= -f2) && \
		echo "$(BLUE)Testing API...$(NC)" && \
		curl -sf http://$$CORE_EXT:8000/health && echo " $(GREEN)✅$(NC)" || echo " $(RED)❌$(NC)" && \
		echo "$(BLUE)Testing Proxy Registry...$(NC)" && \
		curl -sf http://$$CORE_EXT:8080/health && echo " $(GREEN)✅$(NC)" || echo " $(RED)❌$(NC)" && \
		echo "$(BLUE)Testing Dashboard...$(NC)" && \
		curl -sf http://$$CORE_EXT:8001 && echo " $(GREEN)✅$(NC)" || echo " $(RED)❌$(NC)"

destroy: ## Destroy all infrastructure
	@echo "$(RED)⚠️  This will DESTROY all VMs and data!$(NC)"
	@read -p "Are you sure? (yes/no): " confirm && [ "$$confirm" = "yes" ] || exit 1
	@echo "$(RED)🗑️  Destroying infrastructure...$(NC)"
	@cd $(INFRA_DIR) && ./terraform-wrapper.sh destroy -auto-approve
	@echo "$(GREEN)✅ Infrastructure destroyed!$(NC)"

clean: ## Clean generated files
	@echo "$(GREEN)🧹 Cleaning generated files...$(NC)"
	@rm -f .env.bak
	@echo "$(GREEN)✅ Cleaned!$(NC)"

