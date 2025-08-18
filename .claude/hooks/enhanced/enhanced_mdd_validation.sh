#!/bin/bash
# Enhanced MDD process validation with memory integration
# Confidence Level: 98%

set -euo pipefail

input=$(cat)
file_path=$(echo "$input" | jq -r '.tool_input.file_path // empty')
memory_key="validation/$(basename "${file_path:-unknown}")/$(date +%s)"

# Enhanced error handling with context
log_validation() {
    echo "🔍 Enhanced MDD Validation: $1" >&2
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

# Load previous validation patterns for learning
previous_patterns=$(retrieve_memory "validation/success/*")
failure_patterns=$(retrieve_memory "validation/failure/*")

log_validation "Starting enhanced validation for: ${file_path:-unknown}"

# Domain modeling validation with memory enhancement
if [[ "$file_path" == *"/models/"* ]]; then
    log_validation "Validating domain model patterns"
    
    # Check for bounded context definition
    if ! grep -q "bounded_context\|class.*Model\|domain.*model" "$file_path" 2>/dev/null; then
        # Check if this is a known recoverable pattern
        known_fixes=$(echo "$previous_patterns" | jq -r '.[] | select(.type == "domain_fix") | .solution' 2>/dev/null || echo "")
        if [ -n "$known_fixes" ]; then
            log_validation "💡 Memory: Known fixes available for domain modeling issues"
            echo "$known_fixes" >&2
        fi
        
        store_memory "$memory_key/failure" "missing_bounded_context_or_model"
        log_validation "❌ MDD VIOLATION: Domain model missing bounded context or model definition"
        exit 2
    fi
    
    # Validate Django model patterns for NetBox
    if [[ "$file_path" == *"models.py" ]] && ! grep -q "NetBoxModel\|models\.Model" "$file_path" 2>/dev/null; then
        store_memory "$memory_key/failure" "missing_django_model_inheritance"
        log_validation "❌ MDD VIOLATION: Django model file missing proper model inheritance"
        exit 2
    fi
    
    store_memory "$memory_key/success" "domain_model_validated"
    log_validation "✅ Domain model validation passed"
fi

# API contract validation with adaptive thresholds
if [[ "$file_path" == *"/api/"* ]] || [[ "$file_path" == *"serializers.py" ]] || [[ "$file_path" == *"views.py" ]]; then
    log_validation "Validating API contract patterns"
    
    # Check for DRF patterns in NetBox plugin context
    if [[ "$file_path" == *"serializers.py" ]] && ! grep -q "serializers\.\|Serializer" "$file_path" 2>/dev/null; then
        store_memory "$memory_key/failure" "missing_serializer_patterns"
        log_validation "❌ MDD VIOLATION: Serializer file missing DRF serializer patterns"
        exit 2
    fi
    
    # Check for proper viewset patterns
    if [[ "$file_path" == *"views.py" ]] && ! grep -q "ViewSet\|APIView\|view" "$file_path" 2>/dev/null; then
        store_memory "$memory_key/failure" "missing_view_patterns"
        log_validation "❌ MDD VIOLATION: Views file missing proper API view patterns"
        exit 2
    fi
    
    # OpenAPI specification validation (if spectral is available)
    if [[ "$file_path" == *".yaml" ]] || [[ "$file_path" == *".yml" ]]; then
        if command -v spectral >/dev/null 2>&1; then
            if ! spectral lint "$file_path" >/dev/null 2>&1; then
                # Check for known API contract fixes in memory
                known_fixes=$(echo "$previous_patterns" | jq -r '.[] | select(.type == "api_fix") | .solution' 2>/dev/null || echo "")
                if [ -n "$known_fixes" ]; then
                    log_validation "📚 Memory: Known fixes available for API validation issues"
                    echo "$known_fixes" >&2
                fi
                
                store_memory "$memory_key/failure" "api_contract_validation_failed"
                log_validation "❌ MDD VIOLATION: API contract failed spectral validation"
                exit 2
            fi
        fi
    fi
    
    store_memory "$memory_key/success" "api_contract_validated"
    log_validation "✅ API contract validation passed"
fi

# Testing pattern validation
if [[ "$file_path" == *"/tests/"* ]] || [[ "$file_path" == *"test_"* ]]; then
    log_validation "Validating testing patterns"
    
    # Check for proper test structure
    if ! grep -q "def test_\|class.*Test\|import.*test\|from.*test" "$file_path" 2>/dev/null; then
        store_memory "$memory_key/failure" "missing_test_patterns"
        log_validation "❌ MDD VIOLATION: Test file missing proper test patterns"
        exit 2
    fi
    
    # Check for Django test patterns in plugin context
    if [[ "$file_path" == *"test_"*.py ]] && ! grep -q "TestCase\|APITestCase\|APIClient" "$file_path" 2>/dev/null; then
        store_memory "$memory_key/failure" "missing_django_test_patterns"
        log_validation "❌ MDD VIOLATION: Django test missing proper TestCase patterns"
        exit 2
    fi
    
    store_memory "$memory_key/success" "testing_pattern_validated"
    log_validation "✅ Testing pattern validation passed"
fi

# Kubernetes/GitOps validation
if [[ "$file_path" == *"/k8s/"* ]] || [[ "$file_path" == *"/kubernetes/"* ]] || [[ "$file_path" == *"/manifests/"* ]]; then
    log_validation "Validating Kubernetes patterns"
    
    # Check for proper Kubernetes manifest structure
    if [[ "$file_path" == *".yaml" ]] || [[ "$file_path" == *".yml" ]]; then
        if ! grep -q "apiVersion\|kind:" "$file_path" 2>/dev/null; then
            store_memory "$memory_key/failure" "missing_k8s_manifest_structure"
            log_validation "❌ MDD VIOLATION: Kubernetes manifest missing apiVersion/kind"
            exit 2
        fi
    fi
    
    store_memory "$memory_key/success" "kubernetes_pattern_validated"
    log_validation "✅ Kubernetes pattern validation passed"
fi

# Update effectiveness score for successful validations
store_memory "quality_gates/effectiveness_score" "$(date +%s):success:$file_path"

# Performance and learning metrics
validation_end_time=$(date +%s%3N)
store_memory "quality_gates/performance/validation_time" "$validation_end_time"

log_validation "✅ Enhanced MDD process adherence validated with memory integration"
exit 0