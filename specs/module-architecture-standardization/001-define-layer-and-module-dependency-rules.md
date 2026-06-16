# 001 — define-layer-and-module-dependency-rules

## Tipo

architecture

## Objetivo

Definir regras verificáveis de dependência entre camadas e módulos.

## Contexto

A uniformidade de pastas sem direção de dependência não impede acoplamento.

## Pré-condições

- 000 completed

## Estado atual a detectar

Execute na raiz do checkout da branch `project-rai-playground_module-architecture-standardization`:

```bash
rg "^from modules\.|^import modules\." src/modules -g "*.py"
find src/modules -type f -name "*.py" | sort
```

Persistir qualquer saída de inventário indicada no plano. Comando ausente no ambiente deve ser registrado como bloqueio em `execution/runtime.md`; não substituí-lo por suposição.

## Alterações permitidas

- documentação de regras
- tests/architecture/allowlists temporárias

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

1. Especificar imports permitidos por camada.
2. Definir entrypoints públicos permitidos.
3. Proibir imports de models/repositories/use_cases de outro módulo.
4. Definir mecanismo AST para validação.
5. Definir allowlist temporária com owner e spec de remoção.

## Contratos esperados

- domain não importa camadas externas
- application não importa infra/presentation
- infra não importa presentation
- presentation não acessa database diretamente

## Testes obrigatórios

- tests/architecture/test_layer_dependencies.py
- tests/architecture/test_module_boundaries.py

## Comandos de validação

```bash
ruff check src tests
pyright
pytest tests/architecture -q
pytest -q
```

Comandos dependentes de serviços externos, banco ou RabbitMQ são condicionais à infraestrutura confirmada no inventário, mas sua não execução deve ficar registrada como pendência objetiva.

## Critérios de aceite objetivos

- matriz de dependências existe
- cada violação legada está em allowlist explícita
- nova violação não listada falha

## Rollback

1. Remover apenas regras/testes novos e restaurar allowlist anterior.

## Atualização obrigatória de runtime.md

Atualizar `/specs/module-architecture-standardization/execution/runtime.md` com:

- status da spec `001`;
- data e SHA executado;
- arquivos impactados;
- decisões tomadas;
- pendências e riscos novos/resolvidos;
- evidências dos comandos de validação;
- próxima spec recomendada: `002`.
