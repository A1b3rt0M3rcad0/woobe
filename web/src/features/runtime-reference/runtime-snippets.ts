export type RuntimeCodeLanguage = 'curl' | 'python' | 'javascript'
export type PublicRuntimeInterface = 'http' | 'stream'

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
  includeIdempotencyKey?: boolean
}

function endpoint(baseUrl: string, runtimeInterface: PublicRuntimeInterface): string {
  return `${baseUrl}${runtimeInterface === 'stream' ? '/v1/run/stream' : '/v1/run'}`
}

function prettyJson(body: Record<string, unknown>): string {
  return JSON.stringify(body, null, 2)
}

function curlSnippet(input: BuildRuntimeSnippetInput): string {
  const idempotency = input.includeIdempotencyKey
    ? ' \\\n  -H "Idempotency-Key: $(uuidgen)"'
    : ''

  return `curl ${input.runtimeInterface === 'stream' ? '-N ' : ''}-X POST "${endpoint(input.baseUrl, input.runtimeInterface)}" \\
  -H "Authorization: Bearer $WOOBE_API_KEY" \\
  -H "Content-Type: application/json"${idempotency} \\
  -d '${prettyJson(input.body)}'`
}

function pythonSnippet(input: BuildRuntimeSnippetInput): string {
  const uuidImport = input.includeIdempotencyKey ? 'import uuid\n' : ''
  const idempotency = input.includeIdempotencyKey
    ? '\n        "Idempotency-Key": str(uuid.uuid4()),'
    : ''

  if (input.runtimeInterface === 'stream') {
    return `${uuidImport}import json
import os

import requests

response_started = False
event_name = None

with requests.post(
    "${endpoint(input.baseUrl, input.runtimeInterface)}",
    headers={
        "Authorization": f"Bearer {os.environ['WOOBE_API_KEY']}",${idempotency}
    },
    json=${prettyJson(input.body).replace(/true/g, 'True').replace(/false/g, 'False').replace(/null/g, 'None')},
    stream=True,
    timeout=120,
) as response:
    response.raise_for_status()

    for line in response.iter_lines(decode_unicode=True):
        if not line:
            event_name = None
            continue

        if line.startswith("event:"):
            event_name = line.removeprefix("event:").strip()
            continue

        if not line.startswith("data:"):
            continue

        payload = json.loads(line.removeprefix("data:").strip())
        data = payload.get("data", payload)

        if event_name == "token" and data.get("phase") in {
            "response_generation",
            "final_response_generation",
        }:
            print(data.get("content", ""), end="", flush=True)
            response_started = True

        elif event_name in {"error", "execution_failed"}:
            raise RuntimeError(data.get("message", "Woobe execution failed."))

        elif not response_started and event_name in {"done", "network_result"}:
            result = data.get("parsed_output") or data.get("result") or data.get("answer")
            if isinstance(result, (dict, list)):
                print(json.dumps(result, ensure_ascii=False, indent=2), end="")
            elif result:
                print(result, end="")
            response_started = True

print()`
  }

  return `${uuidImport}import os

import requests

response = requests.post(
    "${endpoint(input.baseUrl, input.runtimeInterface)}",
    headers={
        "Authorization": f"Bearer {os.environ['WOOBE_API_KEY']}",${idempotency}
    },
    json=${prettyJson(input.body).replace(/true/g, 'True').replace(/false/g, 'False').replace(/null/g, 'None')},
    timeout=120,
)
response.raise_for_status()

run = response.json()["data"]
print(run.get("parsed_output") or run["answer"])`
}

function javascriptSnippet(input: BuildRuntimeSnippetInput): string {
  const idempotency = input.includeIdempotencyKey
    ? "\n    'Idempotency-Key': crypto.randomUUID(),"
    : ''
  const request = `const response = await fetch('${endpoint(input.baseUrl, input.runtimeInterface)}', {
  method: 'POST',
  headers: {
    Authorization: \`Bearer \${process.env.WOOBE_API_KEY}\`,
    'Content-Type': 'application/json',${idempotency}
  },
  body: JSON.stringify(${prettyJson(input.body)}),
})

if (!response.ok) {
  throw new Error(\`Woobe request failed: \${response.status} \${await response.text()}\`)
}`

  if (input.runtimeInterface === 'stream') {
    return `${request}

if (!response.body) throw new Error('Streaming body is unavailable')

const reader = response.body.getReader()
const decoder = new TextDecoder()
let buffer = ''
let responseStarted = false

while (true) {
  const { value, done } = await reader.read()
  if (done) break

  buffer += decoder.decode(value, { stream: true })
  const frames = buffer.split('\\n\\n')
  buffer = frames.pop() ?? ''

  for (const frame of frames) {
    const eventName = frame.match(/^event:\\s*(.+)$/m)?.[1]?.trim()
    const dataLine = frame.match(/^data:\\s*(.+)$/m)?.[1]
    if (!eventName || !dataLine) continue

    const payload = JSON.parse(dataLine)
    const data = payload.data ?? payload

    if (
      eventName === 'token'
      && ['response_generation', 'final_response_generation'].includes(data.phase)
    ) {
      process.stdout.write(data.content ?? '')
      responseStarted = true
    } else if (['error', 'execution_failed'].includes(eventName)) {
      throw new Error(data.message ?? 'Woobe execution failed.')
    } else if (!responseStarted && ['done', 'network_result'].includes(eventName)) {
      const result = data.parsed_output ?? data.result ?? data.answer
      process.stdout.write(typeof result === 'string' ? result : JSON.stringify(result, null, 2))
      responseStarted = true
    }
  }
}

process.stdout.write('\\n')`
  }

  return `${request}

const run = (await response.json()).data
console.log(run.parsed_output ?? run.answer)`
}

export function buildRuntimeSnippet(input: BuildRuntimeSnippetInput): string {
  switch (input.language) {
    case 'python': return pythonSnippet(input)
    case 'javascript': return javascriptSnippet(input)
    default: return curlSnippet(input)
  }
}
