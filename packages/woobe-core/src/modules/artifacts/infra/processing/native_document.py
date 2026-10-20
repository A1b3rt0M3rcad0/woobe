from modules.artifacts.application.document_codec import decode_canonical
from modules.artifacts.infra.processing.native_pdf import NativePdfProcessor


class NativeDocumentProcessor(NativePdfProcessor):
    name, version = 'native-document', '1'
    media_types = frozenset({'application/pdf', 'image/png', 'image/jpeg'})
    supports_ocr = True
    child_module = 'modules.artifacts.infra.processing.document_child'
    failure_code = 'DOCUMENT_CONVERSION_FAILED'

    def __init__(self, *, ocr_data_dir=None, tesseract_executable='/usr/bin/tesseract', **options):
        super().__init__(**options)
        self.ocr_data_dir = str(ocr_data_dir) if ocr_data_dir is not None else None
        self.tesseract_executable = str(tesseract_executable)

    def source_name(self, revision):
        media = revision.content_type.split(';', 1)[0].strip().lower()
        return {'application/pdf': 'source.pdf', 'image/png': 'source.png', 'image/jpeg': 'source.jpg'}[media]

    async def process(self, revision, content, profile, *, publish_asset=None):
        value = await self._execute(revision, content, profile, 'extract', publish_asset=publish_asset,
            ocr_data_dir=self.ocr_data_dir, tesseract_executable=self.tesseract_executable)
        return decode_canonical(value)
