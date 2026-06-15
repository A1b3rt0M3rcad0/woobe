# 006 — define-presentation-contract

## Tipo

architecture

## Objetivo

Padronizar controllers, routes, schemas e mappers sem alterar contratos HTTP.

## Contexto

Os módulos já possuem controllers e routes, mas a localização e os tipos de retorno precisam ser uniformes.

## Pré-condições

- 004 completed

## Estado atual a detectar

Execute na raiz do checkout da branch `project-rai-playground_module-architecture-standardization`:

```bash
find src/modules -path "*/presentation/*" -type f | sort
rg "APIRouter|class .*Controller|Response\(" src/modules -g "*.py"
```

Persistir qualquer saída de inventário indicada no plano. Comando ausente no ambiente deve ser registrado como bloqueio em `execution/runtime.md`; não substituí-lo por suposição.

## Alterações permitidas

- presentation/controllers
- presentation/routes.py
- presentation/schemas.py
- presentation/mappers.py

## Alterações proibidas

- não fundir bounded contexts apenas para igualar diretórios
- não criar base repository/UoW genérico com semântica de domínio
- não executar rename destrutivo de tabela ou coluna sem expand-migrate-contract
- não alterar regra de negócio de outro módulo
- não importar internals de outro módulo
- não mover domínio para shared
- não colocar worker concreto em src/workers ou shared/workers
- não alterar contrato público sem shim/deprecation e teste de compatibilidade
- não criar comunicação síncrona direta entre módulos para mudança de estado
- não criar Foreign Key física para tabela pertencente a outro módulo

## Plano de implementação

1. Inventariar contratos HTTP atuais.
2. Manter prefixos/status/body durante moves.
3. Routes apenas adaptam FastAPI e chamam composer.
4. Controllers validam DTO e chamam use case.
5. Mappers convertem output para schema público.

## Contratos esperados

- Nenhum controller abre sessão ou instancia repository.
- Nenhuma route contém regra de negócio.
- Shim de rota deve delegar e emitir deprecation.

## Testes obrigatórios

- tests/contract/test_http_routes_compatibility.py

## Comandos de validação

```bash
ruff check src tests
pyright
pytest tests/architecture -q
pytest -q
pytest tests/contract -q
```

Comandos dependentes de serviços externos, banco ou RabbitMQ são condicionais à infraestrutura confirmada no inventário, mas sua não execução deve ficar registrada como pendência objetiva.

## Critérios de aceite objetivos

- OpenAPI antes/depois sem remoção não autorizada
- status codes e schemas preservados
- rotas registradas uma única vez

## Rollback

1. Reativar routes/controllers antigos por shim e remover registro novo.

## Atualização obrigatória de runtime.md

Atualizar `/specs/module-architecture-standardization/execution/runtime.md` com:

- status da spec `006`;
- data e SHA executado;
- arquivos impactados;
- decisões tomadas;
- pendências e riscos novos/resolvidos;
- evidências dos comandos de validação;
- próxima spec recomendada: `007`.
