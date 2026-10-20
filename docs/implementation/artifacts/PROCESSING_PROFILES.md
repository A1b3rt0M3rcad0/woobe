# Immutable processing configuration

Processing recipes are independent of upload. The default is store_only, which
stores originals without executing a parser, indexer, OCR engine or model. A
Workspace can bind an exact profile ID/revision with Workspace CAS, or clear its
binding. An explicit request can select another exact revision; moving latest
aliases are not execution identities. List pages show the latest revision of each
profile ID, while old immutable revisions remain individually readable.

Recipes explicitly select versioned processor, optional OCR component, optional
indexer and optional model enricher. Each component declares original/canonical/
index input, canonical/index/enrichment output, supported media, byte/page/time
ceilings and exact library pins. Shared recipe limits also bound blocks and model
output tokens. Native parameters have typed allowlists and bounded values; there
is no arbitrary string dictionary that could quietly carry an API credential.
Model references contain UUID configuration/model identities and their revisions,
never plaintext credentials, tokens, ciphertext or temporary URLs.

The passive registry normalizes exact library pins, rejects unknown versions,
incompatible limits/input contracts/OCR composition and contradictory dependency
versions. Declaring/importing a recipe never imports a converter, installs weights
or calls a provider. Installed-distribution probes read package metadata only.
Optional implementation/dependency absence produces ready=false with public safe
diagnostics and no ready media formats. A model reference remains unready until
its binding has been explicitly verified by the governed model integration.

At this stage the production registry has no converter implementation registered;
store_only is ready and no extraction/indexing format is advertised. Native text,
PDF, Docling, OCR and index adapters are registered in their dedicated steps after
qualification. Historical profile configuration stays readable and unready when
an optional component is removed or its compatible limits/library pins change.

Profile revisions are scoped by Project/Environment, immutable JSON plus SHA-256,
and cannot be updated through SQL. Repeating the same revision/recipe is idempotent;
changing it conflicts. Workspace defaults have a composite scoped foreign key, so
a revision in another Environment/Project cannot be substituted. Profile creation
requires current administrative project authority; Runtime Keys cannot create
profiles. Selection/default changes additionally use current Workspace grants.

The recipe fingerprint includes component/model/configuration/library versions,
limits and parameters. Processing identity adds the exact original digest, size
and MIME. Identical bytes and recipe have the same reuse identity; parser/library/
model/parameter changes invalidate it. Storage/reuse lookup must still be scoped
to the authorized Workspace and exact source; a content hash is never authority.

The HTTP host exposes artifact-processing-profiles (POST, paged GET, exact revision
GET), Workspace processing-profile (CAS PUT and explicit/default selection GET),
and passive artifact-processing-capabilities. These use the same exact reviewed
Control/Artifacts Runtime permissions and versioned DTOs as direct file operations.
Selection/configuration never schedules work. Manual durable processing is the
next worker step; this profile step does not claim extraction or index completion.

Qualification covers secret-bearing/invalid configuration, incompatible limits,
missing optional dependency, unsupported MIME, separate OCR/index/model contracts,
reproducible/invalidation fingerprints and no optional import side effects. Real
PostgreSQL and HTTP cases verify immutable/idempotent revisions, SQL update refusal,
Workspace CAS/default/reset/manual selection, scoped FK refusal, Runtime creation
denial, bounded signed profile pages and readable historical missing-plugin recipes.
