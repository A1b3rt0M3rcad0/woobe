# Tipografia Woobe — famílias e uso

**Arquivos de fontes binários não são distribuídos neste ZIP.**

## Famílias

1. **Inter** — corpo, navegação, formulários, mensagens, descrições e diálogos. Fonte open-source. Projeto: https://github.com/rsms/inter ; licença SIL Open Font License (consultar versão distribuída).
2. **JetBrains Mono** — comandos, YAML, JSON, identificadores, timestamps, métricas técnicas e rótulos instrumentais. Projeto: https://www.jetbrains.com/lp/mono/ ; licença SIL Open Font License (consultar versão).
3. **Georgia** — títulos editoriais, títulos hero e headlines contextuais, conforme `--g-font-serif` da skill v2. Fontes do sistema: disponibilidade varia por plataforma. Fallback: Times New Roman → serif.
4. **Tiempos Text (opcional)** — nome exibido em um dos boards gerados; é uma família comercial e *não* está incluída, licenciada ou verificada na skill. Somente usar mediante licença apropriada.

## Font stack recomendada (não exige fonte externa embutida)

```css
:root {
  --woobe-font-sans: Inter, system-ui, sans-serif;
  --woobe-font-mono: 'JetBrains Mono', 'Fira Code', monospace;
  --woobe-font-serif: Georgia, 'Times New Roman', serif;
}
body { font-family: var(--woobe-font-sans); }
.editorial-heading { font-family: var(--woobe-font-serif); }
.technical-label, code, pre { font-family: var(--woobe-font-mono); }
```

## Uso operacional

Evite aplicar `font-family: JetBrains Mono` no `body` inteiro; isso deixa a UI pesada. Carregue as fontes open-source separadamente no projeto seguindo suas licenças e valide `document.fonts`/fontes renderizadas em Chromium.
