# 002 — define-stateful-stateless-and-session-reuse-contract

## Tipo

architecture

## Objetivo

Definir semântica inequívoca para stateful, stateless, criação, reutilização e erro de sessão.

## Contexto

O seletor Runtime altera `agent.session_mode`, mas o contrato atual permite que uma sessão inválida seja silenciosamente trocada por outra. O cliente não consegue distinguir continuidade, nova conversa e degradação.

## Pré-condições

- 001 completed com evidência reproduzível.

## Alterações permitidas

- `specs/session-conversation-continuity/**`;
- testes de contrato inicialmente vermelhos.

## Alterações proibidas

- mudar URL pública;
- remover `session_id` da resposta;
- fazer estado do provider substituir a sessão local;
- quebrar clientes stateless existentes sem estratégia de compatibilidade.

## Contrato normativo

### Stateful sem `session_id`

- criar uma nova sessão;
- persistir user e assistant;
- retornar `session_id` em `meta` e `done` no stream e no body sync.

### Stateful com `session_id` válido

- reutilizar exatamente a sessão informada;
- carregar histórico anterior em ordem cronológica;
- não criar sessão alternativa;
- retornar o mesmo ID.

### Stateful com `session_id` inexistente ou incompatível

- não criar nova sessão;
- responder erro explícito com código de domínio estável;
- usar 404 para inexistência ou mismatch de ownership, evitando enumeração;
- usar 409/422 para sessão encerrada ou modo inválido, conforme mapper HTTP existente.

### Stateless

- não criar sessão;
- não persistir mensagens;
- retornar `session_id=null`;
- por compatibilidade, `session_id` recebido deve ser ignorado com evento observável durante esta versão; o frontend deve limpá-lo antes de enviar.

### Active/Inactive

- `active` autoriza execução;
- `inactive`/`archived` bloqueiam execução;
- status do agente não altera a política de memória.

### Snapshot do playground

- `snapshot_override.session_mode` é o modo efetivo da chamada de playground;
- a UI deve indicar quando o modo efetivo vem de draft não salvo;
- trocar para stateless limpa a sessão selecionada no frontend.

## Testes obrigatórios

- matriz de contrato para sync e stream;
- IDs iguais em reuso stateful;
- zero inserts de sessão em ID inválido;
- zero persistência em stateless;
- status active não usado como sinal de memória.

## Comandos de validação

```bash
rg "Stateful com|Stateless|Snapshot do playground" specs/session-conversation-continuity/002-define-stateful-stateless-and-session-reuse-contract.md
```

## Critérios de aceite objetivos

- todos os cenários acima possuem resultado, persistência e erro definidos;
- contrato preserva as URLs e campos públicos existentes;
- não há fallback silencioso.

## Rollback

Reverter apenas antes da implementação das specs dependentes.

## Atualização obrigatória de runtime.md

Registrar decisões e próxima spec `003`.
