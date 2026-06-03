---
name: event-propagation-outbox-inbox
description: Explains how modules communicate through events using outbox, inbox, consumers, and dispatchers.
---

# Comunicação entre módulos com Outbox e Inbox

## Objetivo

Explicar a lógica de comunicação entre módulos usando eventos, outbox e inbox.

Esta skill não deve focar em tecnologias, bibliotecas, banco, fila ou framework.

O objetivo é definir o comportamento do sistema e o fluxo conceitual da comunicação entre módulos.

## Ideia principal

Os módulos não devem depender diretamente uns dos outros para executar efeitos secundários.

Quando um módulo realiza uma ação importante, ele registra um evento dizendo que algo aconteceu.

Outro módulo pode reagir a esse evento depois, de forma separada.

Exemplo:

```txt
core cria um projeto
→ core registra o evento project_created
→ outro processo publica esse evento
→ outro módulo recebe o evento
→ esse módulo executa sua própria reação
```

## Outbox

A outbox representa os eventos produzidos por um módulo.

Quando um módulo altera seu próprio estado, ele também registra um evento na outbox.

Isso significa:

```txt
o módulo fez algo importante
e deixou registrado que isso aconteceu
```

Exemplo:

```txt
identity criou uma organização
→ grava organization_created na outbox
```

A outbox não significa que o evento já foi tratado por outro módulo.

A outbox significa apenas:

```txt
este módulo produziu um evento que precisa ser enviado para fora
```

## Responsabilidade da outbox

A outbox tem uma responsabilidade clara:

```txt
garantir que eventos produzidos por um módulo não sejam perdidos antes de serem publicados
```

Depois que o evento é publicado, a responsabilidade da outbox termina.

O evento pode ser marcado como:

```txt
published
```

Isso quer dizer:

```txt
o evento saiu do módulo produtor e foi entregue ao meio de comunicação
```

Não quer dizer que ele foi consumido.

Não quer dizer que outro módulo já tratou o evento.

## Inbox

A inbox representa os eventos recebidos para processamento interno.

Quando um evento chega para o sistema, ele é primeiro salvo na inbox.

Isso significa:

```txt
o sistema recebeu um evento e agora precisa decidir o que fazer com ele
```

A inbox serve para controlar:

```txt
se o evento já foi recebido
se já foi processado
se falhou
se precisa tentar de novo
```

## Responsabilidade da inbox

A inbox tem uma responsabilidade clara:

```txt
garantir que eventos recebidos sejam processados com controle, segurança e rastreabilidade
```

A inbox termina quando o evento foi tratado pelo dispatcher.

O evento pode ser marcado como:

```txt
processed
```

Isso quer dizer:

```txt
o evento foi recebido e seu handler foi executado
```

## Dispatcher

O dispatcher é quem lê eventos da inbox e decide qual ação executar.

Ele funciona como um roteador interno de eventos.

Exemplo:

```txt
evento recebido: project_created

dispatcher identifica:
project_created deve chamar o handler de criação inicial do projeto

handler executa:
preparar configurações iniciais
registrar uso inicial
criar dados derivados
ou não fazer nada
```

O dispatcher não deve criar regra de negócio solta.

Ele apenas entrega o evento para o handler correto.

## Fluxo completo

```txt
1. Um módulo executa uma ação de negócio.

2. O módulo salva sua alteração principal.

3. O módulo registra um evento na outbox.

4. Um worker coleta eventos da outbox.

5. O worker publica o evento.

6. A outbox marca o evento como published.

7. Um consumer recebe o evento publicado.

8. O consumer salva o evento na inbox.

9. Um dispatcher coleta eventos pendentes da inbox.

10. O dispatcher chama o handler correto.

11. O handler executa a reação necessária.

12. A inbox marca o evento como processed.

13. O handler pode ou não gerar um novo evento na outbox.
```

## Exemplo simples

```txt
identity cria uma organização
→ outbox recebe identity.organization_created
→ evento é publicado
→ inbox recebe identity.organization_created
→ dispatcher processa
→ billing pode preparar customer
→ core pode preparar estrutura inicial
→ metering pode preparar limites iniciais
```

Nenhum módulo precisa chamar diretamente o outro.

Cada módulo reage ao evento se ele for relevante.

## Comunicação entre módulos

