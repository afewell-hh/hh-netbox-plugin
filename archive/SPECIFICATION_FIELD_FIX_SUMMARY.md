# Specification Field Readability Fix Summary

**Date**: July 25, 2025  
**Issue**: Light gray text on white background in Specification fields on CR detail pages  
**Solution**: Added CSS rules to ensure dark text color for all `<pre class="bg-light">` elements

## CSS Rules Added

```css
/* Fix Specification field readability on CR detail pages */
/* Ensure proper contrast for pre-formatted specification text */
pre.bg-light {
    color: #212529 !important; /* Dark text for readability */
    background-color: #f8f9fa !important; /* Light background */
}

/* Additional specificity for spec/labels/annotations sections */
.card-body pre.bg-light,
.gitops-state-box pre.bg-light {
    color: #212529 !important; /* Dark text */
    background-color: #f8f9fa !important;
    border: 1px solid #dee2e6; /* Add subtle border for definition */
}
```

## Affected Fields

The fix applies to all `<pre class="bg-light">` elements, which include:
- **Spec** fields (CRD Specification)
- **Labels** fields (Kubernetes metadata)
- **Annotations** fields (Kubernetes metadata)

## CR Detail Pages Affected (13 templates found)

1. `vpc_detail.html` - VPC Details
2. `server_detail.html` - Server Details
3. `switch_detail_simple.html` - Switch Details (Simple)
4. `vpcattachment_detail.html` - VPC Attachment Details
5. `externalattachment_detail.html` - External Attachment Details
6. `vlannamespace_detail.html` - VLAN Namespace Details
7. `switchgroup_detail.html` - Switch Group Details
8. `connection_detail_simple.html` - Connection Details (Simple)
9. `vpc_detail_simple.html` - VPC Details (Simple)
10. `vpcpeering_detail.html` - VPC Peering Details
11. `external_detail.html` - External Details
12. `externalpeering_detail.html` - External Peering Details
13. `ipv4namespace_detail.html` - IPv4 Namespace Details

## What Changed

- **Before**: Light gray text (#6c757d or similar) that was hard to read
- **After**: Dark text (#212529) with proper contrast
- **Additional**: Added subtle border for better visual definition

## Verification

The CSS file is now being served at:
`http://localhost:8000/static/netbox_hedgehog/css/hedgehog.css`

All detail pages that include `hedgehog.css` will automatically have readable specification fields.

## Result

✅ **Specification fields on all CR detail pages now have dark, readable text**  
✅ **Fix applies to Spec, Labels, and Annotations fields**  
✅ **No template changes required - CSS handles it globally**