# FORGE GREEN PHASE SUCCESS CRITERIA: GitRepositoryRepository Implementation

**Date**: 2025-01-19  
**FORGE Movement**: 3 - Test-First Development  
**Phase**: GREEN (Implementation Required)  
**Component**: GitOps Repository Persistence Layer  
**Validation Agent**: Testing-Validation Engineer

## GREEN PHASE ENTRY REQUIREMENTS

### RED PHASE COMPLETION VALIDATION ✅
- **Test Suite Created**: 25 comprehensive test methods implemented
- **Tests Currently Failing**: All tests fail with proper error messages
- **Performance Thresholds**: Quantitative requirements established
- **Database Schema**: Requirements fully specified
- **Interface Coverage**: 100% of GitRepositoryRepository methods tested

## IMPLEMENTATION REQUIREMENTS FOR GREEN PHASE

### 1. Database Infrastructure Implementation

#### PostgreSQL Connection Factory
```go
// Required implementation in database package
type DatabaseConfig struct {
    Host     string
    Port     int
    Database string
    Username string
    Password string
    SSLMode  string
}

func NewPostgreSQLConnection(config DatabaseConfig) (*sql.DB, error) {
    // Implementation required for database connectivity
}
```

#### Database Schema Migration
```sql
-- Must be implemented: git_repositories table
CREATE TABLE git_repositories (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name                    VARCHAR(100) NOT NULL UNIQUE,
    url                     TEXT NOT NULL,
    description             TEXT,
    authentication_type     VARCHAR(50) NOT NULL,
    encrypted_credentials   TEXT,
    credentials_key_version INTEGER NOT NULL DEFAULT 1,
    connection_status       VARCHAR(20) NOT NULL DEFAULT 'unknown',
    last_validated         TIMESTAMP WITH TIME ZONE,
    validation_error       TEXT,
    default_branch         VARCHAR(100) NOT NULL DEFAULT 'main',
    last_commit_hash       VARCHAR(40),
    last_fetched          TIMESTAMP WITH TIME ZONE,
    created               TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    last_modified         TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    created_by            VARCHAR(100),
    modified_by           VARCHAR(100)
);

-- Required indexes for performance
CREATE INDEX idx_git_repositories_connection_status ON git_repositories(connection_status);
CREATE INDEX idx_git_repositories_last_validated ON git_repositories(last_validated);
CREATE INDEX idx_git_repositories_url ON git_repositories(url);
CREATE INDEX idx_git_repositories_created ON git_repositories(created);
```

### 2. GitRepositoryRepositoryImpl Structure

#### Core Implementation Structure
```go
// Required implementation
type GitRepositoryRepositoryImpl struct {
    db *sql.DB
    logger *slog.Logger
}

func NewGitRepositoryRepository(db *sql.DB) gitops.GitRepositoryRepository {
    return &GitRepositoryRepositoryImpl{
        db: db,
        logger: slog.Default().With("component", "git_repository_repository"),
    }
}
```

### 3. CRUD Operations Implementation

#### Create Method Requirements
```go
func (r *GitRepositoryRepositoryImpl) Create(repo *gitops.GitRepository) error {
    // PERFORMANCE REQUIREMENT: Must complete within 100ms
    // VALIDATION REQUIREMENT: Must handle constraint violations properly
    // TRANSACTION REQUIREMENT: Must support rollback on failure
    
    // Generate UUID if not set
    if repo.ID == "" {
        repo.ID = uuid.New().String()
    }
    
    // SQL implementation with proper error handling
    query := `INSERT INTO git_repositories (...) VALUES (...)`
    // Implementation required
}
```

#### GetByID Method Requirements
```go
func (r *GitRepositoryRepositoryImpl) GetByID(id string) (*gitops.GitRepository, error) {
    // PERFORMANCE REQUIREMENT: Must complete within 100ms
    // ERROR HANDLING: Must return proper "not found" error
    
    if id == "" {
        return nil, fmt.Errorf("repository ID cannot be empty")
    }
    
    query := `SELECT * FROM git_repositories WHERE id = $1`
    // Implementation required with proper struct mapping
}
```

#### List Method Requirements
```go
func (r *GitRepositoryRepositoryImpl) List(offset, limit int) ([]*gitops.GitRepository, int, error) {
    // PERFORMANCE REQUIREMENT: Must complete within 500ms
    // PAGINATION REQUIREMENT: Must support proper offset/limit
    
    // Count total records
    countQuery := `SELECT COUNT(*) FROM git_repositories`
    
    // Fetch paginated results
    listQuery := `SELECT * FROM git_repositories ORDER BY created DESC LIMIT $1 OFFSET $2`
    // Implementation required
}
```

