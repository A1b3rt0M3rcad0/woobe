# Estado atual do banco

*Populado na spec 001 via análise estática. Consultas diretas ao PostgreSQL pendentes.*

## Schemas identificados

| Schema | Origem | Status final esperado |
|---|---|---|
| `agent` | Target schema | Permanecer |
| `ai` | Legacy (bounded context agent) | Migrar para `agent` |
| `knowledge` | Legacy (bounded context agent) | Migrar para `agent` |
| `runtime` | Legacy (bounded context agent) | Migrar para `agent` |
| `core` | Módulo independente | Permanecer inalterado |
| `identity` | Módulo independente | Permanecer inalterado |
| `billing` | Módulo independente | Permanecer inalterado |
| `metering` | Módulo independente | Permanecer inalterado |
| `observability` | Módulo independente | Permanecer inalterado |
| `tools` | Módulo independente | Permanecer inalterado |

## Pendências PostgreSQL

- Row counts por tabela: não disponível (sem acesso ao banco)
- Comparação `Base.metadata` vs catálogo real: não disponível
- Drift entre ambientes: não disponível
- Objetos não-modelados (views, funções, triggers, RLS, grants): não verificados
