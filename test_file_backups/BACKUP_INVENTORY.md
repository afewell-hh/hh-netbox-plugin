# Test File Backup Inventory

**Backup Date**: August 2, 2025  
**Source**: https://github.com/afewell-hh/gitops-test-1/tree/main/gitops/hedgehog/fabric-1/raw  
**Purpose**: Preserve test files before FGD sync functionality testing

## Files Backed Up

### 1. backup_prepop.yaml (11,257 bytes)
**Multi-document YAML file containing 46 CRD objects**:
- 26 × Connection CRDs
- 10 × Server CRDs  
- 7 × Switch CRDs
- 3 × SwitchGroup CRDs

### 2. backup_test-vpc.yaml (199 bytes)
**Single VPC CRD**:
- 1 × VPC (name: test-vpc, subnet: 10.0.1.0/24, vlan: 1001)

### 3. backup_test-vpc-2.yaml (201 bytes)  
**Single VPC CRD**:
- 1 × VPC (name: test-vpc-2, subnet: 10.0.2.0/24, vlan: 1002)

## Expected Ingestion Results

If FGD sync works correctly, these files should be processed as follows:

**From prepop.yaml**:
- 26 files created in managed/connections/
- 10 files created in managed/servers/
- 7 files created in managed/switches/
- 3 files created in managed/switchgroups/

**From test-vpc.yaml**:
- 1 file created in managed/vpcs/ (test-vpc)

**From test-vpc-2.yaml**:
- 1 file created in managed/vpcs/ (test-vpc-2)

**Total Expected**: 48 individual YAML files in managed/ subdirectories

**Original Files**: Should be DELETED from raw/ directory after successful ingestion

## Test Validation Criteria

✅ SUCCESS: Live GitHub repository shows 48 files in managed/ subdirectories, raw/ directory empty  
❌ FAILURE: Files remain in raw/, managed/ subdirectories remain empty (current state)

## Backup Location
`/home/ubuntu/cc/hedgehog-netbox-plugin/test_file_backups/`

## Next Steps
1. Get current HNP fabric configuration
2. Delete existing fabric (clean slate)
3. Recreate fabric via GUI workflow
4. Trigger FGD sync
5. Validate results on live GitHub repository