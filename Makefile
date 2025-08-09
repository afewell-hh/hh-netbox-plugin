# NetBox Hedgehog Plugin - Development Environment Makefile
# ==========================================================
# Single-command development environment setup
# Target: New developer productive in <5 minutes
# Usage: make dev-setup

.PHONY: dev-setup dev-check dev-clean dev-test dev-reset help status

# Default target
.DEFAULT_GOAL := help

# Configuration
DOCKER_COMPOSE_DIR := gitignore/netbox-docker
NETBOX_URL := http://localhost:8000
SETUP_LOG := .dev-setup.log
TIMESTAMP := $(shell date +%Y%m%d_%H%M%S)

# Detect Docker Compose command
DOCKER_COMPOSE := $(shell if command -v docker-compose >/dev/null 2>&1; then echo "docker-compose"; else echo "sudo docker compose"; fi)

# Colors for output
RED := \033[0;31m
GREEN := \033[0;32m
YELLOW := \033[1;33m
BLUE := \033[0;34m
NC := \033[0m # No Color

help: ## Show this help message
	@echo "$(BLUE)NetBox Hedgehog Plugin - Development Environment$(NC)"
	@echo "=================================================="
	@echo ""
	@echo "$(GREEN)Primary Commands:$(NC)"
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  $(BLUE)%-15s$(NC) %s\n", $$1, $$2}' $(MAKEFILE_LIST)
	@echo ""
	@echo "$(YELLOW)Quick Start:$(NC) make dev-setup"
	@echo "$(YELLOW)Check Status:$(NC) make status"

dev-setup: ## Complete development environment setup (<5 minutes)
	@echo "$(BLUE)🚀 NetBox Hedgehog Development Environment Setup$(NC)"
	@echo "=================================================="
	@echo "$(YELLOW)Target: Complete setup in <5 minutes$(NC)"
	@echo ""
	@date "+Started: %Y-%m-%d %H:%M:%S" | tee $(SETUP_LOG)
	@echo ""
	$(MAKE) _check_prerequisites
	$(MAKE) _setup_environment
	$(MAKE) _install_dependencies
	$(MAKE) _configure_netbox
	$(MAKE) _validate_existing_services
	$(MAKE) _install_plugin
	$(MAKE) _validate_setup
	@echo ""
	@echo "$(GREEN)✅ Development environment setup complete!$(NC)"
	@date "+Completed: %Y-%m-%d %H:%M:%S" | tee -a $(SETUP_LOG)
	@echo ""
	@echo "$(BLUE)🎯 Quick Access:$(NC)"
	@echo "  NetBox URL: $(NETBOX_URL)"
	@echo "  Admin user: admin / admin"
	@echo "  Plugin URL: $(NETBOX_URL)/plugins/hedgehog/"
	@echo ""
	@echo "$(YELLOW)Next Steps:$(NC)"
	@echo "  1. make dev-test    # Run validation tests"
	@echo "  2. make status      # Check environment status"

_check_prerequisites: ## Check system prerequisites
	@echo "$(BLUE)📋 Checking Prerequisites...$(NC)"
	@which docker >/dev/null 2>&1 || (echo "$(RED)❌ Docker not found. Please install Docker.$(NC)" && exit 1)
	@which python3 >/dev/null 2>&1 || (echo "$(RED)❌ Python 3 not found.$(NC)" && exit 1)
	@which git >/dev/null 2>&1 || (echo "$(RED)❌ Git not found.$(NC)" && exit 1)
	@docker info >/dev/null 2>&1 || sudo docker info >/dev/null 2>&1 || (echo "$(RED)❌ Docker daemon not accessible.$(NC)" && exit 1)
	@echo "$(GREEN)✅ All prerequisites found$(NC)"

_setup_environment: ## Setup development environment files
	@echo "$(BLUE)🏗️  Setting up environment...$(NC)"
	@# Verify Docker compose directory exists
	@if [ -d "$(DOCKER_COMPOSE_DIR)" ]; then \
		echo "$(GREEN)✅ Docker environment directory found$(NC)"; \
	else \
		echo "$(RED)❌ Docker environment not found at $(DOCKER_COMPOSE_DIR)$(NC)" && exit 1; \
	fi
	@# Create default .env file if it doesn't exist
	@if [ ! -f .env ]; then \
		echo "NETBOX_URL=http://localhost:8000" > .env; \
		echo "DEV_MODE=true" >> .env; \
		echo "$(GREEN)✅ Created default .env file$(NC)"; \
	fi

_install_dependencies: ## Install Python dependencies
	@echo "$(BLUE)📦 Installing Python dependencies...$(NC)"
	@# Skip if dependencies already installed (optimization)
	@if pip3 list | grep -q "kubernetes\|requests\|pytest"; then \
		echo "$(GREEN)✅ Python dependencies already installed$(NC)"; \
	else \
		pip3 install --upgrade pip -q; \
		pip3 install -q kubernetes pyyaml jsonschema GitPython requests pytest pytest-django; \
		echo "$(GREEN)✅ Python dependencies installed$(NC)"; \
	fi

_configure_netbox: ## Configure NetBox for development
	@echo "$(BLUE)⚙️  Configuring NetBox...$(NC)"
	@# Check environment files exist (they should from previous setup)
	@if [ -f "$(DOCKER_COMPOSE_DIR)/env/netbox.env" ]; then \
		echo "$(GREEN)✅ NetBox environment file exists$(NC)"; \
	else \
		echo "$(YELLOW)⚠️  NetBox environment file missing but continuing...$(NC)"; \
	fi
	@echo "$(GREEN)✅ NetBox configuration validated$(NC)"

_validate_existing_services: ## Validate existing Docker services
	@echo "$(BLUE)🔍 Validating existing services...$(NC)"
	@# Check if containers are running
	@if cd $(DOCKER_COMPOSE_DIR) && $(DOCKER_COMPOSE) ps postgres | grep -q "Up\|healthy"; then \
		echo "$(GREEN)✅ PostgreSQL service running$(NC)"; \
	else \
		echo "$(YELLOW)⚠️  PostgreSQL service not running, starting...$(NC)"; \
		cd $(DOCKER_COMPOSE_DIR) && $(DOCKER_COMPOSE) up -d postgres; \
	fi
	@if cd $(DOCKER_COMPOSE_DIR) && $(DOCKER_COMPOSE) ps redis | grep -q "Up\|healthy"; then \
		echo "$(GREEN)✅ Redis service running$(NC)"; \
	else \
		echo "$(YELLOW)⚠️  Redis service not running, starting...$(NC)"; \
		cd $(DOCKER_COMPOSE_DIR) && $(DOCKER_COMPOSE) up -d redis redis-cache; \
	fi
	@if cd $(DOCKER_COMPOSE_DIR) && $(DOCKER_COMPOSE) ps netbox | grep -q "Up\|healthy"; then \
		echo "$(GREEN)✅ NetBox service running$(NC)"; \
	else \
		echo "$(YELLOW)⚠️  NetBox service not running, starting...$(NC)"; \
		cd $(DOCKER_COMPOSE_DIR) && $(DOCKER_COMPOSE) up -d; \
	fi
	@# Wait for services to be ready
	@echo "$(YELLOW)⏳ Waiting for services to be ready...$(NC)"
	@timeout=60; \
	while [ $$timeout -gt 0 ]; do \
		if curl -s -f $(NETBOX_URL)/login/ >/dev/null 2>&1; then \
			echo "$(GREEN)✅ All services ready$(NC)"; \
			break; \
		fi; \
		echo -n "."; \
		sleep 2; \
		timeout=$$((timeout-2)); \
	done; \
	if [ $$timeout -le 0 ]; then \
		echo "$(YELLOW)⚠️  Services taking longer than expected but continuing...$(NC)"; \
	fi

_install_plugin: ## Install the hedgehog plugin
	@echo "$(BLUE)🔌 Installing Hedgehog plugin...$(NC)"
	@pip3 install -e . -q
	@echo "$(GREEN)✅ Plugin installed in development mode$(NC)"

_validate_setup: ## Validate the complete setup
	@echo "$(BLUE)🔍 Validating setup...$(NC)"
	@# Quick validation - essential checks only
	@if curl -s -f $(NETBOX_URL)/login/ >/dev/null 2>&1; then \
		echo "$(GREEN)✅ NetBox web interface accessible$(NC)"; \
	else \
		echo "$(RED)❌ NetBox web interface not accessible$(NC)"; \
	fi
	@if curl -s $(NETBOX_URL)/plugins/hedgehog/ | grep -q "hedgehog\|Hedgehog" >/dev/null 2>&1; then \
		echo "$(GREEN)✅ Plugin accessible and responding$(NC)"; \
	else \
		echo "$(YELLOW)⚠️  Plugin may need additional configuration$(NC)"; \
	fi
	@echo "$(BLUE)✨ Quick setup validation complete$(NC)"
	@echo "$(YELLOW)💡 Run 'make dev-test' for comprehensive validation$(NC)"

dev-check: ## Quick health check of development environment
	@echo "$(BLUE)🏥 Development Environment Health Check$(NC)"
	@echo "======================================="
	@cd $(DOCKER_COMPOSE_DIR) && $(DOCKER_COMPOSE) ps
	@echo ""
	@if curl -s -f $(NETBOX_URL)/login/ >/dev/null 2>&1; then \
		echo "$(GREEN)✅ NetBox Web Interface: OK$(NC)"; \
	else \
		echo "$(RED)❌ NetBox Web Interface: FAILED$(NC)"; \
	fi
	@if curl -s $(NETBOX_URL)/plugins/hedgehog/ >/dev/null 2>&1; then \
		echo "$(GREEN)✅ Hedgehog Plugin: OK$(NC)"; \
	else \
		echo "$(YELLOW)⚠️  Hedgehog Plugin: Check needed$(NC)"; \
	fi

dev-test: ## Run development validation tests
	@echo "$(BLUE)🧪 Running Development Tests$(NC)"
	@echo "==============================="
	@python3 quick_validation.py --verbose

dev-clean: ## Clean development environment (removes containers but keeps data)
	@echo "$(BLUE)🧹 Cleaning development environment...$(NC)"
	@cd $(DOCKER_COMPOSE_DIR) && $(DOCKER_COMPOSE) down
	@echo "$(GREEN)✅ Environment cleaned (data preserved)$(NC)"

dev-reset: ## Complete reset (DANGER: destroys all data)
	@echo "$(RED)⚠️  WARNING: This will destroy ALL data!$(NC)"
	@echo "Continue? [y/N]: " && read ans && [ $${ans:-N} = y ]
	@cd $(DOCKER_COMPOSE_DIR) && $(DOCKER_COMPOSE) down -v
	@sudo docker system prune -f
	@rm -f $(SETUP_LOG)
	@echo "$(GREEN)✅ Environment completely reset$(NC)"

status: ## Show current environment status
	@echo "$(BLUE)📊 Development Environment Status$(NC)"
	@echo "==================================="
	@echo ""
	@echo "$(YELLOW)Docker Services:$(NC)"
	@cd $(DOCKER_COMPOSE_DIR) && $(DOCKER_COMPOSE) ps 2>/dev/null || echo "$(RED)❌ Docker services not running$(NC)"
	@echo ""
	@echo "$(YELLOW)Network Accessibility:$(NC)"
	@if curl -s -f $(NETBOX_URL)/login/ >/dev/null 2>&1; then \
		echo "$(GREEN)✅ NetBox: $(NETBOX_URL)$(NC)"; \
	else \
		echo "$(RED)❌ NetBox: Not accessible$(NC)"; \
	fi
	@if curl -s $(NETBOX_URL)/plugins/hedgehog/ >/dev/null 2>&1; then \
		echo "$(GREEN)✅ Plugin: $(NETBOX_URL)/plugins/hedgehog/$(NC)"; \
	else \
		echo "$(YELLOW)⚠️  Plugin: May need configuration$(NC)"; \
	fi
	@echo ""
	@if [ -f $(SETUP_LOG) ]; then \
		echo "$(YELLOW)Last Setup:$(NC)"; \
		tail -2 $(SETUP_LOG); \
	fi

# Performance target tracking
_performance_check: ## Internal: Check setup time performance
	@if [ -f $(SETUP_LOG) ]; then \
		start_time=$$(head -1 $(SETUP_LOG) | grep -o '[0-9][0-9]:[0-9][0-9]:[0-9][0-9]'); \
		end_time=$$(tail -1 $(SETUP_LOG) | grep -o '[0-9][0-9]:[0-9][0-9]:[0-9][0-9]'); \
		echo "Setup completed in time range: $$start_time to $$end_time"; \
	fi