# Orchestrator Quick Reference Card

**EMERGENCY CARD - Keep This Handy**

---

## Current Project Status (July 2025)
- **State**: 100% MVP Complete, GUI Test Suite Operational
- **Priority**: Management demo prep → Beta readiness
- **Health**: All systems operational, 71/71 GUI tests passing

## Critical Commands
```bash
# GUI test validation (MUST pass before accepting any work)
python3 run_demo_tests.py

# Restart NetBox after changes
sudo docker restart netbox-docker-netbox-1

# Check container health
sudo docker logs -f netbox-docker-netbox-1

# Django debugging
sudo docker exec -it netbox-docker-netbox-1 python manage.py shell
```

## Agent Deployment Checklist
- [ ] Use onboarding templates from `/project_management/06_onboarding_system/99_templates/`
- [ ] Reference standard modules (don't write custom common instructions)
- [ ] Include testing authority requirements
- [ ] Define clear success criteria
- [ ] Set escalation triggers

## Immediate Escalation to CEO Required For:
- Any GUI test failures
- Architectural decisions affecting NetBox compatibility  
- Timeline risks to management demo
- Agent asking CEO to test their work
- Data loss or corruption risks

## Key File Locations
- **Project Coordination**: `/project_management/CLAUDE.md`
- **Onboarding System**: `/project_management/06_onboarding_system/`
- **Current Status**: `/project_management/00_current_state/`
- **Core HNP**: `/netbox_hedgehog/models/fabric.py`
- **GUI Tests**: `/run_demo_tests.py`

## Environment Details
- **NetBox**: `localhost:8000` (admin/admin)
- **HCKC**: `127.0.0.1:6443` via `~/.kube/config`
- **GitOps**: https://github.com/afewell-hh/gitops-test-1.git
- **Container**: `netbox-docker-netbox-1`

## Non-Negotiables
1. GUI tests must always pass (71/71)
2. Agents must test their own work
3. Use onboarding system (don't write custom instructions)
4. Evidence-based validation required
5. Working functionality must be preserved

---

**Remember**: Process over heroics, quality over speed, evidence over claims!