# Análise de origem — baseline `project-rai-playground`; execução `project-rai-playground_module-architecture-standardization`

## Escopo inspecionado

Repositório `A1b3rt0M3rcad0/ProjectRAI`. O diagnóstico inicial foi realizado na branch baseline `project-rai-playground`, comparada com `master` em 14 de junho de 2026. A execução deste pacote deve ocorrer exclusivamente na branch dedicada `project-rai-playground_module-architecture-standardization`, criada a partir da baseline ou atualizada de forma explicitamente registrada.

## Evidências relevantes

1. A baseline `project-rai-playground` estava 124 commits à frente de `master` e continha `src/modules/agent` no momento da inspeção.
2. `agent` possui uma estrutura mais próxima do padrão desejado: `application/composers`, `application/dtos`, `application/use_cases`, `domain`, `infra/database`, `infra/messaging`, `infra/workers` e `presentation/controllers`.
3. `AgentUnitOfWork` expõe repositories próprios, além de Inbox e Outbox, mas o composer de criação de agente ainda usa `shared.infra.database.postgres_unit_of_work.PostgresUnitOfWork`. O padrão precisa ser estabilizado antes de replicação.
4. `billing`, `core`, `identity`, `metering`, `observability` e `tools` mantêm models e repositories diretamente em `infra/`, enquanto casos de uso/DTOs permanecem em `service/`.
5. FKs cruzam bounded contexts:
   - `core` referencia `identity`;
   - `billing` referencia `identity`;
   - `metering` referencia `core` e o schema legado `ai`;
   - `observability` referencia `core`, `ai` e `runtime`;
   - `tools` referencia `core` e `ai`.
6. Todos os módulos observados possuem Outbox/Inbox próprias, mas a localização e a execução dos workers ainda não estão uniformizadas.
7. Eventos existentes usam nomenclaturas não uniformes, como `plan.created` e `subscription.created`, enquanto a convenção final exige `<module>.<event>.v<version>`.

## Decisão de interpretação

“Mesma arquitetura do módulo de agentes” significa padronizar camadas, direção de dependências, composição, UoW, persistência, messaging e workers. Não significa replicar subpacotes específicos de LLM nem criar arquivos vazios sem responsabilidade real.

## Regra de branch

- Branch baseline de diagnóstico: `project-rai-playground`.
- Branch única de implementação: `project-rai-playground_module-architecture-standardization`.
- Nenhuma spec autoriza commits de implementação diretamente na baseline.
- Antes de executar qualquer spec, registrar `git branch --show-current` e `git rev-parse HEAD` em `execution/runtime.md`.
- Se a branch dedicada ainda não existir local ou remotamente, sua criação é pré-condição bloqueante; não executar a migração em outra branch por conveniência.

## Limitação operacional

As specs obrigam um discovery executável no início porque a branch dedicada pode divergir da baseline e porque a inspeção por API não substitui `find`, `rg`, AST e introspecção real do banco executados no checkout local.
