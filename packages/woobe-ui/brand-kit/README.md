# Woobe Design Kit — SVG, PNG, ICO, tokens e componentes

Pacote reconstruído a partir dos boards de identidade visual e de produto fornecidos nesta conversa.

**Amostras:** 25 ícones UI individuais; 53 componentes SVG editáveis; 58 recortes raster; 6 boards completos.

## Comece por aqui

- **`preview/index.html`** — catálogo HTML navegável offline.
- **`brand/svg/`** — símbolo X modular, wordmark delineado, logotipos horizontais e empilhados, versões monocromáticas, avatares e construção.
- **`brand/png/`** — marca em PNG transparente e dimensões práticas.
- **`brand/favicons/favicon.ico`** — favicon multirresolução; PNGs 16/32/48/180/192/512.
- **`brand/social/`** — avatares e imagem de compartilhamento.
- **`icons/`** — ícones de interface SVG, PNG e sprite.
- **`design-tokens/`** — cores em CSS/SCSS/JSON/CSV, tipografia, espaçamento e extensão Tailwind de exemplo.
- **`components/svg/`** e **`components/png/`** — componentes reconstituídos (cards, botões, tabelas, modal, terminal, dashboard).
- **`components/code/`** — CSS e página HTML com componentes sem dependências.
- **`raster-extractions/`** — recortes de pixels dos boards originais, com coordenadas em `crop-manifest.json`.
- **`reference-boards/`** — imagens originais de referência.
- **`documentation/`** — regras e inventário.
- **`typography/`** — stacks de fontes e orientação de licenciamento; **não contém arquivos binários de fontes**.

## Distinção fundamental

Há **três níveis de fidelidade**: (a) `reference-boards/` e `raster-extractions/` preservam os pixels das imagens fornecidas; (b) `brand/svg/woobe-mark-orange.svg` e `brand/svg/woobe-wordmark-outlined.svg` são vetorizados a partir dos pixels (não arquivos mestres de design); (c) `components/svg/` e `components/code/` são interpretações editáveis que seguem a gramática visual, não extração automática de camadas inexistentes.

Fonte comercial/arquivos `.ttf`, `.otf` e `.woff2` **não estão incluídos**. Veja `typography/FONTES.md`.

## Nota importante

Números como 75%, 91% e métricas nos conceitos visuais são **conteúdo ilustrativo, não métricas verificadas da Woobe**. Os boards foram gerados por modelo de imagem e podem conter microtexto imperfeito.


## Atualização de transparência
- Logotipos e ícones de marca foram atualizados para versões sem fundo (transparentes).
- Os arquivos `app-icon-*`, `social/avatar-*` e `brand/favicons/*` agora exportam somente o elemento da marca, sem painéis branco, preto ou laranja ao fundo.
