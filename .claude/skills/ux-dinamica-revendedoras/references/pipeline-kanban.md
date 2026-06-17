# Pipeline Kanban — implementação completa

Snippet vanilla (HTML + CSS + JS), sem biblioteca externa, usando a API nativa de drag-and-drop do navegador. Em Streamlit, drag-and-drop nativo não está disponível — use `st.columns` para as colunas e `st.selectbox` para mover cards entre colunas. O CSS abaixo funciona via `st.markdown(..., unsafe_allow_html=True)`.

## CSS (injetar via st.markdown no início da página)

```css
.kanban-board {
  display: flex; gap: 16px; overflow-x: auto; padding: 8px 4px 16px;
}
.kanban-coluna {
  background: #FAF7F4; border-radius: 14px;
  min-width: 220px; flex: 1 0 220px; padding: 12px;
}
.kanban-coluna h3 {
  font-family: 'Jost', sans-serif; font-size: 11px; font-weight: 600;
  text-transform: uppercase; letter-spacing: .08em; color: #7A6068;
  display: flex; justify-content: space-between; margin: 0 0 10px;
}
.kanban-contagem {
  background: rgba(171,103,116,.12); border-radius: 999px;
  padding: 1px 8px; font-size: 10px;
}
.kanban-lista { display: flex; flex-direction: column; gap: 8px; min-height: 60px; }
.kanban-card {
  background: #fff; border-radius: 10px; padding: 10px 12px;
  box-shadow: 0 1px 2px rgba(171,103,116,.08);
  border: 1px solid rgba(171,103,116,.1);
  transition: transform .15s ease, box-shadow .15s ease;
}
.kanban-card:hover {
  transform: translateY(-2px); box-shadow: 0 6px 14px rgba(171,103,116,.15);
}
.kanban-card .nome { font-family: 'Jost',sans-serif; font-weight: 600; font-size: 13px; color: #2A1A1F; }
.kanban-card .meta { font-family: 'Jost',sans-serif; font-size: 11px; color: #7A6068; margin-top: 2px; }
.au-badge-perola { background: #EDE8E3; color: #6b5d4f; }
.au-badge-ouro { background: #C4985A; color: #fff; }
.au-badge-diamante { background: #AB6774; color: #fff; }
.au-badge-sem { background: #EEE; color: #999; }
.au-badge {
  display: inline-block; font-family: 'Jost',sans-serif; font-size: 10px; font-weight: 600;
  letter-spacing: .06em; text-transform: uppercase; padding: 2px 7px; border-radius: 999px; margin-top: 6px;
}
```

## Estrutura em Streamlit

```python
import streamlit as st

def kanban_captacao(revendedoras: list):
    COLUNAS = ["lead", "contato", "kit_enviado", "ativa", "risco"]
    LABELS = {"lead": "Lead", "contato": "Contato feito", "kit_enviado": "Kit enviado",
              "ativa": "Ativa", "risco": "Em risco"}
    
    cols = st.columns(len(COLUNAS))
    for col, status in zip(cols, COLUNAS):
        grupo = [r for r in revendedoras if r.get("status_captacao") == status]
        with col:
            st.markdown(f"""
            <div class="kanban-coluna">
                <h3>{LABELS[status]} <span class="kanban-contagem">{len(grupo)}</span></h3>
                <div class="kanban-lista">
                {"".join(_card_html(r) for r in grupo) or '<div style="color:#bbb;font-size:11px;text-align:center;padding:12px">—</div>'}
                </div>
            </div>
            """, unsafe_allow_html=True)

def _card_html(r):
    tier = r.get("tier", "sem").lower()
    nome = r.get("nome", "—")
    dias = r.get("dias_nesta_etapa", 0)
    return f"""
    <div class="kanban-card">
        <div class="nome">{nome}</div>
        <div class="meta">{"Hoje" if dias == 0 else f"{dias}d nesta etapa"}</div>
        <span class="au-badge au-badge-{tier}">{tier.capitalize()}</span>
    </div>
    """
```

## Mover card entre colunas (sem drag-and-drop)

```python
# Em um expander ou modal abaixo do board:
with st.expander("Mover revendedora"):
    nomes = [r["nome"] for r in revendedoras]
    escolhida = st.selectbox("Revendedora", nomes)
    novo_status = st.selectbox("Para", list(LABELS.values()))
    if st.button("Mover", type="primary"):
        # Atualizar na fonte de dados (API, banco, etc.)
        st.success(f"{escolhida} movida para {novo_status}")
        st.rerun()
```

## Se o projeto for React

Use `@dnd-kit/core` (moderno) ou `@hello-pangea/dnd` (fork do react-beautiful-dnd). A estrutura conceitual é a mesma: `DndContext` envolvendo as colunas, cada coluna é `useDroppable`, cada card é `useDraggable`, e o callback `onDragEnd` atualiza o estado e dispara a API.
