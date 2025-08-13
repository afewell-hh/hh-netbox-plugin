# Production Deployment Procedures
## Fabric Detail Page Enhancement - Production Rollout Guide

### Pre-Deployment Checklist

#### System Requirements Verification ✅
- [ ] Django 5.2.5+ installed and configured
- [ ] NetBox 4.x environment validated
- [ ] Database migrations current
- [ ] Static files directory writable
- [ ] Web server configuration updated
- [ ] SSL/TLS certificates valid
- [ ] Backup systems operational

#### Security Validation ✅
- [ ] CSRF middleware enabled
- [ ] Authentication system functional
- [ ] Permission system validated
- [ ] XSS protection active
- [ ] Content Security Policy configured
- [ ] HTTPS enforced in production
- [ ] Security headers implemented

#### Performance Baseline ✅
- [ ] Database query performance measured
- [ ] Template rendering benchmarked
- [ ] Static file loading optimized
- [ ] Memory usage profiled
- [ ] CPU utilization assessed
- [ ] Network latency measured

## Deployment Strategy

### Rolling Deployment (Recommended)
**Timeline**: 2-4 hours
**Downtime**: Zero (blue-green deployment)
**Risk Level**: Low

### Big Bang Deployment (Alternative)
**Timeline**: 30 minutes
**Downtime**: 5-10 minutes
**Risk Level**: Medium

## Step-by-Step Deployment

### Phase 1: Pre-Deployment (30 minutes)

#### 1.1 Backup Current System
```bash
# Create complete system backup
sudo systemctl stop netbox
sudo systemctl stop netbox-rq

# Backup database
sudo -u postgres pg_dump netbox > /backup/netbox_pre_fabric_enhancement.sql

# Backup current templates
tar -czf /backup/templates_$(date +%Y%m%d_%H%M).tar.gz /opt/netbox/netbox/templates/

# Backup static files
tar -czf /backup/static_$(date +%Y%m%d_%H%M).tar.gz /opt/netbox/netbox/static/

# Backup configuration
cp /opt/netbox/netbox/netbox/configuration.py /backup/configuration_$(date +%Y%m%d_%H%M).py
```

#### 1.2 Environment Preparation
```bash
# Switch to netbox user
sudo -u netbox -H bash
cd /opt/netbox

# Activate virtual environment
source venv/bin/activate

# Verify environment
python --version  # Should be 3.8+
pip list | grep django  # Should be 5.x
```

### Phase 2: Template Deployment (15 minutes)

#### 2.1 Install Enhanced Templates
```bash
# Copy enhanced fabric detail template
cp /staging/fabric_detail.html /opt/netbox/netbox/templates/netbox_hedgehog/

# Copy enhanced fabric edit template
cp /staging/fabric_edit.html /opt/netbox/netbox/templates/netbox_hedgehog/

# Copy base template updates
cp /staging/base.html /opt/netbox/netbox/templates/netbox_hedgehog/

# Verify template syntax
python manage.py check --tag templates
```

#### 2.2 Validate Template Security
```bash
# Check for security issues
grep -r "mark_safe\|safe\|autoescape off" /opt/netbox/netbox/templates/netbox_hedgehog/

# Verify CSRF token usage
grep -r "csrf_token" /opt/netbox/netbox/templates/netbox_hedgehog/

# Expected: 34 templates with CSRF protection
```

### Phase 3: Static Files Deployment (10 minutes)

#### 3.1 Install Enhanced CSS
```bash
# Copy enhanced stylesheet
cp /staging/hedgehog.css /opt/netbox/netbox/static/netbox_hedgehog/css/

# Collect static files
python manage.py collectstatic --noinput --clear

# Verify file permissions
chown -R netbox:netbox /opt/netbox/netbox/static/
chmod -R 644 /opt/netbox/netbox/static/
```

#### 3.2 CSS Validation
```bash
# Validate CSS syntax (if available)
csslint /opt/netbox/netbox/static/netbox_hedgehog/css/hedgehog.css

# Check file size (should be reasonable)
ls -lh /opt/netbox/netbox/static/netbox_hedgehog/css/hedgehog.css
```

### Phase 4: View Updates (10 minutes)

#### 4.1 Install Enhanced Views
```bash
# Backup current views
cp /opt/netbox/plugins/netbox_hedgehog/views/fabric.py /backup/fabric_views_$(date +%Y%m%d_%H%M).py

# Install enhanced views
cp /staging/fabric.py /opt/netbox/plugins/netbox_hedgehog/views/

# Verify Python syntax
python -m py_compile /opt/netbox/plugins/netbox_hedgehog/views/fabric.py
```

