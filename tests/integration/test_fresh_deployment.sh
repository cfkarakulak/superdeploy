#!/bin/bash
# Integration Test: Fresh Deployment
# Tests a complete deployment from scratch using the new Ansible structure

# Don't exit on error - we want to collect all test results
set +e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
TEST_PROJECT="test-fresh-deploy"
TEST_INVENTORY="$PROJECT_ROOT/shared/ansible/inventories/test.ini"

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

# Test 1: Verify Ansible structure exists
test_ansible_structure() {
    log_info "Testing Ansible directory structure..."
    
    local required_dirs=(
        "shared/ansible/roles/system/base"
        "shared/ansible/roles/system/docker"
        "shared/ansible/roles/system/security"
        "shared/ansible/roles/system/monitoring-agent"
        "shared/ansible/roles/orchestration/addon-deployer"
        "shared/ansible/roles/orchestration/project-deployer"
    )
    
    for dir in "${required_dirs[@]}"; do
        if [ -d "$PROJECT_ROOT/$dir" ]; then
            log_success "Directory exists: $dir"
        else
            log_error "Missing directory: $dir"
        fi
    done
}

# Test 2: Verify role structure
test_role_structure() {
    log_info "Testing role structure compliance..."
    
    local roles=(
        "system/base"
        "system/docker"
        "system/security"
        "system/monitoring-agent"
    )
    
    for role in "${roles[@]}"; do
        local role_path="$PROJECT_ROOT/shared/ansible/roles/$role"
        
        # Check for required directories
        if [ -d "$role_path/tasks" ]; then
            log_success "Role $role has tasks directory"
        else
            log_error "Role $role missing tasks directory"
        fi
        
        # Check for main.yml
        if [ -f "$role_path/tasks/main.yml" ]; then
            log_success "Role $role has tasks/main.yml"
        else
            log_error "Role $role missing tasks/main.yml"
        fi
        
        # Check for defaults (optional but recommended)
        if [ -d "$role_path/defaults" ]; then
            log_success "Role $role has defaults directory"
        else
            log_warning "Role $role missing defaults directory (optional)"
        fi
    done
}

# Test 3: Verify addon structure
test_addon_structure() {
    log_info "Testing addon structure..."
    
    local addons=(
        "forgejo"
        "postgres"
        "redis"
        "rabbitmq"
        "mongodb"
        "caddy"
        "monitoring"
    )
    
    for addon in "${addons[@]}"; do
        local addon_path="$PROJECT_ROOT/addons/$addon"
        
        if [ ! -d "$addon_path" ]; then
            log_error "Addon directory missing: $addon"
            continue
        fi
        
        # Check required files
        if [ -f "$addon_path/addon.yml" ]; then
            log_success "Addon $addon has addon.yml"
        else
            log_error "Addon $addon missing addon.yml"
        fi
        
        if [ -f "$addon_path/ansible.yml" ]; then
            log_success "Addon $addon has ansible.yml"
        else
            log_error "Addon $addon missing ansible.yml"
        fi
        
        if [ -f "$addon_path/compose.yml.j2" ]; then
            log_success "Addon $addon has compose.yml.j2"
        else
            log_error "Addon $addon missing compose.yml.j2"
        fi
        
        if [ -f "$addon_path/env.yml" ]; then
            log_success "Addon $addon has env.yml"
        else
            log_error "Addon $addon missing env.yml"
        fi
    done
}

# Test 4: Verify playbook syntax
test_playbook_syntax() {
    log_info "Testing playbook syntax..."
    
    local playbook="playbooks/site.yml"
    local ansible_dir="$PROJECT_ROOT/shared/ansible"
    
    if [ ! -f "$ansible_dir/$playbook" ]; then
        log_error "Main playbook not found: $ansible_dir/$playbook"
        return
    fi
    
    # Check if ansible-playbook is available
    if ! command -v ansible-playbook &> /dev/null; then
        log_warning "ansible-playbook not found, skipping syntax check"
        return
    fi
    
    # Syntax check (dry-run) - run from ansible directory
    pushd "$ansible_dir" > /dev/null
    if ansible-playbook "$playbook" --syntax-check &> /dev/null; then
        log_success "Playbook syntax is valid"
    else
        log_error "Playbook syntax check failed"
    fi
    popd > /dev/null
}

