#!/usr/bin/env python3
"""
Script to update fabric with HCKC cluster service account credentials
"""

# Credentials from HCKC cluster service account
CLUSTER_ENDPOINT = "https://vlab-art.l.hhdev.io:6443"
SERVICE_ACCOUNT_TOKEN = """eyJhbGciOiJSUzI1NiIsImtpZCI6InVFRUdtN3lLM21zN09hTmpHUW5CVmdPVUJEMjhIdlZET3hEQTk2VG1nYXcifQ.eyJpc3MiOiJrdWJlcm5ldGVzL3NlcnZpY2VhY2NvdW50Iiwia3ViZXJuZXRlcy5pby9zZXJ2aWNlYWNjb3VudC9uYW1lc3BhY2UiOiJuZXRib3gtaGVkZ2Vob2ciLCJrdWJlcm5ldGVzLmlvL3NlcnZpY2VhY2NvdW50L3NlY3JldC5uYW1lIjoibmV0Ym94LWhlZGdlaG9nLXRva2VuIiwia3ViZXJuZXRlcy5pby9zZXJ2aWNlYWNjb3VudC9zZXJ2aWNlLWFjY291bnQubmFtZSI6Im5ldGJveC1oZWRnZWhvZyIsImt1YmVybmV0ZXMuaW8vc2VydmljZWFjY291bnQvc2VydmljZS1hY2NvdW50LnVpZCI6ImU2MTc5ZjQwLWQ4YzUtNDYzMy1iZDJmLWE2ODYxMTE5YjVkMSIsInN1YiI6InN5c3RlbTpzZXJ2aWNlYWNjb3VudDpuZXRib3gtaGVkZ2Vob2c6bmV0Ym94LWhlZGdlaG9nIn0.q9T9BezAYsandk4Gc_T2bwdvhKZLI7cKlWznuhxCLcoMguS_uTgkoz-9HV75xyPmxRVa7fGdOuMo4uuRC4o6PIKf8ulsXdy8RCtZLF4bS8grdl80RDVo40ogz1ZYAT8foVXMof3fC6H2mQ5omCuHUz07-3njTXAisHR53I0ilb6HDkLpcbwlh6pLtocCfY8Vb6GJZGkb7IHvsRT9FY1mbJ3ebn1GvxLRzTx533t4DvhB7nmFy_X7ABGgofi8bRQr70PpmlZw-fEJIChVjeI7lA4Rrr-8oNQPPdS_owaJmyVzuqWBx_JZtaSTxFH5J_GyXcTa1sQP3aOL49JwqsXsuA"""

CA_CERTIFICATE = """-----BEGIN CERTIFICATE-----
MIIBdjCCAR2gAwIBAgIBADAKBggqhkjOPQQDAjAjMSEwHwYDVQQDDBhrM3Mtc2Vy
dmVyLWNhQDE3NTMxMzE4NDIwHhcNMjUwNzIxMjEwNDAyWhcNMzUwNzE5MjEwNDAy
WjAjMSEwHwYDVQQDDBhrM3Mtc2VydmVyLWNhQDE3NTMxMzE4NDIwWTATBgcqhkjO
PQIBBggqhkjOPQMBBwNCAARLLnGyeK8NRky+3U2F6pms/SlabFyx1ijNW/7PR7pO
f8LZJQylF+l1uhqUA3jztPi6xlFjSTWLBk7dmBkmj4avo0IwQDAOBgNVHQ8BAf8E
BAMCAqQwDwYDVR0TAQH/BAUwAwEB/zAdBgNVHQ4EFgQUdsL+R/EFyGRacyetm9/c
SnnzrI0wCgYIKoZIzj0EAwIDRwAwRAIgTVNihZn8iczIku8Xu9d8VjeCRrUnuyCw
buZU7oLIXWYCIBi9DIRHDGJ3XThjYQhmIq1IN9kGdGA+WlsGzZTVWO86
-----END CERTIFICATE-----"""

INSTRUCTIONS = f"""
🔧 HCKC Cluster Service Account Credentials Ready!

To update your fabric in the NetBox HNP GUI:

1. **Go to NetBox HNP**: Navigate to your fabric detail page
2. **Click Edit**: Use the edit button to access the fabric edit form  
3. **Update Kubernetes Configuration**:

   Kubernetes Server: {CLUSTER_ENDPOINT}
   Kubernetes Namespace: netbox-hedgehog (or default)
   
   Service Account Token:
   {SERVICE_ACCOUNT_TOKEN}
   
   CA Certificate:
   {CA_CERTIFICATE}

4. **Test the Connection**: Save the form and test the Git sync functionality

📋 **What the Service Account Can Do**:
✅ Read/Write all Hedgehog CRDs (VPC API, Wiring API)
✅ Watch for real-time changes
✅ Access cluster metadata for monitoring
✅ Read nodes, namespaces, pods for status

📍 **Service Account Details**:
- Namespace: netbox-hedgehog  
- Name: netbox-hedgehog
- ClusterRole: netbox-hedgehog-access
- Token expires: Never (service account token)

🎯 **Next Steps**:
1. Update the fabric configuration in NetBox with these credentials
2. Test the Git sync functionality
3. Verify the Real-Time Monitoring Agent can connect to the cluster
4. Check that HNP can read existing CRDs from the HCKC cluster

The service account has been created with appropriate permissions for both 
current Git sync functionality and future real-time monitoring capabilities!
"""

if __name__ == "__main__":
    print(INSTRUCTIONS)