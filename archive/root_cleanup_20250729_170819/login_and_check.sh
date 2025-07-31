#!/bin/bash

# Get CSRF token and login
echo "Getting CSRF token..."
curl -c cookies.txt -s http://localhost:8000/login/ | grep csrfmiddlewaretoken | sed -n 's/.*value="\([^"]*\)".*/\1/p' > csrf_token.txt
CSRF_TOKEN=$(cat csrf_token.txt)

echo "CSRF Token: $CSRF_TOKEN"
echo "Logging in..."

# Login
curl -b cookies.txt -c cookies.txt -X POST \
  -H "Referer: http://localhost:8000/login/" \
  -d "username=admin&password=admin&csrfmiddlewaretoken=$CSRF_TOKEN&next=/plugins/hedgehog/git-repositories/" \
  http://localhost:8000/login/ -v 2>&1 | grep -E "(Location:|HTTP/)"

echo -e "\nAccessing git repositories list..."
curl -b cookies.txt http://localhost:8000/plugins/hedgehog/git-repositories/ > git_repos_authenticated.html

echo "Saved to git_repos_authenticated.html"