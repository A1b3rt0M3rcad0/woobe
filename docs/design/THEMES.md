# Operational themes and workspaces

The Control Plane offers Light, Dark and System in global navigation, authentication and the Agent/Network workspace headers. `woobe.theme` stores the preference locally; System is the default. The early same-origin `theme-init.js` applies it before application startup. The React provider follows system changes and storage events without replacing the application tree. Unavailable storage keeps the choice in memory.

`woobe-ui/src/styles/theme.css` owns operational color values. Tailwind aliases, CodeMirror, React Flow and portals use these variables. Existing Guild reconstruction assets remain intact. ChatSurface retains its independently configured consumer theme.

## Visual contract

Mode: operational, comfortable reading with compact technical summaries. Primary reference: the user's October 14 Guild Overview and Woobe Playground/Network captures (2560 × 1440 originals, displayed at 2048 × 1152). Supporting reference: `04-dark-agent-grid.png`, used for quiet dark surface separation. Archetypes: RunSummary/TraceList and operational AgentMiniCard, without marketing overlaps or invented optimization metrics.

Light base: mineral `#efede8`, workspace `#f5f3ef`, panel `#fffdf9`, charcoal `#292620`, copper `#a7441d`. Dark base: `#191a17`, workspace `#1d1f1b`, panel `#252721`, off-white `#f0eee7`, copper `#f1a16f`. Navigation remains charcoal in both modes. Elevated surfaces, controls, selection, chart categories and syntax each have semantic roles; control borders are stronger than decorative separators.

Inter serves navigation, forms, labels and prose; Georgia stays on editorial headings; JetBrains Mono serves values, code and technical identities. Operational metadata starts at 12px, code at 13px, panel labels at 13–14px. Layout must adapt before reducing text size.

At 1440px the intended workspace anatomy is a 56px rail, approximately 352px execution pane, flexible center and 320–360px inspector. Below the width needed for these regions, secondary panes become drawers or alternate regions. Numeric values remain unbroken; unavailable pricing is a labeled state with technical detail, never a zero cost.

Context composition compares persisted contribution units, with a zero baseline and exact text values. It does not allocate dollars or rename contribution units as provider tokens. Runtime remains wall-clock latency, independent of overlapping invocation durations.
