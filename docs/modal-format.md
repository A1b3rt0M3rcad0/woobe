# Modal format

Este documento define o formato visual e operacional padrão para modais complexos do Project Ray.

Use este padrão para modais de gerenciamento que tenham identidade do recurso, metadados, ações operacionais e conteúdo editável ou inspecionável. Exemplos: Tools, Collection details, Credential management e Provider model management.

## Quando usar

Use o modal horizontal quando o modal tiver mais de uma destas responsabilidades:

- Mostrar identidade do recurso selecionado.
- Exibir status, contadores, badges ou metadados.
- Permitir ações operacionais como enable, disable, archive, revoke, delete, rotate ou refresh.
- Exibir seções de configuração, uso, documentos, permissões ou regras.
- Precisar de contexto permanente enquanto o usuário lê ou edita conteúdo.

Não use esse formato para confirmações simples, criação curta ou formulários com poucos campos. Nesses casos, use um modal compacto `max-w-2xl` ou menor.

## Regra técnica obrigatória

O markup do modal deve refletir a estrutura visual final. Não use CSS posicional por ordem de filhos, como `nth-child`, para transformar um modal vertical em horizontal.

A estrutura correta deve ser explícita:

- `aside` para identidade, estado e ações operacionais.
- `main` para conteúdo detalhado, listas, regras e configuração.
- footer sticky para fechamento ou save/cancel.

CSS global pode definir tokens e utilitários, mas não deve reorganizar um modal específico por seletor frágil.

## Estrutura padrão

```tsx
<Dialog
  open={open}
  onClose={onClose}
  title="Resource details"
  className="max-h-[calc(100svh-2rem)] max-w-5xl overflow-hidden"
>
  <div className="max-h-[calc(100svh-8rem)] overflow-y-auto pr-1 scrollbar-thin">
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

Qualquer área interna com `overflow-y-auto` deve usar `scrollbar-thin`.

## Aside esquerdo

O `aside` é para contexto permanente e ações operacionais:

1. Card de identidade: ícone, nome principal, subtítulo, `StatusBadge`, pills e identificador essencial.
2. Card de ação operacional primária: ação segura ou recomendada, como rotate, refresh ou upload.
3. Card de lifecycle/danger zone: archive, revoke, delete ou ação sensível.

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

Agrupe por intenção, não por campo individual. Exemplos: Details, Usage, Attached models, Permissions, Documents, Metadata.

## Listas grandes e pickers

Listas grandes dentro de modal não devem ser renderizadas inline quando forem acionadas por um campo de seleção. Isso faz o modal crescer verticalmente e quebra a estabilidade visual.

Use picker em overlay quando a lista for grande, pesquisável ou remota:

- Campo fechado com altura fixa.
- Lista aberta em camada `absolute`/popover com `z-50`.
- `max-h` controlado e `scrollbar-thin`.
- Seleção fecha o overlay.
- `Escape`, blur ou clique fora fecham o overlay.
- O overlay não deve empurrar seções abaixo.

Não use `<select>` nativo para catálogos com dezenas ou centenas de opções. Não use lista inline para catálogo de models.

## Botões e cor

Use cor para comunicar risco e prioridade, sem poluir:

- Ação recomendada e segura: `outline` quando o design for minimalista.
- Atenção/runtime risk: outline neutro com texto âmbar discreto.
- Cleanup sensível/destrutivo: outline neutro com texto vermelho discreto no modal principal; preenchido apenas na confirmação final.
- Fechamento: outline neutro.

## Footer

Use footer sticky para ações finais:

- `Close` quando não há edição inline.
- `Cancel` + `Save changes` quando há edição inline.
- Não coloque archive/revoke/delete no footer principal se forem ações de lifecycle.

## Confirmações

Confirmações simples devem continuar em modais compactos. O modal de confirmação deve ser curto, mostrar o alvo, mostrar impacto quando relevante e bloquear confirmação quando a regra impedir a ação.

## Regra de UX

O usuário deve entender três coisas em menos de 5 segundos:

1. Qual recurso está gerenciando.
2. Qual é o estado atual desse recurso.
3. Quais ações são seguras, sensíveis ou bloqueadas.

## Padrão específico para credenciais

O modal de credenciais deve priorizar rotação, não edição genérica.

```text
Aside:
- Identity card: name, provider, status, attached model count, endpoint.
- Rotate credential: campo inline para novo valor, botão Rotate e ícone de ajuda no título.
- Lifecycle: revoke e archive com cor textual discreta.

Main:
- Credential details.
- Attached models.

Footer:
- Close.
```

Use `Rotate` com campo inline quando a ação for apenas substituir o valor da credencial preservando o mesmo ID. Ao clicar em `Rotate`, abra um modal compacto de confirmação antes de enviar a alteração.

## Padrão específico para provider models

O modal de model deve separar providers catalogáveis de providers manuais.

Provider catalogável:

- `openrouter` usa picker pesquisável em overlay para o catálogo.
- `openai` pode usar picker se o backend retornar catálogo confiável.
- O picker não deve expandir o corpo do modal.
- Selecionar um model do catálogo preenche o identificador e pode preencher nome/preço quando apropriado.

Provider manual:

- `custom` / `OpenAI Compatible` é manual-only no MVP.
- Não deve mostrar catálogo remoto.
- Não deve buscar lista de models.
- Não deve alterar `Model details` por clique em lista.
- Deve mostrar apenas `Model identifier`.

Fluxo esperado:

```text
OpenRouter:
Credential -> Model catalog picker -> Model details

Custom/OpenAI Compatible:
Credential -> Model identifier -> Model details
```
