# Third-Party Notices

This notice applies to third-party components included in Woobe Core and in any Enterprise distribution, regardless of the directory, package or artifact in which they appear. Every third-party component remains governed by the original license terms supplied by its owner.

Neither the Core license in [LICENSE.md](LICENSE.md), the Enterprise license in [LICENSE_EE.md](LICENSE_EE.md), nor an Enterprise Production Authorization replaces, narrows or expands those third-party terms. Placing a third-party component under an Enterprise Covered Path does not make that component Woobe-licensed Enterprise Software.

Conversely, rights granted by a third-party license apply to that third-party material; they do not grant rights to commercially supply the Woobe platform, execute Woobe Enterprise functionality in production or use Woobe branding. Those rights remain governed by the applicable Woobe documents, including [TRADEMARKS.md](TRADEMARKS.md).

## Release artifact inventory

The [Container quality workflow](.github/workflows/containers.yml) generates SPDX SBOMs for these Core container build targets:

- `woobe-api`
- `woobe-workers`
- `woobe-frontend`
- `woobe-embed`

The workflow derives `.test-artifacts/THIRD_PARTY_INVENTORY.md` from those SBOMs and uploads it as `woobe-third-party-inventory` on manual (`workflow_dispatch`) runs. The inventory records the source artifact, package name, package version, declared license and concluded license reported for each discovered component.

The component notices collected in this file do not constitute a complete dependency inventory. The exact source or binary distribution, including packages and container images, determines which third-party notices and other obligations must accompany it.

SBOM generation is evidence, not legal certification. Before any public release, the exact generated inventory must be reviewed against the original component license text and distribution form.

When a dependency requires attribution, preservation of copyright text, a copy of its license, source availability, a source offer or another distribution obligation, that requirement must be satisfied in the released artifact and reflected in this notice file when applicable.

## Enterprise

Every Enterprise distribution must account for the third-party components actually included in its artifacts. The current workflow inventories the Core container targets listed above; it does not establish coverage of an Enterprise artifact.

An existing inventory may be reused only where it covers the actual components, versions and distribution forms. Additional or different Enterprise artifacts require corresponding inventory and notice coverage. Applicable third-party distribution obligations remain in force even when Enterprise functionality is inactive or used only for development and testing.

## Release gate

[RELEASING.md](RELEASING.md) is the publication gate. The release must not be represented as license-complete merely because automated inventory generation succeeds.

## PyYAML

PyYAML 6.0.3 is used to parse Skill frontmatter. It is distributed under the MIT license; the original notice is reproduced below.

