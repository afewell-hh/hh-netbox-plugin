#!/bin/bash
# Memory-driven context loading optimization
# Confidence Level: 92%

set -euo pipefail

input=$(cat)
task_description=$(echo "$input" | jq -r '.task_description // .task // empty')
file_patterns=$(echo "$input" | jq -r '.file_patterns[]? // empty' 2>/dev/null || echo "")

# Enhanced logging
log_context() {
    echo "🧠 Context Injection Optimizer: $1" >&2
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

load_context_file() {
    local context_file="$1"
    local context_path=".claude/contexts/$context_file"
    
    if [[ -f "$context_path" ]]; then
        log_context "Loading context: $context_file"
        echo "# === INJECTED CONTEXT: $context_file ===" >&2
        head -20 "$context_path" >&2
        echo "# === END CONTEXT ===" >&2
        return 0
    else
        log_context "⚠️  Context file not found: $context_path"
        return 1
    fi
}

# Retrieve context effectiveness scores from memory
context_scores=$(retrieve_memory "context/effectiveness/*")
successful_patterns=$(retrieve_memory "context/success_patterns/*")

log_context "Starting memory-driven context optimization"

# Analyze task for context relevance
relevant_contexts=()

# Domain modeling context detection
if [[ "$task_description" =~ (domain|model|schema|aggregate|bounded.*context) ]] || \
   [[ "$file_patterns" =~ models/ ]]; then
    log_context "Domain modeling context detected"
    relevant_contexts+=("domain_modeling.md")
    store_memory "context/triggers/domain_modeling/$(date +%s)" "$task_description"
fi

# API design context detection
if [[ "$task_description" =~ (api|rest|graphql|openapi|contract|endpoint) ]] || \
   [[ "$file_patterns" =~ (api/|serializers|views) ]]; then
    log_context "API design context detected"
    relevant_contexts+=("api_design.md")
    store_memory "context/triggers/api_design/$(date +%s)" "$task_description"
fi

# Kubernetes/GitOps context detection
if [[ "$task_description" =~ (kubernetes|k8s|gitops|crd|operator|cluster) ]] || \
   [[ "$file_patterns" =~ (k8s/|kubernetes/|manifests/) ]]; then
    log_context "Kubernetes integration context detected"
    relevant_contexts+=("kubernetes_integration.md")
    store_memory "context/triggers/kubernetes/$(date +%s)" "$task_description"
fi

# Testing context detection
if [[ "$task_description" =~ (test|testing|tdd|validation|coverage) ]] || \
   [[ "$file_patterns" =~ (tests/|test_) ]]; then
    log_context "Testing patterns context detected"
    relevant_contexts+=("testing_patterns.md")
    store_memory "context/triggers/testing/$(date +%s)" "$task_description"
fi

# Memory-driven context scoring and optimization
for context in "${relevant_contexts[@]}"; do
    # Check context effectiveness score
    effectiveness=$(echo "$context_scores" | jq -r ".[] | select(.context == \"$context\") | .score" 2>/dev/null || echo "0.8")
    
    if (( $(echo "$effectiveness > 0.7" | bc -l 2>/dev/null || echo "1") )); then
        load_context_file "$context"
        store_memory "context/loaded/$(date +%s)" "$context:effective"
    else
        log_context "⚠️  Context $context below effectiveness threshold ($effectiveness)"
        store_memory "context/skipped/$(date +%s)" "$context:ineffective:$effectiveness"
    fi
done

# If no specific contexts detected, use adaptive loading based on success patterns
if [[ ${#relevant_contexts[@]} -eq 0 ]]; then
    log_context "No specific contexts detected, using adaptive loading"
    
    # Load most successful context patterns from memory
    top_contexts=$(echo "$successful_patterns" | jq -r '.[] | select(.success_rate > 0.8) | .context' 2>/dev/null | head -2)
    
    if [[ -n "$top_contexts" ]]; then
        while IFS= read -r context; do
            [[ -n "$context" ]] && load_context_file "$context"
        done <<< "$top_contexts"
        store_memory "context/adaptive_loading/$(date +%s)" "$top_contexts"
    else
        # Fallback to essential context
        load_context_file "domain_modeling.md"
        store_memory "context/fallback/$(date +%s)" "domain_modeling.md"
    fi
fi

# Store context injection session metadata
session_data=$(cat <<EOF
{
  "timestamp": "$(date -Iseconds)",
  "task_description": "$task_description",
  "contexts_loaded": $(printf '%s\n' "${relevant_contexts[@]}" | jq -R . | jq -s .),
  "file_patterns": "$file_patterns",
  "optimization_enabled": true
}
EOF
)

store_memory "context/sessions/$(date +%s)" "$session_data"

log_context "Context injection optimization completed"
log_context "Loaded ${#relevant_contexts[@]} relevant contexts with memory optimization"

exit 0