#### 4.2 Security Validation
```bash
# Check for security decorators
grep -n "csrf_protect\|LoginRequiredMixin\|PermissionRequiredMixin" /opt/netbox/plugins/netbox_hedgehog/views/fabric.py

# Verify permission checks
grep -n "has_perm\|PermissionDenied" /opt/netbox/plugins/netbox_hedgehog/views/fabric.py
```

### Phase 5: System Integration (15 minutes)

#### 5.1 Database Migration Check
```bash
# Check for pending migrations
python manage.py showmigrations netbox_hedgehog

# Apply any pending migrations
python manage.py migrate netbox_hedgehog
```

#### 5.2 Configuration Validation
```bash
# Validate Django configuration
python manage.py check --deploy

# Check for configuration issues
python manage.py check --tag security
python manage.py check --tag compatibility
```

### Phase 6: Service Restart (5 minutes)

#### 6.1 Graceful Service Restart
```bash
# Restart NetBox services
sudo systemctl restart netbox
sudo systemctl restart netbox-rq

# Verify services are running
sudo systemctl status netbox
sudo systemctl status netbox-rq

# Check service logs
sudo journalctl -u netbox --lines=50 --no-pager
```

#### 6.2 Web Server Configuration
```bash
# Restart web server (nginx/apache)
sudo systemctl restart nginx
# OR
sudo systemctl restart apache2

# Verify web server status
sudo systemctl status nginx
curl -I https://your-netbox-domain.com/
```

### Phase 7: Deployment Verification (30 minutes)

#### 7.1 Functional Testing
```bash
# Test basic functionality
curl -s "https://your-netbox-domain.com/plugins/netbox-hedgehog/fabric/1/" | grep -c "Progressive Disclosure"

# Test static file loading
curl -s "https://your-netbox-domain.com/static/netbox_hedgehog/css/hedgehog.css" | head -5
```

#### 7.2 User Interface Testing
1. **Login Test**: Verify authentication system
2. **Fabric List**: Navigate to fabric list page
3. **Fabric Detail**: Open enhanced fabric detail page
4. **Progressive Disclosure**: Test expand/collapse functionality
5. **Edit Form**: Test fabric editing with validation
6. **Mobile View**: Test responsive design on mobile devices

#### 7.3 Security Testing
```bash
# Test CSRF protection
curl -X POST "https://your-netbox-domain.com/plugins/netbox-hedgehog/fabric/1/edit/" \
     -d "name=test" \
     -H "Content-Type: application/x-www-form-urlencoded"
# Expected: 403 Forbidden (CSRF token missing)

# Test authentication
curl -s "https://your-netbox-domain.com/plugins/netbox-hedgehog/fabric/1/edit/"
# Expected: Redirect to login page
```

#### 7.4 Performance Testing
```bash
# Load test fabric detail page
ab -n 100 -c 5 "https://your-netbox-domain.com/plugins/netbox-hedgehog/fabric/1/"

# Expected results:
# - Requests per second: > 50
# - Time per request: < 100ms
# - Failed requests: 0
```

## Rollback Procedures

### Emergency Rollback (5 minutes)
```bash
# Stop services
sudo systemctl stop netbox netbox-rq

# Restore templates
tar -xzf /backup/templates_$(date +%Y%m%d)_*.tar.gz -C /

# Restore static files
tar -xzf /backup/static_$(date +%Y%m%d)_*.tar.gz -C /

# Restore views
cp /backup/fabric_views_$(date +%Y%m%d)_*.py /opt/netbox/plugins/netbox_hedgehog/views/fabric.py

# Collect static files
python manage.py collectstatic --noinput

# Restart services
sudo systemctl start netbox netbox-rq

# Verify rollback success
curl -s "https://your-netbox-domain.com/" | grep -c "NetBox"
```

### Database Rollback (if needed)
```bash
# Stop services
sudo systemctl stop netbox netbox-rq

# Restore database
sudo -u postgres dropdb netbox
sudo -u postgres createdb netbox
sudo -u postgres psql netbox < /backup/netbox_pre_fabric_enhancement.sql

# Restart services
sudo systemctl start netbox netbox-rq
```

## Monitoring & Maintenance

### Post-Deployment Monitoring (First 24 hours)

