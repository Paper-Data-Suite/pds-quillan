# Issue #416 Slice 3 — retained image byte-decoding boundary

Quillan previously passed the canonical Core-retained image path directly to
OpenCV through `cv2.imread(...)`.

Slice 3 changes retained-image loading to:

```text
validated Core retained image
        ↓
Python Path.read_bytes()
        ↓
numpy byte buffer
        ↓
cv2.imdecode(...)
```

The retained Core file remains authoritative and unchanged. OpenCV receives
only the encoded image bytes and does not need to reopen the workspace path.

Historical Core 0.6 long retained filenames therefore no longer depend on
OpenCV's path-opening behavior.

The existing `QuillanPageImageError` boundary remains authoritative for
retained-image read/decode failures.

This slice does not change Quillan's standalone pre-retention/source diagnostic
reader in `qr_decode.py`; #416's production retained-source path boundary is
`retained_scan_pages.py`.

No workspace migration, rename, or record rewrite is performed.
