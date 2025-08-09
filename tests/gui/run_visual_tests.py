#!/usr/bin/env python3
"""
Visual Regression Test Runner

Simple script to run visual regression tests and validate the implementation.
This script helps verify that all visual regression testing components work together.
"""

import sys
import subprocess
from pathlib import Path
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def check_dependencies():
    """Check if required dependencies are installed"""
    required_packages = [
        'playwright',
        'pytest-playwright', 
        'pixelmatch',
        'PIL'  # Pillow
    ]
    
    missing_packages = []
    
    for package in required_packages:
        try:
            if package == 'PIL':
                import PIL
            else:
                __import__(package.replace('-', '_'))
        except ImportError:
            missing_packages.append(package)
    
    if missing_packages:
        logger.error(f"Missing packages: {missing_packages}")
        logger.error("Install with: pip install pixelmatch Pillow pytest-playwright playwright")
        return False
    
    return True

def run_visual_tests():
    """Run visual regression tests"""
    
    if not check_dependencies():
        logger.error("Dependencies not satisfied")
        return False
    
    # Change to test directory
    test_dir = Path(__file__).parent
    
    try:
        # Run just the visual regression tests
        cmd = [
            'python', '-m', 'pytest', 
            'tests/test_visual_regression.py',
            '-v',  # verbose output
            '--tb=short',  # shorter tracebacks
            '--disable-warnings'  # suppress warnings for cleaner output
        ]
        
        logger.info(f"Running command: {' '.join(cmd)}")
        logger.info(f"Working directory: {test_dir}")
        
        result = subprocess.run(
            cmd, 
            cwd=test_dir,
            capture_output=True,
            text=True,
            timeout=300  # 5 minute timeout
        )
        
        # Log output
        if result.stdout:
            logger.info("Test stdout:")
            logger.info(result.stdout)
        
        if result.stderr:
            logger.warning("Test stderr:")
            logger.warning(result.stderr)
        
        if result.returncode == 0:
            logger.info("Visual regression tests completed successfully!")
            return True
        else:
            logger.error(f"Visual regression tests failed with return code: {result.returncode}")
            return False
            
    except subprocess.TimeoutExpired:
        logger.error("Visual regression tests timed out after 5 minutes")
        return False
    except Exception as e:
        logger.error(f"Failed to run visual regression tests: {e}")
        return False

def validate_test_structure():
    """Validate that test structure is correct"""
    
    test_dir = Path(__file__).parent
    required_files = [
        'tests/test_visual_regression.py',
        'page_objects/base.py',
        'utils/auth_helpers.py'
    ]
    
    missing_files = []
    
    for file_path in required_files:
        full_path = test_dir / file_path
        if not full_path.exists():
            missing_files.append(file_path)
    
    if missing_files:
        logger.error(f"Missing test files: {missing_files}")
        return False
    
    logger.info("Test structure validation passed")
    return True

def main():
    """Main function"""
    
    logger.info("Starting visual regression test validation")
    
    # Validate test structure
    if not validate_test_structure():
        logger.error("Test structure validation failed")
        sys.exit(1)
    
    # Run visual regression tests
    if run_visual_tests():
        logger.info("Visual regression testing validation successful!")
        sys.exit(0)
    else:
        logger.error("Visual regression testing validation failed!")
        sys.exit(1)

if __name__ == "__main__":
    main()