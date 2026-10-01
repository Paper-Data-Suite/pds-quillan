# Issue #416 Slice 2 — retained PDF byte-decoding boundary

Quillan previously handed the canonical Core-retained PDF path directly to
`pdf2image` through `pdfinfo_from_path(...)` and `convert_from_path(...)`.

That made Poppler responsible for opening the workspace path and exposed valid
historical retained scans to native Windows path-length limitations.

Slice 2 changes only the PDF decoding boundary:

```text
validated Core retained PDF
        ↓
Python Path.read_bytes()
        ↓
pdfinfo_from_bytes(...) / convert_from_bytes(...)
        ↓
pdf2image bounded temporary file
        ↓
Poppler
```

The Core-retained file remains authoritative and is not renamed, copied into the
workspace, migrated, or rewritten. The `pdf2image` byte APIs create
non-authoritative temporary files for their own Poppler invocation and remove
them afterward.

The existing Quillan page-count and page-conversion error categories remain in
place. A filesystem read failure is reported as the operation-specific PDF
page-count or page-conversion failure.

This slice intentionally does not yet change retained-image decoding through
OpenCV. That is the next #416 boundary.
