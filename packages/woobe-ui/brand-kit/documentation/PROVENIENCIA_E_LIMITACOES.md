# Proveniência, exatidão e limitações

## Imagens fonte fornecidas na conversa

- Brand identity (identidade e variações).
- Logo assets (favicon, app icon, avatares, espaço de proteção e exemplos).
- UI design system (controles, cards, modal e dashboard).
- Product application (laptop/desktop/mobile e exemplos em contexto).
- Landing page (header, hero, cards, métricas, CLI, capacidades e painel).

Esses boards foram gerados por ferramenta de imagem. **Não contêm arquivo Figma ou vetor original com camadas.** `raster-extractions/` preserva recortes exatos de pixels, mantendo a origem no manifesto. `brand/svg/` é traçado vetorial sobre o original; `components/svg/` é reconstrução manual programática.

## Tipografia

Os boards citam `Tiempos Text`; a skill v2, entretanto, mapeia o token serif à stack `Georgia, Times New Roman, serif`. Não se pode inferir da rasterização a fonte exata usada pelo gerador. Tiempos Text exige licença e não está embutida. Consulte `typography/FONTES.md`.

## Garantias e cuidados

- Métricas do mockup não devem ser apresentadas como dados medidos, depoimentos ou promessas reais.
- Copy de demonstração não define contratos de API ou comandos efetivamente existentes.
- Revisar escala, contraste WCAG, responsividade e acessibilidade no aplicativo em execução.
- Não há software de produção/React, repositório upstream, plugin, Figma ou arquivo-fonte de fonte incluídos.
- Não houve avaliação de originalidade/trademark frente a outras marcas.

## Formatos

O ZIP contém SVG editável, PNG raster/recortes, ICO favicon, HTML/CSS, JSON, CSV, SCSS e Markdown.
