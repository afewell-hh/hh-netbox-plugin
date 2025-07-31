
from django.http import HttpResponse, JsonResponse
from django.views import View
from .models import HedgehogFabric
from .models.vpc_api import VPC

class SimpleGitView(View):
    def get(self, request, *args, **kwargs):
        return HttpResponse("<h1>Simple Git Repository Test</h1><p>This is a minimal test view.</p>")

class VPCCountTestView(View):
    """Simple test view to debug VPC count issues"""
    
    def get(self, request):
        try:
            # Test VPC count
            vpc_count = VPC.objects.count()
            vpc_list = list(VPC.objects.values('id', 'name', 'kubernetes_status'))
            
            # Test Fabric count
            fabric_count = HedgehogFabric.objects.count()
            fabric_list = list(HedgehogFabric.objects.values('id', 'name'))
            
            return JsonResponse({
                'status': 'success',
                'vpc_count': vpc_count,
                'vpc_list': vpc_list,
                'fabric_count': fabric_count,
                'fabric_list': fabric_list,
                'test_message': 'VPC count debug test successful'
            })
            
        except Exception as e:
            return JsonResponse({
                'status': 'error',
                'error': str(e),
                'error_type': type(e).__name__
            }, status=500)

class VPCCountHtmlView(View):
    """HTML view to debug VPC count issues"""
    
    def get(self, request):
        try:
            # Test VPC count
            vpc_count = VPC.objects.count()
            vpc_list = list(VPC.objects.all())
            
            # Test Fabric count
            fabric_count = HedgehogFabric.objects.count()
            fabric_list = list(HedgehogFabric.objects.all())
            
            html = f"""
            <html>
            <head><title>VPC Count Debug</title></head>
            <body>
                <h1>VPC Count Debug Results</h1>
                <h2>Counts:</h2>
                <p><strong>VPC Count:</strong> {vpc_count}</p>
                <p><strong>Fabric Count:</strong> {fabric_count}</p>
                
                <h2>VPCs:</h2>
                <ul>
                {''.join([f'<li>VPC {vpc.id}: {vpc.name} (Status: {vpc.kubernetes_status})</li>' for vpc in vpc_list])}
                </ul>
                
                <h2>Fabrics:</h2>
                <ul>
                {''.join([f'<li>Fabric {fabric.id}: {fabric.name}</li>' for fabric in fabric_list])}
                </ul>
                
                <h2>Template Test:</h2>
                <p>VPC Count in h2: <h2>{vpc_count}</h2></p>
                <p>VPC Count in span: <span>{vpc_count}</span></p>
                <p>VPC Count as string: "{str(vpc_count)}"</p>
            </body>
            </html>
            """
            
            return HttpResponse(html)
            
        except Exception as e:
            import traceback
            error_html = f"""
            <html>
            <head><title>VPC Count Debug - ERROR</title></head>
            <body>
                <h1>ERROR</h1>
                <p><strong>Error:</strong> {str(e)}</p>
                <p><strong>Type:</strong> {type(e).__name__}</p>
                <pre>{traceback.format_exc()}</pre>
            </body>
            </html>
            """
            return HttpResponse(error_html)