#### Update Method Requirements
```go
func (r *GitRepositoryRepositoryImpl) Update(repo *gitops.GitRepository) error {
    // PERFORMANCE REQUIREMENT: Must complete within 100ms
    // CONCURRENCY REQUIREMENT: Must handle concurrent modifications
    // VALIDATION REQUIREMENT: Must verify record exists
    
    repo.LastModified = time.Now()
    
    query := `UPDATE git_repositories SET ... WHERE id = $1`
    // Implementation required with optimistic locking
}
```

#### Delete Method Requirements
```go
func (r *GitRepositoryRepositoryImpl) Delete(id string) error {
    // PERFORMANCE REQUIREMENT: Must complete within 100ms
    // VALIDATION REQUIREMENT: Must verify record exists before deletion
    
    if id == "" {
        return fmt.Errorf("repository ID cannot be empty")
    }
    
    query := `DELETE FROM git_repositories WHERE id = $1`
    // Implementation required with existence check
}
```

### 4. Extended Query Methods Implementation

#### GetByConnectionStatus Requirements
```go
func (r *GitRepositoryRepositoryImpl) GetByConnectionStatus(status gitops.ConnectionStatus) ([]*gitops.GitRepository, error) {
    query := `SELECT * FROM git_repositories WHERE connection_status = $1 ORDER BY last_validated DESC`
    // Implementation required
}
```

#### GetNeedingValidation Requirements
```go
func (r *GitRepositoryRepositoryImpl) GetNeedingValidation(since time.Time) ([]*gitops.GitRepository, error) {
    query := `SELECT * FROM git_repositories 
              WHERE last_validated IS NULL 
                 OR last_validated < $1 
                 OR connection_status IN ('unknown', 'failed', 'expired')
              ORDER BY last_validated ASC NULLS FIRST`
    // Implementation required
}
```

#### GetByURL Requirements
```go
func (r *GitRepositoryRepositoryImpl) GetByURL(url string) (*gitops.GitRepository, error) {
    query := `SELECT * FROM git_repositories WHERE url = $1`
    // Implementation required
}
```

#### UpdateConnectionStatuses Requirements
```go
func (r *GitRepositoryRepositoryImpl) UpdateConnectionStatuses(updates map[string]gitops.ConnectionStatus) error {
    // BULK OPERATION: Must efficiently update multiple records
    // TRANSACTION REQUIREMENT: Must be atomic (all or none)
    
    tx, err := r.db.Begin()
    if err != nil {
        return err
    }
    defer tx.Rollback()
    
    // Implementation required with transaction support
}
```

### 5. Transaction Support Implementation

#### Transaction Management Requirements
```go
// Required helper methods for transaction support
func (r *GitRepositoryRepositoryImpl) beginTransaction() (*sql.Tx, error) {
    return r.db.Begin()
}

func (r *GitRepositoryRepositoryImpl) executeInTransaction(fn func(*sql.Tx) error) error {
    tx, err := r.beginTransaction()
    if err != nil {
        return err
    }
    
    defer func() {
        if p := recover(); p != nil {
            tx.Rollback()
            panic(p)
        } else if err != nil {
            tx.Rollback()
        } else {
            err = tx.Commit()
        }
    }()
    
    err = fn(tx)
    return err
}
```

### 6. Performance Optimization Implementation

#### Connection Pooling Configuration
```go
func configureConnectionPool(db *sql.DB) {
    // Performance requirements for concurrent access
    db.SetMaxOpenConns(25)
    db.SetMaxIdleConns(5)
    db.SetConnMaxLifetime(5 * time.Minute)
    db.SetConnMaxIdleTime(1 * time.Minute)
}
```

#### Query Optimization Requirements
- All queries must use proper indexes
- Prepared statements for repeated queries
- Connection pooling for concurrent access
- Query timeouts for reliability

### 7. Error Handling Implementation

#### Standardized Error Types
```go
var (
    ErrRepositoryNotFound = errors.New("repository not found")
    ErrDuplicateRepository = errors.New("repository with this name already exists")
    ErrInvalidRepositoryData = errors.New("invalid repository data")
    ErrDatabaseConnection = errors.New("database connection error")
)

func (r *GitRepositoryRepositoryImpl) handleSQLError(err error) error {
    // Implementation required for proper error classification
    switch {
    case errors.Is(err, sql.ErrNoRows):
        return ErrRepositoryNotFound
    case strings.Contains(err.Error(), "duplicate"):
        return ErrDuplicateRepository
    default:
        return fmt.Errorf("database error: %w", err)
    }
}
```

## GREEN PHASE SUCCESS CRITERIA

