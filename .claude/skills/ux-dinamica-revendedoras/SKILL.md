---
name: ux-dinamica-revendedoras
description: Biblioteca de padrões de UX/UI testados em CRMs (Pipedrive, HubSpot, Nutshell), ferramentas Kanban e dashboards de gamificação de vendas, adaptada para o sistema de gestão de revendedoras da Aureum Joias (Preciosas, tiers Pérola/Ouro/Diamante, supervisoras, maletas). Use esta skill sempre que José pedir para tornar uma tela mais visual, mais dinâmica, mais interativa, "menos robótica", ou quando ele mencionar ranking, funil de captação, pipeline de revendedoras, painel administrativo, ou qualquer tela do sistema que pareça rígida ou pouco engajante — mesmo que ele não use as palavras "UX" ou "design". Consulte também a skill frontend-design para identidade visual/aesthetic direction; esta skill foca em padrões de interação e dinâmica, não em estilo gráfico.
---

# UX Dinâmica para o Sistema de Revendedoras da Aureum

Esta skill existe porque um sistema pode estar com dados corretos e integração de API funcionando, e ainda assim parecer "morto" para quem usa — porque dados corretos não é a mesma coisa que experiência viva. O problema que José descreveu (informação completa, mas tela rígida, sem dinâmica) é o sintoma clássico de um sistema construído de dentro para fora (schema → tela) em vez de de fora para dentro (como a pessoa usa → schema). Esta skill resolve isso trazendo padrões testados em CRMs de vendas, ferramentas Kanban e dashboards de gamificação, mapeados especificamente para o vocabulário da Aureum: revendedoras, Preciosas, tiers, supervisoras, maletas.

## Identidade visual da Aureum

Sempre aplicar ao gerar ou redesenhar qualquer tela:

- **Rosa principal:** `#AB6774` — cor dominante da marca, usada em headers, bordas de destaque, avatares
- **Branco:** `#FFFFFF` — fundo de cards e superfícies
- **Gold complementar:** `#C4985A` — para 1º lugar no ranking, badges Ouro, detalhes de destaque
- **Creme suave:** `#FAF7F4` — fundo de página, seções internas
- **Tipografia:** Cormorant Garamond (equivalente livre de Argue Regular, disponível no Google Fonts) para títulos/valores; Jost Light/Regular (equivalente livre de Gotham Light) para labels e meta-info
- **Badges de tier:** Pérola `#EDE8E3`/texto escuro · Ouro `#C4985A`/texto branco · Diamante `#AB6774`/texto branco
- **Bordas:** `rgba(171,103,116,.15)` — sutil, quente, nunca cinza frio

Em Streamlit, aplicar via `src/theme/aureum.py` com `inject()` no topo de cada página.

## 0. Antes de aplicar qualquer padrão: identifique a stack real

Este projeto usa **Streamlit (Python)**. Todo padrão de HTML/JS desta skill deve ser adaptado para injeção via `st.markdown(..., unsafe_allow_html=True)`. Os snippets de referência são vanilla JS/HTML — leia-os para entender a estrutura e o CSS, depois escreva o equivalente Streamlit com HTML inline.

## 1. Diagnóstico: por que a tela parece rígida

- **Tabela em vez de cartão.** Listas em `st.dataframe` escondem hierarquia visual (quem está em risco, quem está perto de subir de tier) atrás de texto uniforme.
- **Nenhum feedback de ação.** `st.success()` existe mas é genérico — não tem a personalidade da Aureum.
- **Estado único.** A tela só tem um jeito de aparecer: com dados. Não existe versão de "vazio" com a voz da marca.
- **Hierarquia plana.** Tudo tem o mesmo peso visual no `st.metric` padrão.
- **Zero competição/progresso visível.** Tiers existem na lógica mas não aparecem visualmente no ranking.

## 2. Os 5 padrões centrais

### 2.1 Pipeline Kanban
Para funis com etapas (captação, ciclo de maleta). Em Streamlit: `st.columns` com listas de cartões HTML em cada coluna. Drag-and-drop nativo não está disponível; substituir por `st.selectbox` para mudar status, com `st.rerun()` para atualizar.

→ Snippets completos: `references/pipeline-kanban.md`

### 2.2 Cartões em vez de linhas de tabela
Cada revendedora vira HTML card com avatar/iniciais, badge de tier colorido, indicador de status (ponto verde/amarelo/vermelho).

### 2.3 Ranking gamificado: pódio + barra de progresso
Top 3 com pódio visual (altura diferente para 1º/2º/3º), resto com barra de progresso até próximo tier.

→ Snippets completos: `references/leaderboard-gamificacao.md`

### 2.4 Microinterações
`st.success()` com mensagem na voz da Aureum. Contadores animados via JS inline. Transições CSS.

→ Snippets completos: `references/microinteracoes-estados.md`

### 2.5 Estados vazios e de carregamento com voz própria
Em vez de "Nenhum registro encontrado": "Nenhuma Preciosa neste estágio ainda — hora de captar."

## 3. Checklist de auditoria rápida

- [ ] Listas de revendedoras em `st.dataframe` que poderiam ser cartões com status visual?
- [ ] Alguma ação do admin não gera confirmação visível com a voz da Aureum?
- [ ] A tela tem estado vazio desenhado?
- [ ] Progresso até próximo tier está visível?
- [ ] KPIs importantes têm peso visual diferente de informação secundária?

## 4. Tokens visuais de partida

```css
:root {
  --au-rosa: #AB6774;
  --au-rosa-light: #C89199;
  --au-rosa-pale: #F5EBEC;
  --au-white: #FFFFFF;
  --au-cream: #FAF7F4;
  --au-gold: #C4985A;
  --au-gold-light: #E8D5A3;
  --au-ink: #2A1A1F;
  --au-ink-muted: #7A6068;
  --au-border: rgba(171,103,116,.15);
  --au-perola: #EDE8E3;
  --au-ouro: #C4985A;
  --au-diamante: #AB6774;
}
```

## 5. Anti-padrões

- **Animação decorativa sem função.** Toda animação deve responder a uma ação ou comunicar um estado.
- **Ranking sem rede de proteção emocional.** Sempre mostrar progresso individual além da competição.
- **Painel-admin-template genérico.** Sidebar cinza + cards brancos é o "look" padrão — pelo menos a paleta e os badges devem ter identidade própria.
- **Fontes do sistema sem fallback.** Sempre incluir a cadeia completa: `'Cormorant Garamond', Georgia, serif`.
