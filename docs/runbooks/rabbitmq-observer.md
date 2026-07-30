# RabbitMQ Event Observer

Este runbook habilita uma camada opcional de observação para o RabbitMQ do ambiente local/QA. O objetivo é permitir acompanhar taxas de publicação, inspecionar payloads e verificar a ordem dos eventos sem consumir mensagens das filas reais da aplicação.

## Decisão

A solução usa somente recursos oficiais do RabbitMQ:

- RabbitMQ Management UI para topologia, conexões, filas, exchanges e taxas;
- `rabbitmq_tracing` para capturar publicações do exchange da aplicação em JSON;
- uma fila-espelho limitada, vinculada ao exchange com routing key `#`, para inspeção manual dos payloads pelo navegador;
- um container one-shot que provisiona a topologia de observação via HTTP API.

Não foi adicionada uma UI de terceiros. Isso reduz dependências, risco de supply chain e incompatibilidade com RabbitMQ 4.

## Arquivos

- `docker-compose.rabbitmq-observer.yml`: override opcional do Compose;
- `docker/rabbitmq/enabled_plugins`: habilita Management e Tracing;
- `docker/rabbitmq/90-observer.conf`: ativa métricas detalhadas e define o diretório de traces;
- `docker/rabbitmq/init-observer.sh`: cria exchange, fila-espelho, binding e trace de forma idempotente.

## Subir o ambiente com observação

```bash
docker compose \
  -f docker-compose.yml \
  -f docker-compose.rabbitmq-observer.yml \
  up -d
```

Verifique o provisionamento:

```bash
docker compose \
  -f docker-compose.yml \
  -f docker-compose.rabbitmq-observer.yml \
  logs rabbitmq-observer-init
```

O resultado esperado contém:

```text
RabbitMQ observer ready
Management UI: http://rabbitmq:15672
Mirror queue: projectrai.observer.events
Trace: projectrai-events (publish.projectrai.events)
```

## Acessar o frontend

Abra:

```text
http://localhost:15672
```

Credenciais padrão do harness local:

```text
Usuário: projectrai
Senha: projectrai
```

As credenciais reais vêm de `RABBITMQ_USER` e `RABBITMQ_PASSWORD`.

## Ver eventos acontecendo

### 1. Taxas em tempo quase real

No Management UI:

1. abra `Exchanges`;
2. selecione `projectrai.events`;
3. acompanhe `Publish rate`, bindings e filas roteadas.

O override coleta estatísticas a cada dois segundos e habilita taxas detalhadas.

### 2. Inspecionar payloads sem interferir nos consumers

No Management UI:

1. abra `Queues and Streams`;
2. selecione `projectrai.observer.events`;
3. abra `Get messages`;
4. solicite uma quantidade pequena de mensagens.

Essa fila recebe cópias dos eventos. Ler ou remover mensagens dela não retira mensagens das filas operacionais dos módulos.

A fila é limitada por padrão a:

- 1.000 mensagens;
- TTL de uma hora por mensagem;
- `drop-head` quando atingir o limite.

### 3. Ver o trace oficial

No Management UI:

1. abra `Admin`;
2. abra `Tracing`;
3. selecione `projectrai-events`;
4. abra ou baixe o arquivo de trace.

O trace padrão captura apenas publicações em `projectrai.events`, evitando duplicar também cada entrega aos consumers.

Para acompanhar o arquivo em terminal:

```bash
docker compose \
  -f docker-compose.yml \
  -f docker-compose.rabbitmq-observer.yml \
  exec rabbitmq \
  tail -f /var/lib/rabbitmq/tracing/projectrai-events.log
```

Cada linha do arquivo é um objeto JSON independente.

## Configuração opcional

As variáveis abaixo podem ser definidas no `.env`:

```dotenv
RABBITMQ_OBSERVER_QUEUE=projectrai.observer.events
RABBITMQ_OBSERVER_MESSAGE_TTL_MS=3600000
RABBITMQ_OBSERVER_MAX_MESSAGES=1000
RABBITMQ_OBSERVER_TRACE_NAME=projectrai-events
RABBITMQ_OBSERVER_TRACE_PATTERN=
RABBITMQ_OBSERVER_MAX_PAYLOAD_BYTES=262144
```

Quando `RABBITMQ_OBSERVER_TRACE_PATTERN` está vazio, o padrão é derivado do exchange:

```text
publish.<PROJECTRAI_RABBITMQ_EXCHANGE>
```

Para capturar publicação e entrega de todas as mensagens do vhost, use `#`. Isso aumenta significativamente o volume e deve ser usado apenas por períodos curtos.

## Parar o observador

Para encerrar toda a stack iniciada com o override:

```bash
docker compose \
  -f docker-compose.yml \
  -f docker-compose.rabbitmq-observer.yml \
  down
```

Não use `down -v` sem intenção explícita de apagar também os volumes locais de PostgreSQL, RabbitMQ e MinIO.

## Limitações e cautelas

- O tracing aumenta consumo de CPU, RAM e I/O do RabbitMQ.
- A fila-espelho adiciona uma rota e uma cópia por evento publicado.
- Não execute benchmarks de latência ou throughput com este override ativo.
- O Management UI e as credenciais padrão não devem ser expostos em ambientes compartilhados ou produção.
- Se os argumentos da fila-espelho forem alterados depois que ela já existir, remova a fila pelo UI antes de subir novamente o init container.

## Validação recomendada

1. suba a stack com o override;
2. execute um Agent no Playground;
3. confirme aumento da taxa em `projectrai.events`;
4. abra a fila `projectrai.observer.events` e valide o payload;
5. abra o trace `projectrai-events` e valide `routing_keys`, `properties`, `payload` e timestamp;
6. execute uma Network e confirme a ordem dos eventos;
7. finalize o observador antes de medir performance.

## Referências oficiais

- RabbitMQ Management Plugin: https://www.rabbitmq.com/docs/management
- RabbitMQ Firehose Tracer: https://www.rabbitmq.com/docs/firehose
- RabbitMQ Tracing Plugin: https://github.com/rabbitmq/rabbitmq-server/tree/main/deps/rabbitmq_tracing
