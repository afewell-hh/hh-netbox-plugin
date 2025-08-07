"""
Django Management Command for FGD Ingestion Diagnostic
=====================================================

This command manually triggers the FGD ingestion process for the test fabric
to capture detailed logs and identify the exact failure point.

Target: Fabric ID 31 ("Test Fabric for GitOps Initialization")
"""

from django.core.management.base import BaseCommand
from django.conf import settings
import logging
import sys
from pathlib import Path

# Set up comprehensive logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('/tmp/fgd_diagnostic.log')
    ]
)

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Execute diagnostic test for FGD ingestion process'

    def add_arguments(self, parser):
        parser.add_argument(
            '--fabric-id', 
            type=int, 
            default=31,
            help='Fabric ID to test (default: 31)'
        )

    def handle(self, *args, **options):
        """Execute diagnostic test for FGD ingestion"""
        fabric_id = options['fabric_id']
        
        try:
            self.stdout.write("=== FGD INGESTION DIAGNOSTIC TEST STARTING ===")
            logger.info("=== FGD INGESTION DIAGNOSTIC TEST STARTING ===")
            
            # Import Django models
            from netbox_hedgehog.models import Fabric
            from netbox_hedgehog.services.gitops_onboarding_service import GitOpsOnboardingService
            
            # Find the target fabric
            self.stdout.write(f"Looking for fabric (ID {fabric_id})...")
            logger.info(f"Looking for test fabric (ID {fabric_id})...")
            
            try:
                fabric = Fabric.objects.get(id=fabric_id)
                self.stdout.write(f"✅ Found fabric: {fabric.name} (ID: {fabric.id})")
                logger.info(f"Found fabric: {fabric.name} (ID: {fabric.id})")
                
                self.stdout.write(f"Fabric details:")
                self.stdout.write(f"  - Name: {fabric.name}")
                self.stdout.write(f"  - GitOps Directory: {fabric.gitops_directory}")
                self.stdout.write(f"  - Kubernetes Namespace: {fabric.kubernetes_namespace}")
                self.stdout.write(f"  - Created: {fabric.created}")
                
                logger.info(f"Fabric details:")
                logger.info(f"  - Name: {fabric.name}")
                logger.info(f"  - GitOps Directory: {fabric.gitops_directory}")
                logger.info(f"  - Kubernetes Namespace: {fabric.kubernetes_namespace}")
                logger.info(f"  - Created: {fabric.created}")
                
            except Fabric.DoesNotExist:
                self.stdout.write(f"❌ Fabric with ID {fabric_id} not found!")
                logger.error(f"Fabric with ID {fabric_id} not found!")
                self.stdout.write("Available fabrics:")
                for f in Fabric.objects.all():
                    self.stdout.write(f"  - ID {f.id}: {f.name}")
                    logger.info(f"  - ID {f.id}: {f.name}")
                return
            except Exception as e:
                self.stdout.write(f"❌ Error retrieving fabric: {e}")
                logger.error(f"Error retrieving fabric: {e}")
                import traceback
                logger.error(f"Traceback: {traceback.format_exc()}")
                return
            
            # Create GitOps onboarding service
            self.stdout.write("Creating GitOpsOnboardingService...")
            logger.info("Creating GitOpsOnboardingService...")
            
            try:
                onboarding_service = GitOpsOnboardingService(fabric)
                self.stdout.write("✅ GitOpsOnboardingService created successfully")
                logger.info("GitOpsOnboardingService created successfully")
                
                # Check service initialization
                self.stdout.write("Service paths:")
                self.stdout.write(f"  - Base path: {onboarding_service.base_path}")
                self.stdout.write(f"  - Raw path: {onboarding_service.raw_path}")
                self.stdout.write(f"  - Managed path: {onboarding_service.managed_path}")
                self.stdout.write(f"  - Metadata path: {onboarding_service.metadata_path}")
                
                logger.info("Service paths:")
                logger.info(f"  - Base path: {onboarding_service.base_path}")
                logger.info(f"  - Raw path: {onboarding_service.raw_path}")
                logger.info(f"  - Managed path: {onboarding_service.managed_path}")
                logger.info(f"  - Metadata path: {onboarding_service.metadata_path}")
                
            except Exception as e:
                self.stdout.write(f"❌ Failed to create GitOpsOnboardingService: {e}")
                logger.error(f"Failed to create GitOpsOnboardingService: {e}")
                import traceback
                logger.error(f"Traceback: {traceback.format_exc()}")
                return
            
            # Check if GitOps directory structure exists
            self.stdout.write("Checking GitOps directory structure...")
            logger.info("Checking GitOps directory structure...")
            
            try:
                base_path = Path(onboarding_service.base_path)
                raw_path = Path(onboarding_service.raw_path)
                managed_path = Path(onboarding_service.managed_path)
                
                self.stdout.write(f"Base path exists: {base_path.exists()}")
                self.stdout.write(f"Raw path exists: {raw_path.exists()}")
                self.stdout.write(f"Managed path exists: {managed_path.exists()}")
                
                logger.info(f"Base path exists: {base_path.exists()}")
                logger.info(f"Raw path exists: {raw_path.exists()}")
                logger.info(f"Managed path exists: {managed_path.exists()}")
                
                if raw_path.exists():
                    raw_files = list(raw_path.glob('*.yaml')) + list(raw_path.glob('*.yml'))
                    self.stdout.write(f"Files in raw directory: {len(raw_files)}")
                    logger.info(f"Files in raw directory: {len(raw_files)}")
                    
                    for f in raw_files:
                        file_size = f.stat().st_size
                        self.stdout.write(f"  - {f.name} ({file_size} bytes)")
                        logger.info(f"  - {f.name} ({file_size} bytes)")
                else:
                    self.stdout.write("⚠️  Raw directory does not exist!")
                    logger.warning("Raw directory does not exist!")
                    
            except Exception as e:
                self.stdout.write(f"❌ Error checking directory structure: {e}")
                logger.error(f"Error checking directory structure: {e}")
                import traceback
                logger.error(f"Traceback: {traceback.format_exc()}")
            
            # Test the ingestion process
            self.stdout.write("=== STARTING INGESTION TEST ===")
            logger.info("=== STARTING INGESTION TEST ===")
            
            try:
                result = onboarding_service._execute_ingestion_with_validation()
                self.stdout.write(f"Ingestion result: {result}")
                logger.info(f"Ingestion result: {result}")
                
                if result.get('success'):
                    self.stdout.write("✅ Ingestion completed successfully!")
                    logger.info("✅ Ingestion completed successfully!")
                    self.stdout.write(f"Documents extracted: {len(result.get('documents_extracted', []))}")
                    self.stdout.write(f"Files created: {len(result.get('files_created', []))}")
                    logger.info(f"Documents extracted: {len(result.get('documents_extracted', []))}")
                    logger.info(f"Files created: {len(result.get('files_created', []))}")
                else:
                    self.stdout.write("❌ Ingestion failed!")
                    logger.error("❌ Ingestion failed!")
                    error_msg = result.get('error', 'Unknown error')
                    self.stdout.write(f"Error: {error_msg}")
                    logger.error(f"Error: {error_msg}")
                    
            except Exception as e:
                self.stdout.write(f"❌ Exception during ingestion test: {e}")
                logger.error(f"Exception during ingestion test: {e}")
                import traceback
                logger.error(f"Full traceback: {traceback.format_exc()}")
                return
            
            # Final verification
            self.stdout.write("=== FINAL VERIFICATION ===")
            logger.info("=== FINAL VERIFICATION ===")
            
            try:
                managed_files = list(Path(onboarding_service.managed_path).glob('**/*.yaml'))
                self.stdout.write(f"Final managed files count: {len(managed_files)}")
                logger.info(f"Final managed files count: {len(managed_files)}")
                
                for f in managed_files:
                    self.stdout.write(f"  - {f}")
                    logger.info(f"  - {f}")
                    
            except Exception as e:
                self.stdout.write(f"❌ Error in final verification: {e}")
                logger.error(f"Error in final verification: {e}")
            
            self.stdout.write("=== FGD INGESTION DIAGNOSTIC TEST COMPLETED ===")
            logger.info("=== FGD INGESTION DIAGNOSTIC TEST COMPLETED ===")
            self.stdout.write("📄 Full diagnostic log saved to: /tmp/fgd_diagnostic.log")
            
        except Exception as e:
            self.stdout.write(f"❌ Diagnostic test failed: {e}")
            logger.error(f"Diagnostic test failed: {e}")
            import traceback
            logger.error(f"Full traceback: {traceback.format_exc()}")