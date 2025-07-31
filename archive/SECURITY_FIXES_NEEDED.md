
# Security Issues Found and Fixes Needed

## Issues:
1. Fabric list page accessible without authentication
2. Fabric detail page accessible without authentication  
3. Only edit page requires authentication

## Fixes Needed:

### 1. Add authentication to list views
Update netbox_hedgehog/urls.py:

```python
# Current (INSECURE):
path('fabrics/', FabricListView.as_view(), name='fabric_list'),

# Fixed (SECURE):
path('fabrics/', login_required(FabricListView.as_view()), name='fabric_list'),
```

### 2. Add authentication to detail views
```python
# Current (INSECURE):
path('fabrics/<int:pk>/', FabricDetailView.as_view(), name='fabric_detail'),

# Fixed (SECURE):
path('fabrics/<int:pk>/', login_required(FabricDetailView.as_view()), name='fabric_detail'),
```

### 3. Alternative: Use class-based authentication
```python
from django.contrib.auth.mixins import LoginRequiredMixin

class FabricListView(LoginRequiredMixin, ListView):
    model = HedgehogFabric
    # ... rest of view
```

## Testing:
After applying fixes, run:
```bash
python3 fabric_edit_regression_test.py
```

This will verify all pages require authentication.
