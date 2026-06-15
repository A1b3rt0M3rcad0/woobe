# 012 — add-playground-session-continuity-tests

## Tipo

test

## Objetivo

Cobrir o ciclo de vida da sessão no playground e a semântica visual do Runtime.

## Contexto

A UI envia o ID corretamente durante a mesma montagem, mas precisa de garantias para eventos SSE, reload, URL, mudança de modo e cancelamento.

## Pré-condições

- 008 e 009 completed.

## Alterações permitidas

- testes em `web/src/**`;
- fixtures/mocks SSE;
- configuração Vitest estritamente necessária.

## Alterações proibidas

- testar apenas implementação interna sem requests observáveis;
- omitir `meta` e `done` em cenários SSE;
- simular reload mantendo state React antigo;
- usar backend real externo.

## Testes obrigatórios

1. request inicial stateful envia `session_id=null`.
2. evento `meta` define ID.
3. segundo request envia o mesmo ID.
4. `done` mantém ID e invalida query correta.
5. reload via nova montagem lê ID da URL e carrega mensagens.
6. New session remove ID e histórico visual.
7. stateless limpa ID antes do request.
8. active/inactive não muda modo de sessão.
9. erro SSE de histórico não mostra resposta falsa de sucesso.
10. sessão de agent diferente é descartada.

## Comandos de validação

```bash
cd web
npm run test:run
npm run build
```

## Critérios de aceite objetivos

- todos os dez cenários passam;
- requests são inspecionados quanto ao `session_id`;
- reload é uma nova montagem;
- build TypeScript passa.

## Rollback

Somente junto do rollback das specs 008-009.

## Atualização obrigatória de runtime.md

Registrar testes e próxima spec `013`.
