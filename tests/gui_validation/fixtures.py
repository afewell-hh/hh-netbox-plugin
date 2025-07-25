#!/usr/bin/env python3
"""
Test Fixtures for GUI Validation Tests

Provides:
- Minimal test data setup
- Safe test execution (non-destructive)
- Cleanup utilities (if needed)
- Demo-realistic data scenarios

This module provides test data fixtures that are:
1. Safe for existing environments (non-destructive)
2. Realistic for demo scenarios
3. Easy to set up and tear down
4. Isolated from production data
"""

import os
import sys
import json
import time
import requests
from pathlib import Path
from typing import Dict, Any, Optional, List, Union, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime

# Add project root to Python path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from tests.gui_validation.environment import get_environment


@dataclass
class TestFabric:
    """Test fabric data structure"""
    name: str
    asn: int = 65001
    description: str = "Test fabric for demo validation"
    spine_asn: int = 65001
    leaf_asn_min: int = 65100
    leaf_asn_max: int = 65199
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API calls"""
        return asdict(self)


@dataclass
class TestVPC:
    """Test VPC data structure"""
    name: str
    vni: int
    fabric: str
    description: str = "Test VPC for demo validation"
    ipv4_subnet: str = "10.0.0.0/24"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API calls"""
        return asdict(self)


