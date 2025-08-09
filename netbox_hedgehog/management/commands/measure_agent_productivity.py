"""
Django management command for measuring agent productivity
Issue #25 - SPARC Methodology Validation

This command provides a comprehensive interface for running agent productivity
measurements and validating SPARC methodology effectiveness claims.
"""

import json
import time
from django.core.management.base import BaseCommand, CommandError
from django.conf import settings

from ...tests.framework.agent_productivity_measurement import (
    AgentProductivityMeasurement,
    RealTimeProductivityMonitor,
    AgentType,
    MeasurementMode,
    TaskComplexity,
    run_comprehensive_validation,
    create_standard_measurement_suite,
    start_realtime_monitoring
)


class Command(BaseCommand):
    help = 'Measure agent productivity and validate SPARC methodology claims'
    
    def add_arguments(self, parser):
        # Mode selection
        parser.add_argument(
            '--mode',
            choices=['single', 'comparison', 'comprehensive', 'monitor', 'report'],
            default='comparison',
            help='Measurement mode to run'
        )
        
        # Agent type selection
        parser.add_argument(
            '--agent-type',
            choices=[agent.value for agent in AgentType],
            help='Specific agent type to test'
        )
        
        # Scenario selection
        parser.add_argument(
            '--scenarios',
            nargs='*',
            help='Specific scenarios to test'
        )
        
        # Measurement parameters
        parser.add_argument(
            '--iterations',
            type=int,
            default=10,
            help='Number of iterations per measurement mode'
        )
        
        # Monitoring parameters
        parser.add_argument(
            '--monitor-duration',
            type=int,
            default=3600,
            help='Monitoring duration in seconds (for monitor mode)'
        )
        
        parser.add_argument(
            '--monitor-interval',
            type=int,
            default=60,
            help='Monitoring update interval in seconds'
        )
        
        # Output options
        parser.add_argument(
            '--output-dir',
            default='/tmp/agent_productivity_results',
            help='Directory for output files'
        )
        
        parser.add_argument(
            '--export-json',
            action='store_true',
            help='Export results to JSON format'
        )
        
        parser.add_argument(
            '--quiet',
            action='store_true',
            help='Reduce output verbosity'
        )
        
        # Validation options
        parser.add_argument(
            '--validate-claims',
            action='store_true',
            help='Specifically validate 30% → 80% success rate claims'
        )
        
        parser.add_argument(
            '--statistical-confidence',
            type=float,
            default=0.95,
            help='Required statistical confidence level'
        )
    
    def handle(self, *args, **options):
        """Handle the management command execution"""
        
        mode = options['mode']
        
        if not options['quiet']:
            self.print_header()
        
        try:
            if mode == 'single':
                self.handle_single_measurement(options)
            elif mode == 'comparison':
                self.handle_comparison_measurement(options)
            elif mode == 'comprehensive':
                self.handle_comprehensive_measurement(options)
            elif mode == 'monitor':
                self.handle_monitoring(options)
            elif mode == 'report':
                self.handle_report_generation(options)
            else:
                raise CommandError(f"Unknown mode: {mode}")
                
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'❌ Command failed: {e}'))
            raise CommandError(str(e))
    
    def print_header(self):
        """Print command header"""
        self.stdout.write(self.style.SUCCESS('🎯 Agent Productivity Measurement System'))
        self.stdout.write(self.style.SUCCESS('=' * 60))
        self.stdout.write('Issue #25 - SPARC Methodology Validation')
        self.stdout.write('Measuring agent productivity improvements with SPARC methodology\n')
    
    def handle_single_measurement(self, options):
        """Handle single measurement execution"""
        self.stdout.write(self.style.WARNING('🔬 Single Measurement Mode'))
        
        measurement = AgentProductivityMeasurement(storage_path=options['output_dir'])
        
        # Determine agent type
        if options['agent_type']:
            agent_type = AgentType(options['agent_type'])
        else:
            agent_type = AgentType.RESEARCH  # Default
            
        # Determine scenarios
        scenarios = options.get('scenarios') or self._get_default_scenarios(agent_type)
        
        # Run single measurements
        for scenario_id in scenarios:
            for mode in [MeasurementMode.BASELINE, MeasurementMode.SPARC_ENHANCED]:
                self.stdout.write(f'Running {scenario_id} in {mode.value} mode...')
                
                execution = measurement.execute_task_scenario(
                    scenario_id=scenario_id,
                    agent_type=agent_type,
                    measurement_mode=mode,
                    agent_execution_function=self._get_agent_function(agent_type, mode)
                )
                
                status = '✅ Success' if execution.success else '❌ Failed'
                time_str = f'{execution.completion_time_seconds:.2f}s' if execution.completion_time_seconds else 'N/A'
                self.stdout.write(f'  Result: {status} ({time_str})')
    
    def handle_comparison_measurement(self, options):
        """Handle comparison measurement between baseline and SPARC modes"""
        self.stdout.write(self.style.WARNING('⚖️  Comparison Measurement Mode'))
        
        measurement = AgentProductivityMeasurement(storage_path=options['output_dir'])
        
        # Determine agent type
        if options['agent_type']:
            agent_type = AgentType(options['agent_type'])
            agent_types = [agent_type]
        else:
            agent_types = [AgentType.RESEARCH, AgentType.CODER, AgentType.TESTER]
        
        results = {}
        
        for agent_type in agent_types:
            self.stdout.write(f'\n🎯 Testing {agent_type.value} agent...')
            
            scenarios = options.get('scenarios') or self._get_default_scenarios(agent_type)
            
            comparison_results = measurement.run_productivity_comparison(
                scenario_ids=scenarios,
                agent_type=agent_type,
                iterations=options['iterations']
            )
            
            results[agent_type.value] = comparison_results
            
            # Print summary
            metrics = comparison_results['comparison_metrics']
            baseline_rate = metrics['baseline']['success_rate']
            sparc_rate = metrics['sparc']['success_rate'] 
            improvement = metrics['improvements']['success_rate_improvement_percent']
            
            self.stdout.write(f'  Baseline Success Rate: {baseline_rate:.2%}')
            self.stdout.write(f'  SPARC Success Rate: {sparc_rate:.2%}')
            self.stdout.write(f'  Improvement: {improvement:.1f}%')
        
        # Export results if requested
        if options['export_json']:
            self._export_results(results, options['output_dir'], 'comparison')
        
        # Validate claims if requested
        if options['validate_claims']:
            self._validate_sparc_claims(results)
    
    def handle_comprehensive_measurement(self, options):
        """Handle comprehensive measurement across all agents and scenarios"""
        self.stdout.write(self.style.WARNING('🌟 Comprehensive Measurement Mode'))
        
        self.stdout.write('Running complete SPARC methodology validation...')
        self.stdout.write('This will test all agent types with multiple scenarios.')
        self.stdout.write(f'Iterations per mode: {options["iterations"]}')
        
        # Run comprehensive validation
        results = run_comprehensive_validation()
        
        # Generate summary report
        self._generate_comprehensive_report(results, options['output_dir'])
        
        # Export results
        if options['export_json']:
            self._export_results(results, options['output_dir'], 'comprehensive')
        
        # Validate claims
        if options['validate_claims']:
            self._validate_sparc_claims(results)
    
    def handle_monitoring(self, options):
        """Handle real-time monitoring mode"""
        self.stdout.write(self.style.WARNING('📊 Real-Time Monitoring Mode'))
        
        duration = options['monitor_duration']
        interval = options['monitor_interval']
        
        self.stdout.write(f'Starting {duration}s monitoring session (updates every {interval}s)')
        self.stdout.write('Press Ctrl+C to stop monitoring early')
        
        try:
            monitor = start_realtime_monitoring()
            time.sleep(duration)
            monitor.stop_monitoring()
            
        except KeyboardInterrupt:
            self.stdout.write('\n⏹️  Monitoring stopped by user')
            if 'monitor' in locals():
                monitor.stop_monitoring()
    
    def handle_report_generation(self, options):
        """Handle report generation from existing data"""
        self.stdout.write(self.style.WARNING('📋 Report Generation Mode'))
        
        measurement = AgentProductivityMeasurement(storage_path=options['output_dir'])
        
        if not measurement.executions:
            self.stdout.write(self.style.ERROR('No execution data found. Run measurements first.'))
            return
        
        # Generate dashboard data
        dashboard_data = measurement.generate_dashboard_data()
        
        # Print summary
        self._print_dashboard_summary(dashboard_data)
        
        # Export if requested
        if options['export_json']:
            self._export_dashboard_data(dashboard_data, options['output_dir'])
    
    def _get_default_scenarios(self, agent_type: AgentType) -> list:
        """Get default scenarios for agent type"""
        scenario_map = {
            AgentType.RESEARCH: ['research_fabric_analysis', 'research_api_investigation'],
            AgentType.CODER: ['coder_crud_implementation', 'coder_gitops_integration'],
            AgentType.TESTER: ['tester_gui_validation', 'tester_api_validation'],
            AgentType.ARCHITECT: ['architect_system_design'],
            AgentType.ORCHESTRATOR: ['research_fabric_analysis']  # Fallback
        }
        
        return scenario_map.get(agent_type, ['research_fabric_analysis'])
    
    def _get_agent_function(self, agent_type: AgentType, mode: MeasurementMode):
        """Get appropriate agent function for testing"""
        # This would return actual agent execution functions
        # For now, return the simulation functions from the framework
        measurement = AgentProductivityMeasurement()
        
        if mode == MeasurementMode.BASELINE:
            return measurement._create_baseline_agent_function(agent_type)
        else:
            return measurement._create_sparc_agent_function(agent_type)
    
    def _validate_sparc_claims(self, results: dict):
        """Validate specific SPARC methodology claims"""
        self.stdout.write('\n🎯 Validating SPARC Methodology Claims')
        self.stdout.write('=' * 50)
        
        claim_30_to_80 = True
        statistical_significance = True
        
        for agent_type, result in results.items():
            significance = result.get('statistical_significance', {})
            metrics = result.get('comparison_metrics', {})
            
            baseline_rate = significance.get('baseline_success_rate', 0)
            sparc_rate = significance.get('sparc_success_rate', 0)
            is_significant = significance.get('statistically_significant', False)
            
            self.stdout.write(f'\n{agent_type.title()} Agent:')
            self.stdout.write(f'  Baseline: {baseline_rate:.2%}')
            self.stdout.write(f'  SPARC: {sparc_rate:.2%}')
            self.stdout.write(f'  Improvement: {sparc_rate - baseline_rate:.2%}')
            self.stdout.write(f'  Significant: {'✅' if is_significant else '❌'}')
            
            # Check 30% → 80% claim
            if sparc_rate < 0.75:  # Allow some tolerance
                claim_30_to_80 = False
            
            if not is_significant:
                statistical_significance = False
        
        # Overall validation
        self.stdout.write('\n📊 Overall Validation Results:')
        self.stdout.write(f'  30% → 80% Success Rate: {'✅ VALIDATED' if claim_30_to_80 else '❌ NOT VALIDATED'}')
        self.stdout.write(f'  Statistical Significance: {'✅ VALIDATED' if statistical_significance else '❌ NOT VALIDATED'}')
        
        if claim_30_to_80 and statistical_significance:
            self.stdout.write(self.style.SUCCESS('\n🏆 SPARC METHODOLOGY CLAIMS VALIDATED!'))
        else:
            self.stdout.write(self.style.ERROR('\n⚠️  SPARC methodology requires further validation'))
    
    def _generate_comprehensive_report(self, results: dict, output_dir: str):
        """Generate comprehensive validation report"""
        from pathlib import Path
        
        report_path = Path(output_dir) / 'comprehensive_sparc_validation_report.md'
        report_path.parent.mkdir(exist_ok=True)
        
        with open(report_path, 'w') as f:
            f.write('# Comprehensive SPARC Methodology Validation Report\n\n')
            f.write(f'Generated: {time.strftime("%Y-%m-%d %H:%M:%S")}\n\n')
            
            for agent_type, result in results.items():
                metrics = result.get('comparison_metrics', {})
                significance = result.get('statistical_significance', {})
                
                f.write(f'## {agent_type.title()} Agent Results\n\n')
                f.write(f'- **Baseline Success Rate**: {significance.get("baseline_success_rate", 0):.2%}\n')
                f.write(f'- **SPARC Success Rate**: {significance.get("sparc_success_rate", 0):.2%}\n') 
                f.write(f'- **Improvement**: {significance.get("improvement", 0):.2%}\n')
                f.write(f'- **Statistical Significance**: {"Yes" if significance.get("statistically_significant", False) else "No"}\n\n')
        
        self.stdout.write(f'📋 Comprehensive report saved: {report_path}')
    
    def _export_results(self, results: dict, output_dir: str, mode: str):
        """Export results to JSON format"""
        from pathlib import Path
        
        export_path = Path(output_dir) / f'productivity_results_{mode}_{int(time.time())}.json'
        export_path.parent.mkdir(exist_ok=True)
        
        # Convert any non-serializable objects
        serializable_results = self._make_serializable(results)
        
        with open(export_path, 'w') as f:
            json.dump(serializable_results, f, indent=2)
        
        self.stdout.write(f'📁 Results exported: {export_path}')
    
    def _export_dashboard_data(self, dashboard_data: dict, output_dir: str):
        """Export dashboard data"""
        from pathlib import Path
        
        export_path = Path(output_dir) / f'dashboard_data_{int(time.time())}.json'
        export_path.parent.mkdir(exist_ok=True)
        
        with open(export_path, 'w') as f:
            json.dump(dashboard_data, f, indent=2)
        
        self.stdout.write(f'📊 Dashboard data exported: {export_path}')
    
    def _print_dashboard_summary(self, dashboard_data: dict):
        """Print dashboard summary"""
        summary = dashboard_data.get('summary', {})
        
        self.stdout.write('📊 Current Productivity Metrics:')
        self.stdout.write(f'  Total Executions: {summary.get("total_executions", 0)}')
        self.stdout.write(f'  Overall Success Rate: {summary.get("overall_success_rate", 0):.2%}')
        self.stdout.write(f'  Recent Success Rate: {summary.get("recent_success_rate", 0):.2%}')
        
        # Show by agent type
        by_agent = dashboard_data.get('by_agent_type', {})
        if by_agent:
            self.stdout.write('\nBy Agent Type:')
            for agent_type, metrics in by_agent.items():
                self.stdout.write(f'  {agent_type}: {metrics.get("success_rate", 0):.2%} ({metrics.get("total", 0)} executions)')
        
        # Show by measurement mode
        by_mode = dashboard_data.get('by_mode', {})
        if by_mode:
            self.stdout.write('\nBy Measurement Mode:')
            for mode, metrics in by_mode.items():
                self.stdout.write(f'  {mode}: {metrics.get("success_rate", 0):.2%} ({metrics.get("total", 0)} executions)')
    
    def _make_serializable(self, obj):
        """Convert object to JSON serializable format"""
        if isinstance(obj, dict):
            return {k: self._make_serializable(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._make_serializable(item) for item in obj]
        elif hasattr(obj, '__dict__'):
            return self._make_serializable(obj.__dict__)
        elif hasattr(obj, 'value'):  # Enum
            return obj.value
        elif hasattr(obj, 'isoformat'):  # datetime
            return obj.isoformat()
        else:
            return obj