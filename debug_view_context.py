#!/usr/bin/env python3
"""
Debug script to test what context variables are available in the ConnectionListView
"""

template_debug = """
<!-- TEMPORARY DEBUG INFO -->
<div style="background: yellow; padding: 10px; margin: 10px;">
    <h3>DEBUG: Template Context Variables</h3>
    <p><strong>object_list:</strong> {{ object_list|length }} items</p>
    <p><strong>connections:</strong> {{ connections|length }} items</p>
    <p><strong>page_obj:</strong> {{ page_obj|length }} items</p>
    <p><strong>All available variables:</strong></p>
    <ul>
    {% for key, value in debug.context_processors.request %}
        <li><strong>{{ key }}:</strong> {{ value|truncatechars:50 }}</li>
    {% endfor %}
    </ul>
    <p><strong>All object_list items:</strong></p>
    {% for item in object_list %}
        <li>{{ item.name }} - {{ item.fabric }}</li>
    {% empty %}
        <li>No items in object_list!</li>
    {% endfor %}
    <p><strong>Raw queryset test:</strong></p>
    {% load static %}
    
</div>
<!-- END DEBUG -->
"""

with open('/home/ubuntu/cc/hedgehog-netbox-plugin/netbox_hedgehog/templates/netbox_hedgehog/connection_list.html', 'r') as f:
    content = f.read()

# Insert debug info at the beginning of the content div
debug_content = content.replace(
    '<div class="card-body">',
    f'<div class="card-body">\n{template_debug}'
)

with open('/home/ubuntu/cc/hedgehog-netbox-plugin/netbox_hedgehog/templates/netbox_hedgehog/connection_list.html', 'w') as f:
    f.write(debug_content)

print("✅ Added debug information to connection_list.html template")
print("🔄 Restart NetBox and check the connection list page to see debug info")