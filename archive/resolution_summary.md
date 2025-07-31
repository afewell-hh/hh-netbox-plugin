# Git Repositories Page Issue Resolution Summary

## Issue Identified
The Git Repositories page at `/plugins/hedgehog/git-repositories/` returns 404 because:
1. The Docker container has an outdated version of the plugin code baked into the image
2. The container's urls.py maps `repositories/` to a placeholder template instead of a proper view
3. Changes to local files don't affect the running container

## Evidence
1. Local urls.py has WorkingGitRepositoryListView for git-repositories/
2. Container urls.py has TemplateView pointing to simple_placeholder.html
3. Container file permissions prevent runtime code updates
4. URL resolution shows the container is using cached/old mappings

## Current Workaround
Created a debug template at `/plugins/hedgehog/debug-git-repos/` that displays the issue status.

## Permanent Resolution
The Docker image needs to be rebuilt with the latest plugin code:

1. Update the Docker build process to include the latest netbox_hedgehog code
2. Rebuild the netbox-docker image
3. Restart the container with the new image

## Temporary Alternative
If immediate access is needed:
- Use the `/plugins/hedgehog/repositories/` URL (shows recovery mode)
- The git repository data and models are intact and working
- The fabric edit page can still access git repositories via the dropdown

## Technical Details
- Container: netbox-docker-netbox-1
- Plugin location in container: /opt/netbox/netbox/netbox_hedgehog/
- Issue type: Docker image build-time code inclusion
- Django caching: Not the issue - it's container-level code isolation
