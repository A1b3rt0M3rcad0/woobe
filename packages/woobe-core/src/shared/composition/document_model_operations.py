"""Cross-context wiring through the owning module's public capability only.

The caller owns the transaction; this bridge neither queries owner tables nor
opens a second unit of work. No credential material crosses this boundary.
"""
from modules.agent.entrypoint import build_operation_model_bindings
from modules.core.entrypoint import build_project_configuration_runtime


def operation_model_bindings(session):
    return build_operation_model_bindings(session, configuration=build_project_configuration_runtime(session))


def operation_model_runtime():
    from modules.agent.entrypoint import build_operation_model_runtime
    return build_operation_model_runtime()


def operation_configuration_resolver(*, verifier, session_factory, encryption_key):
    from modules.core.entrypoint import build_operation_configuration_runtime_resolver
    return build_operation_configuration_runtime_resolver(operation_verifier=verifier,
        session_factory=session_factory, encryption_key=encryption_key)


def document_model_usage_consumer(engine):
    from modules.metering.entrypoint import build_document_model_usage_consumer
    return build_document_model_usage_consumer(engine)
