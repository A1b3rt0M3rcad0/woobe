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

function pythonSnippet(input: BuildRuntimeSnippetInput): string {
  const uuidImport = input.includeIdempotencyKey ? 'import uuid\n' : ''
  const idempotency = input.includeIdempotencyKey
    ? '\n    "Idempotency-Key": str(uuid.uuid4()),'
    : ''
  const payload = pythonLiteral(input.body)
  const request = `${uuidImport}import requests

API_KEY = "paste_your_runtime_key_here"
url = "${endpoint(input.baseUrl, input.runtimeInterface)}"
headers = {
    "Authorization": f"Bearer {API_KEY}",${idempotency}
}
payload = ${payload}`

  if (input.runtimeInterface === 'stream') {
    return `${request}

# Each SSE frame contains an event name and a JSON data payload.
with requests.post(
    url,
    headers=headers,
    json=payload,
    stream=True,
    timeout=120,
) as response:
    if not response.ok:
        print(f"HTTP {response.status_code}: {response.text}")
        response.raise_for_status()

    for line in response.iter_lines(decode_unicode=True):
        if line:
            print(line)`
  }

  return `${request}

response = requests.post(url, headers=headers, json=payload, timeout=120)
if not response.ok:
    print(f"HTTP {response.status_code}: {response.text}")
    response.raise_for_status()

print(response.json())`
}

function javascriptSnippet(input: BuildRuntimeSnippetInput): string {
  const idempotency = input.includeIdempotencyKey
    ? "\n    'Idempotency-Key': crypto.randomUUID(),"
    : ''
  const request = `const API_KEY = 'paste_your_runtime_key_here'

const response = await fetch('${endpoint(input.baseUrl, input.runtimeInterface)}', {
  method: 'POST',
  headers: {
    Authorization: \`Bearer \${API_KEY}\`,
    'Content-Type': 'application/json',${idempotency}
  },
  body: JSON.stringify(${prettyJson(input.body)}),
})

if (!response.ok) {
  throw new Error(\`Woobe request failed (\${response.status}): \${await response.text()}\`)
}`

  if (input.runtimeInterface === 'stream') {
    return `${request}

// The stream contains raw SSE frames: event: <name> and data: <json>.
if (!response.body) throw new Error('Streaming body is unavailable')

const reader = response.body.getReader()
const decoder = new TextDecoder()

while (true) {
  const { value, done } = await reader.read()
  if (done) break
  process.stdout.write(decoder.decode(value, { stream: true }))
}`
  }

  return `${request}

console.log(await response.json())`
}

function shellQuote(value: string): string {
  return `'${value.replace(/'/g, `'"'"'`)}'`
}

function curlSnippet(input: BuildRuntimeSnippetInput): string {
  const idempotency = input.includeIdempotencyKey
    ? ' \\\n  -H "Idempotency-Key: $(uuidgen)"'
    : ''

  return `WOOBE_API_KEY="paste_your_runtime_key_here"

curl ${input.runtimeInterface === 'stream' ? '-N ' : ''}-X POST "${endpoint(input.baseUrl, input.runtimeInterface)}" \\
  -H "Authorization: Bearer $WOOBE_API_KEY" \\
  -H "Content-Type: application/json"${idempotency} \\
  -d ${shellQuote(prettyJson(input.body))}`
}

export function buildRuntimeSnippet(input: BuildRuntimeSnippetInput): string {
  switch (input.language) {
    case 'python': return pythonSnippet(input)
    case 'javascript': return javascriptSnippet(input)
    default: return curlSnippet(input)
  }
}
