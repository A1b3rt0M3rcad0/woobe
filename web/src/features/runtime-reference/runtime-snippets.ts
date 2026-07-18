export type RuntimeCodeLanguage = 'curl' | 'python' | 'javascript' | 'java' | 'ruby' | 'go'
export type PublicRuntimeInterface = 'http' | 'stream'

export const RUNTIME_CODE_LANGUAGES: Array<{ value: RuntimeCodeLanguage; label: string }> = [
  { value: 'curl', label: 'cURL' },
  { value: 'python', label: 'Python' },
  { value: 'javascript', label: 'JavaScript' },
  { value: 'java', label: 'Java' },
  { value: 'ruby', label: 'Ruby' },
  { value: 'go', label: 'Go' },
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

function compactJson(body: Record<string, unknown>): string {
  return JSON.stringify(body)
}

function prettyJson(body: Record<string, unknown>): string {
  return JSON.stringify(body, null, 2)
}

function escapeJava(value: string): string {
  return value.replace(/\\/g, '\\\\').replace(/"/g, '\\"')
}

function escapeRuby(value: string): string {
  return value.replace(/\\/g, '\\\\').replace(/'/g, "\\'")
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
  const idempotency = input.includeIdempotencyKey
    ? "\n    'Idempotency-Key': str(uuid.uuid4()),"
    : ''
  const uuidImport = input.includeIdempotencyKey ? 'import uuid\n' : ''
  const payload = JSON.stringify(compactJson(input.body))
  if (input.runtimeInterface === 'stream') {
    return `${uuidImport}import json
import os
import requests

url = '${endpoint(input.baseUrl, input.runtimeInterface)}'
headers = {
    'Authorization': f"Bearer {os.environ['WOOBE_API_KEY']}",
    'Content-Type': 'application/json',${idempotency}
}
payload = json.loads(${payload})

with requests.post(url, headers=headers, json=payload, stream=True, timeout=120) as response:
    response.raise_for_status()
    for line in response.iter_lines(decode_unicode=True):
        if line:
            print(line)`
  }
  return `${uuidImport}import json
import os
import requests

url = '${endpoint(input.baseUrl, input.runtimeInterface)}'
headers = {
    'Authorization': f"Bearer {os.environ['WOOBE_API_KEY']}",
    'Content-Type': 'application/json',${idempotency}
}
payload = json.loads(${payload})

response = requests.post(url, headers=headers, json=payload, timeout=120)
response.raise_for_status()
print(response.json())`
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

while (true) {
  const { value, done } = await reader.read()
  if (done) break
  process.stdout.write(decoder.decode(value, { stream: true }))
}`
  }
  return `${request}

console.log(await response.json())`
}

function javaSnippet(input: BuildRuntimeSnippetInput): string {
  const json = escapeJava(compactJson(input.body))
  const idempotency = input.includeIdempotencyKey
    ? '\n        .header("Idempotency-Key", UUID.randomUUID().toString())'
    : ''
  const uuidImport = input.includeIdempotencyKey ? '\nimport java.util.UUID;' : ''
  const handler = input.runtimeInterface === 'stream'
    ? 'HttpResponse.BodyHandlers.ofLines()'
    : 'HttpResponse.BodyHandlers.ofString()'
  const responseType = input.runtimeInterface === 'stream' ? 'Stream<String>' : 'String'
  const bodyUse = input.runtimeInterface === 'stream'
    ? 'response.body().forEach(System.out::println);'
    : 'System.out.println(response.body());'
  const streamImport = input.runtimeInterface === 'stream' ? '\nimport java.util.stream.Stream;' : ''
  return `import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;${uuidImport}${streamImport}

public class WoobeExample {
  public static void main(String[] args) throws Exception {
    var client = HttpClient.newHttpClient();
    var request = HttpRequest.newBuilder()
        .uri(URI.create("${endpoint(input.baseUrl, input.runtimeInterface)}"))
        .header("Authorization", "Bearer " + System.getenv("WOOBE_API_KEY"))
        .header("Content-Type", "application/json")${idempotency}
        .POST(HttpRequest.BodyPublishers.ofString("${json}"))
        .build();

    HttpResponse<${responseType}> response = client.send(request, ${handler});
    if (response.statusCode() >= 400) {
      throw new IllegalStateException("Woobe request failed: " + response.statusCode());
    }
    ${bodyUse}
  }
}`
}

function rubySnippet(input: BuildRuntimeSnippetInput): string {
  const json = escapeRuby(compactJson(input.body))
  const idempotency = input.includeIdempotencyKey
    ? "\nrequest['Idempotency-Key'] = SecureRandom.uuid"
    : ''
  const secureImport = input.includeIdempotencyKey ? "\nrequire 'securerandom'" : ''
  if (input.runtimeInterface === 'stream') {
    return `require 'net/http'
require 'json'${secureImport}

uri = URI('${endpoint(input.baseUrl, input.runtimeInterface)}')
request = Net::HTTP::Post.new(uri)
request['Authorization'] = "Bearer #{ENV.fetch('WOOBE_API_KEY')}"
request['Content-Type'] = 'application/json'${idempotency}
request.body = '${json}'

Net::HTTP.start(uri.host, uri.port, use_ssl: uri.scheme == 'https') do |http|
  http.request(request) do |response|
    raise "Woobe request failed: #{response.code}" unless response.is_a?(Net::HTTPSuccess)
    response.read_body { |chunk| print chunk }
  end
end`
  }
  return `require 'net/http'
require 'json'${secureImport}

uri = URI('${endpoint(input.baseUrl, input.runtimeInterface)}')
request = Net::HTTP::Post.new(uri)
request['Authorization'] = "Bearer #{ENV.fetch('WOOBE_API_KEY')}"
request['Content-Type'] = 'application/json'${idempotency}
request.body = '${json}'

response = Net::HTTP.start(uri.host, uri.port, use_ssl: uri.scheme == 'https') do |http|
  http.request(request)
end

raise "Woobe request failed: #{response.code} #{response.body}" unless response.is_a?(Net::HTTPSuccess)
puts JSON.pretty_generate(JSON.parse(response.body))`
}

function goSnippet(input: BuildRuntimeSnippetInput): string {
  const json = JSON.stringify(compactJson(input.body))
  const idempotency = input.includeIdempotencyKey
    ? '\n\treq.Header.Set("Idempotency-Key", fmt.Sprintf("woobe-%d", time.Now().UnixNano()))'
    : ''
  const timeImport = input.includeIdempotencyKey ? '\n\t"time"' : ''
  const bodyReader = input.runtimeInterface === 'stream'
    ? `scanner := bufio.NewScanner(response.Body)
\tfor scanner.Scan() {
\t\tfmt.Println(scanner.Text())
\t}
\tif err := scanner.Err(); err != nil {
\t\tlog.Fatal(err)
\t}`
    : `body, err := io.ReadAll(response.Body)
\tif err != nil {
\t\tlog.Fatal(err)
\t}
\tfmt.Println(string(body))`
  const streamImport = input.runtimeInterface === 'stream' ? '\n\t"bufio"' : '\n\t"io"'
  return `package main

import (
\t"bytes"${streamImport}
\t"fmt"
\t"log"
\t"net/http"
\t"os"${timeImport}
)

func main() {
\tpayload := []byte(${json})
\treq, err := http.NewRequest(http.MethodPost, "${endpoint(input.baseUrl, input.runtimeInterface)}", bytes.NewReader(payload))
\tif err != nil {
\t\tlog.Fatal(err)
\t}
\treq.Header.Set("Authorization", "Bearer "+os.Getenv("WOOBE_API_KEY"))
\treq.Header.Set("Content-Type", "application/json")${idempotency}

\tresponse, err := http.DefaultClient.Do(req)
\tif err != nil {
\t\tlog.Fatal(err)
\t}
\tdefer response.Body.Close()

\tif response.StatusCode >= 400 {
\t\tlog.Fatalf("Woobe request failed: %s", response.Status)
\t}

\t${bodyReader}
}`
}

export function buildRuntimeSnippet(input: BuildRuntimeSnippetInput): string {
  switch (input.language) {
    case 'python': return pythonSnippet(input)
    case 'javascript': return javascriptSnippet(input)
    case 'java': return javaSnippet(input)
    case 'ruby': return rubySnippet(input)
    case 'go': return goSnippet(input)
    default: return curlSnippet(input)
  }
}
