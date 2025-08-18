package shared

import (
	"errors"
	"fmt"
	"regexp"
	"strconv"
	"strings"
)

// Version represents a semantic version value object
// Following semantic versioning specification (semver.org)
type Version struct {
	major      int
	minor      int
	patch      int
	preRelease string
	build      string
}

// NewVersion creates a new version from a string representation
func NewVersion(version string) (Version, error) {
	if version == "" {
		return Version{}, errors.New("version cannot be empty")
	}
	
	// Remove 'v' prefix if present
	version = strings.TrimPrefix(version, "v")
	
	// Regular expression for semantic version
	semverRegex := regexp.MustCompile(`^(\d+)\.(\d+)\.(\d+)(?:-([0-9A-Za-z\-\.]+))?(?:\+([0-9A-Za-z\-\.]+))?$`)
	matches := semverRegex.FindStringSubmatch(version)
	
	if len(matches) == 0 {
		return Version{}, fmt.Errorf("invalid version format: %s", version)
	}
	
	major, err := strconv.Atoi(matches[1])
	if err != nil {
		return Version{}, fmt.Errorf("invalid major version: %s", matches[1])
	}
	
	minor, err := strconv.Atoi(matches[2])
	if err != nil {
		return Version{}, fmt.Errorf("invalid minor version: %s", matches[2])
	}
	
	patch, err := strconv.Atoi(matches[3])
	if err != nil {
		return Version{}, fmt.Errorf("invalid patch version: %s", matches[3])
	}
	
	// Validate version numbers are non-negative
	if major < 0 || minor < 0 || patch < 0 {
		return Version{}, errors.New("version numbers cannot be negative")
	}
	
	return Version{
		major:      major,
		minor:      minor,
		patch:      patch,
		preRelease: matches[4], // Can be empty
		build:      matches[5], // Can be empty
	}, nil
}

// NewVersionFromComponents creates a version from individual components
func NewVersionFromComponents(major, minor, patch int) (Version, error) {
	if major < 0 || minor < 0 || patch < 0 {
		return Version{}, errors.New("version numbers cannot be negative")
	}
	
	return Version{
		major: major,
		minor: minor,
		patch: patch,
	}, nil
}

// Major returns the major version number
func (v Version) Major() int {
	return v.major
}

// Minor returns the minor version number
func (v Version) Minor() int {
	return v.minor
}

// Patch returns the patch version number
func (v Version) Patch() int {
	return v.patch
}

// PreRelease returns the pre-release identifier
func (v Version) PreRelease() string {
	return v.preRelease
}

// Build returns the build metadata
func (v Version) Build() string {
	return v.build
}

// String returns the string representation of the version
func (v Version) String() string {
	version := fmt.Sprintf("%d.%d.%d", v.major, v.minor, v.patch)
	
	if v.preRelease != "" {
		version += "-" + v.preRelease
	}
	
	if v.build != "" {
		version += "+" + v.build
	}
	
	return version
}

// IsPreRelease returns true if this is a pre-release version
func (v Version) IsPreRelease() bool {
	return v.preRelease != ""
}

// IsStable returns true if this is a stable release (not pre-release)
func (v Version) IsStable() bool {
	return v.preRelease == ""
}

// Equals checks if two versions are equal
func (v Version) Equals(other Version) bool {
	return v.major == other.major &&
		v.minor == other.minor &&
		v.patch == other.patch &&
		v.preRelease == other.preRelease
	// Build metadata is ignored in equality comparison per semver spec
}

// Compare compares two versions
// Returns -1 if v < other, 0 if v == other, 1 if v > other
func (v Version) Compare(other Version) int {
	// Compare major.minor.patch
	if v.major != other.major {
		if v.major < other.major {
			return -1
		}
		return 1
	}
	
	if v.minor != other.minor {
		if v.minor < other.minor {
			return -1
		}
		return 1
	}
	
	if v.patch != other.patch {
		if v.patch < other.patch {
			return -1
		}
		return 1
	}
	
	// If both are stable releases, they're equal
	if v.preRelease == "" && other.preRelease == "" {
		return 0
	}
	
	// Stable release > pre-release
	if v.preRelease == "" && other.preRelease != "" {
		return 1
	}
	if v.preRelease != "" && other.preRelease == "" {
		return -1
	}
	
	// Compare pre-release versions lexically
	if v.preRelease < other.preRelease {
		return -1
	}
	if v.preRelease > other.preRelease {
		return 1
	}
	
	return 0
}

// IsGreaterThan returns true if v > other
func (v Version) IsGreaterThan(other Version) bool {
	return v.Compare(other) > 0
}

// IsLessThan returns true if v < other
func (v Version) IsLessThan(other Version) bool {
	return v.Compare(other) < 0
}

// IsGreaterThanOrEqual returns true if v >= other
func (v Version) IsGreaterThanOrEqual(other Version) bool {
	return v.Compare(other) >= 0
}

// IsLessThanOrEqual returns true if v <= other
func (v Version) IsLessThanOrEqual(other Version) bool {
	return v.Compare(other) <= 0
}

