#!/usr/bin/env python3
"""
Environment Loading Validation Script

This script validates that all modified .claude files properly include
environment variable loading instructions and that agents understand
they must load the .env file explicitly.
"""

import os
import re
from pathlib import Path
from typing import Dict, List, Tuple, Set


class EnvironmentLoadingValidator:
    """Validates environment loading implementation in .claude files."""
    
    def __init__(self, base_path: str = "docs/claude-optimization-research/modified-files-for-review"):
        self.base_path = Path(base_path)
        self.required_patterns = {
            'env_loading_mandatory': [
                r'MANDATORY.*environment',
                r'CRITICAL.*\.env',
                r'Load.*environment.*first',
                r'source \.env'
            ],
            'python_env_loading': [
                r'load_env_file',
                r'Path\(\'\.env\'\)\.exists\(\)',
                r'os\.environ\[.*\] = .*'
            ],
            'bash_env_loading': [
                r'source \.env',
                r'echo.*Environment loaded'
            ],
            'env_verification': [
                r'NETBOX_URL=\$NETBOX_URL',
                r'K8S_TEST_CLUSTER_NAME=\$K8S_TEST_CLUSTER_NAME',
                r'GITOPS_REPO_URL=\$GITOPS_REPO_URL'
            ]
        }
        
        self.critical_env_vars = {
            'NETBOX_URL',
            'K8S_TEST_CLUSTER_NAME', 
            'GITOPS_REPO_URL',
            'PREFER_REAL_INFRASTRUCTURE',
            'TEST_NETBOX_TOKEN',
            'K8S_TEST_CONFIG_PATH',
            'GITOPS_AUTH_TOKEN'
        }
    
    def validate_file(self, file_path: Path) -> Dict[str, any]:
        """Validate a single file for environment loading implementation."""
        if not file_path.exists():
            return {
                'file': str(file_path),
                'exists': False,
                'patterns_found': {},
                'env_vars_found': set(),
                'score': 0,
                'issues': ['File does not exist']
            }
        
        content = file_path.read_text()
        patterns_found = {}
        env_vars_found = set()
        issues = []
        
        # Check for required patterns
        for pattern_type, patterns in self.required_patterns.items():
            patterns_found[pattern_type] = []
            for pattern in patterns:
                matches = re.findall(pattern, content, re.IGNORECASE)
                if matches:
                    patterns_found[pattern_type].extend(matches)
        
        # Check for environment variable usage
        for env_var in self.critical_env_vars:
            if f'${env_var}' in content or f'$"{env_var}"' in content or f"'{env_var}'" in content:
                env_vars_found.add(env_var)
        
        # Calculate score
        score = 0
        total_patterns = len(self.required_patterns)
        patterns_with_matches = sum(1 for patterns in patterns_found.values() if patterns)
        score += (patterns_with_matches / total_patterns) * 70  # 70% for patterns
        
        env_usage_score = (len(env_vars_found) / len(self.critical_env_vars)) * 30  # 30% for env usage
        score += env_usage_score
        
        # Check for specific issues
        if not patterns_found['env_loading_mandatory']:
            issues.append('Missing mandatory environment loading instructions')
        
        if not patterns_found['python_env_loading'] and not patterns_found['bash_env_loading']:
            issues.append('Missing concrete environment loading implementation')
        
        if len(env_vars_found) < 3:
            issues.append(f'Limited environment variable usage ({len(env_vars_found)}/{len(self.critical_env_vars)})')
        
        return {
            'file': str(file_path.name),
            'exists': True,
            'patterns_found': patterns_found,
            'env_vars_found': env_vars_found,
            'score': round(score, 1),
            'issues': issues
        }
    
    def validate_all_files(self) -> Dict[str, any]:
        """Validate all modified .claude files."""
        files_to_check = [
            'CLAUDE.md',
            'agents/coder.md',
            'agents/coordinator.md', 
            'agents/researcher.md',
            'commands/deploy.md',
            'helpers/project-sync.py',
            'helpers/load-env.py'
        ]
        
        results = {}
        total_score = 0
        total_files = 0
        
        for file_path in files_to_check:
            full_path = self.base_path / file_path
            result = self.validate_file(full_path)
            results[file_path] = result
            
            if result['exists']:
                total_score += result['score']
                total_files += 1
        
        overall_score = total_score / total_files if total_files > 0 else 0
        
        return {
            'files': results,
            'overall_score': round(overall_score, 1),
            'total_files': total_files,
            'files_with_issues': sum(1 for r in results.values() if r.get('issues', [])),
            'summary': self._generate_summary(results)
        }
    
    def _generate_summary(self, results: Dict[str, dict]) -> Dict[str, any]:
        """Generate validation summary."""
        high_score_files = [f for f, r in results.items() if r.get('score', 0) >= 80]
        medium_score_files = [f for f, r in results.items() if 60 <= r.get('score', 0) < 80]
        low_score_files = [f for f, r in results.items() if r.get('score', 0) < 60]
        
        common_issues = {}
        for result in results.values():
            for issue in result.get('issues', []):
                common_issues[issue] = common_issues.get(issue, 0) + 1
        
        env_var_coverage = {}
        for env_var in self.critical_env_vars:
            usage_count = sum(1 for r in results.values() if env_var in r.get('env_vars_found', set()))
            env_var_coverage[env_var] = usage_count
        
        return {
            'high_score_files': high_score_files,
            'medium_score_files': medium_score_files,
            'low_score_files': low_score_files,
            'common_issues': common_issues,
            'env_var_coverage': env_var_coverage
        }
    
    def print_validation_report(self):
        """Print detailed validation report."""
        results = self.validate_all_files()
        
        print("🔧 Environment Loading Validation Report")
        print("=" * 60)
        print(f"Overall Score: {results['overall_score']}/100")
        print(f"Files Validated: {results['total_files']}")
        print(f"Files with Issues: {results['files_with_issues']}")
        print()
        
        # File-by-file results
        print("📋 File Validation Results:")
        print("-" * 40)
        for file_path, result in results['files'].items():
            if not result['exists']:
                print(f"❌ {file_path}: FILE NOT FOUND")
                continue
            
            score = result['score']
            if score >= 80:
                status = "✅ EXCELLENT"
            elif score >= 60:
                status = "⚠️ GOOD"
            else:
                status = "❌ NEEDS WORK"
            
            print(f"{status} {file_path}: {score}/100")
            
            if result['issues']:
                for issue in result['issues']:
                    print(f"   - {issue}")
            
            env_count = len(result['env_vars_found'])
            print(f"   - Environment variables used: {env_count}/{len(self.critical_env_vars)}")
            print()
        
        # Summary statistics
        summary = results['summary']
        print("📊 Summary Statistics:")
        print("-" * 30)
        print(f"High Score Files (80+): {len(summary['high_score_files'])}")
        for f in summary['high_score_files']:
            print(f"  ✅ {f}")
        
        if summary['medium_score_files']:
            print(f"Medium Score Files (60-79): {len(summary['medium_score_files'])}")
            for f in summary['medium_score_files']:
                print(f"  ⚠️ {f}")
        
        if summary['low_score_files']:
            print(f"Low Score Files (<60): {len(summary['low_score_files'])}")
            for f in summary['low_score_files']:
                print(f"  ❌ {f}")
        
        print()
        print("🔍 Environment Variable Coverage:")
        print("-" * 35)
        for env_var, count in summary['env_var_coverage'].items():
            coverage = count / results['total_files'] * 100
            if coverage >= 70:
                status = "✅"
            elif coverage >= 40:
                status = "⚠️"
            else:
                status = "❌"
            print(f"{status} {env_var}: {count}/{results['total_files']} files ({coverage:.1f}%)")
        
        if summary['common_issues']:
            print()
            print("⚠️ Common Issues:")
            print("-" * 20)
            for issue, count in sorted(summary['common_issues'].items(), key=lambda x: x[1], reverse=True):
                print(f"  - {issue}: {count} files")
        
        print()
        if results['overall_score'] >= 80:
            print("🎉 VALIDATION PASSED: Environment loading implementation is excellent!")
        elif results['overall_score'] >= 60:
            print("✅ VALIDATION PASSED: Environment loading implementation is good with minor issues.")
        else:
            print("❌ VALIDATION FAILED: Environment loading implementation needs significant improvement.")
        
        return results['overall_score'] >= 60


def main():
    """Main entry point for validation."""
    validator = EnvironmentLoadingValidator()
    
    # Run validation
    passed = validator.print_validation_report()
    
    print()
    print("💡 Next Steps:")
    if passed:
        print("1. Copy modified files from review directory to main .claude directory")
        print("2. Test environment loading with: python3 .claude/helpers/load-env.py")
        print("3. Verify agents now load environment variables correctly")
    else:
        print("1. Review files with low scores and add missing environment loading instructions")
        print("2. Ensure all files have MANDATORY environment loading sections")
        print("3. Add environment variable usage examples")
        print("4. Re-run validation after improvements")
    
    return 0 if passed else 1


if __name__ == "__main__":
    exit(main())