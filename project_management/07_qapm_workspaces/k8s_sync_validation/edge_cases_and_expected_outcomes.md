# GitOps Edge Cases and Expected Outcomes

## Critical Edge Cases for GitOps Synchronization

### 1. MALFORMED YAML FILES

#### Edge Case 1.1: YAML Syntax Errors
**Scenario**: File contains invalid YAML syntax
```yaml
# malformed-syntax.yaml
apiVersion: vpc.hedgehog.io/v1beta1
kind: VPC
metadata:
  name: test-vpc
    invalid_indentation: true  # Wrong indentation
spec:
  - invalid_list_syntax
```

**Expected Outcome**:
- **Processing**: YAML parsing fails with `yaml.YAMLError`
- **File Handling**: File remains in raw directory (NOT archived)
- **Error Logging**: Specific YAML error message logged
- **Ingestion Result**: 
  ```json
  {
    "success": false,
    "files_processed": 0,
    "errors": ["YAML parsing error: mapping values are not allowed here"],
    "warnings": []
  }
  ```
- **Rollback**: No managed files created, no partial state

#### Edge Case 1.2: Invalid UTF-8 Encoding
**Scenario**: File contains invalid character encoding
**Expected Outcome**:
- **Processing**: File encoding error caught
- **Error Message**: "File reading error: 'utf-8' codec can't decode byte"
- **File Status**: Remains in raw directory
- **Recovery**: Clear error message guides user to fix encoding

#### Edge Case 1.3: Extremely Large YAML File (>100MB)
**Scenario**: Single YAML file exceeds memory limits
**Expected Outcome**:
- **Processing**: Memory-efficient streaming parser used
- **Timeout**: Processing fails if exceeds 5-minute limit
- **Memory**: Memory usage monitored, fails gracefully on OOM
- **Error Message**: "File too large for processing" if memory exceeded

### 2. EMPTY FILES AND EDGE CONTENT

#### Edge Case 2.1: Completely Empty File
**Scenario**: Zero-byte YAML file in raw directory
**Expected Outcome**:
- **Processing**: File skipped with warning
- **Warning Message**: "No valid documents found in [filename]"
- **File Handling**: File archived (as processed, even if empty)
- **Archive Log**: Records empty file processing

#### Edge Case 2.2: File with Only Comments and Whitespace
**Scenario**: File contains only YAML comments and whitespace
```yaml
# This file contains only comments
# and whitespace

---
# Another comment

```
**Expected Outcome**:
- **Processing**: No documents parsed, treated as empty
- **Warning**: "No valid documents found in [filename]"
- **File Status**: Archived as processed

#### Edge Case 2.3: Mixed Valid and Null Documents
**Scenario**: Multi-document YAML with null/empty documents
```yaml
apiVersion: vpc.hedgehog.io/v1beta1
kind: VPC
metadata:
  name: valid-vpc
---
null
---
apiVersion: wiring.hedgehog.io/v1beta1
kind: Switch
metadata:
  name: valid-switch
---

```
**Expected Outcome**:
- **Processing**: 2 valid documents processed, null documents skipped
- **Managed Files**: 2 files created (VPC and Switch)
- **Ingestion Result**: Success with warnings about skipped documents
- **Archive**: Original file archived successfully

### 3. MIXED VALID/INVALID CRS

#### Edge Case 3.1: Valid CR Structure with Invalid Content
**Scenario**: Proper YAML structure but invalid CR content
```yaml
apiVersion: vpc.hedgehog.io/v1beta1
kind: VPC
metadata:
  name: ""  # Empty name - invalid
spec:
  invalid_field: true  # Unknown field
```
**Expected Outcome**:
- **K8s Validation**: Passes basic structure validation
- **Content Validation**: Fails on empty name
- **Processing**: Document skipped with warning
- **Warning**: "Skipping invalid document: missing required fields"
- **File Status**: Archived if ANY valid documents exist

