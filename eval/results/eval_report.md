# LayoutProof eval report

- physical files: **66**; unique authored content ids: **52**; derivative (LibreOffice resave) files: **14**
- judge records: positive=29, negative=145, unknown=39

## Distribution

### by source
- libreoffice_resave: 14
- pptxgenjs: 14
- python_pptx: 38

### by language / aspect
- language: en=50, mixed=3, zh=13
- aspect: 16:9=62, 4:3=4

## core profile

- micro TP/FP/FN: 16/0/0; Precision=1.0, Recall=1.0, F1=1.0
- macro avg over 7 evaluated rules: P=1.0, R=1.0, F1=1.0
- timing: total 1053.638 ms; mean 15.964 ms; median 13.69 ms; p90 18.999 ms; max 137.548 ms (66 scans)

| rule | TP | FP | FN | support+ | support- | Precision | Recall | F1 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| broken_reference | 2 | 0 | 0 | 2 | 8 | 1.0 | 1.0 | 1.0 |
| media_broken | 2 | 0 | 0 | 2 | 15 | 1.0 | 1.0 | 1.0 |
| text_overflow | 3 | 0 | 0 | 3 | 13 | 1.0 | 1.0 | 1.0 |
| font_too_small | 2 | 0 | 0 | 2 | 6 | 1.0 | 1.0 | 1.0 |
| offslide_object | 3 | 0 | 0 | 3 | 17 | 1.0 | 1.0 | 1.0 |
| structure_anomaly | 1 | 0 | 0 | 1 | 11 | 1.0 | 1.0 | 1.0 |
| unfinished_placeholder | 3 | 0 | 0 | 3 | 12 | 1.0 | 1.0 | 1.0 |

### status=error files (excluded from matrix)
- python_pptx/p37_error_truncated_zip.pptx: Not a valid zip/pptx package: File is not a zip file

### cannot-judge scenarios (excluded from matrix)
- libreoffice/lo_p02_clean_zh_typeset_16x9.pptx :: offslide_object :: LO round-trip may rewrite coordinates, fonts and background; geometry heuristic not asserted offline
- libreoffice/lo_p02_clean_zh_typeset_16x9.pptx :: text_overflow :: LO round-trip may rewrite coordinates, fonts and background; geometry heuristic not asserted offline
- libreoffice/lo_p03_clean_mixed_16x9.pptx :: offslide_object :: LO round-trip may rewrite coordinates, fonts and background; geometry heuristic not asserted offline
- libreoffice/lo_p03_clean_mixed_16x9.pptx :: text_overflow :: LO round-trip may rewrite coordinates, fonts and background; geometry heuristic not asserted offline
- libreoffice/lo_p05_clean_decorative_group_16x9.pptx :: text_overflow :: LO round-trip may rewrite coordinates, fonts and background; geometry heuristic not asserted offline
- libreoffice/lo_p06_clean_picture_caption_16x9.pptx :: offslide_object :: LO round-trip may rewrite coordinates, fonts and background; geometry heuristic not asserted offline
- libreoffice/lo_p06_clean_picture_caption_16x9.pptx :: text_overflow :: LO round-trip may rewrite coordinates, fonts and background; geometry heuristic not asserted offline
- libreoffice/lo_p11_clean_valid_internal_rel_16x9.pptx :: offslide_object :: LO round-trip may rewrite coordinates, fonts and background; geometry heuristic not asserted offline
- libreoffice/lo_p11_clean_valid_internal_rel_16x9.pptx :: text_overflow :: LO round-trip may rewrite coordinates, fonts and background; geometry heuristic not asserted offline
- libreoffice/lo_p12_clean_media_alts_16x9.pptx :: offslide_object :: LO round-trip may rewrite coordinates, fonts and background; geometry heuristic not asserted offline
- libreoffice/lo_p12_clean_media_alts_16x9.pptx :: text_overflow :: LO round-trip may rewrite coordinates, fonts and background; geometry heuristic not asserted offline
- libreoffice/lo_p13_clean_table_chart_16x9.pptx :: text_overflow :: LO round-trip may rewrite coordinates, fonts and background; geometry heuristic not asserted offline
- libreoffice/lo_p14_clean_bg_and_content_16x9.pptx :: offslide_object :: LO round-trip may rewrite coordinates, fonts and background; geometry heuristic not asserted offline
- libreoffice/lo_p14_clean_bg_and_content_16x9.pptx :: text_overflow :: LO round-trip may rewrite coordinates, fonts and background; geometry heuristic not asserted offline
- libreoffice/lo_j02_clean_zh_typeset_16x9.pptx :: offslide_object :: LO round-trip may rewrite coordinates, fonts and background; geometry heuristic not asserted offline
- libreoffice/lo_j02_clean_zh_typeset_16x9.pptx :: text_overflow :: LO round-trip may rewrite coordinates, fonts and background; geometry heuristic not asserted offline
- libreoffice/lo_j11_clean_images_table_16x9.pptx :: offslide_object :: LO round-trip may rewrite coordinates, fonts and background; geometry heuristic not asserted offline
- libreoffice/lo_j11_clean_images_table_16x9.pptx :: text_overflow :: LO round-trip may rewrite coordinates, fonts and background; geometry heuristic not asserted offline

