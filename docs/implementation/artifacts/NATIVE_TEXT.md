# Native text extraction

The `native-text` processor, version `1`, executes in the existing Worker. Its
recipe pins Python, markdown-it-py 4.0.0 and mdurl 0.1.2. TXT, CommonMark Markdown,
JSON and CSV use no model, network fetch, HTML evaluation or script execution.
MIT dependency notices are retained under `docs/licenses`.

Original revisions remain immutable. Canonical blocks carry independent half-open
byte and Unicode character ranges into the original, decoded source. BOM bytes
are excluded from character coordinates and included in byte positions. Physical
line coordinates start at one and have an exclusive end. Canonical block text
normalizes CRLF/CR to LF, explicitly recorded in each locator. Plain text has no
invented pages. UTF-8, BOM-qualified UTF-16 and explicitly declared Latin-1 are
strictly decoded; invalid encoding and decoded NUL fail explicitly.

Markdown headings retain their level, lists retain their structural token data,
and fenced code remains code even when its contents contain heading markers.
Literal original syntax is retained in block text. JSON retains valid original
numeric tokens rather than coercing arbitrary precision numbers to floats;
duplicate keys and non-finite literals fail. CSV explicitly treats its first row
as columns and preserves quoted multiline cell strings, with bounded rows,
columns, cells, source lines, nesting and canonical output bytes.

Empty documents report unsupported coverage and `empty_document`, never complete
extraction. All source content has `untrusted_source` trust level. Canonical JSON
is streamed to a private attempt object, verified by size and SHA-256, and its
small metadata checkpoint is committed separately. A lost checkpoint ACK resumes
without re-parsing an already committed stage. Publication as a public immutable
representation generation is delivered by step 19; this step exposes no public
derived-object download or representation identity.

`tests/fixtures/artifacts/native-text` contains a Portuguese CRLF/Unicode source
and its reviewed structural golden file. Unit tests check actual original byte
slices, all supported encodings, repeated headings, code markers, CSV empty
tables and multiline cells, precise JSON, integrity failures, closure and limits.
PostgreSQL integration executes the public background factory on local and real
S3-compatible storage, across fresh and populated upgrades, with injected lost
ACK after the native extraction checkpoint.
