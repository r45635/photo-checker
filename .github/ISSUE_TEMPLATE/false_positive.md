---
name: False positive / false negative
about: A file was incorrectly marked as safe to delete (or not found when it should be)
title: "[Match] "
labels: matching
assignees: ''
---

**Type of mismatch**
- [ ] False positive — file marked YES/MAYBE but is NOT in Apple Photos
- [ ] False negative — file IS in Apple Photos but marked NO

**File info (anonymized)**
- File extension (backup): e.g. `.JPG`
- Extension stored in Apple Photos: e.g. `.HEIC`
- `match_confidence` shown in the detail panel: e.g. `medium`
- `match_reason` shown in the detail panel: e.g. `Stem match (format conversion, e.g. JPG↔HEIC)`

**Filename pattern (anonymized — do not include personal names)**
Describe the filename structure, e.g.:
- Has accented characters (é, ü, ñ…)
- Has a copy suffix ("- Copy", "- Copie", "(1)"…)
- Was renamed after import
- Different extension from what Photos stores

**Expected behavior**
What should the tool have shown?

**Steps to reproduce**
1. Scan folder containing `[anonymized filename pattern]`
2. Open detail panel
3. Apple Photos info shows…

**Note**: Do not attach personal photos. Anonymized filenames and patterns are sufficient.
