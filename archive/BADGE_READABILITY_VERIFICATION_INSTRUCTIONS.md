# Badge Readability Verification Instructions

**Date**: July 25, 2025  
**Issue**: Badge text readability inconsistency across the application  
**Fix Applied**: Enhanced CSS specificity with `span.badge` selectors and `!important` declarations

## What Was Fixed

### Problem Identified
- CSS file was not being served from static directory
- Original CSS rules had insufficient specificity to override NetBox defaults
- Docker image updates weren't propagating CSS changes properly

### Solution Applied
1. **Fixed CSS Serving**: Ensured `hedgehog.css` is copied to `/opt/netbox/netbox/static/netbox_hedgehog/css/`
2. **Increased CSS Specificity**: Changed from `.badge.bg-*` to `span.badge.bg-*, .badge.bg-*`
3. **Added Font Weight**: All badges now have `font-weight: 500 !important` for better readability

### Updated CSS Rules Now Active
```css
span.badge.bg-primary, .badge.bg-primary {
    color: #fff !important;
    font-weight: 500 !important;
}

span.badge.bg-secondary, .badge.bg-secondary {
    color: #fff !important;
    font-weight: 500 !important;
}

span.badge.bg-success, .badge.bg-success {
    color: #fff !important;
    font-weight: 500 !important;
}

span.badge.bg-danger, .badge.bg-danger {
    color: #fff !important;
    font-weight: 500 !important;
}

span.badge.bg-warning, .badge.bg-warning {
    color: #212529 !important; /* Dark text on yellow */
    font-weight: 500 !important;
}

span.badge.bg-info, .badge.bg-info {
    color: #fff !important;
    font-weight: 500 !important;
}

span.badge.bg-light, .badge.bg-light {
    color: #212529 !important;
    font-weight: 500 !important;
}

span.badge.bg-dark, .badge.bg-dark {
    color: #fff !important;
    font-weight: 500 !important;
}
```

## Verification URLs

Please check these pages in your browser:

1. **Overview Page**: http://localhost:8000/plugins/hedgehog/
2. **Fabric List**: http://localhost:8000/plugins/hedgehog/fabrics/
3. **VPC List**: http://localhost:8000/plugins/hedgehog/vpcs/
4. **Server List**: http://localhost:8000/plugins/hedgehog/servers/
5. **Switch List**: http://localhost:8000/plugins/hedgehog/switches/
6. **Connection List**: http://localhost:8000/plugins/hedgehog/connections/

## What to Look For

### ✅ EXPECTED: Readable Badge Text
- **Dark backgrounds** (primary, secondary, success, danger, info, dark): **WHITE TEXT**
- **Light backgrounds** (warning, light): **DARK TEXT**
- **All badges**: **Slightly bolder font weight** (500)

### ❌ PROBLEM INDICATORS
- Faded/low contrast text on badges
- Text that's difficult to read against background
- Inconsistent styling between similar badge types

## Browser Developer Tools Check

If badges still appear unreadable:

1. **Right-click on a badge** → "Inspect Element"
2. **Check the CSS rules applied**:
   - Should see `color: #fff !important` or `color: #212529 !important`
   - Should see `font-weight: 500 !important`
3. **Check if CSS is loaded**:
   - Look for `hedgehog.css` in Network tab
   - Verify `http://localhost:8000/static/netbox_hedgehog/css/hedgehog.css` returns 200

## CSS Verification

The CSS file should be accessible at:
**http://localhost:8000/static/netbox_hedgehog/css/hedgehog.css**

Search for "span.badge.bg-secondary" in the CSS - you should find the enhanced rules.

## Current Status

- ✅ **CSS File**: Being served properly (HTTP 200)
- ✅ **Template Inclusion**: All badge-containing templates include the CSS
- ✅ **CSS Rules**: High specificity rules with `!important` declarations
- ✅ **All Badge Types**: 8 Bootstrap variants covered
- ⏳ **Visual Verification**: Awaiting confirmation

**Please verify badge readability on the actual pages and confirm if the issue is resolved.**