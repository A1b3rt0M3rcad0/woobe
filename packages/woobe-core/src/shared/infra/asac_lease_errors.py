"""Map only known database fencing failures after the owner transaction rolls back."""
from functools import wraps
from sqlalchemy.exc import DBAPIError
from shared.contracts.errors import ConflictError


def asac_lease_database_errors(method):
    @wraps(method)
    async def guarded(*args,**kwargs):
        try:
            return await method(*args,**kwargs)
        except DBAPIError as error:
            for code in ('ASAC_LEASE_FENCED','ASAC_LEASE_EXPIRED','ASAC_DEPLOYMENT_COMMIT_INVALID','ASAC_DEPLOYMENT_RECEIPT_REQUIRED','ASAC_SELECTION_MANAGED'):
                if code in str(error.orig):
                    raise ConflictError(code+': Database rejected an incompatible lifecycle transaction') from None
            raise
    return guarded
