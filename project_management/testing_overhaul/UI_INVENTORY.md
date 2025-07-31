# UI Element Inventory - Hedgehog NetBox Plugin

**Purpose**: Comprehensive catalog of every UI element requiring functional testing
**Date Started**: July 26, 2025
**Status**: In Progress

## Overview Pages

### 1. Main Dashboard (`/plugins/hedgehog/`)
**Current Test Coverage**: Page loads, text content checks only
**Missing Functional Tests**: Button clicks, navigation, data refresh

#### Navigation Elements
- [ ] **Fabrics Button/Link** - Navigate to fabric list
- [ ] **VPCs Button/Link** - Navigate to VPC list  
- [ ] **Git Repositories Button/Link** - Navigate to git repo list
- [ ] **External Systems Button/Link** - Navigate to externals
- [ ] **Wiring API Button/Link** - Navigate to wiring components

#### Action Buttons
- [ ] **"Create New" Buttons** - Should open creation forms
- [ ] **"View All" Buttons** - Should navigate to list pages
- [ ] **Statistics/Count Displays** - Should show real data

#### Status Indicators  
- [ ] **CRD Count Displays** - Should reflect actual data
- [ ] **Sync Status Indicators** - Should show real sync state
- [ ] **Connection Status** - Should validate external connectivity

## Fabric Management

### 2. Fabric List Page (`/plugins/hedgehog/fabrics/`)
**Current Test Coverage**: Page loads, basic content
**Missing Functional Tests**: All button actions, data operations

#### Table Elements
- [ ] **Fabric List Table** - Should display real fabric data
- [ ] **Edit Links** - Should open fabric edit forms
- [ ] **Delete Buttons** - Should remove fabrics with confirmation
- [ ] **Sync Status Column** - Should show actual sync state

#### Action Buttons
- [ ] **"Add Fabric" Button** - Should open creation form
- [ ] **Bulk Operations** - Should perform multi-select actions
- [ ] **Search/Filter** - Should filter displayed results

### 3. Fabric Detail Page (`/plugins/hedgehog/fabrics/{id}/`)
**Current Test Coverage**: Page loads, text presence
**Missing Functional Tests**: Critical - Git sync, connections, CRD operations

#### Critical Action Buttons
- [ ] **"Sync from Git" Button** - CRITICAL: Should trigger actual Git sync
- [ ] **"Test Connection" Button** - Should validate connectivity  
- [ ] **"Edit Fabric" Button** - Should open edit form
- [ ] **"Delete Fabric" Button** - Should remove with confirmation

#### Git Integration Section
- [ ] **Git Repository Link** - Should open repository in new tab
- [ ] **Last Sync Timestamp** - Should show real sync data
- [ ] **Sync Status Indicator** - Should reflect actual state
- [ ] **Branch/Commit Info** - Should show current Git state

#### CRD Management Section
- [ ] **CRD Count Displays** - Should show real counts
- [ ] **"View CRDs" Links** - Should navigate to filtered CRD lists
- [ ] **"Create CRD" Buttons** - Should open CRD creation forms

## Git Repository Management

### 4. Git Repository List (`/plugins/hedgehog/git-repos/`)
**Current Test Coverage**: Page structure only
**Missing Functional Tests**: All Git operations

#### Repository List
- [ ] **Repository Table** - Should display configured repos
- [ ] **Status Indicators** - Should show connection/auth status
- [ ] **Last Sync Info** - Should display real sync timestamps
- [ ] **Action Buttons** - Edit, delete, sync operations

#### Critical Actions
- [ ] **"Add Repository" Button** - Should open repo configuration form
- [ ] **"Test Connection" Buttons** - Should validate Git access
- [ ] **"Sync Now" Buttons** - Should trigger immediate sync
- [ ] **"View Files" Links** - Should show repository content

### 5. Git Repository Detail (`/plugins/hedgehog/git-repos/{id}/`)
**Current Test Coverage**: None identified
**Missing Functional Tests**: All Git integration functionality

#### Repository Information
- [ ] **Connection Status** - Should show real auth/connectivity
- [ ] **Branch Information** - Should display current branch
- [ ] **File Tree** - Should show repository structure
- [ ] **Commit History** - Should display recent commits

#### Operations
- [ ] **"Sync from Remote" Button** - Should pull latest changes
- [ ] **"Push to Remote" Button** - Should push local changes
- [ ] **"Test Authentication" Button** - Should validate credentials
- [ ] **File Edit/View** - Should allow YAML editing

## CRD Management Pages

### 6. VPC List Page (`/plugins/hedgehog/vpcs/`)
**Current Test Coverage**: Basic page structure
**Missing Functional Tests**: All CRUD operations

#### VPC Table
- [ ] **VPC List Display** - Should show real VPC data from cluster
- [ ] **Status Column** - Should reflect Kubernetes status
- [ ] **Actions Column** - Edit, delete, deploy operations

#### VPC Operations
- [ ] **"Create VPC" Button** - Should open VPC creation form
- [ ] **"Import from Cluster" Button** - Should sync from K8s
- [ ] **"Deploy All" Button** - Should deploy to cluster
- [ ] **Search/Filter** - Should filter VPC list

