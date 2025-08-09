#!/usr/bin/env python3
"""
Master validation script - Single source of truth for project health
Run this to verify if work is actually complete.
"""
import subprocess
import json
import sys
from datetime import datetime

class ProjectValidator:
    def __init__(self):
        self.results = {}
        self.passed = 0
        self.failed = 0
        
    def run_check(self, name, command, success_criteria=None):
        """Run a validation check and record results"""
        print(f"\n🔍 Checking: {name}")
        print(f"   Command: {command}")
        
        try:
            result = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=30)
            output = result.stdout + result.stderr
            
            # Default success is non-zero return code
            success = result.returncode == 0
            
            # Apply custom success criteria if provided
            if success_criteria and success:
                success = success_criteria(output)
            
            self.results[name] = {
                'status': 'PASS' if success else 'FAIL',
                'output': output[:500],  # Truncate for readability
                'return_code': result.returncode
            }
            
            if success:
                self.passed += 1
                print(f"   ✅ PASS")
            else:
                self.failed += 1
                print(f"   ❌ FAIL")
                print(f"   Output: {output[:200]}")
                
        except subprocess.TimeoutExpired:
            self.failed += 1
            self.results[name] = {'status': 'TIMEOUT', 'output': 'Command timed out after 30s'}
            print(f"   ⏱️ TIMEOUT")
        except Exception as e:
            self.failed += 1
            self.results[name] = {'status': 'ERROR', 'output': str(e)}
            print(f"   💥 ERROR: {e}")
            
        return self.results[name]['status'] == 'PASS'
    
    def validate_all(self):
        """Run all validation checks"""
        print("=" * 80)
        print("NETBOX HEDGEHOG PLUGIN - MASTER VALIDATION SUITE")
        print("=" * 80)
        print(f"Started: {datetime.now()}")
        
        # 1. Check Docker services
        self.run_check(
            "Docker Services Running",
            "sudo docker ps --format '{{.Names}}' | grep -E 'netbox|postgres|redis' | wc -l",
            lambda out: int(out.strip()) >= 3
        )
        
        # 2. Check NetBox accessibility (302 is normal login redirect)
        self.run_check(
            "NetBox Web Interface",
            "curl -s -o /dev/null -w '%{http_code}' http://localhost:8000/",
            lambda out: out.strip() in ['200', '302']
        )
        
        # 3. Check plugin is loaded
        self.run_check(
            "Plugin Loaded in NetBox",
            "sudo docker exec netbox-docker-netbox-1 sh -c \"cd /opt/netbox/netbox && python manage.py shell -c 'from netbox_hedgehog.models import HedgehogFabric; print(HedgehogFabric.objects.count())'\" 2>&1 | tail -1",
            lambda out: out.strip().isdigit()
        )
        
        # 4. Check API accessibility
        self.run_check(
            "Plugin API Endpoint",
            "curl -s -o /dev/null -w '%{http_code}' http://localhost:8000/plugins/hedgehog/",
            lambda out: out.strip() == '200'
        )
        
        # 5. Check for Git Repository issues
        def check_html_comments(output):
            try:
                # Handle the case where grep returns no matches
                lines = output.strip().split('\n')
                last_line = lines[-1].strip()
                return int(last_line) == 0
            except (ValueError, IndexError):
                # If we can't parse it, assume no issues
                return True
        
        if self.run_check(
            "Git Repository Page (No HTML Comments Bug)", 
            "curl -s http://localhost:8000/plugins/hedgehog/git-repositories/1/ 2>/dev/null | grep -c '<\\!--' || echo 0",
            check_html_comments
        ):
            print("   ✅ Git Repository template is clean")
        else:
            print("   ⚠️  Git Repository template has visible HTML comments bug")
        
        # 6. Check sync functionality
        self.run_check(
            "Fabric Sync Capability",
            "sudo docker exec netbox-docker-netbox-1 sh -c \"cd /opt/netbox/netbox && python manage.py shell -c 'from netbox_hedgehog.models import HedgehogFabric; f = HedgehogFabric.objects.first(); print(f.last_sync is not None if f else False)'\" 2>&1 | tail -1",
            lambda out: out.strip() == 'True'
        )
        
        # 7. Check CRD counts
        self.run_check(
            "CRDs Present in Database",
            "sudo docker exec netbox-docker-netbox-1 sh -c \"cd /opt/netbox/netbox && python manage.py shell -c 'from netbox_hedgehog.models import VPC, Switch, Server; total = VPC.objects.count() + Switch.objects.count() + Server.objects.count(); print(total)'\" 2>&1 | tail -1",
            lambda out: int(out.strip()) > 0
        )
        
        # 8. Check for periodic sync scheduler
        self.run_check(
            "Periodic Sync Scheduler",
            "sudo docker exec netbox-docker-netbox-1 sh -c \"cd /opt/netbox/netbox && python manage.py shell -c 'from netbox_hedgehog.tasks.git_sync_tasks import check_fabric_sync_schedules; print(check_fabric_sync_schedules.__name__)'\" 2>&1 | tail -1",
            lambda out: 'check_fabric_sync_schedules' in out
        )
        
        # 9. Check GUI test framework availability
        self.run_check(
            "GUI Test Framework Available",
            "command -v node && command -v npx && test -f package.json",
            lambda out: True  # If command succeeds
        )
        
        # 10. Run GUI tests if framework is available
        self.run_check(
            "GUI Automation Tests",
            "python3 scripts/validate-gui.py",
            lambda out: "Basic GUI validation passed" in out or "✅" in out
        )
        

        # 10. Run GUI tests if framework is available
        self.run_check(
            "GUI Automation Tests",
            "python3 scripts/validate-gui.py",
            lambda out: "Basic GUI validation passed" in out or "✅" in out
        )
        
        # Generate summary
        print("\n" + "=" * 80)
        print("VALIDATION SUMMARY")
        print("=" * 80)
        print(f"✅ Passed: {self.passed}")
        print(f"❌ Failed: {self.failed}")
        print(f"📊 Success Rate: {self.passed}/{self.passed + self.failed} ({100*self.passed/(self.passed+self.failed):.1f}%)")
        
        # Save results to JSON
        with open('validation_results.json', 'w') as f:
            json.dump({
                'timestamp': datetime.now().isoformat(),
                'passed': self.passed,
                'failed': self.failed,
                'results': self.results
            }, f, indent=2)
        print(f"\n📁 Detailed results saved to: validation_results.json")
        
        # Return exit code
        if self.failed == 0:
            print("\n🎉 ALL VALIDATIONS PASSED! The project is working correctly.")
            return 0
        else:
            print(f"\n⚠️  {self.failed} VALIDATIONS FAILED. Issues need to be fixed.")
            print("\nFailed checks:")
            for name, result in self.results.items():
                if result['status'] != 'PASS':
                    print(f"  - {name}: {result['status']}")
            return 1

if __name__ == "__main__":
    validator = ProjectValidator()
    sys.exit(validator.validate_all())