A comunicação entre módulos deve seguir esta lógica:

```txt
módulo produtor não sabe quem vai consumir
módulo consumidor decide se o evento importa
módulo consumidor executa sua própria reação
```

Isso reduz acoplamento.

Exemplo ruim:

```txt
identity chama billing diretamente
identity chama core diretamente
identity chama metering diretamente
```

Exemplo correto:

```txt
identity emite organization_created
billing reage se precisar
core reage se precisar
metering reage se precisar
```

## Diferença entre comando e evento

Um comando pede para algo acontecer.

Um evento informa que algo já aconteceu.

Exemplo de comando:

```txt
CreateProject
```

Significa:

```txt
crie um projeto
```

Exemplo de evento:

```txt
ProjectCreated
```

Significa:

```txt
um projeto foi criado
```

A outbox deve guardar eventos, não comandos.

## Regra de ouro

```txt
Outbox termina quando o evento é publicado.
Inbox termina quando o evento é processado.
```

## Estados conceituais

### Outbox

```txt
pending
published
failed
dead
```

Significado:

```txt
pending = evento criado, mas ainda não publicado
published = evento publicado com sucesso
failed = tentativa falhou, pode tentar de novo
dead = falhou demais e precisa intervenção
```

### Inbox

```txt
pending
processing
processed
failed
dead
```

Significado:

```txt
pending = evento recebido, aguardando processamento
processing = evento está sendo tratado
processed = handler executado com sucesso
failed = tentativa falhou, pode tentar de novo
dead = falhou demais e precisa intervenção
```

## Idempotência

O sistema deve assumir que o mesmo evento pode chegar mais de uma vez.

Por isso, o inbox precisa impedir que o mesmo evento seja processado de forma indevida.

A regra é:

```txt
se o evento já foi recebido e processado, não execute de novo
```

Isso evita duplicações como:

```txt
cobrar duas vezes
criar dois registros iguais
enviar duas notificações
duplicar usage
duplicar configuração
```

## Encadeamento de eventos

Um handler pode gerar outro evento.

Exemplo:

```txt
organization_created
→ billing cria customer
→ billing gera customer_created
→ metering reage ao customer_created
```

Isso é permitido.

Mas é preciso evitar loops.

Exemplo de loop ruim:

```txt
A gera evento
B reage e gera evento
A reage e gera o mesmo evento de novo
B reage de novo
loop infinito
```

A regra é:

```txt
um evento deve representar uma mudança real de estado
não gerar eventos sem necessidade
não gerar eventos repetidos para o mesmo estado
```

## Quando usar evento

Use evento quando uma ação de um módulo pode interessar a outro módulo.

Exemplos:

```txt
user_registered
organization_created
project_created
api_key_created
agent_created
document_uploaded
document_indexed
tool_created
ask_completed
usage_recorded
subscription_updated
```

## Quando não usar evento

Não use evento para tudo.

Evite evento para ações internas pequenas que ninguém precisa saber.

Exemplos:

```txt
validar campo
formatar texto
calcular slug
converter entidade
montar resposta HTTP
```

## Relação com os módulos do sistema

### identity

Produz eventos como:

```txt
user_registered
organization_created
member_added
invite_accepted
```

### core

Produz eventos como:

```txt
project_created
api_key_created
api_key_revoked
```

### ai

Produz eventos como:

```txt
agent_created
agent_updated
provider_credential_created
```

### knowledge

Produz eventos como:

```txt
document_uploaded
document_parsed
document_indexed
```

### runtime

Produz eventos como:

```txt
ask_started
ask_completed
message_created
```

### tools

Produz eventos como:

```txt
tool_created
tool_executed
tool_failed
```

### metering

Produz eventos como:

```txt
usage_recorded
limit_reached
```

### billing

Produz eventos como:

```txt
subscription_created
subscription_updated
subscription_canceled
payment_failed
```

## Regra final para implementação futura

O fluxo deve manter esta separação:

```txt
módulo produtor
→ outbox
→ publicação
→ inbox
→ dispatcher
→ handler do módulo consumidor
→ possível novo outbox
```

A lógica central é:

```txt
módulos não chamam outros módulos diretamente para efeitos secundários.
módulos anunciam eventos.
outros módulos reagem quando fizer sentido.
```
