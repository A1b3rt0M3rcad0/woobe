# CI e proteção de branches do MVP

## Workflows

Os workflows são executados em pull requests destinados a `development-mvp` e `development`. Todos usam permissões de repositório somente para leitura, dependências travadas e infraestrutura descartável.

Checks obrigatórios:

- `Backend / quality`
- `Frontend / build-and-test`
- `Migrations / schema`
- `Containers / build`
- `Containers / smoke`

## Proteção de `development-mvp`

Configure pull request obrigatório, pelo menos uma aprovação humana, descarte de aprovação obsoleta, resolução obrigatória de conversas, branch atualizada antes do merge, os cinco checks acima, bloqueio de push direto, force push e exclusão.

## Promoção final

A mesma suíte deve ser obrigatória no PR manual de `development-mvp` para `development`. Esse PR não deve usar squash merge.

## Segurança operacional

Os workflows não usam segredos de produção nem bancos compartilhados. As credenciais declaradas são exclusivas do ambiente efêmero do runner.
