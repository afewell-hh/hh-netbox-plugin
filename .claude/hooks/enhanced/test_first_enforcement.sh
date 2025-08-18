#!/bin/bash
# Test-First Development Enforcement Hook
# Prevents implementation without validated tests
# Integrates with existing enhanced MDD validation

set -euo pipefail

input=$(cat)
tool_name=$(echo "$input" | jq -r '.tool_name // empty')
file_path=$(echo "$input" | jq -r '.tool_input.file_path // empty')
content=$(echo "$input" | jq -r '.tool_input.content // .tool_input.new_string // empty')
memory_key="test_first/$(basename "${file_path:-unknown}")/$(date +%s)"

# Enhanced logging for test-first enforcement
log_enforcement() {
    echo "🧪 Test-First Enforcement: $1" >&2
}

store_memory() {
    local key="$1"
    local value="$2"
    if command -v npx >/dev/null 2>&1; then
        npx ruv-swarm memory-usage --action store --key "$key" --value "$value" 2>/dev/null || true
    fi
}

retrieve_memory() {
    local pattern="$1"
    if command -v npx >/dev/null 2>&1; then
        npx ruv-swarm memory-usage --action retrieve --pattern "$pattern" 2>/dev/null || echo "[]"
    else
        echo "[]"
    fi
}

# Check if this is a Write or Edit operation
if [[ "$tool_name" != "Write" && "$tool_name" != "Edit" && "$tool_name" != "MultiEdit" ]]; then
    exit 0  # Only enforce on file modifications
fi

log_enforcement "Checking test-first compliance for: ${file_path:-unknown}"

# Skip validation for test files themselves and configuration files
if [[ "$file_path" == *"/tests/"* ]] || [[ "$file_path" == *"test_"* ]] || \
   [[ "$file_path" == *".md" ]] || [[ "$file_path" == *".json" ]] || \
   [[ "$file_path" == *".yaml" ]] || [[ "$file_path" == *".yml" ]] || \
   [[ "$file_path" == *".sh" ]] || [[ "$file_path" == *"CLAUDE.md" ]]; then
    log_enforcement "✅ Skipping test-first enforcement for configuration/test file"
    exit 0
fi

# Load test-first compliance patterns from memory
test_patterns=$(retrieve_memory "test_first/success/*")
violation_patterns=$(retrieve_memory "test_first/violations/*")

# Check if implementation code is being written
is_implementation=false
implementation_indicators=(
    "func " "class " "def " "function " "const " "let " "var "
    "interface " "type " "struct " "impl " "package " "import "
    "@app.route" "@router" "router.HandleFunc" "http.Handle"
    "models.Model" "serializers." "ViewSet" "APIView"
)

for indicator in "${implementation_indicators[@]}"; do
    if [[ "$content" == *"$indicator"* ]]; then
        is_implementation=true
        break
    fi
done

if ! $is_implementation; then
    log_enforcement "✅ No implementation code detected, test-first enforcement not required"
    exit 0
fi

log_enforcement "🚨 Implementation code detected, enforcing test-first requirements"

# Determine expected test file paths based on implementation file
test_file_paths=()
if [[ "$file_path" == *"/cnoc/"* ]]; then
    # Go project structure
    test_dir="${file_path%/*}"
    base_name=$(basename "$file_path" .go)
    test_file_paths+=("${test_dir}/${base_name}_test.go")
    test_file_paths+=("${test_dir}/test_${base_name}.go")
    # Also check for test directory
    test_file_paths+=("${test_dir}/../tests/test_${base_name}.go")
elif [[ "$file_path" == *"/netbox_hedgehog/"* ]]; then
    # Django project structure
    app_dir="${file_path%/*}"
    base_name=$(basename "$file_path" .py)
    test_file_paths+=("${app_dir}/tests/test_${base_name}.py")
    test_file_paths+=("${app_dir}/test_${base_name}.py")
    # Root tests directory
    test_file_paths+=("tests/test_${base_name}.py")
