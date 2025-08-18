#!/usr/bin/env python3
"""
Enhanced Hive Orchestration Task Classifier

This classifier automatically determines task complexity and assigns appropriate
workflows to prevent agent false completions and ensure proper validation.
"""

import json
import re
import sys
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List
import os

@dataclass
class TaskClassification:
    """Result of task classification analysis."""
    level: str  # SIMPLE, MEDIUM, COMPLEX
    confidence: float  # 0.0 to 1.0
    reasoning: List[str]
    recommended_workflow: str
    validation_requirements: List[str]
    git_strategy: str
    required_checkpoints: List[str]
    estimated_duration: str
    risk_factors: List[str]

class EnhancedTaskClassifier:
    """Intelligent task classifier for Enhanced Hive Orchestration."""
    
    def __init__(self):
        self._load_environment()
        
        self.simple_patterns = {
            'single_file_edit': [r'\b(edit|modify|update|fix|change)\s+(\w+\.(py|js|html|css|md))\b'],
            'documentation': [r'\b(readme|documentation|docs?|comment|docstring)\b'],
            'configuration': [r'\bconfig\s+(file|setting)\b', r'\benvironment\s+variable\b']
        }
        
        self.medium_patterns = {
            'multi_file_changes': [r'\bmultiple\s+files?\b', r'\bseveral\s+files?\b'],
            'api_changes': [r'\bapi\s+(endpoint|route|method)\b', r'\brest\s+api\b'],
            'model_changes': [r'\bmodel\s+(add|create|modify|update)\b']
        }
        
        self.complex_patterns = {
            'architecture_changes': [r'\barchitecture\s+(change|refactor|redesign)\b'],
            'major_features': [r'\bmajor\s+feature\b', r'\blarge\s+feature\b', r'\bepic\b']
        }
        
        self.workflows = {
            'SIMPLE': {
                'git_strategy': 'current_branch_direct_commit',
                'validation_requirements': ['basic_syntax_check', 'quick_test'],
                'checkpoints': ['environment_load', 'quick_deploy', 'basic_validation'],
                'estimated_duration': '15-30 minutes'
            },
            'MEDIUM': {
                'git_strategy': 'feature_branch_pr_workflow',
                'validation_requirements': ['full_test_suite', 'integration_tests'],
                'checkpoints': ['environment_load', 'feature_branch', 'comprehensive_test'],
                'estimated_duration': '1-4 hours'
            },
            'COMPLEX': {
                'git_strategy': 'epic_branch_hierarchy',
                'validation_requirements': ['full_test_suite', 'integration_tests', 'performance_tests'],
                'checkpoints': ['environment_load', 'epic_planning', 'milestone_testing'],
                'estimated_duration': '1-5 days'
            }
        }
    
    def _load_environment(self):
        """Load environment variables from .env file if available."""
        env_path = Path('.env')
        if env_path.exists():
            try:
                with open(env_path, 'r') as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith('#') and '=' in line:
                            key, value = line.split('=', 1)
                            os.environ[key.strip()] = value.strip()
            except Exception as e:
                print(f"Warning: Could not load .env file: {e}")
    
    def classify_task(self, task_description: str) -> TaskClassification:
        """Classify a task based on its description."""
        text = task_description.lower().strip()
        
        simple_matches = self._count_pattern_matches(text, self.simple_patterns)
        medium_matches = self._count_pattern_matches(text, self.medium_patterns)
        complex_matches = self._count_pattern_matches(text, self.complex_patterns)
        
        total_matches = simple_matches + medium_matches + complex_matches
        
        if total_matches == 0:
            level = 'MEDIUM'
            confidence = 0.5
            reasoning = ['Task description unclear, defaulting to MEDIUM complexity for safety']
        elif complex_matches > 0:
            level = 'COMPLEX'
            confidence = 0.8
            reasoning = [f'Complex patterns detected: {complex_matches} matches']
        elif medium_matches > simple_matches:
            level = 'MEDIUM'
            confidence = 0.7
            reasoning = [f'Medium complexity patterns detected: {medium_matches} matches']
        else:
            level = 'SIMPLE'
            confidence = 0.8
            reasoning = [f'Simple patterns detected: {simple_matches} matches']
        
        workflow = self.workflows[level]
        
        return TaskClassification(
            level=level,
            confidence=confidence,
            reasoning=reasoning,
            recommended_workflow=f"{level.lower()}_workflow",
            validation_requirements=workflow['validation_requirements'],
            git_strategy=workflow['git_strategy'],
            required_checkpoints=workflow['checkpoints'],
            estimated_duration=workflow['estimated_duration'],
            risk_factors=[]
        )
    
    def _count_pattern_matches(self, text: str, pattern_dict: Dict[str, List[str]]) -> int:
        """Count total pattern matches in text."""
        total_matches = 0
        for category, patterns in pattern_dict.items():
            for pattern in patterns:
                matches = len(re.findall(pattern, text, re.IGNORECASE))
                total_matches += matches
        return total_matches

def main():
    """Main entry point for task classification."""
    if len(sys.argv) < 2:
        print("Usage: python3 task-classifier.py '<task_description>'")
        sys.exit(1)
    
    task_description = ' '.join(sys.argv[1:])
    classifier = EnhancedTaskClassifier()
    classification = classifier.classify_task(task_description)
    
    print("🔍 Enhanced Hive Orchestration - Task Classification")
    print("=" * 60)
    print(f"Task: {task_description}")
    print(f"Classification: {classification.level}")
    print(f"Confidence: {classification.confidence:.1%}")
    print(f"Estimated Duration: {classification.estimated_duration}")
    print(f"Git Strategy: {classification.git_strategy}")
    
    # Save classification
    result = {
        'task_description': task_description,
        'classification': asdict(classification),
        'timestamp': datetime.now().isoformat()
    }
    
    classification_file = Path('.claude/state/current-task-classification.json')
    classification_file.parent.mkdir(parents=True, exist_ok=True)
    with open(classification_file, 'w') as f:
        json.dump(result, f, indent=2)
    
    print(f"📄 Classification saved to: {classification_file}")
    return 0

if __name__ == "__main__":
    exit(main())
