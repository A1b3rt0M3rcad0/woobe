export type RuntimeCodeLanguage = 'curl' | 'python' | 'javascript'
export type PublicRuntimeInterface = 'http' | 'stream'
export type RuntimeSnippetTargetType = 'agent' | 'network'
export type RuntimeSnippetEnvironment = 'production' | 'staging'

export const RUNTIME_CODE_LANGUAGES: Array<{ value: RuntimeCodeLanguage; label: string }> = [
  { value: 'python', label: 'Python' },
  { value: 'javascript', label: 'JavaScript' },
  { value: 'curl', label: 'cURL' },
]

interface BuildRuntimeSnippetInput {
  language: RuntimeCodeLanguage
  runtimeInterface: PublicRuntimeInterface
  baseUrl: string
  body: Record<string, unknown>
  targetType: RuntimeSnippetTargetType
  targetName: string
  environment: RuntimeSnippetEnvironment
  version?: string | null
  includeIdempotencyKey?: boolean
}

function endpoint(baseUrl: string, runtimeInterface: PublicRuntimeInterface): string {
  return `${baseUrl}${runtimeInterface === 'stream' ? '/v1/run/stream' : '/v1/run'}`
}

function prettyJson(body: Record<string, unknown>): string {
  return JSON.stringify(body, null, 2)
}

function pythonLiteral(value: unknown, indent = 0): string {
  if (value === null) return 'None'
  if (value === true) return 'True'
  if (value === false) return 'False'
  if (typeof value === 'string') return JSON.stringify(value)
  if (typeof value === 'number') return String(value)

  const currentIndent = ' '.repeat(indent)
  const childIndent = ' '.repeat(indent + 4)

  if (Array.isArray(value)) {
    if (value.length === 0) return '[]'
    return `[
${value.map((item) => `${childIndent}${pythonLiteral(item, indent + 4)},`).join('\n')}
${currentIndent}]`
  }

  if (value && typeof value === 'object') {
    const entries = Object.entries(value as Record<string, unknown>)
    if (entries.length === 0) return '{}'
    return `{
${entries.map(([key, item]) => `${childIndent}${JSON.stringify(key)}: ${pythonLiteral(item, indent + 4)},`).join('\n')}
${currentIndent}}`
  }

  return 'None'
}

function pythonHelpers(input: BuildRuntimeSnippetInput): string {
  return `TARGET_TYPE = ${pythonLiteral(input.targetType)}
TARGET_NAME = ${pythonLiteral(input.targetName)}
ENVIRONMENT = ${pythonLiteral(input.environment === 'production' ? 'Production' : 'Staging')}
VERSION = ${pythonLiteral(input.version ?? null)}


def print_field(label, value):
    if value is not None and value != "":
        print(f"  {label}: {value}")


def duration(run):
    latency_ms = run.get("latency_ms")
    if isinstance(latency_ms, (int, float)):
        return f"{latency_ms / 1000:.2f}s"

    started_at = run.get("started_at")
    completed_at = run.get("completed_at")
    if not started_at or not completed_at:
        return None

    try:
        started = datetime.fromisoformat(started_at.replace("Z", "+00:00"))
        completed = datetime.fromisoformat(completed_at.replace("Z", "+00:00"))
        return f"{(completed - started).total_seconds():.2f}s"
    except ValueError:
        return None


def print_identity():
    print("Network" if TARGET_TYPE == "network" else "Agent")
    print_field("Name", TARGET_NAME)
    print_field("Environment", ENVIRONMENT)
    if TARGET_TYPE == "network":
        print_field("Version", VERSION)


def print_execution(run):
    print("Execution")
    if TARGET_TYPE == "network":
        print_field("Run ID", run.get("execution_id"))
    else:
        print_field("Provider", run.get("provider"))
        print_field("Model", run.get("model"))

    print_field("Session", run.get("session_id") or run.get("network_session_id"))
    print_field("Trace", run.get("trace_id"))
    print_field("Duration", duration(run))

    usage = run.get("usage") or {}
    print_field("Tokens", usage.get("total_tokens"))
    cost = usage.get("cost_usd")
    if isinstance(cost, (int, float)):
        print_field("Cost", "$" + f"{cost:.6f}")
    if run.get("fallback_used") is True:
        print_field("Fallback", "used")


def print_result(run):
    parsed_output = run.get("parsed_output")
    if parsed_output is not None:
        print("Structured result")
        print(json.dumps(parsed_output, ensure_ascii=False, indent=2))
        return

    print("Response")
    print(str(run.get("result") or run.get("answer") or ""))


def print_run(run):
    run_label = "Network Run" if TARGET_TYPE == "network" else "Agent Run"
    print(f"✓ {run_label} completed\\n")
    print_identity()
    print()
    print_execution(run)
    print()
    print_result(run)


def print_stream_completion(run):
    run_label = "Network Run" if TARGET_TYPE == "network" else "Agent Run"
    print(f"✓ {run_label} completed\\n")
    print_execution(run)`
}