### 1. All Tests Must Pass ✅
- **Test Count**: 25 test methods must pass
- **Test Categories**: CRUD, Extended Queries, Performance, Transactions, Data Integrity
- **Zero Failures**: No test failures or skips allowed

### 2. Performance Thresholds Must Be Met ✅
- **Create Operations**: < 100ms average
- **Read Operations**: < 100ms average
- **List Operations**: < 500ms average
- **Update Operations**: < 100ms average
- **Delete Operations**: < 100ms average

### 3. Database Integration Must Work ✅
- **Connection**: PostgreSQL connectivity established
- **Schema**: All tables and indexes created
- **Migrations**: Schema migration scripts functional
- **Transactions**: Rollback behavior working correctly

### 4. Error Handling Must Be Comprehensive ✅
- **Not Found Errors**: Proper error messages for missing records
- **Constraint Violations**: Clear errors for duplicate/invalid data
- **Connection Errors**: Graceful handling of database issues
- **Parameter Validation**: Proper validation of input parameters

### 5. Concurrent Access Must Be Safe ✅
- **Race Conditions**: No data corruption under concurrent access
- **Deadlock Prevention**: Proper transaction ordering
- **Connection Pooling**: Efficient resource management
- **Isolation Levels**: Proper transaction isolation

### 6. Data Integrity Must Be Preserved ✅
- **Encryption**: Encrypted credentials properly stored/retrieved
- **Timestamps**: Accurate audit trail maintenance
- **Foreign Keys**: Referential integrity maintained
- **Constraints**: All database constraints enforced

## IMPLEMENTATION FILE STRUCTURE

### Required Files for GREEN Phase
```
internal/infrastructure/persistence/postgresql/
├── git_repository_repository_impl.go           # Main implementation
├── git_repository_repository_test.go           # Test suite (existing)
├── database_connection.go                      # Connection factory
├── migrations/                                 # Database schema
│   ├── 001_create_git_repositories.up.sql
│   └── 001_create_git_repositories.down.sql
├── sql_queries.go                              # SQL query constants
└── error_handling.go                           # Error type definitions
```

### Configuration Requirements
```go
// Required environment configuration
type PostgreSQLConfig struct {
    Host     string `env:"POSTGRES_HOST" default:"localhost"`
    Port     int    `env:"POSTGRES_PORT" default:"5432"`
    Database string `env:"POSTGRES_DB" required:"true"`
    Username string `env:"POSTGRES_USER" required:"true"`
    Password string `env:"POSTGRES_PASSWORD" required:"true"`
    SSLMode  string `env:"POSTGRES_SSLMODE" default:"prefer"`
}
```

## VALIDATION EVIDENCE REQUIRED

### Test Execution Evidence
1. **Test Results**: All 25 tests passing with performance metrics
2. **Coverage Report**: 100% code coverage for implementation
3. **Performance Benchmarks**: Actual vs. required performance data
4. **Error Scenarios**: All error paths tested and working

### Database Evidence
1. **Schema Validation**: Table structure matches requirements
2. **Index Performance**: Query performance meets thresholds
3. **Transaction Logs**: Rollback behavior demonstrated
4. **Concurrent Access**: Multi-user testing results

### Integration Evidence
1. **Application Service Integration**: Works with existing services
2. **Domain Model Mapping**: Proper conversion between layers
3. **Configuration Loading**: Environment-based configuration
4. **Logging Integration**: Proper structured logging

## HANDOFF TO IMPLEMENTATION SPECIALIST

### Implementation Tasks
1. **Database Layer**: Connection factory and migration scripts
2. **Repository Implementation**: All CRUD and query methods
3. **Transaction Support**: Proper transaction management
4. **Performance Optimization**: Connection pooling and query optimization
5. **Error Handling**: Comprehensive error classification and messaging

### Validation Requirements
1. **Execute Test Suite**: All tests must pass without modification
2. **Performance Validation**: Meet all quantitative thresholds
3. **Integration Testing**: Work with existing application services
4. **Documentation**: Implementation details and deployment guide

### Success Metrics
- **Test Pass Rate**: 100% (25/25 tests passing)
- **Performance Compliance**: 100% of operations under thresholds
- **Error Coverage**: All error scenarios handled gracefully
- **Integration Success**: Seamless integration with existing codebase

---

**GREEN PHASE STATUS**: ⏳ PENDING IMPLEMENTATION  
**Implementation Effort**: Estimated 1-2 days for experienced developer  
**Critical Dependencies**: PostgreSQL database setup and schema migration  
**Success Criteria**: All tests pass with performance compliance  
**Validation Method**: Automated test execution with evidence collection