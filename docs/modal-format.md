# Modal format

Este documento define o formato visual e operacional padrão para modais complexos do Project Ray.

Use este padrão para modais de gerenciamento que tenham identidade do recurso, metadados, ações operacionais e conteúdo editável ou inspecionável. Exemplos atuais de referência: Tools, Collection details e Credential management.

## Quando usar

Use o modal horizontal quando o modal tiver mais de uma destas responsabilidades:

- Mostrar identidade do recurso selecionado.
- Exibir status, contadores, badges ou metadados.
- Permitir ações operacionais como enable, disable, archive, revoke, delete, rotate ou refresh.
- Exibir uma ou mais seções de configuração, uso, documentos, permissões ou regras.
- Precisar de contexto permanente enquanto o usuário lê ou edita conteúdo.

Não use esse formato para confirmações simples, criação curta ou formulários com poucos campos. Nesses casos, um modal compacto `max-w-2xl` ou menor continua adequado.

## Regra técnica obrigatória

O markup do modal deve refletir a estrutura visual final. Não use CSS posicional por ordem de filhos, como `nth-child`, para transformar um modal vertical em horizontal.

A estrutura correta deve ser explícita:

- `aside` para identidade, estado e ações operacionais.
- `main` para conteúdo detalhado, listas, regras e configuração.
- footer sticky para fechamento ou save/cancel.

CSS global pode definir tokens e utilitários, mas não deve reorganizar um modal específico por seletor frágil.

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
   - Endpoint ou identificador essencial quando isso ajuda a reconhecer o recurso.

2. Card de ação operacional primária:
   - Ação recomendada e segura, quando existir.
   - Exemplo: `Rotate credential`, `Refresh tools`, `Upload document`.
   - Deve ter botão visualmente mais forte que ações sensíveis.

3. Card de lifecycle ou danger zone:
   - Archive, revoke, delete ou outra ação sensível.
   - Texto objetivo sobre impacto.
   - Botão que abre confirmação, não execução destrutiva direta.

Ações perigosas devem ficar no `aside`, não espalhadas no conteúdo principal nem no footer.

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
- Attached models.
- Permissions.
- Documents.
- Lifecycle rules.
- Metadata.

Evite empilhar muitos cards soltos sem hierarquia. Isso deixa o modal vertical demais e piora a leitura.

## Botões e cor

Use cor para comunicar risco e prioridade, sem poluir o modal:

- Ação recomendada e segura: botão primário (`default`).
- Ação de atenção/runtime risk: outline com tom âmbar.
- Ação destrutiva ou cleanup sensível: outline vermelho no modal principal; vermelho preenchido apenas na confirmação final.
- Fechamento: outline neutro.

Exemplo para credenciais:

- `Rotate credential`: primário, porque é a ação segura recomendada.
- `Revoke credential`: âmbar, porque pode quebrar runtime imediatamente.
- `Archive credential`: vermelho discreto, porque remove da operação normal e pode ser bloqueado por referências.
- `Close`: neutro.

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
- Credentials: usa aside para identidade, rotação e lifecycle; main para credential details, attached models e lifecycle rules.

## Padrão específico para credenciais

O modal de credenciais deve priorizar rotação, não edição genérica.

Estrutura recomendada:

```text
Aside:
- Identity card: name, provider, status, attached model count, endpoint.
- Rotate credential: ação primária e segura.
- Lifecycle: revoke e archive com cores de risco.

Main:
- Credential details: name, provider, endpoint.
- Attached models: lista compacta dos models ativos que usam a credential.
- Lifecycle rules: rotate, revoke e archive explicados lado a lado.

Footer:
- Close.
```

Use `Rotate credential` em vez de `Edit credential` quando a ação abrir o fluxo de substituição de segredo/provider settings preservando o mesmo ID da credencial.
