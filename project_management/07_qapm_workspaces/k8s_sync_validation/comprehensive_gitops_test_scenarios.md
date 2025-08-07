# Comprehensive GitOps Sync Test Scenarios

## Test Scenario Matrix

### 1. PRE-EXISTING YAML FILE INGESTION DURING FABRIC INIT

#### Test Scenario 1.1: Single Valid YAML File in Raw Directory
**Objective**: Verify fabric initialization with pre-existing valid YAML files
**Setup**:
- Create fabric with GitOps directory containing `raw/test-vpc.yaml`
- YAML contains single valid VPC CR
**Test Steps**:
1. Initialize fabric GitOps structure
2. Trigger ingestion service
3. Verify file processing
**Expected Outcomes**:
- File moved from `raw/` to `.archived` extension
- New file created in `managed/vpcs/test-vpc.yaml`
- HNP annotations added to managed file
- Archive log updated with ingestion operation

#### Test Scenario 1.2: Multiple Valid YAML Files in Raw Directory
**Objective**: Verify batch processing of multiple pre-existing files
**Setup**:
- Raw directory contains: `switches.yaml`, `connections.yaml`, `servers.yaml`
- Each file contains single valid CR
**Test Steps**:
1. Initialize fabric
2. Trigger batch ingestion
3. Verify all files processed in order (oldest first)
**Expected Outcomes**:
- All 3 files archived with `.archived` extension
- 3 managed files created in appropriate subdirectories
- Processing order follows modification time (oldest first)
- Single ingestion operation in archive log

#### Test Scenario 1.3: Empty Raw Directory During Init
**Objective**: Verify graceful handling of empty raw directory
**Setup**:
- Raw directory exists but contains no YAML files
**Test Steps**:
1. Initialize fabric
2. Trigger ingestion service
**Expected Outcomes**:
- No errors thrown
- Success response with "No files to process" message
- Directory structure remains intact
- No archive log entries created

### 2. SINGLE CR YAML FILE PROCESSING

#### Test Scenario 2.1: Valid Single-Document YAML Processing
**Objective**: Verify processing of standard single-CR YAML files
**Setup**:
- File: `raw/single-vpc.yaml` with valid VPC CR
**Test Steps**:
1. Process single file via ingestion service
2. Verify normalization process
**Expected Outcomes**:
- Original file archived as `single-vpc.yaml.archived`
- Managed file created: `managed/vpcs/test-vpc.yaml`
- HNP tracking annotations added:
  - `hnp.githedgehog.com/managed-by: hedgehog-netbox-plugin`
  - `hnp.githedgehog.com/fabric: [fabric-name]`
  - `hnp.githedgehog.com/original-file: single-vpc.yaml`
  - `hnp.githedgehog.com/original-document-index: "0"`
  - `hnp.githedgehog.com/ingested-at: [timestamp]`

#### Test Scenario 2.2: Single YAML with Namespace Specification
**Objective**: Verify namespace handling in managed file naming
**Setup**:
- YAML with `metadata.namespace: production`
**Expected Outcomes**:
- Managed file named: `production-vpc-name.yaml`
- Namespace preserved in managed file

#### Test Scenario 2.3: Single YAML with Name Conflicts
**Objective**: Verify handling of naming conflicts in managed directory
**Setup**:
- Process file with same name as existing managed file
**Expected Outcomes**:
- New file created with conflict resolution: `vpc-name-1.yaml`
- Counter increments for additional conflicts

### 3. MULTI-CR YAML FILE SPLITTING

#### Test Scenario 3.1: Valid Multi-Document YAML Splitting
**Objective**: Verify splitting of multi-document YAML files
**Setup**:
- File: `raw/multi-resources.yaml` containing:
  ```yaml
  apiVersion: vpc.hedgehog.io/v1beta1
  kind: VPC
  metadata:
    name: vpc-1
  ---
  apiVersion: wiring.hedgehog.io/v1beta1
  kind: Switch
  metadata:
    name: switch-1
  ---
  apiVersion: wiring.hedgehog.io/v1beta1
  kind: Connection
  metadata:
    name: connection-1
  ```
**Test Steps**:
1. Process multi-document file
2. Verify document splitting
**Expected Outcomes**:
- Original file archived: `multi-resources.yaml.archived`
- 3 managed files created:
  - `managed/vpcs/vpc-1.yaml`
  - `managed/switches/switch-1.yaml`
  - `managed/connections/connection-1.yaml`
