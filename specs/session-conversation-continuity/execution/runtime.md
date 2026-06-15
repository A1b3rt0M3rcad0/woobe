# Runtime — Session Conversation Continuity

## Baseline

- baseline branch: `development`
- implementation branch: `development_session-conversation-continuity`
- baseline SHA: `PENDING — registrar na spec 001`
- started_at: `PENDING`
- owner: `PENDING`

## Status

| Spec | Status | SHA | Evidência | Bloqueios |
|---:|---|---|---|---|
| 000 | pending | - | - | - |
| 001 | pending | - | - | - |
| 002 | pending | - | - | - |
| 003 | pending | - | - | - |
| 004 | pending | - | - | - |
| 005 | pending | - | - | - |
| 006 | pending | - | - | - |
| 007 | pending | - | - | - |
| 008 | pending | - | - | - |
| 009 | pending | - | - | - |
| 010 | pending | - | - | - |
| 011 | pending | - | - | - |
| 012 | pending | - | - | - |
| 013 | pending | - | - | - |

## Diagnóstico inicial

- provável causa raiz: `AIMessage(tool_calls=None)` seguido de `except Exception: return []`;
- defeito associado: turno atual persistido antes da carga e anexado novamente;
- defeito associado: session ID inválido cria nova sessão silenciosamente;
- defeito associado: janela retorna registros mais antigos;
- frontend envia e atualiza session ID durante a mesma montagem;
- painel Runtime `stateful` é necessário, mas não corrige falhas de reconstrução.

## Registro de decisões

Preencher durante execução.

## Evidências de comandos

Preencher por spec, sem substituir comandos ausentes por suposição.

## Pendências e riscos

- confirmar versão efetiva de `langchain-core` no lock/ambiente;
- confirmar política desejada para user message quando stream é cancelado;
- confirmar mapeamento HTTP canônico de sessão closed/expired/error;
- confirmar limite de histórico e orçamento de tokens.
