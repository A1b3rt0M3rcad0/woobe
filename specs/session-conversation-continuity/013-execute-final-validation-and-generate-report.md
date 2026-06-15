# 013 — execute-final-validation-and-generate-report

## Tipo

validation/report

## Objetivo

Executar a validação completa, registrar evidências e declarar conclusão somente sem regressões.

## Contexto

A correção cruza application, repository, stream, frontend e observabilidade. Teste isolado não é suficiente.

## Pré-condições

- 011 e 012 completed;
- runtime sem bloqueios críticos abertos.

## Alterações permitidas

- correções estritamente necessárias para satisfazer critérios já definidos;
- `specs/session-conversation-continuity/execution/**`.

## Alterações proibidas

- reduzir assertions para obter verde;
- ignorar falhas pré-existentes sem baseline comparável;
- marcar completed sem evidência dos comandos;
- usar teste manual como substituto dos testes automatizados obrigatórios.

## Comandos de validação

```bash
ruff check src tests
pyright
pytest tests/architecture -q
pytest tests/contract -q
pytest tests/modules/agent/unit -q
pytest tests/modules/agent/integration -q
pytest -q
cd web
npm run test:run
npm run build
```

Executar também smoke test controlado com fake/stub LLM ou provider de desenvolvimento:

1. criar/selecionar agent active e stateful;
2. enviar turno 1;
3. capturar `session_id`;
4. enviar turno 2 com o mesmo ID perguntando pelo turno anterior;
5. repetir via `/runtime/ask` e `/runtime/ask/stream`;
6. confirmar no banco uma sessão e quatro mensagens;
7. confirmar trace `conversation.history_loaded` com contagem maior que zero.

## Relatório obrigatório

Criar `execution/final-report.md` contendo:

- baseline SHA e final SHA;
- arquivos alterados;
- causa raiz confirmada;
- decisões de contrato;
- resultados de todos os comandos;
- testes adicionados;
- evidência do smoke test;
- riscos residuais;
- rollback validado;
- declaração explícita de conclusão ou bloqueio.

## Critérios de aceite objetivos

- pergunta anterior é recuperada em sync e stream;
- mesmo `session_id` é reutilizado;
- assistant sem tool calls não apaga histórico;
- turno atual não é duplicado;
- ID inválido não cria nova sessão;
- últimas N mensagens são usadas em sessão longa;
- stateless persiste zero mensagens;
- frontend preserva/limpa ID conforme contrato;
- todos os comandos passam ou falhas pré-existentes possuem baseline objetiva e não foram ampliadas.

## Rollback

1. reverter commits na ordem inversa;
2. não remover dados de sessões existentes;
3. restaurar comportamento HTTP somente com teste de compatibilidade;
4. executar novamente a suíte de baseline.

## Atualização obrigatória de runtime.md

Marcar `013 completed` somente se todos os critérios forem satisfeitos. Caso contrário, `blocked` com causa e próximo passo objetivo.