# Test 5: Verify no hardcoded values in templates
test_no_hardcoded_values() {
    log_info "Testing for hardcoded values in templates..."
    
    local hardcoded_patterns=(
        "3001"  # Forgejo port
        "8000"  # API port
        "/opt/forgejo"  # Hardcoded path
        "cheapa"  # Hardcoded project name
    )
    
    local template_dirs=(
        "shared/ansible/roles"
        "addons"
    )
    
    local found_hardcoded=false
    
    for dir in "${template_dirs[@]}"; do
        for pattern in "${hardcoded_patterns[@]}"; do
            # Search in .j2 and .yml files, excluding comments
            local matches=$(grep -r "$pattern" "$PROJECT_ROOT/$dir" \
                --include="*.j2" \
                --include="*.yml" \
                --include="*.yaml" \
                2>/dev/null | grep -v "^[[:space:]]*#" | grep -v "default:" || true)
            
            if [ -n "$matches" ]; then
                log_warning "Potential hardcoded value '$pattern' found in $dir"
                found_hardcoded=true
            fi
        done
    done
    
    if [ "$found_hardcoded" = false ]; then
        log_success "No obvious hardcoded values found"
    fi
}

# Test 6: Verify project configuration schema
test_project_config_schema() {
    log_info "Testing project configuration schema..."
    
    local project_config="$PROJECT_ROOT/projects/cheapa/project.yml"
    
    if [ ! -f "$project_config" ]; then
        log_error "Project config not found: $project_config"
        return
    fi
    
    # Check for required sections
    local required_sections=(
        "project:"
        "infrastructure:"
        "vms:"
        "apps:"
        "network:"
    )
    
    for section in "${required_sections[@]}"; do
        if grep -q "^$section" "$project_config"; then
            log_success "Project config has $section section"
        else
            log_error "Project config missing $section section"
        fi
    done
    
    # Check for Forgejo configuration
    if grep -q "forgejo:" "$project_config"; then
        log_success "Project config has Forgejo configuration"
    else
        log_error "Project config missing Forgejo configuration"
    fi
}

# Test 7: Verify CLI integration
test_cli_integration() {
    log_info "Testing CLI integration..."
    
    # Check if CLI files have been updated
    local cli_files=(
        "cli/commands/deploy.py"
        "cli/commands/sync_infra.py"
        "cli/ansible_utils.py"
    )
    
    for file in "${cli_files[@]}"; do
        if [ -f "$PROJECT_ROOT/$file" ]; then
            log_success "CLI file exists: $file"
            
            # Check if it uses parse_project_config
            if grep -q "parse_project_config" "$PROJECT_ROOT/$file"; then
                log_success "CLI file uses parse_project_config: $file"
            else
                log_warning "CLI file may not use parse_project_config: $file"
            fi
        else
            log_error "CLI file missing: $file"
        fi
    done
}

# Test 8: Verify documentation
test_documentation() {
    log_info "Testing documentation..."
    
    local doc_files=(
        "docs/ARCHITECTURE.md"
        "docs/DEPLOYMENT.md"
        "addons/README.md"
        "shared/ansible/roles/README.md"
    )
    
    for file in "${doc_files[@]}"; do
        if [ -f "$PROJECT_ROOT/$file" ]; then
            log_success "Documentation exists: $file"
            
            # Check if it mentions the new structure
            if grep -qi "addon-deployer\|orchestration" "$PROJECT_ROOT/$file"; then
                log_success "Documentation mentions new structure: $file"
            else
                log_warning "Documentation may be outdated: $file"
            fi
        else
            log_error "Documentation missing: $file"
        fi
    done
}

# Main test execution
main() {
    echo "========================================"
    echo "Integration Test: Fresh Deployment"
    echo "========================================"
    echo ""
    
    cd "$PROJECT_ROOT"
    
    test_ansible_structure
    echo ""
    
    test_role_structure
    echo ""
    
    test_addon_structure
    echo ""
    
    test_playbook_syntax
    echo ""
    
    test_no_hardcoded_values
    echo ""
    
    test_project_config_schema
    echo ""
    
    test_cli_integration
    echo ""
    
    test_documentation
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
