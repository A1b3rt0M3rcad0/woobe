## Objetivo

Descreva o resultado entregue e o escopo deliberadamente excluído.

## Critérios de aceite

- [ ] Cada critério possui evidência verificável.
- [ ] A mudança está limitada ao escopo do PR.

## Testes

- [ ] Backend: Ruff, Pyright e Pytest.
- [ ] Frontend: npm ci, build e Vitest.
- [ ] Migrations: uma única head e upgrade em banco vazio.
- [ ] Containers: builds e smoke test.

## Banco de dados

- [ ] Não altera schema.
- [ ] Migration aditiva e reversível incluída.
- [ ] Upgrade validado em banco vazio e no caminho suportado.

## Segurança

- [ ] Autenticação e autorização revisadas quando aplicável.
- [ ] Nenhum segredo, token ou dado pessoal incluído.
- [ ] Logs e erros não expõem informação sensível.

## Rollback

Descreva comandos e impacto do rollback.

## Riscos e trabalho adiado

Liste riscos residuais, limitações e itens fora de escopo.
