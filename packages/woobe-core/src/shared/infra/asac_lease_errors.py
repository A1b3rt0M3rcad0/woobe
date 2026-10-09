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
            for code in ('ASAC_LEASE_FENCED','ASAC_LEASE_EXPIRED'):
                if code in str(error.orig):
                    raise ConflictError(code+': Database rejected a superseded or expired workflow lease') from None
            raise
    return guarded
