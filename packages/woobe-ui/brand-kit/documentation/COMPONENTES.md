# Inventário dos componentes SVG

Total: **53** componentes editáveis SVG, cada um com render PNG correspondente.

| Família | Arquivos (em `components/svg/`) |
|---|---|
| Controles | `button-*.svg`, `field-*.svg`, `segmented-control.svg`, `tabs-navigation.svg` |
| Status | `badge-*.svg` |
| Agentes | `agent-mini-*.svg` |
| Métricas | `metric-*.svg`, `dashboard-stat-*.svg` |
| Capacidades | `feature-*.svg` |
| Observabilidade | `reliability-performance.svg`, `technical-dot-meter.svg`, `dashboard-overview-composition.svg` |
| Técnica e governo | `terminal-cli-window.svg`, `table-agent-list.svg`, `modal-deploy-confirmation.svg` |
| Identidade aplicada | `top-navigation.svg`, `landing-hero-illustration.svg`, `color-swatch-*.svg` |

Esses componentes representam reconstruções vetoriais editáveis. Não equivalem a código React integrado ao backend, nem garantem pixel-perfect nos browsers. `components/code/` contém CSS e HTML sem dependências como base inicial.

## Navegação de arquivos

Abra `preview/index.html` para prévia geral, `components/components-manifest.json` para inventário estruturado, `raster-extractions/crop-manifest.json` para rastrear os recortes de imagem aos boards.

## Recomendações de implantação

- Utilize tokens globais em vez de valores repetidos em componentes.
- Texto de interface: Inter; títulos editoriais: Georgia; rótulos instrumentais: JetBrains Mono.
- Card técnico: contorno 1px, cabeçalho compacto, corpo alinhado, linha de separação e footer técnico.
- Valores e preços: conteúdo demonstrativo deve ser trocado por dados reais verificados.
- Responsividade operacional requer implementação específica; SVGs são recursos visuais de referência.
