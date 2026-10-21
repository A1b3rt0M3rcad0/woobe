from shared.contracts.object_storage import ObjectStorageError


def legacy_document_error(error: ObjectStorageError):
    if error.code in {'invalid_key', 'invalid_object', 'range', 'integrity'}:
        return ValueError(str(error))
    if isinstance(error.__cause__, OSError):
        return error.__cause__
    if error.code == 'not_found':
        return FileNotFoundError('Document is unavailable')
    return OSError(str(error))