#### 1. System Health Monitoring
```bash
# Monitor system resources
watch -n 5 'top -b -n 1 | head -20'
watch -n 5 'free -h'
watch -n 5 'df -h'

# Monitor service logs
sudo tail -f /opt/netbox/logs/netbox.log
sudo journalctl -u netbox -f
```

#### 2. Performance Monitoring
```bash
# Monitor response times
while true; do
    curl -w "Response time: %{time_total}s\n" -o /dev/null -s "https://your-netbox-domain.com/plugins/netbox-hedgehog/fabric/1/"
    sleep 60
done
```

#### 3. Error Monitoring
```bash
# Monitor for errors
sudo tail -f /var/log/nginx/error.log
sudo grep -i error /opt/netbox/logs/netbox.log | tail -20
```

### Weekly Maintenance Tasks

#### 1. Performance Review
```bash
# Analyze server logs for performance issues
sudo grep "slow" /opt/netbox/logs/netbox.log
sudo awk '$9 > 500' /var/log/nginx/access.log | tail -20  # Slow requests
```

#### 2. Security Audit
```bash
# Check for security issues
sudo grep -i "403\|401\|security" /var/log/nginx/access.log | tail -20
sudo grep -i "permission\|auth" /opt/netbox/logs/netbox.log | tail -20
```

#### 3. System Updates
```bash
# Update system packages
sudo apt update && sudo apt upgrade -y

# Update Python dependencies (test in staging first)
pip list --outdated
```

### Monthly Maintenance Tasks

#### 1. Backup Validation
```bash
# Test backup restore process
sudo -u postgres pg_dump netbox > /backup/monthly_test_$(date +%Y%m%d).sql
sudo -u postgres dropdb netbox_test 2>/dev/null || true
sudo -u postgres createdb netbox_test
sudo -u postgres psql netbox_test < /backup/monthly_test_$(date +%Y%m%d).sql
```

#### 2. Performance Optimization
```bash
# Database maintenance
sudo -u postgres vacuumdb --analyze netbox
sudo -u postgres reindexdb netbox
```

#### 3. Security Review
```bash
# Check for security updates
pip list --outdated | grep -i security
sudo apt list --upgradable | grep -i security
```

## Troubleshooting Guide

### Common Issues and Solutions

#### Issue: Templates Not Loading
**Symptoms**: 500 errors, template does not exist errors
**Solution**:
```bash
# Check template paths
python manage.py check --tag templates
ls -la /opt/netbox/netbox/templates/netbox_hedgehog/

# Verify permissions
chown -R netbox:netbox /opt/netbox/netbox/templates/
```

#### Issue: Static Files Not Loading
**Symptoms**: CSS not applying, 404 errors for static files
**Solution**:
```bash
# Recollect static files
python manage.py collectstatic --noinput --clear
sudo systemctl restart nginx
```

#### Issue: Permission Errors
**Symptoms**: 403 Forbidden, permission denied errors
**Solution**:
```bash
# Check user permissions
python manage.py shell
>>> from django.contrib.auth.models import User
>>> user = User.objects.get(username='admin')
>>> user.has_perm('netbox_hedgehog.view_hedgehogfabric')
```

#### Issue: CSRF Errors
**Symptoms**: 403 CSRF verification failed
**Solution**:
```bash
# Check CSRF settings
grep -r "CSRF" /opt/netbox/netbox/netbox/configuration.py
python manage.py check --tag security
```

### Emergency Contacts
- **System Administrator**: [contact info]
- **NetBox Administrator**: [contact info]
- **Development Team**: [contact info]
- **Security Team**: [contact info]

## Success Criteria

### Deployment Success Indicators ✅
- [ ] All services running without errors
- [ ] Fabric detail pages loading correctly
- [ ] Progressive disclosure functionality working
- [ ] Edit forms functioning with validation
- [ ] No 500 errors in logs
- [ ] Response times under 100ms
- [ ] CSRF protection active
- [ ] Permission system functional
- [ ] Mobile responsiveness confirmed
- [ ] Accessibility features working

### Business Success Metrics
- **User Experience**: Improved page usability
- **Performance**: Faster page load times
- **Security**: Enhanced protection measures
- **Maintainability**: Better code organization
- **Accessibility**: WCAG AA compliance

---
*Deployment Guide Version: 1.0*
*Last Updated: 2025-01-09*
*Next Review Date: 2025-02-09*