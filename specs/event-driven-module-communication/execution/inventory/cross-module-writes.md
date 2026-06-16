# Cross Module Writes

Levantamento em: 2026-06-16

## Agent → Metering (writes diretos)

### agent/infra/adapters/metering_usage_recorder.py
- `MeteringUsageRecorder` usa `modules.metering.infra.database.repositories` para persistir registros de uso
- Utiliza a mesma transação/sessão do agent (compartilhamento de UoW)
- **Violação**: escreve em tabelas de metering usando transação do agent

### agent/application/composers/ask_agent_composer.py
- Importa `MeteringUsageRecorder` — injeta o recorder que escreve em metering

### agent/infra/workers/ask_job_worker.py
- Importa `MeteringUsageRecorder` — worker do agent escreve em metering

## Agent → Observability (writes diretos)

### agent/infra/adapters/observability_trace_recorder.py
- `ObservabilityTraceRecorder` usa `modules.observability.infra.database.repositories` para persistir traces
- Utiliza a mesma transação/sessão do agent (compartilhamento de UoW)
- **Violação**: escreve em tabelas de observability usando transação do agent

### agent/application/composers/ask_agent_composer.py
- Importa `ObservabilityTraceRecorder` — injeta o recorder que escreve em observability

### agent/infra/workers/ask_job_worker.py
- Importa `ObservabilityTraceRecorder` — worker do agent escreve em observability

## Classificação

| Origem | Destino | Mecanismo | Severidade | Spec de correção |
|---|---|---|---|---|
| agent (MeteringUsageRecorder) | metering | direct repository + shared UoW | alta | 011-012 |
| agent (ObservabilityTraceRecorder) | observability | direct repository + shared UoW | alta | 013-014 |