## full profile

- micro TP/FP/FN: 29/0/0; Precision=1.0, Recall=1.0, F1=1.0
- macro avg over 12 evaluated rules: P=1.0, R=1.0, F1=1.0
- timing: total 1408.755 ms; mean 21.345 ms; median 20.806 ms; p90 28.428 ms; max 36.875 ms (66 scans)

| rule | TP | FP | FN | support+ | support- | Precision | Recall | F1 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| broken_reference | 2 | 0 | 0 | 2 | 8 | 1.0 | 1.0 | 1.0 |
| media_broken | 2 | 0 | 0 | 2 | 15 | 1.0 | 1.0 | 1.0 |
| structure_anomaly | 1 | 0 | 0 | 1 | 11 | 1.0 | 1.0 | 1.0 |
| text_overflow | 3 | 0 | 0 | 3 | 13 | 1.0 | 1.0 | 1.0 |
| blank_slide | 2 | 0 | 0 | 2 | 23 | 1.0 | 1.0 | 1.0 |
| font_too_small | 2 | 0 | 0 | 2 | 6 | 1.0 | 1.0 | 1.0 |
| missing_alt_text | 2 | 0 | 0 | 2 | 14 | 1.0 | 1.0 | 1.0 |
| offslide_object | 3 | 0 | 0 | 3 | 17 | 1.0 | 1.0 | 1.0 |
| low_contrast | 4 | 0 | 0 | 4 | 5 | 1.0 | 1.0 | 1.0 |
| unfinished_placeholder | 3 | 0 | 0 | 3 | 12 | 1.0 | 1.0 | 1.0 |
| object_overlap | 2 | 0 | 0 | 2 | 14 | 1.0 | 1.0 | 1.0 |
| cjk_typography | 3 | 0 | 0 | 3 | 7 | 1.0 | 1.0 | 1.0 |

### status=error files (excluded from matrix)
- python_pptx/p37_error_truncated_zip.pptx: Not a valid zip/pptx package: File is not a zip file

