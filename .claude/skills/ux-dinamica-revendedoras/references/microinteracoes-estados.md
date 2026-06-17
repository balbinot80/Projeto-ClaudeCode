# Microinterações e estados — toast, contador animado, skeleton, empty state

## 1. Fontes Aureum via Google Fonts (injetar UMA VEZ por página)

```python
AU_FONTS = """
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,400;0,600;1,400&family=Jost:wght@300;400;600&display=swap" rel="stylesheet">
"""
```

- **Cormorant Garamond** → equivalente de Argue Regular (display serif elegante)
- **Jost** → equivalente de Gotham Light (geométrica, clean)

## 2. Contador animado em KPIs

Injetar no início da página e chamar `animarContadores()` depois dos cards estarem no DOM:

```html
<script>
function animarContadores() {
  document.querySelectorAll('[data-contador]').forEach(el => {
    const final = parseFloat(el.dataset.contador);
    const prefixo = el.dataset.prefixo || '';
    const sufixo = el.dataset.sufixo || '';
    const dur = 900;
    const inicio = performance.now();
    function step(agora) {
      const p = Math.min(1, (agora - inicio) / dur);
      const eased = 1 - Math.pow(1 - p, 3);
      const val = Math.round(eased * final);
      el.textContent = prefixo + val.toLocaleString('pt-BR') + sufixo;
      if (p < 1) requestAnimationFrame(step);
    }
    requestAnimationFrame(step);
  });
}
// Streamlit re-renderiza o DOM após cada rerun, então executar com delay pequeno
setTimeout(animarContadores, 100);
</script>
```

Uso no HTML do card:
```html
<p class="au-kpi-value" data-contador="48750" data-prefixo="R$ ">R$ 0</p>
```

## 3. Empty state com voz da Aureum

```python
def empty_state(titulo: str, texto: str, icone: str = "✦") -> str:
    return f"""
    <div style="text-align:center;padding:40px 20px;color:#AB6774">
      <div style="font-size:28px;margin-bottom:10px;opacity:.6">{icone}</div>
      <p style="font-family:'Cormorant Garamond',Georgia,serif;font-size:18px;
               font-weight:600;color:#2A1A1F;margin:0 0 6px">{titulo}</p>
      <p style="font-family:'Jost',sans-serif;font-size:12px;font-weight:300;
               color:#7A6068;margin:0">{texto}</p>
    </div>
    """
```

Exemplos de textos com a voz da Aureum:
- Ranking vazio no início do mês: `("Ranking em formação", "O mês começou — as vendas do mês ainda não foram contabilizadas.")`
- Funil sem leads: `("Nenhuma Preciosa neste estágio", "Hora de captar — arraste a primeira lead pra cá quando aparecer.")`
- Supervisora sem revendedoras: `("Nenhuma revendedora neste filtro", "Tente ajustar o filtro de supervisora.")`

## 4. Skeleton screen (estado de carregamento)

```css
.au-skeleton {
  background: linear-gradient(90deg, #ECE7DD 25%, #F5F0E8 50%, #ECE7DD 75%);
  background-size: 200% 100%;
  animation: au-shimmer 1.4s ease-in-out infinite;
  border-radius: 8px;
}
@keyframes au-shimmer {
  0% { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}
```

Skeleton de um card de revendedora:
```html
<div style="display:flex;align-items:center;gap:12px;padding:14px;background:#fff;border-radius:12px;margin-bottom:8px">
  <div class="au-skeleton" style="width:42px;height:42px;border-radius:50%;flex-shrink:0"></div>
  <div style="flex:1">
    <div class="au-skeleton" style="height:13px;width:55%;margin-bottom:7px"></div>
    <div class="au-skeleton" style="height:10px;width:35%"></div>
  </div>
  <div class="au-skeleton" style="height:16px;width:70px"></div>
</div>
```

Em Streamlit, mostrar skeleton enquanto dados carregam:
```python
placeholder = st.empty()
with placeholder.container():
    st.markdown(skeleton_html, unsafe_allow_html=True)
dados = carregar_dados()         # chamada à API
placeholder.empty()              # remove skeleton
renderizar_com_dados(dados)      # mostra conteúdo real
```

## 5. Toast no Streamlit

O Streamlit tem `st.toast()` nativo (versão ≥ 1.28). Use-o:

```python
st.toast("✦ Agendamento salvo com sucesso!", icon="✅")
st.toast(f"{nome} movida para Ouro 🥇")
```

Para versões mais antigas, usar `st.success()` posicionado próximo ao botão de ação. Sempre escrever a mensagem com a voz da Aureum, não com texto genérico de sistema.

## 6. Hover e transições CSS (Streamlit)

Streamlit não expõe CSS de hover via Python, mas o CSS injetado via `st.markdown` funciona normalmente em HTML personalizado. A regra é sempre incluir `transition: transform .15s ease, box-shadow .15s ease` em todo elemento clicável/interativo. Isso sozinho muda a percepção de "sistema morto" para "sistema responsivo".
