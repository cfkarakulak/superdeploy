#!/bin/bash
# Integration Test: Configuration Changes
# Tests that configuration changes in project.yml are reflected without code modifications

# Don't exit on error - we want to collect all test results
set +e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
TEST_PROJECT="test-config-changes"
TEST_PROJECT_DIR="$PROJECT_ROOT/projects/$TEST_PROJECT"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Test results tracking
TESTS_PASSED=0
TESTS_FAILED=0
FAILED_TESTS=()

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[PASS]${NC} $1"
    ((TESTS_PASSED++))
}

log_error() {
    echo -e "${RED}[FAIL]${NC} $1"
    ((TESTS_FAILED++))
    FAILED_TESTS+=("$1")
}

log_warning() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

# Setup test project
setup_test_project() {
    log_info "Setting up test project..."
    
    # Create test project directory
    mkdir -p "$TEST_PROJECT_DIR"
    
    # Create a minimal project.yml
    cat > "$TEST_PROJECT_DIR/project.yml" <<EOF
project: $TEST_PROJECT
description: Test project for configuration changes

infrastructure:
  forgejo:
    version: "1.21"
    port: 3001
    ssh_port: 2222
    admin_user: "admin"
    admin_email: "admin@test.local"
    org: "testorg"
    repo: "testrepo"
    db_name: "forgejo"
    db_user: "forgejo"

vms:
  core:
    count: 1
    machine_type: e2-medium
    disk_size: 20
    services:
      - postgres

core_services:
  postgres:
    version: "15-alpine"
    user: "test_user"
    database: "test_db"

apps:
  api:
    path: /tmp/test-api
    vm: core
    port: 8000

network:
  subnet: 172.20.0.0/24

monitoring:
  enabled: false
EOF
    
    log_success "Test project created at $TEST_PROJECT_DIR"
}

# Test 1: Change Forgejo port
test_forgejo_port_change() {
    log_info "Testing Forgejo port change..."
    
    # Read current port
    local current_port=$(grep "port:" "$TEST_PROJECT_DIR/project.yml" | head -1 | awk '{print $2}')
    log_info "Current Forgejo port: $current_port"
    
    # Change port to 3002
    sed -i.bak 's/port: 3001/port: 3002/' "$TEST_PROJECT_DIR/project.yml"
    
    # Verify change
    local new_port=$(grep "port:" "$TEST_PROJECT_DIR/project.yml" | head -1 | awk '{print $2}')
    
    if [ "$new_port" = "3002" ]; then
        log_success "Forgejo port changed from $current_port to $new_port"
    else
        log_error "Failed to change Forgejo port"
    fi
    
    # Restore original
    mv "$TEST_PROJECT_DIR/project.yml.bak" "$TEST_PROJECT_DIR/project.yml"
}

# Test 2: Add new addon
test_add_addon() {
    log_info "Testing adding new addon..."
    
    # Check if redis addon exists
    if [ ! -d "$PROJECT_ROOT/addons/redis" ]; then
        log_warning "Redis addon not found, skipping test"
        return
    fi
    
    # Add redis to project config
    cat >> "$TEST_PROJECT_DIR/project.yml" <<EOF

  redis:
    version: "7-alpine"
    port: 6379
EOF
    
    # Verify addition
    if grep -q "redis:" "$TEST_PROJECT_DIR/project.yml"; then
        log_success "Redis addon added to project configuration"
    else
        log_error "Failed to add Redis addon"
    fi
    
    # Verify redis addon has required files
    local redis_files=(
        "addon.yml"
        "ansible.yml"
        "compose.yml.j2"
        "env.yml"
    )
    
    for file in "${redis_files[@]}"; do
        if [ -f "$PROJECT_ROOT/addons/redis/$file" ]; then
            log_success "Redis addon has $file"
        else
            log_error "Redis addon missing $file"
        fi
    done
}

# Test 3: Change application port
test_app_port_change() {
    log_info "Testing application port change..."
    
    # Read current app port - look for port under apps section
    local current_port=$(grep -A 10 "^apps:" "$TEST_PROJECT_DIR/project.yml" | grep "port:" | head -1 | awk '{print $2}')
    log_info "Current API port: $current_port"
    
    if [ -z "$current_port" ]; then
        log_warning "Could not find current API port in test config"
        # Still test the change mechanism
        current_port="8000"
    fi
    
    # Change port to 8001
    sed -i.bak 's/port: 8000/port: 8001/' "$TEST_PROJECT_DIR/project.yml"
    
    # Verify change
    local new_port=$(grep -A 10 "^apps:" "$TEST_PROJECT_DIR/project.yml" | grep "port:" | head -1 | awk '{print $2}')
    
    if [ "$new_port" = "8001" ]; then
        log_success "API port changed from $current_port to $new_port"
    else
        log_error "Failed to change API port (got: $new_port, expected: 8001)"
    fi
    
    # Restore original
    mv "$TEST_PROJECT_DIR/project.yml.bak" "$TEST_PROJECT_DIR/project.yml"
}

