# ProjectRAI — Module Communication Hardening

Pacote independente com **10 specs** para corrigir os problemas encontrados na comunicação event-driven entre módulos.

## Branch de execução

`development_event-driven-module-communication`

## Baseline de remediação

`b4f5c9cc9d8a9d990e3ae330c036440d9843c2c8`

## Pasta da suíte

```text
specs/module-communication-hardening/
```

## Ordem

1. `000` — reabrir o cutover e criar gates de regressão;
2. `001` — corrigir async/await e fronteiras transacionais do Agent;
3. `002` — remover o caminho legado cross-module do AskJob;
4. `003` — completar eventos do Agent e corrigir idempotência;
5. `004` — corrigir Metering;
6. `005` — corrigir Observability;
7. `006` — corrigir Tool e remover self-subscription do Agent;
8. `007` — padronizar producers dos demais módulos;
9. `008` — endurecer RabbitMQ, DLQ, ACK, retry e replay;
10. `009` — executar cutover com zero violação.

## Regra de conclusão

Nenhuma spec pode ser concluída com testes obrigatórios falhando, violação arquitetural em allowlist ou fluxo legado cross-module ainda ativo.
