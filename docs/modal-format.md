# Modal format

Este documento define o formato visual e operacional padrão para modais complexos do Project Ray.

Use este padrão para modais de gerenciamento que tenham identidade do recurso, metadados, ações operacionais e conteúdo editável ou inspecionável. Exemplos atuais de referência: Tools, Collection details e Credential management.

## Quando usar

Use o modal horizontal quando o modal tiver mais de uma destas responsabilidades:

- Mostrar identidade do recurso selecionado.
- Exibir status, contadores, badges ou metadados.
- Permitir ações operacionais como enable, disable, archive, revoke, delete ou refresh.
- Exibir uma ou mais seções de configuração, uso, documentos, permissões ou regras.
- Precisar de contexto permanente enquanto o usuário lê ou edita conteúdo.

Não use esse formato para confirmações simples, criação curta ou formulários com poucos campos. Nesses casos, um modal compacto `max-w-2xl` ou menor continua adequado.

## Estrutura padrão

O shell recomendado é:

```tsx
<Dialog
  open={open}
  onClose={onClose}
  title="Resource details"
  className="max-h-[calc(100svh-2rem)] max-w-5xl overflow-hidden"
>
  <div className="max-h-[calc(100svh-8rem)] overflow-y-auto pr-1">
    <div className="grid gap-6 lg:grid-cols-[280px_minmax(0,1fr)]">
      <aside className="space-y-4 lg:sticky lg:top-0 lg:self-start">
        {/* identity, status and lifecycle actions */}
      </aside>

      <main className="space-y-5">
        {/* operational sections */}
      </main>
    </div>

    <div className="sticky bottom-0 -mx-1 mt-6 flex justify-end gap-2 border-t border-border bg-surface/95 px-1 py-4 backdrop-blur">
      {/* close / cancel / save */}
    </div>
  </div>
</Dialog>
```

## Layout

O modal deve ser horizontal em telas `lg+`:

```text
┌──────────────────────────────────────────────────────────────┐
│ Dialog title                                                  │
├──────────────────────────────────────────────────────────────┤
│ ┌────────────────────────┐ ┌───────────────────────────────┐ │
│ │ Aside                  │ │ Main                          │ │
│ │                        │ │                               │ │
│ │ Identity card          │ │ Section 1                     │ │
│ │ Status / badges        │ │ Section 2                     │ │
│ │ Lifecycle actions      │ │ Section 3                     │ │
│ └────────────────────────┘ └───────────────────────────────┘ │
├──────────────────────────────────────────────────────────────┤
│ Sticky footer                                                 │
└──────────────────────────────────────────────────────────────┘
```

Em telas menores, a grid pode colapsar naturalmente em uma coluna.

## Aside esquerdo

O `aside` é para contexto permanente e ações operacionais. Ele deve conter:

1. Card de identidade:
   - Ícone do recurso.
   - Nome principal.
   - Subtítulo curto, normalmente tipo/provider.
   - `StatusBadge`.
   - Pills de contadores ou classificação.

2. Card de status operacional:
   - Explicação curta.
   - Ação operacional primária, quando existir.

3. Card de lifecycle ou danger zone:
   - Archive, revoke, delete ou outra ação sensível.
   - Texto objetivo sobre impacto.
   - Botão que abre confirmação, não execução destrutiva direta.

Ações perigosas devem ficar no `aside`, não espalhadas no conteúdo principal.

## Main direito

O `main` é para conteúdo inspecionável ou editável. Use seções largas:

```tsx
<section className="rounded-xl border border-border/80 bg-surface/65 p-4">
  <h3 className="text-sm font-semibold text-white">Section title</h3>
  <p className="mt-1 text-xs leading-5 text-muted">Short explanation.</p>
  <div className="mt-4">...</div>
</section>
```

Seções devem ser agrupadas por intenção, não por campo individual. Exemplos:

- General / Details.
- Usage.
- Permissions.
- Documents.
- Lifecycle rules.
- Metadata.

Evite empilhar muitos cards soltos sem hierarquia. Isso deixa o modal vertical demais e piora a leitura.

## Footer

Use footer sticky para ações finais:

- `Close` quando não há edição inline.
- `Cancel` + `Save changes` quando há edição inline.
- Não coloque archive/revoke/delete no footer principal se forem ações de lifecycle; coloque no `aside`.

O footer deve usar:

```tsx
<div className="sticky bottom-0 -mx-1 mt-6 flex justify-end gap-2 border-t border-border bg-surface/95 px-1 py-4 backdrop-blur">
```

Quando precisar de responsividade com botões empilhados no mobile:

```tsx
<div className="sticky bottom-0 -mx-1 mt-6 flex flex-col-reverse gap-2 border-t border-border bg-surface/95 px-1 py-4 backdrop-blur sm:flex-row sm:justify-end">
```

## Confirmações

Confirmações simples devem continuar em modais compactos. Exemplo: delete document, revoke credential, archive model.

O modal de confirmação deve:

- Ser curto.
- Mostrar o alvo.
- Mostrar impacto ou uso atual, quando relevante.
- Bloquear confirmação quando a regra de negócio impedir a ação.
- Não substituir o modal principal de gerenciamento.

## Regra de UX

O usuário deve entender três coisas em menos de 5 segundos:

1. Qual recurso está gerenciando.
2. Qual é o estado atual desse recurso.
3. Quais ações são seguras, sensíveis ou bloqueadas.

Para isso, mantenha identidade e ações no `aside`, e conteúdo detalhado no `main`.

## Aplicação recomendada

- Tools: usa aside para identidade, runtime status e danger zone; main para general e MCP permissions.
- Collections: usa aside para identidade, contadores e metadata; main para collection information e documents.
- Credentials: deve usar aside para identidade, runtime status e lifecycle; main para credential details, usage e lifecycle rules.
