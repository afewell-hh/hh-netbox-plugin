"""
Agent Productivity Dashboard Views - Issue #25
Real-time monitoring and visualization of agent productivity metrics
"""

import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any

from django.shortcuts import render
from django.http import JsonResponse, HttpResponse
from django.views import View
from django.views.generic import TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.utils import timezone
from django.conf import settings

from ..tests.framework.agent_productivity_measurement import (
    AgentProductivityMeasurement,
    AgentType,
    MeasurementMode,
    TaskComplexity
)


class ProductivityDashboardView(LoginRequiredMixin, TemplateView):
    """Main productivity dashboard view"""
    template_name = 'netbox_hedgehog/productivity_dashboard.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get productivity measurement framework
        measurement = AgentProductivityMeasurement()
        dashboard_data = measurement.generate_dashboard_data()
        
        context.update({
            'page_title': 'Agent Productivity Dashboard',
            'dashboard_data': dashboard_data,
            'agent_types': [agent.value for agent in AgentType],
            'measurement_modes': [mode.value for mode in MeasurementMode],
            'task_complexities': [complexity.value for complexity in TaskComplexity],
            'refresh_interval': 30,  # seconds
        })
        
        return context


class ProductivityMetricsAPIView(View):
    """API endpoint for real-time productivity metrics"""
    
    def get(self, request):
        """Return current productivity metrics as JSON"""
        try:
            # Get query parameters
            agent_type = request.GET.get('agent_type')
            mode = request.GET.get('mode')
            time_range = request.GET.get('time_range', '24h')
            
            # Initialize measurement framework
            measurement = AgentProductivityMeasurement()
            
            # Generate dashboard data
            dashboard_data = measurement.generate_dashboard_data()
            
            # Filter data based on parameters
            if agent_type:
                filtered_data = self._filter_by_agent_type(dashboard_data, agent_type)
            elif mode:
                filtered_data = self._filter_by_mode(dashboard_data, mode)
            else:
                filtered_data = dashboard_data
            
            # Add real-time metrics
            realtime_metrics = self._get_realtime_metrics(measurement, time_range)
            filtered_data['realtime'] = realtime_metrics
            
            return JsonResponse({
                'success': True,
                'data': filtered_data,
                'timestamp': timezone.now().isoformat(),
                'time_range': time_range
            })
            
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e),
                'timestamp': timezone.now().isoformat()
            }, status=500)
    
    def _filter_by_agent_type(self, data: Dict[str, Any], agent_type: str) -> Dict[str, Any]:
        """Filter dashboard data by agent type"""
        filtered = data.copy()
        by_agent = data.get('by_agent_type', {})
        
        if agent_type in by_agent:
            filtered['by_agent_type'] = {agent_type: by_agent[agent_type]}
        
        return filtered
    
    def _filter_by_mode(self, data: Dict[str, Any], mode: str) -> Dict[str, Any]:
        """Filter dashboard data by measurement mode"""
        filtered = data.copy()
        by_mode = data.get('by_mode', {})
        
        if mode in by_mode:
            filtered['by_mode'] = {mode: by_mode[mode]}
        
        return filtered
    
    def _get_realtime_metrics(self, measurement: AgentProductivityMeasurement, 
                            time_range: str) -> Dict[str, Any]:
        """Get real-time metrics for specified time range"""
        
        # Parse time range
        if time_range == '1h':
            since = timezone.now() - timedelta(hours=1)
        elif time_range == '24h':
            since = timezone.now() - timedelta(days=1)
        elif time_range == '7d':
            since = timezone.now() - timedelta(days=7)
        else:
            since = timezone.now() - timedelta(days=1)  # Default to 24h
        
        # Get recent executions
        recent_executions = [
            e for e in measurement.executions 
            if e.start_time >= since.replace(tzinfo=None)
        ]
        
        if not recent_executions:
            return {'message': f'No executions in the last {time_range}'}
        
        # Calculate real-time metrics
        total_executions = len(recent_executions)
        successful_executions = sum(1 for e in recent_executions if e.success)
        success_rate = successful_executions / total_executions if total_executions > 0 else 0
        
        # Calculate average completion time
        completion_times = [e.completion_time_seconds for e in recent_executions if e.completion_time_seconds]
        avg_completion_time = sum(completion_times) / len(completion_times) if completion_times else 0
        
        # Group by hour for trend data
        hourly_data = self._group_executions_by_hour(recent_executions, since)
        
        return {
            'total_executions': total_executions,
            'successful_executions': successful_executions,
            'success_rate': success_rate,
            'avg_completion_time': avg_completion_time,
            'hourly_trend': hourly_data,
            'time_range': time_range
        }
    
    def _group_executions_by_hour(self, executions, since):
        """Group executions by hour for trend visualization"""
        from collections import defaultdict
        
        hourly_data = defaultdict(lambda: {'total': 0, 'successful': 0})
        
        for execution in executions:
            hour_key = execution.start_time.strftime('%Y-%m-%d %H:00')
            hourly_data[hour_key]['total'] += 1
            if execution.success:
                hourly_data[hour_key]['successful'] += 1
        
        # Convert to list format for charts
        trend_data = []
        for hour, data in sorted(hourly_data.items()):
            success_rate = data['successful'] / data['total'] if data['total'] > 0 else 0
            trend_data.append({
                'hour': hour,
                'total_executions': data['total'],
                'success_rate': success_rate
            })
        
        return trend_data