fi

# Check if corresponding tests exist
tests_exist=false
existing_test_files=()
for test_path in "${test_file_paths[@]}"; do
    if [[ -f "$test_path" ]]; then
        tests_exist=true
        existing_test_files+=("$test_path")
        log_enforcement "✅ Found test file: $test_path"
    fi
done

if ! $tests_exist; then
    # Check for any test files that might cover this functionality
    test_search_dirs=("tests/" "*/tests/" "*/test_*.py" "*/test_*.go")
    for pattern in "${test_search_dirs[@]}"; do
        if find . -path "*/${pattern}" -type f 2>/dev/null | head -1 | grep -q .; then
            log_enforcement "📂 Found test directory structure, checking for related tests..."
            # Look for test files that might reference the implementation being modified
            implementation_name=$(basename "$file_path" | cut -d. -f1)
            if find . -name "*test*" -type f -exec grep -l "$implementation_name" {} \; 2>/dev/null | head -1 | grep -q .; then
                tests_exist=true
                log_enforcement "✅ Found tests referencing implementation: $implementation_name"
                break
            fi
        fi
    done
fi

if ! $tests_exist; then
    # Check if this is a known false completion pattern
    known_violations=$(echo "$violation_patterns" | jq -r '.[] | select(.type == "implementation_without_tests") | .pattern' 2>/dev/null || echo "")
    
    store_memory "$memory_key/violation" "implementation_without_tests:$file_path"
    log_enforcement "❌ TEST-FIRST VIOLATION: Implementation code being written without corresponding tests"
    log_enforcement "📋 Required: Create tests first using Testing-Validation Engineer agent"
    log_enforcement "🎯 Expected test files: ${test_file_paths[*]}"
    log_enforcement "📖 Process: 1) Create tests 2) Validate red-green-refactor 3) Then implement"
    
    echo "🚨 TEST-FIRST ENFORCEMENT BLOCKED" >&2
    echo "Implementation detected without corresponding tests." >&2
    echo "Required process:" >&2
    echo "1. Use Testing-Validation Engineer agent to create tests first" >&2
    echo "2. Validate tests fail (red phase)" >&2
    echo "3. Then use Implementation Specialist agent to make tests pass" >&2
    echo "Expected test files: ${test_file_paths[*]}" >&2
    exit 3
fi

# Validate that existing tests follow proper patterns
log_enforcement "🔍 Validating existing test quality and completeness"

test_quality_issues=()
for test_file in "${existing_test_files[@]}"; do
    # Check for common inadequate test patterns
    if grep -q "assert.*200" "$test_file" 2>/dev/null && \
       ! grep -q "assert.*len\|assert.*Greater\|assert.*Contains" "$test_file" 2>/dev/null; then
        test_quality_issues+=("$test_file: Potential inadequate testing (HTTP status only)")
    fi
    
    # Check for proper test structure
    if ! grep -q "func Test\|def test_\|class.*Test" "$test_file" 2>/dev/null; then
        test_quality_issues+=("$test_file: Missing proper test function structure")
    fi
done

if [[ ${#test_quality_issues[@]} -gt 0 ]]; then
    log_enforcement "⚠️  Test quality issues detected:"
    for issue in "${test_quality_issues[@]}"; do
        log_enforcement "   - $issue"
    done
    log_enforcement "💡 Consider enhancing tests with quantitative validation before implementation"
fi

# Store successful test-first compliance in memory
store_memory "$memory_key/success" "test_first_compliance:$file_path:${existing_test_files[*]}"
store_memory "test_first/patterns/success" "$(date +%s):$file_path:${#existing_test_files[@]}_tests_found"

# Integration with existing MDD validation
log_enforcement "🔗 Integrating with enhanced MDD validation process"

log_enforcement "✅ Test-first enforcement passed - tests exist for implementation"
log_enforcement "📋 Tests found: ${existing_test_files[*]}"
log_enforcement "🎯 Proceeding with implementation under test-driven constraints"

exit 0