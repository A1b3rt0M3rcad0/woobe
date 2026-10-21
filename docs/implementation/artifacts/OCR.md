# Selective native OCR and visual provenance

`native-document` version `1` supports static PNG, JPEG and PDF. It preserves
source visuals without manufacturing text when OCR is not selected. Recipes can
select `native-tesseract` version `1`, backed by the qualified Tesseract 5.5.0
engine. Default languages resolve explicitly to `por, eng` in the frozen recipe;
other uninstalled languages are unready. A maximum of eight language selectors
is accepted. Recognition and orientation data are pinned to the official
tessdata_fast commit `87416418657359cb625c412a48b6e1d6d41c29bd` and exact SHA-256
digests. The engine binary, build information and model manifest also enter the
recipe fingerprint.

Install public model files explicitly with `scripts/processing/acquire_models.py`,
using the shipped `manifests/tesseract-fast-v1.json`, then run
`scripts/processing/qualify_tesseract.py --directory <model-directory>`. Set
`WOOBE_ARTIFACT_OCR_DATA_DIR` to that directory; the optional executable setting is
`WOOBE_ARTIFACT_TESSERACT_EXECUTABLE`, default `/usr/bin/tesseract`. Runtime never
downloads models. A missing language, changed binary, corrupt model or missing
qualification receipt cannot become an empty successful result. Capability checks
stream-verify installed file hashes without loading an OCR model or starting the
engine. The Worker additionally verifies the real engine/build before processing.
Receipts survive filesystem copies because identity depends on bytes rather than
inode timestamps.

Native PDF text remains native. Scanned pages receive OCR; blank native pages are
not recognized again. On a hybrid page, direct image regions without existing
native text can receive OCR independently. Existing native text and overlapping
regions are preserved without duplicate recognition. Nested Form XObject geometry,
very small regions or regions already containing native text retain their visual
and explicit partial diagnostics instead of guessed coordinates. Word boxes map
back through orientation and crop transforms into the preserved source visual.
Physical PDF indices stay zero-based and display numbers one-based. Images use a
separate normalized image_bbox and have no invented PDF pages.

JPEG EXIF orientation is applied to the preserved PNG visual. Transparency is
composited onto white; original revisions remain byte-for-byte unchanged. Derived
PNG metadata is stripped. Tesseract OSD orientation is applied only with its
reported confidence at least five; missing/low confidence is explicit. TSV word
scores remain raw, uncalibrated engine-reported scores, with unknown confidence
represented by null. No probability or aggregate certainty is fabricated. OCR
blocks identify extraction_method=ocr, their source asset, canonical character
space and raw word/region evidence. SourceRef character coordinates into those
blocks require an exact representation generation.

Source images and page renders are limited to 16 million pixels, each PNG to
64 MiB, visual manifests to 4 MiB and the total visual output to the bounded
processing budget (at most 512 MiB). Existing recipe page/block/line/time limits
also apply. Each job has private scratch and an isolated process group, bounded
memory/CPU/files/descriptors, no inherited provider environment and no conversion
network access. Cancellation drains actual Tesseract descendants, including
repeated cancellation, before scratch removal and owner acknowledgement.

Visual bytes stream to private immutable storage outside database transactions.
Canonical asset identities must match every successfully stored visual; a small
checkpoint points to a verified visual manifest instead of embedding large blobs
in SQL. Failed or cancelled stages cannot publish a successful canonical receipt.
Public coherent generation publication and derived-byte lifecycle/accounting are
the next step, 19; these private staging objects are not advertised as ready public
representations. OCR results always retain honest partial visual coverage and do
not claim semantic understanding of figures, formulas or tables.

The Docker profiles `native-ocr` and `docling-ocr` install the actual engine,
explicitly acquire/qualify pinned models and make them readable by the existing
unprivileged runtime user. Base/Docling-only images can start without OCR models.
The native dependency path and standalone qualification script are tested locally;
a full optional product image build has not been qualified locally. The dedicated
read-only CI workflow uses the actual native engine, local fixtures, PostgreSQL
and a real S3-compatible server.

Qualification includes real Portuguese accents, PNG/JPEG/EXIF, scanned and hybrid
PDF pages, known poor scans, orientation, pixel limits, original byte preservation,
portable/corrupt model receipts, raw score provenance, live-engine cancellation,
durable lost-ACK recovery and cancellation acknowledgement. Blank/unreadable scans
keep their visual instead of claiming complete extraction. Test fixtures are
first-party authored; DejaVu is used only to render synthetic fixture glyphs.

Stage 19 publishes verified visual outputs inside coherent read-only generations;
see [REPRESENTATIONS.md](REPRESENTATIONS.md). Every persisted derivative now has a
durable quota intent and receipt. The private checkpoint boundary above describes
the stage 18 implementation, rather than the current public publication surface.