class StartMeasurementAPIView(View):
    """API endpoint to start new productivity measurements"""
    
    def post(self, request):
        """Start a new measurement session"""
        try:
            data = json.loads(request.body)
            
            agent_type = data.get('agent_type')
            scenarios = data.get('scenarios', [])
            iterations = data.get('iterations', 5)
            mode = data.get('mode', 'comparison')
            
            # Validate inputs
            if agent_type and agent_type not in [a.value for a in AgentType]:
                return JsonResponse({
                    'success': False,
                    'error': f'Invalid agent type: {agent_type}'
                }, status=400)
            
            # Initialize measurement framework
            measurement = AgentProductivityMeasurement()
            
            if mode == 'comparison' and agent_type:
                # Run comparison measurement
                agent = AgentType(agent_type)
                result = measurement.run_productivity_comparison(
                    scenario_ids=scenarios or measurement._get_default_scenarios(agent),
                    agent_type=agent,
                    iterations=iterations
                )
                
                return JsonResponse({
                    'success': True,
                    'message': f'Comparison measurement started for {agent_type}',
                    'measurement_id': f"{agent_type}_{int(timezone.now().timestamp())}",
                    'result_summary': {
                        'baseline_success_rate': result['statistical_significance']['baseline_success_rate'],
                        'sparc_success_rate': result['statistical_significance']['sparc_success_rate'],
                        'improvement': result['statistical_significance']['improvement']
                    }
                })
            
            else:
                return JsonResponse({
                    'success': False,
                    'error': 'Mode not implemented or missing parameters'
                }, status=400)
            
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=500)


