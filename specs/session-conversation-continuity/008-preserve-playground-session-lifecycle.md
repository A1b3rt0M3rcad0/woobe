# 008 — preserve-playground-session-lifecycle

## Tipo

frontend

## Objetivo

Tornar explícita e persistente a sessão ativa do playground durante navegação, reload, seleção e criação de nova conversa.

## Contexto

`AgentPlaygroundPage` mantém `sessionId` apenas em state local. Durante a mesma montagem ele é reutilizado corretamente, mas reload inicia com `null` até o usuário selecionar manualmente uma sessão.

## Pré-condições

- 002, 005 e 007 completed.

## Alterações permitidas

- `web/src/pages/AgentPlaygroundPage.tsx`;
- componentes e hooks do playground;
- roteamento/query params;
- testes Vitest/Testing Library;
- runtime.

## Alterações proibidas

- armazenar histórico completo em localStorage como fonte de verdade;
- gerar session ID no frontend;
- reutilizar sessão de outro agent/project;
- selecionar automaticamente sessão incompatível com modo stateless.

## Plano de implementação

1. Representar a sessão ativa por query param estável, por exemplo `?session=<uuid>`, ou rota equivalente sem quebrar URL existente.
2. Inicializar `sessionId` a partir da URL somente após validar que a sessão pertence ao agent/project atual.
3. Atualizar a URL quando SSE `meta` retornar nova sessão.
4. `New session` deve limpar URL, state, mensagens, trace selecionado e requests em voo.
5. Seleção de sessão deve atualizar URL e carregar mensagens do backend.
6. Reload com sessão válida deve restaurar histórico.
7. Reload sem sessão não deve autoanexar arbitrariamente a sessão mais recente.
8. Troca de agent/project deve limpar ID incompatível.

## Testes obrigatórios

- primeiro turno recebe ID e URL é atualizada;
- segundo turno envia o mesmo ID;
- reload restaura sessão e mensagens;
- new session remove ID;
- sessão de outro agent é rejeitada/limpa;
- requisição cancelada não deixa state inconsistente.

## Comandos de validação

```bash
cd web
npm run test:run -- AgentPlaygroundPage.session-continuity
npm run build
```

## Critérios de aceite objetivos

- mesma conversa sobrevive a reload explícito;
- nova conversa não reutiliza ID anterior;
- backend continua fonte de verdade das mensagens.

## Rollback

Remover sincronização com URL e restaurar state local; não manter query param sem validação.

## Atualização obrigatória de runtime.md

Registrar estratégia de URL e próxima spec `009`.