// IsCompatibleWith checks if this version is compatible with another version
// Uses semantic versioning compatibility rules:
// - Patch level changes: 1.0.4 -> 1.0.6 (compatible)
// - Minor level changes: 1.0.4 -> 1.1.0 (compatible for non-breaking changes)
// - Major level changes: 1.2.3 -> 2.0.0 (not compatible)
func (v Version) IsCompatibleWith(other Version) bool {
	// Same major version is compatible
	if v.major == other.major {
		return true
	}
	
	// Major version 0 is special - minor version changes can be breaking
	if v.major == 0 || other.major == 0 {
		return v.major == other.major && v.minor == other.minor
	}
	
	// Different major versions are not compatible
	return false
}

// NextMajor returns the next major version (e.g., 1.2.3 -> 2.0.0)
func (v Version) NextMajor() Version {
	return Version{
		major: v.major + 1,
		minor: 0,
		patch: 0,
	}
}

// NextMinor returns the next minor version (e.g., 1.2.3 -> 1.3.0)
func (v Version) NextMinor() Version {
	return Version{
		major: v.major,
		minor: v.minor + 1,
		patch: 0,
	}
}

// NextPatch returns the next patch version (e.g., 1.2.3 -> 1.2.4)
func (v Version) NextPatch() Version {
	return Version{
		major: v.major,
		minor: v.minor,
		patch: v.patch + 1,
	}
}

// WithPreRelease returns a version with the specified pre-release identifier
func (v Version) WithPreRelease(preRelease string) (Version, error) {
	if preRelease != "" {
		// Validate pre-release format
		validPreRelease := regexp.MustCompile(`^[0-9A-Za-z\-\.]+$`)
		if !validPreRelease.MatchString(preRelease) {
			return Version{}, fmt.Errorf("invalid pre-release format: %s", preRelease)
		}
	}
	
	return Version{
		major:      v.major,
		minor:      v.minor,
		patch:      v.patch,
		preRelease: preRelease,
		build:      v.build,
	}, nil
}

// WithBuild returns a version with the specified build metadata
func (v Version) WithBuild(build string) (Version, error) {
	if build != "" {
		// Validate build format
		validBuild := regexp.MustCompile(`^[0-9A-Za-z\-\.]+$`)
		if !validBuild.MatchString(build) {
			return Version{}, fmt.Errorf("invalid build format: %s", build)
		}
	}
	
	return Version{
		major:      v.major,
		minor:      v.minor,
		patch:      v.patch,
		preRelease: v.preRelease,
		build:      build,
	}, nil
}

// VersionConstraint represents a version constraint for dependency checking
type VersionConstraint struct {
	operator string  // ">=", "<=", ">", "<", "=", "~", "^"
	version  Version
}

// NewVersionConstraint creates a new version constraint
func NewVersionConstraint(constraint string) (VersionConstraint, error) {
	// Parse constraint format like ">=1.2.3", "~1.2", "^2.0.0"
	constraintRegex := regexp.MustCompile(`^([><=~^]*)\s*(.+)$`)
	matches := constraintRegex.FindStringSubmatch(strings.TrimSpace(constraint))
	
	if len(matches) != 3 {
		return VersionConstraint{}, fmt.Errorf("invalid constraint format: %s", constraint)
	}
	
	operator := matches[1]
	if operator == "" {
		operator = "=" // Default to exact match
	}
	
	version, err := NewVersion(matches[2])
	if err != nil {
		return VersionConstraint{}, fmt.Errorf("invalid version in constraint: %w", err)
	}
	
	return VersionConstraint{
		operator: operator,
		version:  version,
	}, nil
}

// Satisfies checks if a version satisfies this constraint
func (vc VersionConstraint) Satisfies(version Version) bool {
	switch vc.operator {
	case "=", "":
		return version.Equals(vc.version)
	case ">":
		return version.IsGreaterThan(vc.version)
	case ">=":
		return version.IsGreaterThanOrEqual(vc.version)
	case "<":
		return version.IsLessThan(vc.version)
	case "<=":
		return version.IsLessThanOrEqual(vc.version)
	case "~":
		// Tilde range: allows patch-level changes if a minor version is specified
		// ~1.2.3 := >=1.2.3 <1.3.0
		// ~1.2 := >=1.2.0 <1.3.0
		return version.major == vc.version.major &&
			version.minor == vc.version.minor &&
			version.IsGreaterThanOrEqual(vc.version)
	case "^":
		// Caret range: allows changes that do not modify major version
		// ^1.2.3 := >=1.2.3 <2.0.0
		// ^0.2.3 := >=0.2.3 <0.3.0 (special case for 0.x.x)
		if vc.version.major == 0 {
			return version.major == 0 &&
				version.minor == vc.version.minor &&
				version.IsGreaterThanOrEqual(vc.version)
		}
		return version.major == vc.version.major &&
			version.IsGreaterThanOrEqual(vc.version)
	default:
		return false
	}
}

// String returns the string representation of the constraint
func (vc VersionConstraint) String() string {
	if vc.operator == "=" {
		return vc.version.String()
	}
	return vc.operator + vc.version.String()
}