#### Edge Case 3.2: Mixing Hedgehog and Non-Hedgehog CRs
**Scenario**: Multi-document with both supported and unsupported kinds
```yaml
apiVersion: vpc.hedgehog.io/v1beta1
kind: VPC
metadata:
  name: hedgehog-vpc
---
apiVersion: v1
kind: ConfigMap
metadata:
  name: non-hedgehog-config
```
**Expected Outcome**:
- **Hedgehog CR**: Processed normally, managed file created
- **Non-Hedgehog CR**: Skipped with warning about unsupported kind
- **Overall Result**: Success with warnings
- **Warning**: "Unsupported kind 'ConfigMap' in document 1"

#### Edge Case 3.3: Invalid API Versions
**Scenario**: CRs with outdated or incorrect API versions
```yaml
apiVersion: vpc.hedgehog.io/v1alpha1  # Deprecated version
kind: VPC
metadata:
  name: outdated-vpc
```
**Expected Outcome**:
- **Processing**: Document processed (kind validation passes)
- **Warning**: Schema warning about unexpected API version
- **Managed File**: Created with warning annotation
- **Schema Warning**: "Unexpected API version for VPC: vpc.hedgehog.io/v1alpha1"

### 4. NESTED DIRECTORY STRUCTURES

#### Edge Case 4.1: Deep Directory Nesting (10+ levels)
**Scenario**: YAML files in deeply nested raw subdirectories
```
raw/
└── projects/
    └── fabric-a/
        └── environments/
            └── production/
                └── regions/
                    └── us-west/
                        └── clusters/
                            └── cluster-1/
                                └── resources/
                                    └── vpcs.yaml
```
**Expected Outcome**:
- **File Discovery**: All files found via recursive glob
- **Processing**: Files processed regardless of depth
- **Performance**: No significant performance impact for reasonable depths
- **Path Limits**: Handles OS path length limits gracefully

#### Edge Case 4.2: Symbolic Links in Directory Structure
**Scenario**: Raw directory contains symbolic links to YAML files
**Expected Outcome**:
- **Link Handling**: Symbolic links followed if they point to valid files
- **Security**: Links outside repository are ignored for security
- **Error Handling**: Broken links logged as warnings, processing continues

#### Edge Case 4.3: Hidden Files and System Files
**Scenario**: Raw directory contains hidden files (.filename) and system files
```
raw/
├── .hidden-vpc.yaml
├── .DS_Store
├── Thumbs.db
└── valid-vpc.yaml
```
**Expected Outcome**:
- **Hidden YAML**: `.hidden-vpc.yaml` processed (YAML extension takes precedence)
- **System Files**: `.DS_Store`, `Thumbs.db` ignored silently
- **Processing**: Only YAML files processed regardless of hidden status

### 5. PERMISSION ISSUES

#### Edge Case 5.1: Read-Only Raw Directory
**Scenario**: Raw directory has read-only permissions
**Expected Outcome**:
- **File Reading**: Files can be read and processed
- **Archiving**: Fails when attempting to rename/move files
- **Error Handling**: Clear permission error message
- **Rollback**: No managed files created if archiving fails
- **Error**: "Permission denied: cannot archive file [filename]"

#### Edge Case 5.2: Write-Protected Managed Directory
**Scenario**: Managed directory becomes write-protected during processing
**Expected Outcome**:
- **Processing**: Fails when attempting to write managed files
- **Transaction**: Database transaction rolled back
- **File State**: Raw files remain unmodified
- **Error**: "Permission denied: cannot create managed file"
- **Recovery**: Clear instructions to fix permissions

#### Edge Case 5.3: Network File System Issues
**Scenario**: GitOps directories on network filesystem with intermittent issues
**Expected Outcome**:
- **Retry Logic**: Automatic retry for transient network errors
- **Timeout**: Fails after reasonable timeout (30 seconds)
- **Error Message**: Distinguishes network errors from other issues
- **State**: Maintains consistency despite network interruptions

### 6. CONCURRENCY AND RACE CONDITIONS

#### Edge Case 6.1: Simultaneous Ingestion Attempts
**Scenario**: Two processes attempt ingestion simultaneously
**Expected Outcome**:
- **Database Locking**: Transaction isolation prevents conflicts
- **Process Coordination**: One process succeeds, other gets lock error
- **Error Message**: "Another ingestion process is currently running"
- **File Safety**: No file corruption or duplicate processing
- **Retry**: Failed process can retry after completion