- Each managed file contains single document
- Document index annotations: "0", "1", "2"

#### Test Scenario 3.2: Multi-Document with Mixed Valid/Invalid CRs
**Objective**: Verify handling of mixed validity in multi-document files
**Setup**:
- Multi-document YAML with 2 valid CRs and 1 invalid CR (missing required fields)
**Expected Outcomes**:
- 2 valid CRs processed and managed files created
- 1 invalid CR skipped with warning in ingestion result
- Original file still archived (partial success)
- Warnings included in ingestion result

#### Test Scenario 3.3: Multi-Document with Unsupported Kinds
**Objective**: Verify handling of unsupported Kubernetes resources
**Setup**:
- Multi-document with VPC (supported) and ConfigMap (unsupported)
**Expected Outcomes**:
- VPC CR processed normally
- ConfigMap skipped with warning
- Ingestion completes successfully with warnings

### 4. RAW DIRECTORY FILE INGESTION

#### Test Scenario 4.1: Recursive Directory Processing
**Objective**: Verify recursive processing of files in raw directory structure
**Setup**:
- Raw directory structure:
  ```
  raw/
  ├── pending/vpc-configs.yaml
  ├── switches/leaf-switches.yaml
  └── connections.yaml
  ```
**Expected Outcomes**:
- All YAML files processed regardless of subdirectory
- Files sorted by modification time before processing
- Directory structure flattened in managed output

#### Test Scenario 4.2: Mixed File Types in Raw Directory
**Objective**: Verify filtering of non-YAML files during ingestion
**Setup**:
- Raw directory contains: `.yaml`, `.yml`, `.json`, `.txt`, `.md` files
**Expected Outcomes**:
- Only `.yaml` and `.yml` files processed
- Other file types ignored without errors
- No warnings for standard non-Kubernetes files (mkdocs.yml, docker-compose.yml)

#### Test Scenario 4.3: Large File Processing
**Objective**: Verify handling of large YAML files
**Setup**:
- Large multi-document YAML (100+ documents, 10MB+ file size)
**Expected Outcomes**:
- All documents processed without memory issues
- Transaction rollback on any processing failures
- Performance within acceptable limits (< 30 seconds)

### 5. INVALID FILE MOVEMENT TO UNMANAGED

#### Test Scenario 5.1: Malformed YAML Syntax Errors
**Objective**: Verify handling of YAML with syntax errors
**Setup**:
- File with YAML syntax errors (invalid indentation, missing colons)
**Test Steps**:
1. Attempt to process malformed file
2. Verify error handling
**Expected Outcomes**:
- YAML parsing error caught and logged
- File NOT archived (remains in raw)
- Error details in ingestion result
- No managed files created

#### Test Scenario 5.2: Missing Required Kubernetes Fields
**Objective**: Verify handling of incomplete Kubernetes resources
**Setup**:
- YAML files missing: `apiVersion`, `kind`, `metadata.name`
**Expected Outcomes**:
- Invalid documents skipped during processing
- Warning messages in ingestion result
- Original file archived if ANY valid documents exist
- No managed files created for invalid documents

#### Test Scenario 5.3: Invalid CRD Schema Validation
**Objective**: Verify handling of CRDs with invalid schemas
**Setup**:
- Valid YAML structure but invalid CRD schema (wrong apiVersion, invalid spec)
**Expected Outcomes**:
- Document processed (basic validation passes)
- Schema warnings logged
- Managed file created with potential issues flagged

### 6. DIRECTORY STRUCTURE VALIDATION/REPAIR

#### Test Scenario 6.1: Missing Required Directories
**Objective**: Verify automatic directory creation during ingestion
**Setup**:
- GitOps structure missing `managed/vpcs/` directory
- Process VPC YAML file
**Expected Outcomes**:
- Missing directory created automatically: `managed/vpcs/`
- File processing continues normally
- Directory creation logged

#### Test Scenario 6.2: Corrupted Directory Structure
**Objective**: Verify repair of corrupted GitOps structure
**Setup**:
- Delete essential directories: `managed/`, `.hnp/`
- Attempt ingestion
**Expected Outcomes**:
- Structure validation fails
- Error message indicates missing required directories
- Ingestion does not proceed
- Recommendation to reinitialize structure

