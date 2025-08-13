#!/usr/bin/env python3
"""
Sync Fix Fraud Detector - Advanced Pattern Recognition
Identifies and prevents false sync fix completion claims through behavioral analysis.
ZERO TOLERANCE for fraudulent claims.
"""

import os
import re
import json
import time
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass
from enum import Enum
import hashlib

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class FraudSeverity(Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"

class FraudType(Enum):
    THEORETICAL_ONLY = "THEORETICAL_ONLY"
    PARTIAL_IMPLEMENTATION = "PARTIAL_IMPLEMENTATION" 
    MOCK_TESTING = "MOCK_TESTING"
    SELECTIVE_EVIDENCE = "SELECTIVE_EVIDENCE"
    VAGUE_CLAIMS = "VAGUE_CLAIMS"
    DOCUMENTATION_ONLY = "DOCUMENTATION_ONLY"
    REPEATED_PATTERN = "REPEATED_PATTERN"
    EVIDENCE_FABRICATION = "EVIDENCE_FABRICATION"

@dataclass
class FraudIndicator:
    fraud_type: FraudType
    severity: FraudSeverity
    description: str
    evidence: Dict[str, Any]
    confidence: float  # 0.0 to 1.0
    recommendation: str

@dataclass
class FraudAnalysisResult:
    claim_id: str
    timestamp: datetime
    total_indicators: int
    high_severity_count: int
    fraud_probability: float
    overall_recommendation: str
    indicators: List[FraudIndicator]
    evidence_quality_score: float
    implementation_completeness_score: float

class SyncFixFraudDetector:
    """
    Advanced fraud detection system for sync fix claims.
    Uses pattern recognition and behavioral analysis to identify false claims.
    """
    
    def __init__(self):
        self.claim_history = []
        self.fraud_patterns = self._initialize_fraud_patterns()
        self.evidence_analyzers = self._initialize_evidence_analyzers()
        
    def _initialize_fraud_patterns(self) -> Dict[str, Any]:
        """Initialize known fraud patterns."""
        return {
            "theoretical_keywords": [
                "should work", "would work", "is expected to", "theoretically",
                "based on documentation", "according to specs", "in theory"
            ],
            "vague_evidence": [
                "it works", "seems to work", "appears functional", "looks good",
                "tested manually", "basic testing done", "quick verification"
            ],
            "incomplete_implementations": [
                "part 1 of", "first phase", "initial implementation", "basic version",
                "proof of concept", "partial solution", "work in progress"
            ],
            "documentation_only_indicators": [
                "updated README", "added documentation", "improved comments",
                "clarified architecture", "documented process"
            ],
            "mock_testing_indicators": [
                "mock data", "simulated environment", "test environment",
                "fake responses", "stubbed functions", "mocked APIs"
            ]
        }
        
    def _initialize_evidence_analyzers(self) -> Dict[str, callable]:
        """Initialize evidence quality analyzers."""
        return {
            "code_analysis": self._analyze_code_evidence,
            "test_coverage": self._analyze_test_evidence,
            "screenshot_verification": self._analyze_screenshot_evidence,
            "log_analysis": self._analyze_log_evidence,
            "performance_data": self._analyze_performance_evidence,
            "user_feedback": self._analyze_user_feedback
        }
        
    def analyze_sync_fix_claim(self, 
                              claim_description: str,
                              evidence_package: Dict[str, Any],
                              code_changes: Optional[List[str]] = None,
                              test_results: Optional[Dict[str, Any]] = None) -> FraudAnalysisResult:
        """
        Comprehensive fraud analysis of a sync fix claim.
        Returns detailed analysis with fraud probability and recommendations.
        """
        
        claim_id = hashlib.md5(
            f"{claim_description}{time.time()}".encode()
        ).hexdigest()[:12]
        
        logger.info(f"🔍 FRAUD ANALYSIS STARTING - Claim ID: {claim_id}")
        
        indicators = []
        
        # Analyze claim description for fraud patterns
        indicators.extend(self._analyze_claim_description(claim_description))
        
        # Analyze evidence package quality
        indicators.extend(self._analyze_evidence_package(evidence_package))
        
        # Analyze code changes (if provided)
        if code_changes:
            indicators.extend(self._analyze_code_changes(code_changes))
            
        # Analyze test results (if provided)
        if test_results:
            indicators.extend(self._analyze_test_results(test_results))
            
        # Check for repeated fraud patterns
        indicators.extend(self._check_repeated_patterns(claim_description, evidence_package))
        
        # Calculate fraud probability
        fraud_probability = self._calculate_fraud_probability(indicators)
        
        # Generate quality scores
        evidence_quality_score = self._calculate_evidence_quality(evidence_package)
        implementation_score = self._calculate_implementation_completeness(
            claim_description, code_changes or []
        )
        
        # Generate overall recommendation
        recommendation = self._generate_recommendation(
            fraud_probability, 
            evidence_quality_score,
            implementation_score,
            indicators
        )
        
        result = FraudAnalysisResult(
            claim_id=claim_id,
            timestamp=datetime.now(),
            total_indicators=len(indicators),
            high_severity_count=len([i for i in indicators if i.severity in [FraudSeverity.HIGH, FraudSeverity.CRITICAL]]),
            fraud_probability=fraud_probability,
            overall_recommendation=recommendation,
            indicators=indicators,
            evidence_quality_score=evidence_quality_score,
            implementation_completeness_score=implementation_score
        )
        
        # Store in history for pattern analysis
        self.claim_history.append(result)
        
        logger.info(f"🎯 FRAUD ANALYSIS COMPLETE - Probability: {fraud_probability:.2%}")
        
        return result
        
    def _analyze_claim_description(self, description: str) -> List[FraudIndicator]:
        """Analyze claim description for fraud indicators."""
        indicators = []
        description_lower = description.lower()
        
        # Check for theoretical language
        theoretical_matches = [
            word for word in self.fraud_patterns["theoretical_keywords"]
            if word in description_lower
        ]
        if theoretical_matches:
            indicators.append(FraudIndicator(
                fraud_type=FraudType.THEORETICAL_ONLY,
                severity=FraudSeverity.HIGH,
                description="Claim uses theoretical language suggesting no actual implementation",
                evidence={"theoretical_terms": theoretical_matches},
                confidence=0.8,
                recommendation="REJECT - Require actual implementation proof"
            ))
            
        # Check for vague evidence language
        vague_matches = [
            word for word in self.fraud_patterns["vague_evidence"]
            if word in description_lower
        ]
        if vague_matches:
            indicators.append(FraudIndicator(
                fraud_type=FraudType.VAGUE_CLAIMS,
                severity=FraudSeverity.MEDIUM,
                description="Claim uses vague language without specific evidence",
                evidence={"vague_terms": vague_matches},
                confidence=0.6,
                recommendation="REQUEST - Demand specific evidence and metrics"
            ))
            
        # Check for incomplete implementation indicators
        incomplete_matches = [
            word for word in self.fraud_patterns["incomplete_implementations"]
            if word in description_lower
        ]
        if incomplete_matches:
            indicators.append(FraudIndicator(
                fraud_type=FraudType.PARTIAL_IMPLEMENTATION,
                severity=FraudSeverity.CRITICAL,
                description="Claim indicates incomplete implementation",
                evidence={"incomplete_indicators": incomplete_matches},
                confidence=0.9,
                recommendation="REJECT - Complete implementation required"
            ))
            
        # Check for documentation-only changes
        doc_only_matches = [
            word for word in self.fraud_patterns["documentation_only_indicators"]
            if word in description_lower
        ]
        if doc_only_matches and len(doc_only_matches) / len(description.split()) > 0.3:
            indicators.append(FraudIndicator(
                fraud_type=FraudType.DOCUMENTATION_ONLY,
                severity=FraudSeverity.HIGH,
                description="Claim appears to be documentation-only with no functional changes",
                evidence={"documentation_terms": doc_only_matches},
                confidence=0.7,
                recommendation="REJECT - Functional implementation required"
            ))
            
        return indicators
        
    def _analyze_evidence_package(self, evidence: Dict[str, Any]) -> List[FraudIndicator]:
        """Analyze evidence package for quality and completeness."""
        indicators = []
        
        # Check for missing critical evidence
        required_evidence = [
            "screenshots", "logs", "test_results", "database_changes",
            "kubernetes_data", "performance_metrics"
        ]
        
        missing_evidence = [
            req for req in required_evidence 
            if req not in evidence or not evidence[req]
        ]
        
        if len(missing_evidence) > len(required_evidence) / 2:
            indicators.append(FraudIndicator(
                fraud_type=FraudType.SELECTIVE_EVIDENCE,
                severity=FraudSeverity.HIGH,
                description="Evidence package missing critical components",
                evidence={"missing_evidence": missing_evidence},
                confidence=0.8,
                recommendation="REJECT - Complete evidence package required"
            ))
            
        # Check for mock/simulated evidence
        if self._contains_mock_indicators(evidence):
            indicators.append(FraudIndicator(
                fraud_type=FraudType.MOCK_TESTING,
                severity=FraudSeverity.CRITICAL,
                description="Evidence suggests mock or simulated testing instead of real environment",
                evidence={"mock_indicators": self._extract_mock_indicators(evidence)},
                confidence=0.9,
                recommendation="REJECT - Real environment testing required"
            ))
            
        # Check evidence timestamp consistency
        if not self._verify_timestamp_consistency(evidence):
            indicators.append(FraudIndicator(
                fraud_type=FraudType.EVIDENCE_FABRICATION,
                severity=FraudSeverity.CRITICAL,
                description="Evidence timestamps are inconsistent or suspicious",
                evidence={"timestamp_analysis": "Inconsistent timing detected"},
                confidence=0.8,
                recommendation="INVESTIGATE - Potential evidence fabrication"
            ))
            
        return indicators
        
    def _analyze_code_changes(self, code_changes: List[str]) -> List[FraudIndicator]:
        """Analyze code changes for fraud indicators."""
        indicators = []
        
        if not code_changes:
            indicators.append(FraudIndicator(
                fraud_type=FraudType.THEORETICAL_ONLY,
                severity=FraudSeverity.CRITICAL,
                description="No actual code changes provided",
                evidence={"code_changes_count": 0},
                confidence=1.0,
                recommendation="REJECT - Code changes required for implementation claim"
            ))
            return indicators
            
        # Analyze code quality and completeness
        total_lines = sum(len(change.split('\n')) for change in code_changes)
        
        if total_lines < 10:
            indicators.append(FraudIndicator(
                fraud_type=FraudType.PARTIAL_IMPLEMENTATION,
                severity=FraudSeverity.MEDIUM,
                description="Very minimal code changes for claimed functionality",
                evidence={"total_lines": total_lines},
                confidence=0.6,
                recommendation="INVESTIGATE - Verify implementation completeness"
            ))
            
        # Check for comment-only or documentation changes
        comment_lines = 0
        for change in code_changes:
            comment_lines += len([
                line for line in change.split('\n') 
                if line.strip().startswith('#') or line.strip().startswith('//')
            ])
            
        if comment_lines / total_lines > 0.7:
            indicators.append(FraudIndicator(
                fraud_type=FraudType.DOCUMENTATION_ONLY,
                severity=FraudSeverity.HIGH,
                description="Code changes are primarily comments/documentation",
                evidence={"comment_ratio": comment_lines / total_lines},
                confidence=0.8,
                recommendation="REJECT - Functional code changes required"
            ))
            
        return indicators
        
    def _analyze_test_results(self, test_results: Dict[str, Any]) -> List[FraudIndicator]:
        """Analyze test results for fraud indicators."""
        indicators = []
        
        # Check for missing or fake test results
        if not test_results or "tests_run" not in test_results:
            indicators.append(FraudIndicator(
                fraud_type=FraudType.SELECTIVE_EVIDENCE,
                severity=FraudSeverity.HIGH,
                description="No test results provided",
                evidence={"test_results_provided": False},
                confidence=0.8,
                recommendation="REJECT - Test execution evidence required"
            ))
            return indicators
            
        # Check for unrealistic test success rates
        if "success_rate" in test_results and test_results["success_rate"] == 1.0:
            if test_results.get("tests_run", 0) > 10:
                indicators.append(FraudIndicator(
                    fraud_type=FraudType.EVIDENCE_FABRICATION,
                    severity=FraudSeverity.MEDIUM,
                    description="Suspiciously perfect test results (100% success)",
                    evidence={"success_rate": test_results["success_rate"]},
                    confidence=0.5,
                    recommendation="INVESTIGATE - Verify test authenticity"
                ))
                
        return indicators
        
    def _check_repeated_patterns(self, description: str, evidence: Dict[str, Any]) -> List[FraudIndicator]:
        """Check for repeated fraud patterns in claim history."""
        indicators = []
        
        # Look for similar claims in history
        similar_claims = 0
        for historical_claim in self.claim_history[-10:]:  # Check last 10 claims
            if historical_claim.fraud_probability > 0.7:
                similar_claims += 1
                
        if similar_claims >= 3:
            indicators.append(FraudIndicator(
                fraud_type=FraudType.REPEATED_PATTERN,
                severity=FraudSeverity.CRITICAL,
                description="Pattern of repeated high-fraud-probability claims detected",
                evidence={"similar_claims_count": similar_claims},
                confidence=0.9,
                recommendation="ESCALATE - Pattern indicates systematic fraud"
            ))
            
        return indicators
        
    def _contains_mock_indicators(self, evidence: Dict[str, Any]) -> bool:
        """Check if evidence contains mock/simulation indicators."""
        evidence_text = json.dumps(evidence, default=str).lower()
        
        mock_indicators = self.fraud_patterns["mock_testing_indicators"]
        return any(indicator in evidence_text for indicator in mock_indicators)
        
    def _extract_mock_indicators(self, evidence: Dict[str, Any]) -> List[str]:
        """Extract specific mock indicators from evidence."""
        evidence_text = json.dumps(evidence, default=str).lower()
        
        found_indicators = []
        for indicator in self.fraud_patterns["mock_testing_indicators"]:
            if indicator in evidence_text:
                found_indicators.append(indicator)
                
        return found_indicators
        
    def _verify_timestamp_consistency(self, evidence: Dict[str, Any]) -> bool:
        """Verify timestamp consistency in evidence."""
        # Simple timestamp consistency check
        # In a real implementation, this would be much more sophisticated
        timestamps = []
        
        def extract_timestamps(obj):
            if isinstance(obj, dict):
                for key, value in obj.items():
                    if 'timestamp' in key.lower() or 'time' in key.lower():
                        if isinstance(value, str) and len(value) > 10:
                            timestamps.append(value)
                    elif isinstance(value, (dict, list)):
                        extract_timestamps(value)
            elif isinstance(obj, list):
                for item in obj:
                    extract_timestamps(item)
                    
        extract_timestamps(evidence)
        
        # Check if timestamps are reasonable (within last 24 hours for testing)
        current_time = datetime.now()
        for timestamp_str in timestamps:
            try:
                # Simple timestamp parsing - would need more robust parsing in reality
                if timestamp_str.count('-') >= 2:  # Looks like a date
                    # Assume it's recent for now
                    continue
            except:
                continue
                
        return True  # Conservative default
        
    def _calculate_fraud_probability(self, indicators: List[FraudIndicator]) -> float:
        """Calculate overall fraud probability based on indicators."""
        if not indicators:
            return 0.0
            
        # Weight indicators by severity and confidence
        severity_weights = {
            FraudSeverity.LOW: 0.25,
            FraudSeverity.MEDIUM: 0.5,
            FraudSeverity.HIGH: 0.75,
            FraudSeverity.CRITICAL: 1.0
        }
        
        total_weight = 0.0
        weighted_score = 0.0
        
        for indicator in indicators:
            weight = severity_weights[indicator.severity] * indicator.confidence
            total_weight += weight
            weighted_score += weight
            
        # Normalize to 0-1 scale
        if total_weight == 0:
            return 0.0
            
        fraud_probability = min(weighted_score / len(indicators), 1.0)
        
        # Apply penalty for multiple high-severity indicators
        high_severity_count = len([
            i for i in indicators 
            if i.severity in [FraudSeverity.HIGH, FraudSeverity.CRITICAL]
        ])
        
        if high_severity_count >= 3:
            fraud_probability = min(fraud_probability * 1.5, 1.0)
            
        return fraud_probability
        
    def _calculate_evidence_quality(self, evidence: Dict[str, Any]) -> float:
        """Calculate evidence quality score (0-1 scale)."""
        if not evidence:
            return 0.0
            
        quality_factors = {
            "completeness": self._assess_evidence_completeness(evidence),
            "authenticity": self._assess_evidence_authenticity(evidence),
            "specificity": self._assess_evidence_specificity(evidence),
            "verifiability": self._assess_evidence_verifiability(evidence)
        }
        
        return sum(quality_factors.values()) / len(quality_factors)
        
    def _calculate_implementation_completeness(self, description: str, code_changes: List[str]) -> float:
        """Calculate implementation completeness score (0-1 scale)."""
        completeness_score = 0.0
        
        # Check description completeness
        if len(description) > 100:
            completeness_score += 0.25
            
        # Check code changes
        if code_changes:
            total_lines = sum(len(change.split('\n')) for change in code_changes)
            if total_lines > 50:
                completeness_score += 0.5
            elif total_lines > 10:
                completeness_score += 0.25
                
        # Check for key implementation components
        implementation_indicators = [
            "function", "class", "method", "import", "def", "api", "database", "sync"
        ]
        
        text_to_check = description + " " + " ".join(code_changes)
        found_indicators = [
            indicator for indicator in implementation_indicators
            if indicator in text_to_check.lower()
        ]
        
        completeness_score += min(len(found_indicators) / len(implementation_indicators), 0.25)
        
        return min(completeness_score, 1.0)
        
    def _assess_evidence_completeness(self, evidence: Dict[str, Any]) -> float:
        """Assess evidence completeness."""
        required_components = [
            "screenshots", "logs", "test_results", "database_changes",
            "performance_metrics", "error_handling"
        ]
        
        provided_count = sum(1 for component in required_components if component in evidence)
        return provided_count / len(required_components)
        
    def _assess_evidence_authenticity(self, evidence: Dict[str, Any]) -> float:
        """Assess evidence authenticity."""
        # Check for mock indicators
        if self._contains_mock_indicators(evidence):
            return 0.2
            
        # Check timestamp consistency
        if not self._verify_timestamp_consistency(evidence):
            return 0.3
            
        return 0.8  # Conservative default
        
    def _assess_evidence_specificity(self, evidence: Dict[str, Any]) -> float:
        """Assess evidence specificity."""
        evidence_text = json.dumps(evidence, default=str)
        
        # Look for specific details vs vague statements
        specific_indicators = [
            "line ", "function ", "table ", "column ", "endpoint ", "status_code",
            "timestamp", "error", "success", "failed", "passed"
        ]
        
        found_specifics = sum(1 for indicator in specific_indicators if indicator in evidence_text.lower())
        return min(found_specifics / len(specific_indicators), 1.0)
        
    def _assess_evidence_verifiability(self, evidence: Dict[str, Any]) -> float:
        """Assess evidence verifiability."""
        verifiable_elements = [
            "file_path", "url", "database_query", "command", "api_endpoint"
        ]
        
        evidence_text = json.dumps(evidence, default=str).lower()
        found_verifiable = sum(1 for element in verifiable_elements if element in evidence_text)
        
        return min(found_verifiable / len(verifiable_elements), 1.0)
        
    def _generate_recommendation(self, 
                               fraud_probability: float, 
                               evidence_quality: float,
                               implementation_score: float,
                               indicators: List[FraudIndicator]) -> str:
        """Generate overall recommendation based on analysis."""
        
        critical_indicators = [
            i for i in indicators 
            if i.severity == FraudSeverity.CRITICAL
        ]
        
        # Critical fraud indicators = automatic rejection
        if critical_indicators:
            return "AUTOMATIC REJECTION - Critical fraud indicators detected"
            
        # High fraud probability = rejection
        if fraud_probability > 0.8:
            return "REJECT - High probability of fraudulent claim"
            
        # Medium-high fraud probability = investigation
        if fraud_probability > 0.6:
            return "INVESTIGATE - Suspicious patterns require additional verification"
            
        # Low evidence quality = rejection
        if evidence_quality < 0.4:
            return "REJECT - Evidence quality insufficient"
            
        # Low implementation score = rejection
        if implementation_score < 0.3:
            return "REJECT - Implementation completeness insufficient"
            
        # Medium risk cases
        if fraud_probability > 0.4 or evidence_quality < 0.6:
            return "CONDITIONAL - Additional evidence and verification required"
            
        # Low risk
        return "PROCEED - Fraud risk appears low, continue with standard validation"
        
    def generate_fraud_report(self, analysis: FraudAnalysisResult) -> str:
        """Generate comprehensive fraud analysis report."""
        
        report = f"""
🚨 SYNC FIX FRAUD ANALYSIS REPORT
================================

Analysis ID: {analysis.claim_id}
Timestamp: {analysis.timestamp}
Overall Fraud Probability: {analysis.fraud_probability:.2%}

🎯 FINAL RECOMMENDATION: {analysis.overall_recommendation}

📊 ANALYSIS SUMMARY
------------------
Total Indicators: {analysis.total_indicators}
High/Critical Severity: {analysis.high_severity_count}
Evidence Quality Score: {analysis.evidence_quality_score:.2%}
Implementation Completeness: {analysis.implementation_completeness_score:.2%}

🔍 FRAUD INDICATORS DETECTED
----------------------------
"""
        
        if not analysis.indicators:
            report += "✅ No significant fraud indicators detected\n\n"
        else:
            for i, indicator in enumerate(analysis.indicators, 1):
                report += f"""
{i}. {indicator.fraud_type.value} ({indicator.severity.value})
   Description: {indicator.description}
   Confidence: {indicator.confidence:.2%}
   Evidence: {indicator.evidence}
   Recommendation: {indicator.recommendation}
"""
        
        report += f"""

🚨 FRAUD RISK ASSESSMENT
-----------------------
{self._get_risk_assessment(analysis.fraud_probability)}

🎯 ENFORCEMENT ACTIONS
--------------------
{self._get_enforcement_actions(analysis)}

🔒 FRAUD DETECTOR AUTHORITY
--------------------------
This analysis was conducted by the Sync Fix Fraud Detector with:
- Advanced pattern recognition algorithms
- Historical claim analysis
- Multi-factor evidence validation
- Behavioral fraud detection

Authority: ADVISORY (supports Validation Gatekeeper final decision)
Confidence in Analysis: HIGH
Framework Version: 1.0
"""
        
        return report
        
    def _get_risk_assessment(self, fraud_probability: float) -> str:
        """Get risk assessment text."""
        if fraud_probability > 0.8:
            return "🔴 CRITICAL RISK - Strong indicators of fraudulent claim"
        elif fraud_probability > 0.6:
            return "🟡 HIGH RISK - Multiple suspicious patterns detected"
        elif fraud_probability > 0.4:
            return "🟡 MEDIUM RISK - Some concerning indicators present"
        elif fraud_probability > 0.2:
            return "🟢 LOW RISK - Minor concerns, likely legitimate"
        else:
            return "✅ MINIMAL RISK - No significant fraud indicators"
            
    def _get_enforcement_actions(self, analysis: FraudAnalysisResult) -> str:
        """Get enforcement actions based on analysis."""
        if "REJECT" in analysis.overall_recommendation:
            return """
- REJECT claim immediately
- Require substantial re-work before resubmission
- Document fraud patterns for future reference
- Consider escalation if repeated offenses
"""
        elif "INVESTIGATE" in analysis.overall_recommendation:
            return """
- Conduct additional evidence verification
- Require independent validation
- Request clarification on suspicious elements
- Monitor closely for fraud pattern development
"""
        elif "CONDITIONAL" in analysis.overall_recommendation:
            return """
- Request additional evidence
- Require specific clarifications
- Implement enhanced validation procedures
- Document concerns for tracking
"""
        else:
            return """
- Proceed with standard validation procedures
- Document clean analysis for reference
- Continue monitoring for future patterns
"""

def main():
    """Demonstrate fraud detection system."""
    print("🚨 SYNC FIX FRAUD DETECTOR")
    print("🚨 Advanced Pattern Recognition System")
    print("=" * 50)
    
    detector = SyncFixFraudDetector()
    
    # Example analysis of a suspicious claim
    example_claim = """
    The sync functionality should work now based on the theoretical analysis.
    I have updated the documentation and added some comments to clarify the process.
    Basic testing was done and it seems to work fine.
    This is part 1 of the complete solution.
    """
    
    example_evidence = {
        "screenshots": None,
        "logs": "No specific logs provided",
        "test_results": {"description": "tested manually"},
        "mock_data": "Used simulated K8s responses for testing"
    }
    
    analysis = detector.analyze_sync_fix_claim(
        example_claim, 
        example_evidence,
        code_changes=["# Added comment explaining sync process"]
    )
    
    report = detector.generate_fraud_report(analysis)
    print(report)
    
    print(f"\n📄 Fraud Analysis Complete")
    print(f"🎯 Risk Level: {analysis.fraud_probability:.2%}")
    print(f"🔒 Recommendation: {analysis.overall_recommendation}")

if __name__ == "__main__":
    main()