function pythonSnippet(input: BuildRuntimeSnippetInput): string {
  const uuidImport = input.includeIdempotencyKey ? 'import uuid\n' : ''
  const idempotency = input.includeIdempotencyKey
    ? '\n        "Idempotency-Key": str(uuid.uuid4()),'
    : ''
  const payload = pythonLiteral(input.body)
  const helpers = pythonHelpers(input)

  if (input.runtimeInterface === 'stream') {
    return `${uuidImport}import json
from datetime import datetime

import requests

WOOBE_API_KEY = "paste_your_runtime_key_here"

${helpers}

payload = ${payload}
terminal = {}
response_started = False
event_name = None

print_identity()
print("\\nResponse")

with requests.post(
    "${endpoint(input.baseUrl, input.runtimeInterface)}",
    headers={
        "Authorization": f"Bearer {WOOBE_API_KEY}",${idempotency}
    },
    json=payload,
    stream=True,
    timeout=120,
) as response:
    if not response.ok:
        error = response.json() if response.headers.get("content-type", "").startswith("application/json") else {}
        raise RuntimeError(error.get("message", response.text))

    for line in response.iter_lines(decode_unicode=True):
        if not line:
            event_name = None
            continue

        if line.startswith("event:"):
            event_name = line.removeprefix("event:").strip()
            continue

        if not line.startswith("data:"):
            continue

        event_payload = json.loads(line.removeprefix("data:").strip())
        current_event = event_name or event_payload.get("type")
        data = event_payload.get("data", event_payload)

        if current_event == "token" and data.get("phase") in {
            "response_generation",
            "final_response_generation",
        }:
            print(data.get("content", ""), end="", flush=True)
            response_started = True
        elif current_event in {"error", "execution_failed"}:
            raise RuntimeError(data.get("message", "Woobe execution failed."))
        elif current_event in {"done", "network_result"}:
            terminal = {**event_payload, **data}

if not response_started:
    print_result(terminal)

print("\\n")
print_stream_completion(terminal)`
  }

  return `${uuidImport}import json
from datetime import datetime

import requests

WOOBE_API_KEY = "paste_your_runtime_key_here"

${helpers}

payload = ${payload}
response = requests.post(
    "${endpoint(input.baseUrl, input.runtimeInterface)}",
    headers={
        "Authorization": f"Bearer {WOOBE_API_KEY}",${idempotency}
    },
    json=payload,
    timeout=120,
)

if not response.ok:
    error = response.json() if response.headers.get("content-type", "").startswith("application/json") else {}
    raise RuntimeError(error.get("message", response.text))

print_run(response.json()["data"])`
}

