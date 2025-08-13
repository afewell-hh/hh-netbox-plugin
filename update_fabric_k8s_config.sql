
-- Direct SQL update for fabric K8s configuration
-- Run this against the NetBox database

UPDATE netbox_hedgehog_hedgehogfabric 
SET 
    kubernetes_server = 'https://vlab-art.l.hhdev.io:6443',
    kubernetes_token = 'eyJhbGciOiJSUzI1NiIsImtpZCI6IkV5Q0thR0ZCcVp0YWFVNWZLOTJoNmhxbUkyZ095RG1wdGYzY2wzSFE3MU0ifQ.eyJpc3MiOiJrdWJlcm5ldGVzL3NlcnZpY2VhY2NvdW50Iiwia3ViZXJuZXRlcy5pby9zZXJ2aWNlYWNjb3VudC9uYW1lc3BhY2UiOiJkZWZhdWx0Iiwia3ViZXJuZXRlcy5pby9zZXJ2aWNlYWNjb3VudC9zZWNyZXQubmFtZSI6ImhucC1zeW5jLXRva2VuIiwia3ViZXJuZXRlcy5pby9zZXJ2aWNlYWNjb3VudC9zZXJ2aWNlLWFjY291bnQubmFtZSI6ImhucC1zeW5jIiwia3ViZXJuZXRlcy5pby9zZXJ2aWNlYWNjb3VudC9zZXJ2aWNlLWFjY291bnQudWlkIjoiY2ExODIxZTctMTZkMi00OGIzLTgxMzYtZDY0MGVhZGViNDUzIiwic3ViIjoic3lzdGVtOnNlcnZpY2VhY2NvdW50OmRlZmF1bHQ6aG5wLXN5bmMifQ.Npaq21BbAuadOQ8snnVm-G6qSTWjvkIjuqoNhpCJnmgHD9aE5opZwPO4tYxkCA2szo9xU1jJV62j-l7IkqonVVaQdfI4-UXoNlfVG9Cg-ip2ncKoickig1BoWyCov3m_W4zGoKdUarC2Xt9iBUFoOmRXQjjoNOCSwfI4Kn9r8qZpHtweVIY3QNdXk2H85Ftfx2O2LeLX0-kKlknkcWKn9IDEem_LGcaLOMah0dYEL0nqFUq1tQMcJXoO07p6-nECO_TjNO7Vy0WuvWk1EXqY0dfcbirbXW4b1YlbFKonCWbU050s3BWGhNY0ktUQzj_Vn9O10cgTz083mDNK07EFeQ',
    kubernetes_ca_cert = '-----BEGIN CERTIFICATE-----
MIIBdjCCAR2gAwIBAgIBADAKBggqhkjOPQQDAjAjMSEwHwYDVQQDDBhrM3Mtc2Vy
dmVyLWNhQDE3NTMzMTE5NTcwHhcNMjUwNzIzMjMwNTU3WhcNMzUwNzIxMjMwNTU3
WjAjMSEwHwYDVQQDDBhrM3Mtc2VydmVyLWNhQDE3NTMzMTE5NTcwWTATBgcqhkjO
PQIBBggqhkjOPQMBBwNCAARAiqUEa76YqEaa0gohq4QDXeSoax3aBm7HQsL9TokF
XT9+2abFBasj7yxpaaJUerfSdG3ecPrup47KDV15YLfRo0IwQDAOBgNVHQ8BAf8E
BAMCAqQwDwYDVR0TAQH/BAUwAwEB/zAdBgNVHQ4EFgQUsokLDiEEwwuyDIZH05E6
DOIeG+kwCgYIKoZIzj0EAwIDRwAwRAIgTjEipnU+ClooGgW9fCegG27+5I/tBB2P
wdrWXDu58osCIAp7kn+KzfXhPpN568aE1D0zukjyac//doVsbGuGvx0Z
-----END CERTIFICATE-----
',
    kubernetes_namespace = 'default',
    sync_enabled = TRUE,
    sync_error = '',
    connection_error = ''
WHERE id IN (SELECT id FROM netbox_hedgehog_hedgehogfabric ORDER BY id LIMIT 1);

-- Verify the update
SELECT 
    id, 
    name, 
    kubernetes_server, 
    kubernetes_namespace,
    sync_enabled,
    CASE WHEN LENGTH(kubernetes_token) > 0 THEN 'TOKEN_CONFIGURED' ELSE 'NO_TOKEN' END as token_status,
    CASE WHEN LENGTH(kubernetes_ca_cert) > 0 THEN 'CERT_CONFIGURED' ELSE 'NO_CERT' END as cert_status
FROM netbox_hedgehog_hedgehogfabric;