### 7. VPC Detail Page (`/plugins/hedgehog/vpcs/{id}/`)
**Current Test Coverage**: Form loading only
**Missing Functional Tests**: All CRD lifecycle operations

#### VPC Information
- [ ] **VPC Specification Display** - Should show YAML/JSON
- [ ] **Kubernetes Status** - Should reflect real cluster state
- [ ] **Associated Resources** - Should list related CRDs

#### Critical CRD Operations
- [ ] **"Edit Specification" Button** - Should open YAML editor
- [ ] **"Deploy to Cluster" Button** - Should apply to Kubernetes
- [ ] **"Sync from Cluster" Button** - Should fetch current state
- [ ] **"Delete from Cluster" Button** - Should remove from K8s

#### Form Elements (When Editing)
- [ ] **YAML Editor** - Should validate syntax and save
- [ ] **Field Validation** - Should enforce CRD schema
- [ ] **"Save" Button** - Should persist to database and optionally deploy
- [ ] **"Cancel" Button** - Should discard changes

### 8. External Systems Pages (`/plugins/hedgehog/externals/`)
**Current Test Coverage**: Form loading
**Missing Functional Tests**: External system integration

#### External List/Detail Operations
- [ ] **External System CRUD** - Create, read, update, delete
- [ ] **Attachment Management** - External attachment operations
- [ ] **Peering Configuration** - External peering setup

### 9. Wiring API Pages (Connections, Switches, Servers)
**Current Test Coverage**: Form loading only
**Missing Functional Tests**: Physical topology management

#### Wiring Component Operations
- [ ] **Connection Management** - Physical connection CRUD
- [ ] **Switch Configuration** - Switch profile and config
- [ ] **Server Management** - Server profile and wiring

## Form Testing Requirements

### Universal Form Elements (All CRD Types)
- [ ] **Required Field Validation** - Should prevent submission
- [ ] **Field Format Validation** - Should validate data types
- [ ] **Cross-Field Validation** - Should validate relationships
- [ ] **Error Message Display** - Should show helpful errors
- [ ] **Success Confirmation** - Should confirm save operations

### Advanced Form Features
- [ ] **YAML Syntax Validation** - Should catch YAML errors
- [ ] **Real-time Validation** - Should validate as user types
- [ ] **Auto-save/Draft** - Should preserve work in progress
- [ ] **Conflict Resolution** - Should handle concurrent edits

## Integration Testing Requirements

### NetBox ↔ Git Integration
- [ ] **Bidirectional Sync** - Changes flow both directions
- [ ] **Conflict Resolution** - Handle sync conflicts
- [ ] **Authentication** - Git credentials work correctly
- [ ] **Branch Management** - Proper branch handling

### NetBox ↔ Kubernetes Integration  
- [ ] **CRD Deployment** - NetBox changes deploy to cluster
- [ ] **Status Synchronization** - Cluster status reflects in NetBox
- [ ] **Resource Validation** - K8s validates CRD specs
- [ ] **Error Handling** - Failed deployments handled gracefully

### End-to-End Workflows
- [ ] **Fabric Creation → Git Setup → CRD Sync** - Complete onboarding
- [ ] **CRD Edit → Deploy → Status Update** - Complete lifecycle
- [ ] **Git Change → NetBox Sync → Cluster Deploy** - GitOps flow

## Performance Testing Requirements

### Page Load Performance
- [ ] **Dashboard Load Time** - Should load under 2 seconds
- [ ] **Large Dataset Display** - Should handle 100+ CRDs
- [ ] **Search/Filter Performance** - Should filter quickly

### Operation Performance
- [ ] **Git Sync Operations** - Should complete within 30 seconds
- [ ] **Cluster Deployment** - Should deploy within reasonable time
- [ ] **Bulk Operations** - Should handle multiple CRDs efficiently

## Error Scenario Testing

### Network Failures
- [ ] **Git Repository Unreachable** - Should handle gracefully
- [ ] **Kubernetes Cluster Down** - Should show appropriate errors
- [ ] **NetBox API Errors** - Should handle API failures

### Authentication Failures
- [ ] **Expired Git Tokens** - Should prompt for new credentials
- [ ] **Invalid K8s Config** - Should show clear error messages
- [ ] **NetBox Permission Denied** - Should handle authorization errors

### Data Corruption/Conflicts
- [ ] **Invalid YAML** - Should prevent deployment
- [ ] **CRD Schema Violations** - Should validate before save
- [ ] **Concurrent Modifications** - Should detect and resolve conflicts

## Testing Priority Matrix

### 🔴 CRITICAL (Must work for basic functionality)
1. Fabric "Sync from Git" button
2. CRD creation and editing forms
3. Deploy to cluster operations
4. Git repository authentication

### 🟡 HIGH (Important for user experience)  
1. All navigation buttons and links
2. Search and filtering functionality
3. Status displays and indicators
4. Form validation and error messages

### 🟢 MEDIUM (Enhancement features)
1. Performance optimizations
2. Advanced error handling
3. Bulk operations
4. Real-time updates

**Next Steps**: Begin systematic testing starting with CRITICAL items

**Last Updated**: July 26, 2025