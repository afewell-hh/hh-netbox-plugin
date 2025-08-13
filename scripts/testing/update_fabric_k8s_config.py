
# Run this in Django shell or as a management command
from netbox_hedgehog.models.fabric import HedgehogFabric

# Update fabric with K8s configuration
try:
    fabric = HedgehogFabric.objects.first()
    if fabric:
        print(f"Updating fabric: {fabric.name}")
        
        # Configure Kubernetes connection
        fabric.kubernetes_server = 'https://vlab-art.l.hhdev.io:6443'
        fabric.kubernetes_token = 'eyJhbGciOiJSUzI1NiIsImtpZCI6IkV5Q0thR0ZCcVp0YWFVNWZLOTJoNmhxbUkyZ095RG1wdGYzY2wzSFE3MU0ifQ.eyJpc3MiOiJrdWJlcm5ldGVzL3NlcnZpY2VhY2NvdW50Iiwia3ViZXJuZXRlcy5pby9zZXJ2aWNlYWNjb3VudC9uYW1lc3BhY2UiOiJkZWZhdWx0Iiwia3ViZXJuZXRlcy5pby9zZXJ2aWNlYWNjb3VudC9zZWNyZXQubmFtZSI6ImhucC1zeW5jLXRva2VuIiwia3ViZXJuZXRlcy5pby9zZXJ2aWNlYWNjb3VudC9zZXJ2aWNlLWFjY291bnQubmFtZSI6ImhucC1zeW5jIiwia3ViZXJuZXRlcy5pby9zZXJ2aWNlYWNjb3VudC9zZXJ2aWNlLWFjY291bnQudWlkIjoiY2ExODIxZTctMTZkMi00OGIzLTgxMzYtZDY0MGVhZGViNDUzIiwic3ViIjoic3lzdGVtOnNlcnZpY2VhY2NvdW50OmRlZmF1bHQ6aG5wLXN5bmMifQ.Npaq21BbAuadOQ8snnVm-G6qSTWjvkIjuqoNhpCJnmgHD9aE5opZwPO4tYxkCA2szo9xU1jJV62j-l7IkqonVVaQdfI4-UXoNlfVG9Cg-ip2ncKoickig1BoWyCov3m_W4zGoKdUarC2Xt9iBUFoOmRXQjjoNOCSwfI4Kn9r8qZpHtweVIY3QNdXk2H85Ftfx2O2LeLX0-kKlknkcWKn9IDEem_LGcaLOMah0dYEL0nqFUq1tQMcJXoO07p6-nECO_TjNO7Vy0WuvWk1EXqY0dfcbirbXW4b1YlbFKonCWbU050s3BWGhNY0ktUQzj_Vn9O10cgTz083mDNK07EFeQ'
        fabric.kubernetes_ca_cert = '''-----BEGIN CERTIFICATE-----
MIIBdjCCAR2gAwIBAgIBADAKBggqhkjOPQQDAjAjMSEwHwYDVQQDDBhrM3Mtc2Vy
dmVyLWNhQDE3NTMzMTE5NTcwHhcNMjUwNzIzMjMwNTU3WhcNMzUwNzIxMjMwNTU3
WjAjMSEwHwYDVQQDDBhrM3Mtc2VydmVyLWNhQDE3NTMzMTE5NTcwWTATBgcqhkjO
PQIBBggqhkjOPQMBBwNCAARAiqUEa76YqEaa0gohq4QDXeSoax3aBm7HQsL9TokF
XT9+2abFBasj7yxpaaJUerfSdG3ecPrup47KDV15YLfRo0IwQDAOBgNVHQ8BAf8E
BAMCAqQwDwYDVR0TAQH/BAUwAwEB/zAdBgNVHQ4EFgQUsokLDiEEwwuyDIZH05E6
DOIeG+kwCgYIKoZIzj0EAwIDRwAwRAIgTjEipnU+ClooGgW9fCegG27+5I/tBB2P
wdrWXDu58osCIAp7kn+KzfXhPpN568aE1D0zukjyac//doVsbGuGvx0Z
-----END CERTIFICATE-----
'''
        fabric.kubernetes_namespace = 'default'
        
        # Enable sync
        fabric.sync_enabled = True
        fabric.sync_error = ''
        fabric.connection_error = ''
        
        # Save changes
        fabric.save()
        
        print("✅ Fabric updated successfully!")
        print(f"   K8s Server: {fabric.kubernetes_server}")
        print(f"   Namespace: {fabric.kubernetes_namespace}")
        print(f"   Token configured: {bool(fabric.kubernetes_token)}")
        print(f"   CA cert configured: {bool(fabric.kubernetes_ca_cert)}")
        
    else:
        print("❌ No fabric found in database")
        
except Exception as e:
    print(f"❌ Error updating fabric: {e}")
