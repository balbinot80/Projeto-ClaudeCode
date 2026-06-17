Quando este comando for invocado, aplique a identidade visual da Aureum Joias e os padrões de UX da skill em `.claude/skills/ux-dinamica-revendedoras/SKILL.md`.

**O que fazer ao receber `/aureum-ui`:**

1. Leia `.claude/skills/ux-dinamica-revendedoras/SKILL.md` e os arquivos em `references/`.
2. Leia o arquivo da página ou componente que o usuário quer redesenhar (ou o que foi indicado no contexto da conversa).
3. Aplique a identidade visual Aureum:
   - Rosa `#AB6774`, gold `#C4985A`, creme `#FAF7F4`
   - Fontes: Cormorant Garamond (títulos/valores) + Jost (labels/meta-info) via Google Fonts
   - Badges de tier: Pérola `#EDE8E3`, Ouro `#C4985A`, Diamante `#AB6774`
4. Substitua `st.dataframe` / `st.metric` por HTML cards com hover e transição CSS onde o contexto for lista de revendedoras, ranking ou KPIs de destaque.
5. Crie a versão redesenhada em um arquivo paralelo (`*_preview.py`) — não sobrescreva o original.
6. Adicione a rota `"🎨 Preview UI"` no sidebar do admin em `app.py` se ainda não existir.

**Não faça:** não altere lógica de dados, não mude regras de competência, não toque em arquivos de `src/logic/` ou `src/api/`.

**Referências rápidas:**
- Brand theme: `src/theme/aureum.py`
- Kanban: `.claude/skills/ux-dinamica-revendedoras/references/pipeline-kanban.md`
- Ranking: `.claude/skills/ux-dinamica-revendedoras/references/leaderboard-gamificacao.md`
- Microinterações: `.claude/skills/ux-dinamica-revendedoras/references/microinteracoes-estados.md`