function javascriptHelpers(input: BuildRuntimeSnippetInput): string {
  return `const TARGET_TYPE = ${JSON.stringify(input.targetType)}
const TARGET_NAME = ${JSON.stringify(input.targetName)}
const ENVIRONMENT = ${JSON.stringify(input.environment === 'production' ? 'Production' : 'Staging')}
const VERSION = ${JSON.stringify(input.version ?? null)}

function printField(label, value) {
  if (value !== null && value !== undefined && value !== '') {
    console.log(\`  \${label}: \${value}\`)
  }
}

function duration(run) {
  if (typeof run.latency_ms === 'number') return \`\${(run.latency_ms / 1000).toFixed(2)}s\`
  if (!run.started_at || !run.completed_at) return null

  const milliseconds = Date.parse(run.completed_at) - Date.parse(run.started_at)
  return Number.isFinite(milliseconds) ? \`\${(milliseconds / 1000).toFixed(2)}s\` : null
}

function printIdentity() {
  console.log(TARGET_TYPE === 'network' ? 'Network' : 'Agent')
  printField('Name', TARGET_NAME)
  printField('Environment', ENVIRONMENT)
  if (TARGET_TYPE === 'network') printField('Version', VERSION)
}

function printExecution(run) {
  console.log('Execution')
  if (TARGET_TYPE === 'network') {
    printField('Run ID', run.execution_id)
  } else {
    printField('Provider', run.provider)
    printField('Model', run.model)
  }

  printField('Session', run.session_id ?? run.network_session_id)
  printField('Trace', run.trace_id)
  printField('Duration', duration(run))
  printField('Tokens', run.usage?.total_tokens)
  if (typeof run.usage?.cost_usd === 'number') {
    printField('Cost', \`$\${run.usage.cost_usd.toFixed(6)}\`)
  }
  if (run.fallback_used === true) printField('Fallback', 'used')
}

function printResult(run) {
  if (run.parsed_output !== null && run.parsed_output !== undefined) {
    console.log('Structured result')
    console.log(JSON.stringify(run.parsed_output, null, 2))
    return
  }

  console.log('Response')
  console.log(run.result ?? run.answer ?? '')
}

function printRun(run) {
  console.log(\`✓ \${TARGET_TYPE === 'network' ? 'Network Run' : 'Agent Run'} completed\\n\`)
  printIdentity()
  console.log('')
  printExecution(run)
  console.log('')
  printResult(run)
}

function printStreamCompletion(run) {
  console.log(\`✓ \${TARGET_TYPE === 'network' ? 'Network Run' : 'Agent Run'} completed\\n\`)
  printExecution(run)
}`
}

function javascriptRequest(input: BuildRuntimeSnippetInput): string {
  const idempotency = input.includeIdempotencyKey
    ? "\n    'Idempotency-Key': crypto.randomUUID(),"
    : ''

  return `const WOOBE_API_KEY = 'paste_your_runtime_key_here'

const response = await fetch('${endpoint(input.baseUrl, input.runtimeInterface)}', {
  method: 'POST',
  headers: {
    Authorization: \`Bearer \${WOOBE_API_KEY}\`,
    'Content-Type': 'application/json',${idempotency}
  },
  body: JSON.stringify(${prettyJson(input.body)}),
})

if (!response.ok) {
  const error = await response.json().catch(() => ({ message: response.statusText }))
  throw new Error(error.message ?? \`Woobe request failed: \${response.status}\`)
}`
}

function javascriptSnippet(input: BuildRuntimeSnippetInput): string {
  const helpers = javascriptHelpers(input)
  const request = javascriptRequest(input)

  if (input.runtimeInterface === 'stream') {
    return `${helpers}

${request}

if (!response.body) throw new Error('Streaming body is unavailable')

const reader = response.body.getReader()
const decoder = new TextDecoder()
let buffer = ''
let terminal = {}
let responseStarted = false

printIdentity()
console.log('\\nResponse')

while (true) {
  const { value, done } = await reader.read()
  if (done) break

  buffer += decoder.decode(value, { stream: true })
  const frames = buffer.split(/\\r?\\n\\r?\\n/)
  buffer = frames.pop() ?? ''

  for (const frame of frames) {
    const declaredEvent = frame.match(/^event:\\s*(.+)$/m)?.[1]?.trim()
    const dataLine = frame.match(/^data:\\s*(.+)$/m)?.[1]
    if (!dataLine) continue

    const eventPayload = JSON.parse(dataLine)
    const eventName = declaredEvent ?? eventPayload.type
    const data = eventPayload.data ?? eventPayload

    if (
      eventName === 'token'
      && ['response_generation', 'final_response_generation'].includes(data.phase)
    ) {
      process.stdout.write(data.content ?? '')
      responseStarted = true
    } else if (['error', 'execution_failed'].includes(eventName)) {
      throw new Error(data.message ?? 'Woobe execution failed.')
    } else if (['done', 'network_result'].includes(eventName)) {
      terminal = { ...eventPayload, ...data }
    }
  }
}

if (!responseStarted) printResult(terminal)
process.stdout.write('\\n\\n')
printStreamCompletion(terminal)`
  }

  return `${helpers}

${request}

printRun((await response.json()).data)`
}