```text
Copyright (c) 2017-2021 Ingy döt Net
Copyright (c) 2006-2016 Kirill Simonov

Permission is hereby granted, free of charge, to any person obtaining a copy of
this software and associated documentation files (the "Software"), to deal in
the Software without restriction, including without limitation the rights to
use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies
of the Software, and to permit persons to whom the Software is furnished to do
so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

## Self-hosted interface fonts

Inter and JetBrains Mono variable Latin/Latin Extended WOFF2 assets are distributed
from Fontsource packages `@fontsource-variable/inter` and
`@fontsource-variable/jetbrains-mono` version 5.3.0 (npm registry). Both families
use the SIL Open Font License 1.1. Full notices are preserved in
`packages/woobe-ui/src/assets/fonts/inter-OFL.txt` and
`packages/woobe-ui/src/assets/fonts/jetbrains-mono-OFL.txt`. Sources:
https://github.com/rsms/inter and https://github.com/JetBrains/JetBrainsMono.

The Guild-inspired v2 reconstruction token values were supplied by the repository
owner in `guild-inspired-enterprise-ui-v2.zip`. Reference screenshots remain
review inputs only and are not shipped as Woobe product assets.

## Native document Markdown parsing

The native document processor uses markdown-it-py 4.0.0 (MIT, copyright 2020
ExecutableBookProject) and mdurl 0.1.2 (MIT, copyright 2015 Vitaly Puzrin/Alex
Kocharin and 2021 Taneli Hukkinen). Both are pinned in uv.lock and remain governed
by their upstream licenses. Full notices are preserved in
[markdown-it-py](docs/licenses/markdown-it-py-4.0.0.txt) and
[mdurl](docs/licenses/mdurl-0.1.2.txt), as well as installed distribution metadata.
Sources: https://github.com/executablebooks/markdown-it-py and
https://github.com/executablebooks/mdurl. Parsing disables HTML rendering and
performs no remote-resource fetch or script execution.

## Native PDF extraction and rendering

The isolated native PDF adapter uses pypdf 6.19.0 (BSD-3-Clause), pypdfium2 5.14.0
(Apache-2.0/BSD-3-Clause), its PDFium 156.0.8076.0 binary and Pillow 12.3.0
(MIT-CMU). Exact wheels and hashes are locked in uv.lock. Full original notices,
including the PDFium build dependencies and Pillow's bundled dependency notices,
are retained under [docs/licenses](docs/licenses). PDFium build notices include
FreeType, ICU, libjpeg-turbo, libpng, OpenJPEG, lcms, zlib, Abseil, AGG, fast_float,
simdutf and llvm-libc; those components retain their individual upstream terms.
The pypdfium2 distribution's CC-BY-4.0 documentation notice is also preserved.
No PyMuPDF/MuPDF component is included in this implementation.

Sources: https://github.com/py-pdf/pypdf,
https://github.com/pypdfium2-team/pypdfium2,
https://pdfium.googlesource.com/pdfium/ and https://github.com/python-pillow/Pillow.
The original FreeType attribution is: "Portions of this software are copyright
© The FreeType Project (www.freetype.org). All rights reserved."

## Optional model-free Docling conversion

The `docling-processing` extra uses the official Docling Slim 2.140.0 distribution,
Docling Core 2.103.1 and Docling Parse 7.22.1, licensed under MIT. The selected
NativePdfPipeline and DOCX SimplePipeline use no model weights, Torch or implicit
model downloads. Model-based layout/OCR/enrichment is not enabled by this profile.

Exact parser dependencies are pinned and inventoried in
[the license manifest](docs/licenses/docling-dependencies/manifest.json), together
with their retained upstream notices. They include Python Docx, lxml, Doclang,
NumPy, SciPy, pandas, Rtree, tabulate, defusedxml and latex2mathml. Optional binary
dependency notices include their own bundled components; in particular SciPy's
compiler runtime is covered by its retained GCC Runtime Library Exception.
The first-party Woobe license does not replace these upstream terms.

Upstream sources: https://github.com/docling-project/docling,
https://github.com/docling-project/docling-core,
https://github.com/docling-project/docling-parse, https://github.com/python-openxml/python-docx,
https://github.com/lxml/lxml, https://github.com/numpy/numpy,
https://github.com/scipy/scipy, https://github.com/pandas-dev/pandas and
https://github.com/Toblerity/rtree. latex2mathml's source and wheel omit the license
file; its original upstream MIT notice is retained from commit
`902beef9cb7794183c1114b0b09b27b5695ad252` in
https://github.com/roniemartinez/latex2mathml, with the notice digest recorded in
the license manifest.

## Optional native OCR

The native OCR profile invokes Tesseract 5.5.0 (Apache-2.0) and uses the official
tessdata_fast eng, por and osd artifacts from commit
`87416418657359cb625c412a48b6e1d6d41c29bd` (Apache-2.0). Source URLs, file sizes and
SHA-256 digests are retained in the packaged tesseract-fast-v1 manifest. The full
[upstream model license](docs/licenses/tesseract-tessdata-fast-Apache-2.0.txt) is
retained. Engine/system dependency notices remain in their original installed
distribution, including Tesseract and Leptonica package documentation; this
profile does not replace those terms.

Sources: https://github.com/tesseract-ocr/tesseract,
https://github.com/tesseract-ocr/tessdata_fast and https://github.com/DanBloomberg/leptonica.
Synthetic OCR fixtures use locally installed DejaVu Sans to render first-party
test text; no font binary is copied into the repository.
