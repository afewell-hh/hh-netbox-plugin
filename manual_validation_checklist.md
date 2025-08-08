# Issue #17 Manual GUI Validation Checklist

## 🎯 How to Validate the Fixes

**Important**: Open NetBox in your browser at http://localhost:8000 and navigate to each page to verify these fixes work.

## ✅ Test 1: Fabric List Page - Column Header Rename

**Steps:**
1. Go to: **Hedgehog Plugin → Fabrics**
2. Look at the table header columns

**Expected Result:**
- ✅ Column header should say **"Git Sync Status"** (not "Sync Status")

**Fixed:** Renamed column header in `/netbox_hedgehog/templates/netbox_hedgehog/fabric_list_simple.html:36`

---

## ✅ Test 2: Git Repository Detail Page - No Visible HTML Comments  

**Steps:**
1. Go to: **Hedgehog Plugin → Git Repositories**
2. Click on any repository to view detail page
3. Look for visible text like `{# Breadcrumbs #}`, `{# Actions #}`, etc.

**Expected Result:**
- ✅ Should NOT see any visible HTML comments on the page
- ✅ Page should look clean with proper sections

**Fixed:** Removed all visible `{# ... #}` comments from git repository detail template

---

## ✅ Test 3: Git Repository Detail Page - Edit/Delete Button Fix

**Steps:**
1. Go to: **Hedgehog Plugin → Git Repositories**  
2. Click on any repository to view detail page
3. Look at the "Actions" section on the right side

**Expected Result:**
- ✅ Should NOT have broken Edit/Delete buttons
- ✅ Should show informational message: "Edit and delete functions are not yet implemented for git repositories"
- ✅ Should have "Back to Dashboard" button instead

**Fixed:** Replaced broken edit/delete buttons with informational message

---

## ✅ Test 4: VPC List Page - Invalid Records Cleanup

**Steps:**
1. Go to: **Hedgehog Plugin → VPCs**
2. Look at the "Git File" column for all VPC records

**Expected Result:**
- ✅ Should NOT see any records with "Not from Git" in the Git File column
- ✅ All remaining VPC records should have actual git file paths

**Fixed:** Deleted 3 invalid VPC records (`sync-test-vpc`, `signal-test-vpc`, `actual-save-test`)

---

## 🎉 Success Criteria

**All fixes are working if:**
1. ✅ Fabric list shows "Git Sync Status" column
2. ✅ Git repository detail page has no visible HTML comments  
3. ✅ Git repository detail page shows proper "not implemented" message instead of broken buttons
4. ✅ VPC list has no "Not from Git" records

---

## 🚨 If Any Test Fails

If you see any issues when testing these manually:
1. Take a screenshot of the problem
2. Note which specific test failed
3. Let me know so I can fix it

**The changes were made to these files:**
- `netbox_hedgehog/templates/netbox_hedgehog/fabric_list_simple.html` - Column rename
- `netbox_hedgehog/templates/netbox_hedgehog/git_repository_detail_simple.html` - Comments and buttons fix  
- Database - Deleted invalid VPC records via Django shell