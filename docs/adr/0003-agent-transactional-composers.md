# ADR 0003 — Transaction boundaries for Agent composers

Status: Proposed

## Contexto

O módulo `agent` já possui uma camada explícita de `composition`, porém os composers ainda não seguem um único contrato de saída.

A maior parte dos composers CRUD já cria uma única `AgentUnitOfWork`, resolve repositories a partir dessa mesma instância, monta use case/controller e retorna `TransactionalHandler`. Entretanto, existem caminhos que ainda retornam handlers crus ou executam o use case dentro da própria função de composition:

- `ask_agent_composer` retorna `AskAgentController(...).handle`;
- `ask_agent_stream_composer` retorna um callable HTTP cru;
- `public_run_composer` retorna `PublicRunController(...).handle`;
- `public_stream_composer` retorna um callable HTTP cru;
- `vector_snapshot_composers.py` contém funções que recebem `session_factory + DTO`, abrem a UoW e executam o use case imediatamente, portanto não são composers reais apesar de estarem no diretório de composers.

O padrão desejado é que um composer apenas monte o grafo de dependências e devolva uma fronteira executável padronizada. A execução e o ciclo transacional não devem acontecer dentro do composer.

Referência utilizada: `Desafio-Hostgator`, onde o fluxo regular é:

`Route -> Composer -> TransactionalHandler -> UnitOfWork -> Controller -> UseCase -> Repository`

Para streaming, a referência usa `StreamingTransactionalHandler`, mantendo o ciclo da UoW coerente com o consumo da stream e realizando rollback quando a iteração falha.

## Decisão proposta

Todo callable público com sufixo `_composer` em `src/modules/agent/composition/composers/**` deverá retornar exatamente um dos dois wrappers:

- `TransactionalHandler` para fluxos request/response normais;
- `StreamingTransactionalHandler` para fluxos cujo resultado é consumido incrementalmente.

Helpers que apenas constroem infraestrutura, como `build_tool_runtime_registry`, não serão classificados como composers e não estarão sujeitos a essa regra.

Funções atualmente localizadas em arquivos `*_composers.py` mas que executam diretamente um use case serão convertidas em composers reais ou movidas para um local que represente sua responsabilidade corretamente. Não permanecerá execução transacional direta dentro de `composition/composers`.

## Contratos de handler

O `TransactionalHandler` atual é acoplado a `shared.presentation.http.Request` e `Response`. Ele deverá se tornar genérico sem alterar o comportamento transacional:

```python
RequestT = TypeVar("RequestT", contravariant=True)
ResponseT = TypeVar("ResponseT", covariant=True)

class Handler(Protocol[RequestT, ResponseT]):
    async def __call__(self, request: RequestT) -> ResponseT: ...

class TransactionalHandler(Generic[RequestT, ResponseT]):
    def __init__(self, uow: UnitOfWork, handler: Handler[RequestT, ResponseT]) -> None: ...

    async def __call__(self, request: RequestT) -> ResponseT:
        async with self._uow:
            return await self._handler(request)
```

O contrato deixa de ser exclusivamente HTTP e passa a poder envolver controllers, DTO handlers e outros callables assíncronos sem `Any` como contrato principal.

Será criado um `StreamingTransactionalHandler` com a mesma premissa: abrir a UoW antes da execução, propagar erro do handler, preservar a UoW enquanto o stream administrado estiver ativo e finalizar a UoW somente quando o consumo terminar ou falhar.

A implementação deve preservar:

- commit no término bem-sucedido;
- rollback em exceção antes da criação do stream;
- rollback quando o stream falhar durante a iteração;
- fechamento da UoW quando o consumidor encerrar/cancelar o stream;
- nenhuma materialização completa do stream em memória.

Para não introduzir dependência de FastAPI/Starlette no handler transacional, o wrapper de streaming deverá operar sobre um contrato estrutural/neutral de stream. A adaptação para `fastapi.responses.StreamingResponse` continuará na borda HTTP.

## Unit of Work e repositories

O `AgentUnitOfWork` já possui a característica necessária para esse padrão: ele cria a sessão no `__aenter__`, executa commit/rollback no `__aexit__` e expõe repositories lazy ligados à própria UoW.

Os repositories SQLAlchemy acessam a sessão ativa através da UoW. Portanto o composer deve sempre obedecer a seguinte invariável:

1. criar exatamente uma `AgentUnitOfWork` para o boundary transacional;
2. obter os repositories usados pelo use case a partir dessa mesma UoW, ou construir adapters SQLAlchemy recebendo essa mesma UoW;
3. montar use case e controller;
4. entregar a mesma UoW ao `TransactionalHandler`/`StreamingTransactionalHandler`;
5. nunca abrir `async with AgentUnitOfWork(...)` dentro do próprio composer.

Isso garante que repository e transaction handler operem sobre a mesma sessão transacional.

A refatoração não mudará os contratos da Application nem o comportamento dos repositories. Interfaces de repository permanecem na Application e as implementações SQLAlchemy continuam na Infra. O objetivo é mudar quem controla o lifetime da UoW, não mudar o contrato de persistência.

## Runtime e streaming

Os caminhos de execução de Agent possuem uma particularidade que não existe nos CRUDs: chamadas de LLM, Tools, SSE, cancelamento e persistências em fases diferentes podem durar muito mais que uma requisição de banco convencional.

A implementação não deverá transformar todo o runtime em uma única transação SQL longa apenas para satisfazer a forma do composer. Antes de migrar `ask_agent_composer`, `ask_agent_stream_composer`, `public_run_composer` e `public_stream_composer`, será identificado quais repositories pertencem ao boundary externo e quais persistências internas precisam continuar usando transações curtas/checkpoints próprios.