### cannot-judge scenarios (excluded from matrix)
- python_pptx/p14_clean_bg_and_content_16x9.pptx :: low_contrast :: body text sits over a full-bleed picture; background color cannot be resolved offline, so the contrast rule fails open
- libreoffice/lo_p02_clean_zh_typeset_16x9.pptx :: offslide_object :: LO round-trip may rewrite coordinates, fonts and background; geometry heuristic not asserted offline
- libreoffice/lo_p02_clean_zh_typeset_16x9.pptx :: text_overflow :: LO round-trip may rewrite coordinates, fonts and background; geometry heuristic not asserted offline
- libreoffice/lo_p02_clean_zh_typeset_16x9.pptx :: object_overlap :: LO round-trip may rewrite coordinates, fonts and background; geometry heuristic not asserted offline
- libreoffice/lo_p03_clean_mixed_16x9.pptx :: offslide_object :: LO round-trip may rewrite coordinates, fonts and background; geometry heuristic not asserted offline
- libreoffice/lo_p03_clean_mixed_16x9.pptx :: text_overflow :: LO round-trip may rewrite coordinates, fonts and background; geometry heuristic not asserted offline
- libreoffice/lo_p03_clean_mixed_16x9.pptx :: low_contrast :: LO round-trip may rewrite coordinates, fonts and background; geometry heuristic not asserted offline
- libreoffice/lo_p04_clean_en_4x3.pptx :: object_overlap :: LO round-trip may rewrite coordinates, fonts and background; geometry heuristic not asserted offline
- libreoffice/lo_p04_clean_en_4x3.pptx :: low_contrast :: LO round-trip may rewrite coordinates, fonts and background; geometry heuristic not asserted offline
- libreoffice/lo_p05_clean_decorative_group_16x9.pptx :: text_overflow :: LO round-trip may rewrite coordinates, fonts and background; geometry heuristic not asserted offline
- libreoffice/lo_p05_clean_decorative_group_16x9.pptx :: low_contrast :: LO round-trip may rewrite coordinates, fonts and background; geometry heuristic not asserted offline
- libreoffice/lo_p06_clean_picture_caption_16x9.pptx :: offslide_object :: LO round-trip may rewrite coordinates, fonts and background; geometry heuristic not asserted offline
- libreoffice/lo_p06_clean_picture_caption_16x9.pptx :: text_overflow :: LO round-trip may rewrite coordinates, fonts and background; geometry heuristic not asserted offline
- libreoffice/lo_p06_clean_picture_caption_16x9.pptx :: low_contrast :: LO round-trip may rewrite coordinates, fonts and background; geometry heuristic not asserted offline
- libreoffice/lo_p07_clean_normautofit_16x9.pptx :: object_overlap :: LO round-trip may rewrite coordinates, fonts and background; geometry heuristic not asserted offline
- libreoffice/lo_p07_clean_normautofit_16x9.pptx :: low_contrast :: LO round-trip may rewrite coordinates, fonts and background; geometry heuristic not asserted offline
- libreoffice/lo_p11_clean_valid_internal_rel_16x9.pptx :: offslide_object :: LO round-trip may rewrite coordinates, fonts and background; geometry heuristic not asserted offline
- libreoffice/lo_p11_clean_valid_internal_rel_16x9.pptx :: text_overflow :: LO round-trip may rewrite coordinates, fonts and background; geometry heuristic not asserted offline
- libreoffice/lo_p11_clean_valid_internal_rel_16x9.pptx :: object_overlap :: LO round-trip may rewrite coordinates, fonts and background; geometry heuristic not asserted offline
- libreoffice/lo_p11_clean_valid_internal_rel_16x9.pptx :: low_contrast :: LO round-trip may rewrite coordinates, fonts and background; geometry heuristic not asserted offline
- libreoffice/lo_p12_clean_media_alts_16x9.pptx :: offslide_object :: LO round-trip may rewrite coordinates, fonts and background; geometry heuristic not asserted offline
- libreoffice/lo_p12_clean_media_alts_16x9.pptx :: text_overflow :: LO round-trip may rewrite coordinates, fonts and background; geometry heuristic not asserted offline
- libreoffice/lo_p12_clean_media_alts_16x9.pptx :: object_overlap :: LO round-trip may rewrite coordinates, fonts and background; geometry heuristic not asserted offline
- libreoffice/lo_p12_clean_media_alts_16x9.pptx :: low_contrast :: LO round-trip may rewrite coordinates, fonts and background; geometry heuristic not asserted offline
- libreoffice/lo_p13_clean_table_chart_16x9.pptx :: text_overflow :: LO round-trip may rewrite coordinates, fonts and background; geometry heuristic not asserted offline
- libreoffice/lo_p13_clean_table_chart_16x9.pptx :: low_contrast :: LO round-trip may rewrite coordinates, fonts and background; geometry heuristic not asserted offline
- libreoffice/lo_p14_clean_bg_and_content_16x9.pptx :: low_contrast :: body text sits over a full-bleed picture; background color cannot be resolved offline, so the contrast rule fails open
- libreoffice/lo_p14_clean_bg_and_content_16x9.pptx :: offslide_object :: LO round-trip may rewrite coordinates, fonts and background; geometry heuristic not asserted offline
- libreoffice/lo_p14_clean_bg_and_content_16x9.pptx :: text_overflow :: LO round-trip may rewrite coordinates, fonts and background; geometry heuristic not asserted offline
- libreoffice/lo_p14_clean_bg_and_content_16x9.pptx :: object_overlap :: LO round-trip may rewrite coordinates, fonts and background; geometry heuristic not asserted offline
- libreoffice/lo_j01_clean_en_table_image_16x9.pptx :: low_contrast :: LO round-trip may rewrite coordinates, fonts and background; geometry heuristic not asserted offline
- libreoffice/lo_j02_clean_zh_typeset_16x9.pptx :: offslide_object :: LO round-trip may rewrite coordinates, fonts and background; geometry heuristic not asserted offline
- libreoffice/lo_j02_clean_zh_typeset_16x9.pptx :: text_overflow :: LO round-trip may rewrite coordinates, fonts and background; geometry heuristic not asserted offline
- libreoffice/lo_j02_clean_zh_typeset_16x9.pptx :: object_overlap :: LO round-trip may rewrite coordinates, fonts and background; geometry heuristic not asserted offline
- libreoffice/lo_j02_clean_zh_typeset_16x9.pptx :: low_contrast :: LO round-trip may rewrite coordinates, fonts and background; geometry heuristic not asserted offline
- libreoffice/lo_j11_clean_images_table_16x9.pptx :: offslide_object :: LO round-trip may rewrite coordinates, fonts and background; geometry heuristic not asserted offline
- libreoffice/lo_j11_clean_images_table_16x9.pptx :: text_overflow :: LO round-trip may rewrite coordinates, fonts and background; geometry heuristic not asserted offline
- libreoffice/lo_j11_clean_images_table_16x9.pptx :: object_overlap :: LO round-trip may rewrite coordinates, fonts and background; geometry heuristic not asserted offline
- libreoffice/lo_j11_clean_images_table_16x9.pptx :: low_contrast :: LO round-trip may rewrite coordinates, fonts and background; geometry heuristic not asserted offline

## Observed mismatches (FP/FN/count/severity)

None under current ground truth.

Detailed machine-readable mismatch list: findings/observed_mismatches.json
