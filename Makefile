# =============================================================================
# SuperDeploy - Makefile (Legacy aliases for backward compatibility)
# =============================================================================
# ⚠️  DEPRECATED: Use 'superdeploy' CLI instead!
#
# Old:  make deploy
# New:  superdeploy up && superdeploy sync
#
# Old:  make status
# New:  superdeploy status
# =============================================================================

.PHONY: help install

# Colors
GREEN := \033[0;32m
YELLOW := \033[1;33m
BLUE := \033[0;34m
NC := \033[0m

help:
	@echo "$(YELLOW)⚠️  Makefile is DEPRECATED - Use Python CLI instead!$(NC)"
	@echo ""
	@echo "$(GREEN)Install CLI:$(NC)"
	@echo "  make install    # Install superdeploy CLI"
	@echo ""
	@echo "$(GREEN)New Commands:$(NC)"
	@echo "  $(BLUE)superdeploy init$(NC)      # Interactive setup"
	@echo "  $(BLUE)superdeploy up$(NC)        # Deploy infrastructure"
	@echo "  $(BLUE)superdeploy sync$(NC)      # Sync secrets"
	@echo "  $(BLUE)superdeploy status$(NC)    # Show status"
	@echo "  $(BLUE)superdeploy doctor$(NC)    # Health check"
	@echo "  $(BLUE)superdeploy logs -a api -f$(NC)  # View logs"
	@echo ""
	@echo "$(YELLOW)Run: superdeploy --help$(NC)"

install:
	@echo "$(GREEN)📦 Installing superdeploy CLI...$(NC)"
	@if [ ! -d "venv" ]; then \
		python3 -m venv venv && \
		. venv/bin/activate && \
		pip install --upgrade pip && \
		pip install -e .; \
	fi
	@echo "$(GREEN)✅ Installed! Activate with:$(NC)"
	@echo "  source venv/bin/activate"
	@echo "  superdeploy --help"

# Legacy aliases (backward compatibility)
deploy:
	@echo "$(YELLOW)⚠️  'make deploy' is deprecated!$(NC)"
	@echo "$(GREEN)Use instead:$(NC) superdeploy up && superdeploy sync"
	@exit 1

status:
	@echo "$(YELLOW)⚠️  'make status' is deprecated!$(NC)"
	@echo "$(GREEN)Use instead:$(NC) superdeploy status"
	@exit 1

destroy:
	@echo "$(YELLOW)⚠️  'make destroy' is deprecated!$(NC)"
	@echo "$(GREEN)Use instead:$(NC) superdeploy destroy"
	@exit 1