A regra é: padronizar a saída do composer sem manter locks/conexões SQL ociosos durante chamadas externas longas. Se o runtime precisar de transações internas por fase, elas continuam explícitas no serviço responsável; o wrapper externo não deve mascarar isso nem criar uma falsa atomicidade.

## Vector snapshots

`vector_snapshot_composers.py` será normalizado. As funções atuais recebem DTO e executam imediatamente dentro de `async with AgentUnitOfWork(...)`.

O alvo é:

```text
composition/http
    -> *_composer(session_factory)
    -> TransactionalHandler
    -> handler/controller
    -> use case
    -> repositories ligados à mesma AgentUnitOfWork
```

Os contratos HTTP e payloads externos não serão alterados.

## Quality Gate

A policy arquitetural do Agent será ampliada para tornar esse padrão obrigatório.

Será adicionada uma regra semântica específica para composers, declarada em `quality_gate/architecture/policies/agent.toml` e executada pela engine genérica em `quality_gate/architecture/checker.py`.

Regras planejadas:

- `ARCH021`: todo callable público terminado em `_composer` dentro de `composition/composers/**` deve possuir return annotation explícita para `TransactionalHandler` ou `StreamingTransactionalHandler`;
- `ARCH022`: composers normais não podem retornar controller `.handle`, use case, lambda/callable cru ou executar diretamente o request;
- `ARCH023`: composers de streaming (`*_stream_composer`) devem retornar `StreamingTransactionalHandler`;
- `ARCH024`: nenhum composer pode abrir `AgentUnitOfWork` via `async with`; o lifetime da UoW pertence ao handler transacional;
- `ARCH025`: o wrapper retornado deve receber a mesma variável de UoW criada pelo composer, impedindo uma UoW para repositories e outra para o transaction boundary.

A configuração continuará declarativa no `agent.toml`. O checker genérico não deverá conter `if module == "agent"`.

O gate também deverá tratar corretamente arquivos com múltiplos composers, como `tools_composers.py` e `public_runtime_composers.py`, e ignorar helpers que não terminam em `_composer`.

## Testes da engine de Quality Gate

Serão adicionados testes sintéticos em `tests/quality_gate/architecture/test_checker.py` para provar que o gate:

- aceita composer que retorna `TransactionalHandler`;
- aceita composer que retorna `StreamingTransactionalHandler`;
- rejeita composer que retorna `controller.handle`;
- rejeita composer sem annotation;
- rejeita `_stream_composer` usando `TransactionalHandler`;
- rejeita `async with AgentUnitOfWork(...)` dentro do composer;
- rejeita UoWs diferentes entre repositories/wrapper quando a forma puder ser determinada estaticamente;
- ignora factories/helpers que não são composers.

## Migração planejada

1. Generalizar o contrato de `TransactionalHandler` preservando sua API de chamada.
2. Adicionar o `StreamingTransactionalHandler` e testes unitários de commit/rollback/cancelamento.
3. Adicionar primeiro as regras de composer ao Quality Gate e os testes da engine.
4. Executar o gate para obter o inventário exato de composers ainda fora do contrato.
5. Migrar os composers CRUD/read existentes apenas onde necessário; os já compatíveis devem sofrer no máximo ajustes de typing/import.
6. Refatorar `ask_agent_composer` e `public_run_composer` para retornarem `TransactionalHandler` sem alterar request/response externos.
7. Refatorar `ask_agent_stream_composer` e `public_stream_composer` para retornarem `StreamingTransactionalHandler`, preservando SSE, headers, cancelamento e ordem de eventos.
8. Transformar `vector_snapshot_composers.py` em composers reais e adaptar seus callers sem alterar DTOs/API.
9. Verificar que cada repository usado por um composer está ligado à mesma `AgentUnitOfWork` entregue ao wrapper.
10. Atualizar apenas imports/expectativas estruturais de testes existentes quando necessário; comportamento funcional não será reescrito para fazer testes passarem.
11. Rodar Quality Gate, Backend test suite, Acceptance, Security e Container quality somente quando a implementação estiver concluída e a validação for solicitada.

## Compatibilidade e não objetivos

Esta é uma refatoração interna. Não deve alterar:

- endpoints;
- payloads request/response;
- status codes;
- contratos de DTO;
- schemas SQL;
- migrations;
- regras de releases, runtime, tools ou knowledge;
- interfaces de repository da Application;
- semântica de commit/rollback já esperada pelos fluxos existentes.

Não serão refatorados outros bounded contexts neste PR. A regra de composer será ativada inicialmente apenas para `agent`, seguindo o ratchet do Architecture Quality Gate.

## Resultado esperado

Depois da implementação:

```text
Route / HTTP adapter
        |
        v
Composer
        |
        +--> cria uma AgentUnitOfWork
        +--> resolve repositories/adapters
        +--> monta UseCase
        +--> monta Controller/Handler
        |
        v
TransactionalHandler
ou StreamingTransactionalHandler
        |
        v
UnitOfWork lifecycle
        |
        v
Controller/Handler -> UseCase -> Repository
```

Nenhum composer do Agent devolverá um controller/use case/callable cru. Nenhum composer executará diretamente uma UoW. O Quality Gate bloqueará regressões automaticamente.

Para fluxos comuns, repository e wrapper compartilharão a mesma `AgentUnitOfWork`, garantindo uma única fronteira de commit/rollback por execução. Para streaming, a UoW será finalizada de forma segura somente de acordo com a semântica definida para o stream, sem materializar o conteúdo e sem alterar o contrato HTTP público.