function shellQuote(value: string): string {
  return `'${value.replace(/'/g, `'"'"'`)}'`
}

function curlSummaryFilter(input: BuildRuntimeSnippetInput): string {
  const targetLabel = input.targetType === 'network' ? 'Network' : 'Agent'
  const runLabel = input.targetType === 'network' ? 'Network Run' : 'Agent Run'
  const name = JSON.stringify(`  Name: ${input.targetName}`)
  const environment = JSON.stringify(`  Environment: ${input.environment === 'production' ? 'Production' : 'Staging'}`)
  const version = JSON.stringify(`  Version: ${input.version ?? '-'}`)
  const identityFields = input.targetType === 'network'
    ? `${name}, ${environment}, ${version}`
    : `${name}, ${environment}, (if $run.provider then "  Provider: \\($run.provider)" else empty end), (if $run.model then "  Model: \\($run.model)" else empty end)`
  const executionFields = input.targetType === 'network'
    ? `(if $run.execution_id then "  Run ID: \\($run.execution_id)" else empty end), (if $run.session_id then "  Session: \\($run.session_id)" else empty end), (if $run.trace_id then "  Trace: \\($run.trace_id)" else empty end)`
    : `(if $run.session_id then "  Session: \\($run.session_id)" else empty end), (if $run.trace_id then "  Trace: \\($run.trace_id)" else empty end), (if $run.latency_ms then "  Duration: \\($run.latency_ms / 1000)s" else empty end), (if $run.usage.total_tokens then "  Tokens: \\($run.usage.total_tokens)" else empty end), (if $run.usage.cost_usd then "  Cost: $\\($run.usage.cost_usd)" else empty end)`

  return `.data as $run |
[
  "✓ ${runLabel} completed",
  "",
  "${targetLabel}",
  ${identityFields},
  "",
  "Execution",
  ${executionFields},
  "",
  (if $run.parsed_output != null then "Structured result", ($run.parsed_output | tojson) else "Response", ($run.result // $run.answer // "") end)
] | .[]`
}

function curlSnippet(input: BuildRuntimeSnippetInput): string {
  const idempotency = input.includeIdempotencyKey
    ? ' \\\n  -H "Idempotency-Key: $(uuidgen)"'
    : ''
  const request = `curl -sS ${input.runtimeInterface === 'stream' ? '-N ' : ''}-X POST "${endpoint(input.baseUrl, input.runtimeInterface)}" \\
  -H "Authorization: Bearer $WOOBE_API_KEY" \\
  -H "Content-Type: application/json"${idempotency} \\
  -d ${shellQuote(prettyJson(input.body))}`

  if (input.runtimeInterface === 'stream') {
    return `WOOBE_API_KEY="paste_your_runtime_key_here"

# Use Python or JavaScript for a formatted streaming summary.
# cURL intentionally exposes the raw SSE protocol.
${request}`
  }

  return `WOOBE_API_KEY="paste_your_runtime_key_here"

# Requires jq to format the real Runtime response.
${request} | jq -r '${curlSummaryFilter(input)}'`
}

export function buildRuntimeSnippet(input: BuildRuntimeSnippetInput): string {
  switch (input.language) {
    case 'python': return pythonSnippet(input)
    case 'javascript': return javascriptSnippet(input)
    default: return curlSnippet(input)
  }
}