class SPARCValidationAPIView(View):
    """API endpoint for SPARC methodology validation"""
    
    def get(self, request):
        """Get current SPARC validation status"""
        try:
            measurement = AgentProductivityMeasurement()
            dashboard_data = measurement.generate_dashboard_data()
            
            # Calculate SPARC validation metrics
            validation_results = self._calculate_sparc_validation(dashboard_data)
            
            return JsonResponse({
                'success': True,
                'validation': validation_results,
                'timestamp': timezone.now().isoformat()
            })
            
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=500)
    
    def _calculate_sparc_validation(self, dashboard_data: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate SPARC methodology validation status"""
        by_mode = dashboard_data.get('by_mode', {})
        
        baseline_metrics = by_mode.get('baseline', {})
        sparc_metrics = by_mode.get('sparc', {})
        
        if not baseline_metrics or not sparc_metrics:
            return {
                'status': 'insufficient_data',
                'message': 'Need both baseline and SPARC measurements for validation'
            }
        
        baseline_rate = baseline_metrics.get('success_rate', 0)
        sparc_rate = sparc_metrics.get('success_rate', 0)
        improvement = sparc_rate - baseline_rate
        
        # Check validation criteria
        criteria_met = {
            'minimum_baseline': baseline_rate >= 0.25,  # At least 25% baseline
            'sparc_target': sparc_rate >= 0.75,         # At least 75% with SPARC
            'significant_improvement': improvement >= 0.40,  # At least 40% improvement
            'sufficient_samples': (baseline_metrics.get('total', 0) >= 10 and 
                                 sparc_metrics.get('total', 0) >= 10)
        }
        
        all_criteria_met = all(criteria_met.values())
        
        return {
            'status': 'validated' if all_criteria_met else 'not_validated',
            'baseline_success_rate': baseline_rate,
            'sparc_success_rate': sparc_rate,
            'improvement': improvement,
            'improvement_percent': (improvement / baseline_rate * 100) if baseline_rate > 0 else 0,
            'criteria_met': criteria_met,
            'overall_validated': all_criteria_met,
            'sample_sizes': {
                'baseline': baseline_metrics.get('total', 0),
                'sparc': sparc_metrics.get('total', 0)
            }
        }


class ExportProductivityDataView(View):
    """Export productivity data in various formats"""
    
    def get(self, request):
        """Export data based on format parameter"""
        format_type = request.GET.get('format', 'json')
        time_range = request.GET.get('time_range', '24h')
        
        try:
            measurement = AgentProductivityMeasurement()
            dashboard_data = measurement.generate_dashboard_data()
            
            if format_type == 'json':
                return JsonResponse(dashboard_data)
            
            elif format_type == 'csv':
                return self._export_csv(dashboard_data)
            
            elif format_type == 'report':
                return self._export_report(dashboard_data, time_range)
            
            else:
                return JsonResponse({
                    'error': f'Unsupported format: {format_type}'
                }, status=400)
                
        except Exception as e:
            return JsonResponse({
                'error': str(e)
            }, status=500)
    
    def _export_csv(self, dashboard_data: Dict[str, Any]) -> HttpResponse:
        """Export data as CSV"""
        import csv
        from io import StringIO
        
        output = StringIO()
        writer = csv.writer(output)
        
        # Write headers
        writer.writerow([
            'Agent Type', 'Measurement Mode', 'Success Rate', 
            'Total Executions', 'Avg Completion Time'
        ])
        
        # Write agent type data
        for agent_type, metrics in dashboard_data.get('by_agent_type', {}).items():
            writer.writerow([
                agent_type, 'combined', 
                f"{metrics.get('success_rate', 0):.2%}",
                metrics.get('total', 0),
                f"{metrics.get('avg_completion_time', 0):.2f}s"
            ])
        
        # Write mode data
        for mode, metrics in dashboard_data.get('by_mode', {}).items():
            writer.writerow([
                'all', mode,
                f"{metrics.get('success_rate', 0):.2%}",
                metrics.get('total', 0),
                f"{metrics.get('avg_completion_time', 0):.2f}s"
            ])
        
        response = HttpResponse(
            output.getvalue(),
            content_type='text/csv'
        )
        response['Content-Disposition'] = 'attachment; filename="productivity_data.csv"'
        
        return response
    
    def _export_report(self, dashboard_data: Dict[str, Any], time_range: str) -> HttpResponse:
        """Export data as formatted report"""
        
        summary = dashboard_data.get('summary', {})
        
        report = f"""# Agent Productivity Report
Generated: {timezone.now().strftime('%Y-%m-%d %H:%M:%S')}
Time Range: {time_range}

## Summary
- Total Executions: {summary.get('total_executions', 0)}
- Overall Success Rate: {summary.get('overall_success_rate', 0):.2%}
- Recent Success Rate: {summary.get('recent_success_rate', 0):.2%}

## By Agent Type
"""
        
        for agent_type, metrics in dashboard_data.get('by_agent_type', {}).items():
            report += f"""
### {agent_type.title()}
- Success Rate: {metrics.get('success_rate', 0):.2%}
- Total Executions: {metrics.get('total', 0)}
- Avg Completion Time: {metrics.get('avg_completion_time', 0):.2f}s
"""
        
        report += "\n## By Measurement Mode\n"
        
        for mode, metrics in dashboard_data.get('by_mode', {}).items():
            report += f"""
### {mode.title()}
- Success Rate: {metrics.get('success_rate', 0):.2%}
- Total Executions: {metrics.get('total', 0)}
- Avg Completion Time: {metrics.get('avg_completion_time', 0):.2f}s
"""
        
        response = HttpResponse(
            report,
            content_type='text/markdown'
        )
        response['Content-Disposition'] = 'attachment; filename="productivity_report.md"'
        
        return response


# URL patterns for productivity dashboard
from django.urls import path

productivity_urls = [
    path('productivity/', ProductivityDashboardView.as_view(), name='productivity_dashboard'),
    path('api/productivity/metrics/', ProductivityMetricsAPIView.as_view(), name='productivity_metrics_api'),
    path('api/productivity/start/', StartMeasurementAPIView.as_view(), name='start_measurement_api'),
    path('api/productivity/validation/', SPARCValidationAPIView.as_view(), name='sparc_validation_api'),
    path('api/productivity/export/', ExportProductivityDataView.as_view(), name='export_productivity_data'),
]