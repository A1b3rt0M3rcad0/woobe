# 009 — align-runtime-controls-with-effective-execution-mode

## Tipo

frontend/contract

## Objetivo

Alinhar os controles Session Mode e Status com o modo efetivamente enviado ao backend e eliminar ambiguidade entre draft, configuração salva e sessão ativa.

## Contexto

O painel Runtime da imagem é implementado em `AgentSettingsTab`. O playground sempre envia `snapshot_override=toSnapshot()`, incluindo `session_mode`; portanto, uma alteração não salva pode modificar imediatamente a política de memória.

## Pré-condições

- 002 e 008 completed.

## Alterações permitidas

- AgentEditorContext;
- AgentSettingsTab;
- header/status bar do playground;
- request builder;
- testes frontend.

## Alterações proibidas

- tratar `Status=Active` como sinônimo de stateful;
- ocultar que draft não salvo está sendo executado;
- manter uma sessão ativa no state quando o modo efetivo é stateless;
- mudar valor persistido sem ação explícita do usuário.

## Plano de implementação

1. Exibir `Effective runtime: Stateful/Stateless` próximo ao chat.
2. Indicar origem: `saved agent`, `unsaved draft` ou `release`.
3. Ao mudar efetivamente para stateless:
   - limpar `sessionId` e query param;
   - não carregar histórico;
   - informar que cada request é isolado.
4. Ao mudar para stateful:
   - não ressuscitar sessão antiga automaticamente;
   - próximo envio sem ID cria nova sessão.
5. Descrever `Active` como disponibilidade operacional, sem referência a memória.
6. No debug payload, destacar `session_mode`, `session_id` e fonte da configuração.
7. Garantir que release production use o `session_mode` da release no contexto production.

## Testes obrigatórios

- draft stateful é refletido no payload e badge;
- draft stateless limpa sessão;
- active não altera sessão;
- reset do draft restaura modo e comportamento;
- release/draft source aparece corretamente.

## Comandos de validação

```bash
cd web
npm run test:run -- runtime-mode
npm run build
```

## Critérios de aceite objetivos

- usuário consegue identificar o modo efetivo antes de enviar;
- stateless não envia ID antigo;
- status e memória permanecem conceitos separados.

## Rollback

Reverter UI e request builder juntos para evitar badge divergente do payload.

## Atualização obrigatória de runtime.md

Registrar UX final e próxima spec `010`.