@dataclass
class TestSwitch:
    """Test switch data structure"""
    name: str
    fabric: str
    description: str = "Test switch for demo validation"
    role: str = "leaf"
    asn: int = 65101
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API calls"""
        return asdict(self)


class FixtureError(Exception):
    """Base exception for fixture-related errors"""
    pass


class DataCreationError(FixtureError):
    """Exception for data creation failures"""
    pass


class TestDataManager:
    """
    Manages test data for GUI validation tests.
    
    Provides methods for:
    - Creating minimal test data
    - Safe data operations (non-destructive)
    - Cleanup utilities
    - Demo-realistic scenarios
    """
    
    def __init__(self):
        self.environment = get_environment()
        self.session = self.environment.get_authenticated_session()
        self.base_url = self.environment.get_netbox_url()
        self.created_objects = []  # Track created objects for cleanup
        
        # Test data prefix for isolation
        self.test_prefix = "test_demo_"
        self.test_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    def create_minimal_test_data(self) -> Dict[str, List[Dict[str, Any]]]:
        """
        Create minimal test data for demo validation.
        
        Creates just enough data to make the demo UI functional without
        overwhelming the interface or conflicting with existing data.
        
        Returns:
            Dictionary mapping object types to created objects
        """
        print("📝 Creating minimal test data for demo validation...")
        
        created_data = {
            'fabrics': [],
            'vpcs': [],
            'switches': []
        }
        
        try:
            # Create one test fabric
            fabric_data = TestFabric(
                name=f"{self.test_prefix}fabric_{self.test_timestamp}",
                description="Demo validation test fabric - safe to delete"
            )
            
            fabric = self._create_fabric(fabric_data)
            if fabric:
                created_data['fabrics'].append(fabric)
                print(f"✅ Created test fabric: {fabric['name']}")
            
            # Create one test VPC in the fabric
            if fabric:
                vpc_data = TestVPC(
                    name=f"{self.test_prefix}vpc_{self.test_timestamp}",
                    vni=9999,  # Use high VNI to avoid conflicts
                    fabric=fabric['name'],
                    description="Demo validation test VPC - safe to delete"
                )
                
                vpc = self._create_vpc(vpc_data)
                if vpc:
                    created_data['vpcs'].append(vpc)
                    print(f"✅ Created test VPC: {vpc['name']}")
            
            # Create one test switch in the fabric
            if fabric:
                switch_data = TestSwitch(
                    name=f"{self.test_prefix}switch_{self.test_timestamp}",
                    fabric=fabric['name'],
                    description="Demo validation test switch - safe to delete"
                )
                
                switch = self._create_switch(switch_data)
                if switch:
                    created_data['switches'].append(switch)
                    print(f"✅ Created test switch: {switch['name']}")
            
            print(f"✅ Minimal test data created successfully!")
            return created_data
            
        except Exception as e:
            print(f"❌ Failed to create minimal test data: {e}")
            # Attempt cleanup of any partially created data
            self.cleanup_test_data()
            raise DataCreationError(f"Failed to create minimal test data: {e}")
    
    def create_demo_realistic_data(self) -> Dict[str, List[Dict[str, Any]]]:
        """
        Create demo-realistic test data.
        
        Creates a more comprehensive set of test data that showcases
        the plugin's capabilities in a realistic demo scenario.
        
        Returns:
            Dictionary mapping object types to created objects
        """
        print("🎭 Creating demo-realistic test data...")
        
        created_data = {
            'fabrics': [],
            'vpcs': [],
            'switches': []
        }
        
        try:
            # Create a demo fabric
            fabric_data = TestFabric(
                name=f"{self.test_prefix}demo_fabric",
                description="Demo fabric showcasing Hedgehog capabilities",
                asn=65000
            )
            
            fabric = self._create_fabric(fabric_data)
            if fabric:
                created_data['fabrics'].append(fabric)
                print(f"✅ Created demo fabric: {fabric['name']}")
                
                # Create multiple VPCs for demo
                vpc_configs = [
                    {"name": "production", "vni": 1001, "subnet": "10.1.0.0/24"},
                    {"name": "staging", "vni": 1002, "subnet": "10.2.0.0/24"},
                    {"name": "development", "vni": 1003, "subnet": "10.3.0.0/24"}
                ]
                
                for vpc_config in vpc_configs:
                    vpc_data = TestVPC(
                        name=f"{self.test_prefix}{vpc_config['name']}",
                        vni=vpc_config['vni'],
                        fabric=fabric['name'],
                        ipv4_subnet=vpc_config['subnet'],
                        description=f"Demo {vpc_config['name']} VPC"
                    )
                    
                    vpc = self._create_vpc(vpc_data)
                    if vpc:
                        created_data['vpcs'].append(vpc)
                        print(f"✅ Created demo VPC: {vpc['name']}")
                
                # Create multiple switches for demo
                switch_configs = [
                    {"name": "spine-01", "role": "spine", "asn": 65000},
                    {"name": "leaf-01", "role": "leaf", "asn": 65101},
                    {"name": "leaf-02", "role": "leaf", "asn": 65102}
                ]
                
                for switch_config in switch_configs:
                    switch_data = TestSwitch(
                        name=f"{self.test_prefix}{switch_config['name']}",
                        fabric=fabric['name'],
                        role=switch_config['role'],
                        asn=switch_config['asn'],
                        description=f"Demo {switch_config['role']} switch"
                    )
                    
                    switch = self._create_switch(switch_data)
                    if switch:
                        created_data['switches'].append(switch)
                        print(f"✅ Created demo switch: {switch['name']}")
            
            print(f"✅ Demo-realistic test data created successfully!")
            return created_data
            
        except Exception as e:
            print(f"❌ Failed to create demo-realistic test data: {e}")
            self.cleanup_test_data()
            raise DataCreationError(f"Failed to create demo-realistic test data: {e}")
    
    def _create_fabric(self, fabric_data: TestFabric) -> Optional[Dict[str, Any]]:
        """Create a fabric via API"""
        try:
            # First check if fabric already exists
            existing = self._get_existing_fabric(fabric_data.name)
            if existing:
                print(f"⚠️  Fabric {fabric_data.name} already exists, using existing")
                return existing
            
            # Create new fabric
            url = f"{self.base_url}/api/plugins/hedgehog/fabrics/"
            response = self.session.post(url, json=fabric_data.to_dict())
            
            if response.status_code in [200, 201]:
                fabric = response.json()
                self.created_objects.append(('fabric', fabric['id'], fabric['name']))
                return fabric
            else:
                print(f"⚠️  Failed to create fabric: {response.status_code} - {response.text}")
                return None
                
        except Exception as e:
            print(f"⚠️  Error creating fabric: {e}")
            return None
    
    def _create_vpc(self, vpc_data: TestVPC) -> Optional[Dict[str, Any]]:
        """Create a VPC via API"""
        try:
            # First check if VPC already exists
            existing = self._get_existing_vpc(vpc_data.name)
            if existing:
                print(f"⚠️  VPC {vpc_data.name} already exists, using existing")
                return existing
            
            # Create new VPC
            url = f"{self.base_url}/api/plugins/hedgehog/vpcs/"
            response = self.session.post(url, json=vpc_data.to_dict())
            
            if response.status_code in [200, 201]:
                vpc = response.json()
                self.created_objects.append(('vpc', vpc['id'], vpc['name']))
                return vpc
            else:
                print(f"⚠️  Failed to create VPC: {response.status_code} - {response.text}")
                return None
                
        except Exception as e:
            print(f"⚠️  Error creating VPC: {e}")
            return None
    
    def _create_switch(self, switch_data: TestSwitch) -> Optional[Dict[str, Any]]:
        """Create a switch via API"""
        try:
            # First check if switch already exists
            existing = self._get_existing_switch(switch_data.name)
            if existing:
                print(f"⚠️  Switch {switch_data.name} already exists, using existing")
                return existing
            
            # Create new switch
            url = f"{self.base_url}/api/plugins/hedgehog/switches/"
            response = self.session.post(url, json=switch_data.to_dict())
            
            if response.status_code in [200, 201]:
                switch = response.json()
                self.created_objects.append(('switch', switch['id'], switch['name']))
                return switch
            else:
                print(f"⚠️  Failed to create switch: {response.status_code} - {response.text}")
                return None
                
        except Exception as e:
            print(f"⚠️  Error creating switch: {e}")
            return None
    
    def _get_existing_fabric(self, name: str) -> Optional[Dict[str, Any]]:
        """Check if fabric already exists"""
        try:
            url = f"{self.base_url}/api/plugins/hedgehog/fabrics/"
            response = self.session.get(url, params={'name': name})
            
            if response.status_code == 200:
                data = response.json()
                if data.get('results') and len(data['results']) > 0:
                    return data['results'][0]
            
            return None
        except Exception:
            return None
    
    def _get_existing_vpc(self, name: str) -> Optional[Dict[str, Any]]:
        """Check if VPC already exists"""
        try:
            url = f"{self.base_url}/api/plugins/hedgehog/vpcs/"
            response = self.session.get(url, params={'name': name})
            
            if response.status_code == 200:
                data = response.json()
                if data.get('results') and len(data['results']) > 0:
                    return data['results'][0]
            
            return None
        except Exception:
            return None
    
    def _get_existing_switch(self, name: str) -> Optional[Dict[str, Any]]:
        """Check if switch already exists"""
        try:
            url = f"{self.base_url}/api/plugins/hedgehog/switches/"
            response = self.session.get(url, params={'name': name})
            
            if response.status_code == 200:
                data = response.json()
                if data.get('results') and len(data['results']) > 0:
                    return data['results'][0]
            
            return None
        except Exception:
            return None
    
    def cleanup_test_data(self):
        """Clean up test data created during tests"""
        if not self.created_objects:
            print("✅ No test data to clean up")
            return
        
        print(f"🧹 Cleaning up {len(self.created_objects)} test objects...")
        
        # Clean up in reverse order (dependencies)
        for obj_type, obj_id, obj_name in reversed(self.created_objects):
            try:
                url = f"{self.base_url}/api/plugins/hedgehog/{obj_type}s/{obj_id}/"
                response = self.session.delete(url)
                
                if response.status_code in [200, 204]:
                    print(f"✅ Deleted {obj_type}: {obj_name}")
                else:
                    print(f"⚠️  Failed to delete {obj_type} {obj_name}: {response.status_code}")
                    
            except Exception as e:
                print(f"⚠️  Error deleting {obj_type} {obj_name}: {e}")
        
        self.created_objects.clear()
        print("✅ Test data cleanup complete")
    
    def cleanup_by_prefix(self, prefix: str = None):
        """Clean up all objects with test prefix"""
        if prefix is None:
            prefix = self.test_prefix
        
        print(f"🧹 Cleaning up all objects with prefix '{prefix}'...")
        
        object_types = ['switches', 'vpcs', 'fabrics']  # Order matters for dependencies
        
        for obj_type in object_types:
            try:
                url = f"{self.base_url}/api/plugins/hedgehog/{obj_type}/"
                response = self.session.get(url)
                
                if response.status_code == 200:
                    data = response.json()
                    objects = data.get('results', [])
                    
                    for obj in objects:
                        if obj['name'].startswith(prefix):
                            delete_url = f"{url}{obj['id']}/"
                            delete_response = self.session.delete(delete_url)
                            
                            if delete_response.status_code in [200, 204]:
                                print(f"✅ Deleted {obj_type[:-1]}: {obj['name']}")
                            else:
                                print(f"⚠️  Failed to delete {obj['name']}: {delete_response.status_code}")
                                
            except Exception as e:
                print(f"⚠️  Error cleaning up {obj_type}: {e}")
        
        print("✅ Prefix-based cleanup complete")
    
    def get_test_data_summary(self) -> Dict[str, int]:
        """Get summary of existing test data"""
        summary = {'fabrics': 0, 'vpcs': 0, 'switches': 0}
        
        for obj_type in summary.keys():
            try:
                url = f"{self.base_url}/api/plugins/hedgehog/{obj_type}/"
                response = self.session.get(url)
                
                if response.status_code == 200:
                    data = response.json()
                    objects = data.get('results', [])
                    
                    # Count objects with test prefix
                    test_objects = [obj for obj in objects if obj['name'].startswith(self.test_prefix)]
                    summary[obj_type] = len(test_objects)
                    
            except Exception:
                summary[obj_type] = -1  # Error indicator
        
        return summary
    
    def validate_test_data(self) -> Tuple[bool, List[str]]:
        """
        Validate that test data is properly set up and accessible.
        
        Returns:
            Tuple of (is_valid, list_of_issues)
        """
        issues = []
        
        # Check API accessibility
        try:
            url = f"{self.base_url}/api/plugins/hedgehog/"
            response = self.session.get(url)
            
            if response.status_code != 200:
                issues.append(f"API not accessible: status {response.status_code}")
        except Exception as e:
            issues.append(f"Cannot access API: {e}")
        
        # Check basic data integrity
        summary = self.get_test_data_summary()
        
        for obj_type, count in summary.items():
            if count == -1:
                issues.append(f"Cannot query {obj_type}")
            elif count == 0:
                issues.append(f"No test {obj_type} found (may need to create test data)")
        
        return len(issues) == 0, issues


# Fixture management functions for easy use in tests

def setup_minimal_fixtures() -> TestDataManager:
    """Set up minimal test fixtures"""
    manager = TestDataManager()
    manager.create_minimal_test_data()
    return manager


def setup_demo_fixtures() -> TestDataManager:
    """Set up demo-realistic test fixtures"""
    manager = TestDataManager()
    manager.create_demo_realistic_data()
    return manager


def cleanup_all_test_fixtures():
    """Clean up all test fixtures"""
    manager = TestDataManager()
    manager.cleanup_by_prefix()


def validate_fixtures() -> bool:
    """Validate that fixtures are properly set up"""
    manager = TestDataManager()
    is_valid, issues = manager.validate_test_data()
    
    if not is_valid:
        print("⚠️  Fixture validation issues:")
        for issue in issues:
            print(f"  • {issue}")
    
    return is_valid


# Context manager for test data
class TestDataContext:
    """Context manager for safe test data handling"""
    
    def __init__(self, create_minimal: bool = True, cleanup_on_exit: bool = True):
        self.create_minimal = create_minimal
        self.cleanup_on_exit = cleanup_on_exit
        self.manager = None
    
    def __enter__(self) -> TestDataManager:
        self.manager = TestDataManager()
        
        if self.create_minimal:
            self.manager.create_minimal_test_data()
        
        return self.manager
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.manager and self.cleanup_on_exit:
            self.manager.cleanup_test_data()


if __name__ == '__main__':
    # Demo the fixture system
    import argparse
    
    parser = argparse.ArgumentParser(description='Test Data Fixture Management')
    parser.add_argument('--create-minimal', action='store_true', 
                       help='Create minimal test data')
    parser.add_argument('--create-demo', action='store_true',
                       help='Create demo-realistic test data')
    parser.add_argument('--cleanup', action='store_true',
                       help='Clean up all test data')
    parser.add_argument('--validate', action='store_true',
                       help='Validate test data setup')
    parser.add_argument('--summary', action='store_true',
                       help='Show test data summary')
    
    args = parser.parse_args()
    
    try:
        if args.create_minimal:
            manager = setup_minimal_fixtures()
            print("✅ Minimal fixtures created")
        elif args.create_demo:
            manager = setup_demo_fixtures()
            print("✅ Demo fixtures created")
        elif args.cleanup:
            cleanup_all_test_fixtures()
            print("✅ All test fixtures cleaned up")
        elif args.validate:
            is_valid = validate_fixtures()
            sys.exit(0 if is_valid else 1)
        elif args.summary:
            manager = TestDataManager()
            summary = manager.get_test_data_summary()
            print("📊 Test Data Summary:")
            for obj_type, count in summary.items():
                status = f"{count} objects" if count >= 0 else "Error querying"
                print(f"  • {obj_type}: {status}")
        else:
            # Default: show summary and validate
            manager = TestDataManager()
            summary = manager.get_test_data_summary()
            print("📊 Test Data Summary:")
            for obj_type, count in summary.items():
                status = f"{count} objects" if count >= 0 else "Error querying"
                print(f"  • {obj_type}: {status}")
            
            is_valid = validate_fixtures()
            sys.exit(0 if is_valid else 1)
            
    except Exception as e:
        print(f"❌ Fixture operation failed: {e}")
        sys.exit(1)