#### Test Scenario 6.3: Permission Issues on Directories
**Objective**: Verify handling of filesystem permission errors
**Setup**:
- Set read-only permissions on `managed/` directory
**Expected Outcomes**:
- Permission error caught during file writing
- Clear error message about access issues
- Rollback of any partial changes
- Original files remain in raw directory

### 7. EDGE CASES AND ERROR CONDITIONS

#### Test Scenario 7.1: Network Interruption During Processing
**Objective**: Verify resilience to network issues during Git operations
**Setup**:
- Simulate network interruption during commit/push
**Expected Outcomes**:
- Transaction rollback prevents partial state
- Clear error message about network issues
- Files remain in raw directory for retry
- No corrupted managed files

#### Test Scenario 7.2: Concurrent Processing Attempts
**Objective**: Verify handling of simultaneous ingestion attempts
**Setup**:
- Trigger two ingestion processes simultaneously
**Expected Outcomes**:
- Database transaction isolation prevents conflicts
- One process succeeds, other gets appropriate error
- No file corruption or duplicate processing

#### Test Scenario 7.3: Extremely Large Multi-Document File
**Objective**: Verify memory handling with very large files
**Setup**:
- Multi-document YAML with 1000+ documents
**Expected Outcomes**:
- Memory usage remains stable
- Processing completes within timeout (5 minutes)
- All documents processed correctly
- No memory leaks or crashes

#### Test Scenario 7.4: Special Characters in File Names
**Objective**: Verify handling of files with special characters
**Setup**:
- Files named: `vpc-üñîçödé.yaml`, `switch (production).yaml`
**Expected Outcomes**:
- File names sanitized for filesystem compatibility
- Processing completes successfully
- Clear mapping in archive log

#### Test Scenario 7.5: Empty YAML Documents
**Objective**: Verify handling of empty or null documents
**Setup**:
- Multi-document YAML with empty documents between valid ones
**Expected Outcomes**:
- Empty documents skipped silently
- Valid documents processed normally
- No errors thrown for empty documents

### 8. PERFORMANCE AND SCALABILITY

#### Test Scenario 8.1: Batch Processing Performance
**Objective**: Verify performance with large numbers of files
**Setup**:
- 100 YAML files in raw directory (mix of single and multi-document)
**Expected Outcomes**:
- All files processed within 2 minutes
- Memory usage remains stable
- Processing order maintained (oldest first)

#### Test Scenario 8.2: Deep Directory Structure Processing
**Objective**: Verify handling of deeply nested directory structures
**Setup**:
- Raw directory with 5+ levels of subdirectories containing YAML files
**Expected Outcomes**:
- All files found and processed regardless of depth
- No path length issues
- Performance remains acceptable

## Test Data Requirements

### Sample YAML Files Needed:

1. **Valid Single-Document Files**:
   - `valid-vpc.yaml` - Standard VPC CR
   - `valid-switch.yaml` - Standard Switch CR
   - `valid-connection.yaml` - Standard Connection CR

2. **Valid Multi-Document Files**:
   - `multi-vpc-switch.yaml` - VPC + Switch
   - `large-multi-doc.yaml` - 50+ documents

3. **Invalid Files**:
   - `syntax-error.yaml` - YAML syntax errors
   - `missing-fields.yaml` - Missing required K8s fields
   - `invalid-kind.yaml` - Unsupported kind

4. **Edge Case Files**:
   - `empty-docs.yaml` - Contains empty documents
   - `unicode-names.yaml` - Special characters
   - `large-single-doc.yaml` - Very large single document

### Directory Structures for Testing:

1. **Standard Structure**: Complete GitOps directory with all subdirectories
2. **Minimal Structure**: Only raw/ directory exists
3. **Corrupted Structure**: Missing essential directories
4. **Deep Structure**: Multiple levels of subdirectories

## Integration with CI/CD

Each test scenario should be:
1. Automated with clear pass/fail criteria
2. Include performance benchmarks
3. Generate detailed logs for debugging
4. Clean up test data after execution
5. Verify no side effects on other fabrics

This comprehensive test suite ensures robust GitOps synchronization functionality across all supported use cases and edge conditions.