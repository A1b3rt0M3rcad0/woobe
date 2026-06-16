# Event Payload Policy

Levantamento em: 2026-06-16

## Princípios

1. Payloads contêm apenas informações necessárias ao consumidor
2. Dados sensíveis NÃO são transportados em eventos
3. Secrets, API keys, authorization headers, prompts completos, respostas completas e tool outputs sensíveis são excluídos ou referenciados por ID

## Itens proibidos em payloads de eventos

- Secrets e API keys
- Authorization headers e tokens
- Prompts completos do LLM (apenas metadados: token count, model, duration)
- Respostas completas do LLM (apenas metadados)
- Tool outputs sensíveis (dados de usuário, PII)
- Credenciais de provedores

## Formato do payload por evento

### agent.execution.*.v1
```json
{
  "execution_id": "uuid",
  "agent_id": "uuid",
  "session_id": "uuid | null",
  "user_id": "uuid | null",
  "project_id": "uuid | null",
  "organization_id": "uuid | null",
  "correlation_id": "uuid",
  "timestamp": "ISO8601"
}
```

### agent.execution.llm_completed.v1 (adicional)
```json
{
  "llm_provider": "string",
  "llm_model": "string",
  "input_tokens": "int",
  "output_tokens": "int",
  "duration_ms": "int",
  "cost_usd": "float | null"
}
```

### agent.execution.tool_completed.v1 (adicional)
```json
{
  "tool_name": "string",
  "tool_type": "string",
  "duration_ms": "int",
  "success": "bool"
}
```

## Redaction

- Dados sensíveis são redactados antes da publicação
- Referências a dados sensíveis usam `reference_id` (UUID) que o consumidor pode resolver através de API própria do módulo produtor
- O consumidor NUNCA recebe o valor sensível no evento

## Segurança

- Payloads não transportam secrets, API keys, authorization headers, prompts completos, respostas completas ou tool outputs sensíveis sem redaction/reference explícita
