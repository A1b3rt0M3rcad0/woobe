# Optional offline Docling profile

Install Core with `woobe-core[docling-processing]`, or use the root frozen extra
`uv sync --frozen --all-groups --extra test --extra docling-processing`. The extra
pins the official Docling Slim 2.140.0, Core 2.103.1 and Parse 7.22.1 distributions
and their parser dependencies. The shipped package includes a small, hashed
manifest. Its digest and every parser version enter the recipe fingerprint.
The child refuses a frozen manifest that differs from its installed manifest.
The Docker dependency stage also accepts
`--build-arg WOOBE_PROCESSING_PROFILE=docling-native` when building the existing
`workers` target. The default `base` profile omits the extra; unknown profile
names fail. Native frozen-extra and wheel checks qualify the dependency/package
path; a complete optional Docker image build has not been qualified locally.

The qualified component is `docling-native` version `2.140.0`. DOCX uses the
official SimplePipeline and native PDF uses the official NativePdfPipeline.
Neither uses weights or Torch. The model manifest deliberately has an empty
models list because this active profile requires none. Model-based layout,
table recognition, OCR or picture understanding is not advertised by this profile.
Native PDF reports partial coverage and `native_pdf_layout_not_inferred`; its
parser order and boxes are evidence, not an inferred promise of reading order.

DOCX headings, actual upstream parent hierarchy, lists, structured table cells,
figures and text map to the shared canonical contract. Per-item original Docling
JSON is retained as private evidence, excluding image binary/path fields. Figures
without transcribed content report partial coverage. DOCX has no fabricated PDF
pages or byte offsets into its ZIP container. PDF blocks retain physical page
identity, separate printed labels and normalized top-left boxes. Character spans
explicitly address canonical block text and require the exact representation
generation when used in a SourceRef.

The existing Worker runs each conversion in its own subprocess and private scratch
directory. `WOOBE_ARTIFACT_DOCLING_MEMORY_MIB` defaults to 2048 (512–8192), and
`WOOBE_ARTIFACT_DOCLING_THREADS` defaults to 2 (1–8). CPU/time/file/descriptor limits,
process-group cancellation and cleanup use the qualified isolated execution path.
The child inherits no provider credential environment and disables network
connections, remote services, external plugins and picture/model enrichment.
The DOCX backend disables the lazy LibreOffice fallback; macros, embedded active
objects and external image/template/resource relationships are refused. Hyperlink
text stays untrusted source data. XML uses defused parsing and ZIP entry/count/
expanded-byte checks. Legacy drawings or unevaluated active fields report explicit
diagnostics instead of claiming complete conversion.

API/Core import and capability discovery inspect metadata only. Without the extra,
the component has ready=false and no advertised media types; actual execution
returns PROCESSOR_UNAVAILABLE. This is checked in a separate real base venv, and
CI installs the base first before adding the optional profile. No framework import,
model download or conversion occurs during API startup imports.

`scripts/processing/acquire_models.py` is an explicit acquisition tool for future
audited model profiles. A nonempty manifest requires immutable 40-hex revisions,
licenses, approved HTTPS upstreams, exact file sizes and SHA-256 digests. The
default verifies offline; `--download` explicitly permits acquisition. Files are
bounded, privately staged, verified and published without overwriting existing
artifacts. Conversion never invokes this tool. Tests use labeled integrity
fixtures; they do not qualify real model weights. Hugging Face access is currently
refused by the environment proxy, and a network configuration draft is saved for
optional future weight acquisition. This does not prevent the qualified model-free
profile from operating offline.

Qualification executes real library conversions of a Portuguese DOCX with nested
headings, table and figure, and a multicolumn 12-page PDF with missing text. It checks
structure, parent references, physical pages/boxes, canonical codec roundtrip,
untrusted evidence, protected PDFs, macro/external-resource refusal and stale
manifest rejection. Actual PostgreSQL/Worker/local/S3 cases cover the optional PDF
profile. Full license notices, including bundled scientific-library runtime terms,
are retained under docs/licenses/docling-dependencies. No ML-weight quality claim
is made by these checks.
