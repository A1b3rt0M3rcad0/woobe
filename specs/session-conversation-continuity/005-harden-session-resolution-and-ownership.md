# 005 — harden-session-resolution-and-ownership

## Tipo

refactor

## Objetivo

Impedir substituição silenciosa de sessão e validar ownership antes de carregar ou gravar mensagens.

## Contexto

`SessionRepository.get_by_id` levanta `SessionNotFoundError`, mas `_resolve_session` captura qualquer exceção e cria uma sessão nova. A sessão retornada não é validada contra o request.

## Pré-condições

- 002 completed;
- teste vermelho de fallback silencioso presente.

## Alterações permitidas

- domain errors do agent;
- application handler de resolução de sessão;
- use cases de ask;
- controllers/mapeamento HTTP somente para erros novos;
- testes.

## Alterações proibidas

- `except Exception: pass` na resolução de sessão;
- criar nova sessão quando `session_id` foi informado;
- revelar existência de sessão pertencente a outro projeto/agente/tenant;
- consultar diretamente modelos SQLAlchemy na aplicação.

## Plano de implementação

1. Extrair `SessionResolver` dependente apenas de `SessionRepository`.
2. Em stateful sem ID, criar sessão.
3. Em stateful com ID, carregar e propagar `SessionNotFoundError`.
4. Validar:
   - `session.project_id == input.project_id`;
   - `session.agent_id == input.agent_id`;
   - tenant/user quando ambos os lados estiverem preenchidos;
   - status não pertencente a `{closed, expired, error}`.
5. Para mismatch, responder como not found, sem indicar ownership externo.
6. Para stateless, não consultar nem criar sessão; emitir evento de ID ignorado se recebido.
7. Aplicar a mesma resolução a sync, stream e ask job.

## Testes obrigatórios

- ID inexistente não cria sessão;
- ID de outro agent não é aceito;
- ID de outro project não é aceito;
- mismatch de tenant/user não é aceito;
- sessão closed/expired/error não recebe novas mensagens;
- stateful sem ID cria exatamente uma sessão;
- stateless cria zero sessões.

## Comandos de validação

```bash
pytest tests/modules/agent/unit/application/test_session_resolution.py -q
pytest tests/contract -q
```

## Critérios de aceite objetivos

- nenhum catch amplo na resolução;
- zero fallback de ID informado para nova sessão;
- ownership coberto por testes;
- contrato HTTP compatível e documentado.

## Rollback

Reverter resolver, erros e mappers HTTP como uma unidade.

## Atualização obrigatória de runtime.md

Registrar códigos de erro e próxima spec `006`.