#### Edge Case 6.2: File Modification During Processing
**Scenario**: Raw file modified while being processed
**Expected Outcome**:
- **File Locking**: Process locks file during reading
- **Atomic Operations**: File operations are atomic where possible
- **Error Detection**: Checksum validation detects modifications
- **Recovery**: Process either uses original version or fails cleanly

#### Edge Case 6.3: Repository State Changes During Ingestion
**Scenario**: Git repository updated externally during ingestion
**Expected Outcome**:
- **Working Copy**: Processing uses local working copy, unaffected
- **Conflict Detection**: Git conflicts detected before pushing
- **Merge Strategy**: Automatic merge or user intervention required
- **Rollback**: Changes rolled back if push fails

### 7. RESOURCE EXHAUSTION

#### Edge Case 7.1: Disk Space Exhaustion
**Scenario**: System runs out of disk space during processing
**Expected Outcome**:
- **Early Detection**: Check available space before processing
- **Graceful Failure**: Stop processing when space low
- **Cleanup**: Remove temporary files to free space
- **Error Message**: "Insufficient disk space for processing"

#### Edge Case 7.2: Memory Exhaustion
**Scenario**: Processing very large files causes memory exhaustion
**Expected Outcome**:
- **Streaming**: Use streaming YAML parser for large files
- **Memory Monitoring**: Monitor memory usage during processing
- **Limits**: Fail gracefully when approaching memory limits
- **Error**: "File too large for available memory"

#### Edge Case 7.3: Too Many Open Files
**Scenario**: System file descriptor limit reached
**Expected Outcome**:
- **File Management**: Close files promptly after processing
- **Batch Processing**: Process files in smaller batches
- **Error Handling**: Clear error message about system limits
- **Recovery**: Automatic retry with smaller batch sizes

### 8. INTEGRATION EDGE CASES

#### Edge Case 8.1: Git Repository Becomes Unavailable
**Scenario**: Git repository server becomes unreachable during processing
**Expected Outcome**:
- **Network Timeout**: Fail with timeout after 30 seconds
- **Local Processing**: Continue with local operations where possible
- **Error Message**: "Cannot connect to Git repository"
- **Retry Strategy**: Exponential backoff for temporary failures

#### Edge Case 8.2: Authentication Token Expires
**Scenario**: Git authentication token expires during operation
**Expected Outcome**:
- **Auth Detection**: Detect authentication failure immediately
- **Token Refresh**: Attempt automatic token refresh if possible
- **Error Message**: "Authentication failed - token may be expired"
- **Recovery**: Clear instructions for token renewal

#### Edge Case 8.3: Branch Protection Rules
**Scenario**: Git repository has branch protection preventing direct pushes
**Expected Outcome**:
- **Branch Detection**: Detect protected branch restrictions
- **PR Creation**: Automatically create pull request for changes
- **Error Handling**: Clear message about protection rules
- **Alternative Flow**: Use configured alternative branch

## Expected Behavioral Patterns

### 1. Error Recovery Philosophy
- **Fail Fast**: Detect errors early in the process
- **Atomic Operations**: All-or-nothing approach to file processing
- **Clear Messages**: Specific, actionable error messages
- **State Preservation**: Never leave system in inconsistent state

### 2. Performance Expectations
- **File Processing**: < 1 second per file for standard files
- **Batch Operations**: < 100 files per minute
- **Memory Usage**: < 500MB for typical workloads
- **Network Timeouts**: 30 seconds for Git operations

### 3. Logging and Monitoring
- **Error Logging**: All errors logged with full context
- **Performance Metrics**: Processing times tracked
- **Success Tracking**: Successful operations logged for audit
- **Warning Aggregation**: Related warnings grouped together

### 4. User Experience
- **Progress Feedback**: Clear progress indication for long operations
- **Actionable Errors**: Error messages include resolution steps
- **Documentation**: Comprehensive error code documentation
- **Support Information**: Contact information for complex issues

This comprehensive edge case documentation ensures robust error handling and consistent behavior across all possible scenarios in the GitOps synchronization system.