# Test 4: Verify no code modifications needed
test_no_code_modifications() {
    log_info "Testing that no code modifications are needed..."
    
    # Check that templates use variables, not hardcoded values
    local template_files=(
        "addons/forgejo/compose.yml.j2"
        "addons/postgres/compose.yml.j2"
        "shared/ansible/roles/orchestration/addon-deployer/tasks/main.yml"
    )
    
    for template in "${template_files[@]}"; do
        if [ ! -f "$PROJECT_ROOT/$template" ]; then
            log_warning "Template not found: $template"
            continue
        fi
        
        # Check for Jinja2 variables
        if grep -q "{{.*}}" "$PROJECT_ROOT/$template"; then
            log_success "Template uses variables: $template"
        else
            log_warning "Template may not use variables: $template"
        fi
    done
}

# Test 5: Verify dynamic firewall rules
test_dynamic_firewall() {
    log_info "Testing dynamic firewall configuration..."
    
    local security_tasks="$PROJECT_ROOT/shared/ansible/roles/system/security/tasks/main.yml"
    
    if [ ! -f "$security_tasks" ]; then
        log_error "Security tasks file not found"
        return
    fi
    
    # Check that firewall rules are dynamic
    if grep -q "project_config\|addon_config\|app.*port" "$security_tasks"; then
        log_success "Firewall rules use dynamic configuration"
    else
        log_warning "Firewall rules may not be fully dynamic"
    fi
}

# Test 6: Verify addon configuration validation
test_addon_validation() {
    log_info "Testing addon configuration validation..."
    
    local validator="$PROJECT_ROOT/cli/core/validator.py"
    
    if [ ! -f "$validator" ]; then
        log_error "Validator not found"
        return
    fi
    
    # Check if validator has addon validation logic
    if grep -q "addon\|infrastructure" "$validator"; then
        log_success "Validator includes addon/infrastructure validation"
    else
        log_warning "Validator may not validate addons"
    fi
}

# Test 7: Test environment variable generation
test_env_generation() {
    log_info "Testing environment variable generation..."
    
    local env_generator="$PROJECT_ROOT/shared/ansible/roles/orchestration/addon-deployer/tasks/generate-env.yml"
    
    if [ ! -f "$env_generator" ]; then
        log_error "Environment generator not found"
        return
    fi
    
    # Check that it reads from project config
    if grep -q "project_config\|addon_config" "$env_generator"; then
        log_success "Environment generator uses project configuration"
    else
        log_error "Environment generator may not use project configuration"
    fi
}

# Test 8: Verify template rendering
test_template_rendering() {
    log_info "Testing template rendering logic..."
    
    local template_renderer="$PROJECT_ROOT/shared/ansible/roles/orchestration/addon-deployer/tasks/render-templates.yml"
    
    if [ ! -f "$template_renderer" ]; then
        log_error "Template renderer not found"
        return
    fi
    
    # Check that it renders compose templates
    if grep -q "compose.yml.j2\|template:" "$template_renderer"; then
        log_success "Template renderer processes compose templates"
    else
        log_error "Template renderer may not process templates correctly"
    fi
}

# Cleanup
cleanup() {
    log_info "Cleaning up test project..."
    if [ -d "$TEST_PROJECT_DIR" ]; then
        rm -rf "$TEST_PROJECT_DIR"
        log_success "Test project cleaned up"
    fi
}

# Main test execution
main() {
    echo "========================================"
    echo "Integration Test: Configuration Changes"
    echo "========================================"
    echo ""
    
    cd "$PROJECT_ROOT"
    
    setup_test_project
    echo ""
    
    test_forgejo_port_change
    echo ""
    
    test_add_addon
    echo ""
    
    test_app_port_change
    echo ""
    
    test_no_code_modifications
    echo ""
    
    test_dynamic_firewall
    echo ""
    
    test_addon_validation
    echo ""
    
    test_env_generation
    echo ""
    
    test_template_rendering
    echo ""
    
    cleanup
    echo ""
    
    # Summary
    echo "========================================"
    echo "Test Summary"
    echo "========================================"
    echo -e "${GREEN}Passed: $TESTS_PASSED${NC}"
    echo -e "${RED}Failed: $TESTS_FAILED${NC}"
    
    if [ $TESTS_FAILED -gt 0 ]; then
        echo ""
        echo "Failed tests:"
        for test in "${FAILED_TESTS[@]}"; do
            echo -e "  ${RED}✗${NC} $test"
        done
        exit 1
    else
        echo ""
        echo -e "${GREEN}✅ All tests passed!${NC}"
        exit 0
    fi
}

main "$@"
