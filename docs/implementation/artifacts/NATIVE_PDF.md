# Native PDF processing

`native-pdf` version `1` accepts verified application/pdf originals. The recipe
pins pypdf 6.19.0, pypdfium2 5.14.0, PDFium 156.0.8076.0, Pillow 12.3.0 and Python.
The PDFium engine is checked against its qualified version inside the child.
Dependency licenses and binary build notices are retained under `docs/licenses`.
Synthetic fixtures are first-party authored and contain no downloaded fonts or
books. Their source generator and physical-page golden file are checked in.

Extraction and PNG rendering execute in a dedicated Linux subprocess, with no
inherited provider/configuration environment. Each invocation uses an exclusive
private scratch directory. CPU, address-space, file-size and descriptor limits
apply; wall time and cancellation kill and reap the owned process group before
removing scratch. Original input is streamed to disk and checked against its
declared size/SHA-256 before parsing. API/Core entrypoint and passive capability
discovery do not import PDFium, Pillow or the PDF parser implementation.

Every physical page has its zero-based index, one-based presentation number,
separate PDF page label, dimensions, text character count, status and diagnostics.
Roman labels never replace physical identity. Text blocks reference page-extracted
Unicode coordinates, never fabricated byte offsets into compressed PDF objects.
PDFium expands ligatures; its exact version is part of the recipe fingerprint.
All extracted source remains untrusted data. Forms and JavaScript are never
initialized, and annotations/actions or remote references are not executed.

Image-only pages report needs_ocr, blank pages report empty, and mixed documents
report partial coverage. Large same-baseline glyph gaps flag possibly degraded
reading order; this conservative heuristic does not promise column reconstruction.
The inspection is bounded and explicitly reports truncation on very large pages.
Entirely image-only documents report needs_ocr; empty documents report unsupported.
No empty result is complete. Password-protected and invalid PDFs have distinct
safe error codes; protected files are not decrypted by the platform.

Rendering addresses the physical page index and enforces 72–300 DPI, at most
16 million pixels and a 64 MiB PNG. Page and original byte limits apply before
rendering. The native adapter returns actual PNG bytes for the representation
pipeline; publication/authorized visual read APIs are delivered with immutable
representation generations in subsequent steps.

Qualification includes a 12-page synthetic document with a table of contents,
Roman labels, blank and image pages, two columns, a chapter crossing pages and a
Unicode ligature map. It verifies that page number 12 resolves to physical index
11. Real PNG decoding, protected/corrupt/disguised PDFs, page/pixel budgets,
cancelled rendering and wall-time process cleanup are tested. The existing public
background factory processes actual uploaded PDFs against PostgreSQL and both
storage adapters; original bytes remain unchanged. Detailed diagnostics stay in
the canonical object while checkpoint/result summaries are bounded to 32 entries.
