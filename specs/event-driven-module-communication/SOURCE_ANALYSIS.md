# SOURCE ANALYSIS — development

## Baseline

- Repository: `A1b3rt0M3rcad0/ProjectRAI`
- Branch: `development`
- HEAD observado: `cd8d5867967fea25ea170bd88ebc9a461ed16c09`
- Branch proposta: `development_event-driven-module-communication`

## Achados

1. Tool já foi consolidada em `agent`; Agent→Tool é chamada interna, não integração cross-module.
2. `MeteringUsageRecorder` e `ObservabilityTraceRecorder` importam internals e gravam diretamente nos módulos consumidores usando a sessão/UoW do agent.
3. Sync, stream e AskJob repetem esse acoplamento.
4. O writer de Outbox do agent hardcodeia `agent.event` e perde idempotência/routing dos eventos de domínio.
5. As filas agent/identity/core/billing estão ligadas ao próprio prefixo e vários routers apenas escrevem log.
6. Metering e observability têm registries vazios; seus consumers atuais só varrem tabelas locais.
7. O startup constrói o WorkerRunner, mas não inicia o loop.
8. Inbox/Outbox de módulos não são uniformes quanto a message_id, routing, idempotency e locks.
9. FKs cross-module persistem em core, billing, metering e observability.
10. Streaming usa objetos ligados a sessões fechadas e mantém transações/objetos por fases inadequadas.

## Decisão

Corrigir contrato e runtime de mensageria primeiro; depois transformar agent em producer puro, implementar metering/observability como consumers reais, limpar os demais módulos e remover FKs.
