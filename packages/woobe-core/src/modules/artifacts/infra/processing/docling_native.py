from modules.artifacts.infra.processing.native_pdf import NativePdfProcessor


DOCX_MEDIA_TYPE = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'


class DoclingNativeProcessor(NativePdfProcessor):
    name, version = 'docling-native', '2.140.0'
    media_types = frozenset({'application/pdf', DOCX_MEDIA_TYPE})
    child_module = 'modules.artifacts.infra.processing.docling_child'
    failure_code = 'DOCUMENT_CONVERSION_FAILED'

    def source_name(self, revision):
        return 'source.pdf' if revision.content_type.split(';', 1)[0].strip().lower() == 'application/pdf' else 'source.docx'
