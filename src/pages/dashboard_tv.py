import base64
from datetime import date
from pathlib import Path

import streamlit as st

_R = lambda v: f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
_MESES_PT  = ["Janeiro","Fevereiro","Março","Abril","Maio","Junho",
              "Julho","Agosto","Setembro","Outubro","Novembro","Dezembro"]
_MESES_ABR = ["Jan","Fev","Mar","Abr","Mai","Jun","Jul","Ago","Set","Out","Nov","Dez"]
_SLIDES    = ["🛍️ Vendas", "🏆 Premiações", "📊 Desempenho"]
_N         = len(_SLIDES)


# ── Utilitários ────────────────────────────────────────────────────────────────

def _logo_b64(filename: str):
    p = Path("assets") / filename
    if not p.exists():
        return None
    try:
        from PIL import Image
        import io
        img = Image.open(p).convert("RGBA")
        bbox = img.getbbox()
        if bbox:
            img = img.crop(bbox)
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)
        return base64.b64encode(buf.read()).decode()
    except Exception:
        try:
            return base64.b64encode(p.read_bytes()).decode()
        except Exception:
            return None


def _css():
    st.markdown("""
    <style>
    [data-testid="stSidebar"],
    [data-testid="stSidebarNav"],
    header[data-testid="stHeader"] { display: none !important; }

    .stMainBlockContainer, .block-container {
        max-width: 100% !important;
        padding: 0.5rem 1.5rem !important;
    }

    [data-testid="stMetricValue"] {
        font-size: 1.75rem !important;
        font-weight: 700 !important;
    }
    [data-testid="stMetricLabel"] { font-size: 0.9rem !important; }
    </style>
    """, unsafe_allow_html=True)


def _header_bar(titulo: str, subtitulo: str = "", ultima: str = ""):
    logo_b64 = _logo_b64("Logo branco.png") or _logo_b64("Logo rosa.png")
    logo_html = (
        f'<img src="data:image/png;base64,{logo_b64}" '
        f'style="height:42px;filter:drop-shadow(0 1px 3px rgba(0,0,0,0.2))">'
    ) if logo_b64 else ""

    sub_h = (
        f'<div style="font-size:0.9em;color:rgba(255,255,255,0.82);margin-top:2px">{subtitulo}</div>'
    ) if subtitulo else ""
    upd_h = (
        f'<div style="font-size:0.75em;color:rgba(255,255,255,0.6);margin-top:4px">🕐 {ultima}</div>'
    ) if ultima else ""

    st.markdown(
        f'<div style="display:flex;align-items:center;justify-content:space-between;'
        f'padding:10px 22px;background:linear-gradient(135deg,#AB6776 0%,#7a3c50 100%);'
        f'border-radius:10px;margin-bottom:12px;box-shadow:0 2px 8px rgba(0,0,0,0.18)">'
        f'  <div>{logo_html}</div>'
        f'  <div style="text-align:center">'
        f'    <div style="font-size:1.7em;font-weight:800;color:white;letter-spacing:3px">{titulo}</div>'
        f'    {sub_h}'
        f'  </div>'
        f'  <div style="text-align:right">'
        f'    {logo_html}'
        f'    {upd_h}'
        f'  </div>'
        f'</div>',
        unsafe_allow_html=True,
    )


def _sep():
    st.markdown(
        '<hr style="margin:5px 0 8px;border:none;border-top:2px solid #f1f5f9">',
        unsafe_allow_html=True,
    )


def _nav(slide_idx: int):
    paused = st.session_state.get("tv_paused", False)
    c_prev, c_dots, c_pause, c_next = st.columns([1, 7, 1, 1])
    with c_prev:
        if st.button("◀", key="tv_prev", use_container_width=True):
            st.session_state.tv_slide = (slide_idx - 1) % _N
            st.rerun()
    with c_dots:
        partes = []
        for i, nome in enumerate(_SLIDES):
            if i == slide_idx:
                partes.append(
                    f'<span style="color:#AB6776;font-weight:700;font-size:1.1em;margin:0 14px">'
                    f'● {nome}</span>'
                )
            else:
                partes.append(
                    f'<span style="color:#cbd5e1;font-size:0.9em;margin:0 14px">'
                    f'○ {nome}</span>'
                )
        st.markdown(
            f'<div style="text-align:center;padding:5px 0">{"".join(partes)}</div>',
            unsafe_allow_html=True,
        )
    with c_pause:
        label = "▶ Continuar" if paused else "⏸ Pausar"
        if st.button(label, key="tv_pause", use_container_width=True):
            st.session_state.tv_paused = not paused
            st.rerun()
    with c_next:
        if st.button("▶", key="tv_next", use_container_width=True):
            st.session_state.tv_slide = (slide_idx + 1) % _N
            st.rerun()


# ── Slide 0: Vendas ────────────────────────────────────────────────────────────

def _nivel_por_rev(todos_pedidos: list, mes: int, ano: int) -> dict:
    """Retorna {fk_revendedor_id: ícone_do_nível} com base nos pedidos do mês."""
    from src.logic.niveis import nivel_por_pecas, _qtd_original, ICONE_NIVEL
    from src.logic.revendedoras import parse_date

    nivel_map = {}
    for p in todos_pedidos:
        rid = p.get("fk_revendedor_id")
        if not rid:
            continue
        status = p.get("status", "")
        if status == "Baixado":
            d = parse_date(p.get("data_baixa"))
            if not (d and d.month == mes and d.year == ano):
                continue
        elif status == "Aberto":
            d = parse_date(p.get("data_acerto"))
            if not (d and d.month == mes and d.year == ano):
                continue
        else:
            continue
        nivel = nivel_por_pecas(_qtd_original(p))
        if nivel != "Sem nível":
            nivel_map[rid] = ICONE_NIVEL.get(nivel, "")
    return nivel_map


def _slide_vendas(todos_pedidos: list, hoje: date, ultima: str):
    from src.logic.revendedoras import calcular_competencia
    from src.logic.premiacoes import calcular_ranking, load_premiacoes

    mes, ano = hoje.month, hoje.year
    _header_bar("🛍️ VENDAS", f"{_MESES_PT[mes-1]} de {ano}", ultima)

    df_res, _ = calcular_competencia(todos_pedidos, mes, ano)

    n_revs   = len(df_res) if not df_res.empty else 0
    tot_vend = df_res["Total"].sum() if not df_res.empty else 0.0
    tot_bx   = df_res["Baixado"].sum() if not df_res.empty else 0.0
    tot_pb   = df_res["Pré-baixa"].sum() if not df_res.empty else 0.0
    ticket   = tot_vend / n_revs if n_revs > 0 else 0.0
    n_risco  = 0
    if not df_res.empty and "Risco" in df_res.columns:
        n_risco = int(df_res["Risco"].isin(["🔴 Sem vendas", "🟡 Abaixo do mínimo"]).sum())

    c1, c2, c3, c4, c5, c6 = st.columns(6)
    c1.metric("Revendedoras", n_revs)
    c2.metric("Total vendido", _R(tot_vend))
    c3.metric("↓ Baixados", _R(tot_bx))
    c4.metric("↓ Pré-baixa", _R(tot_pb))
    c5.metric("Ticket médio", _R(ticket))
    c6.metric("⚠️ Em risco", n_risco)

    _sep()

    prems   = load_premiacoes()
    mes_key = f"{mes:02d}/{ano}"
    meta    = prems.get(mes_key, {}).get("meta", 0.0)
    ranking = calcular_ranking(todos_pedidos, mes, ano, meta)[:30]

    # Mapa de nível para cada revendedora
    nivel_map = _nivel_por_rev(todos_pedidos, mes, ano)

    st.markdown("**🏅 Top 30 do mês** — baixas + pré-baixa")

    col1, col2, col3 = st.columns(3)
    cols30 = [col1, col2, col3]

    for i, r in enumerate(ranking):
        col = cols30[i // 10]
        pos   = i + 1
        medal = "🥇" if pos == 1 else "🥈" if pos == 2 else "🥉" if pos == 3 else f"{pos}."
        bg    = "#fef9c3" if pos <= 3 else ("#f8fafc" if i % 2 == 0 else "white")
        icone = nivel_map.get(r["id"], "")
        col.markdown(
            f'<div style="display:flex;justify-content:space-between;align-items:center;'
            f'padding:3px 8px;border-radius:4px;font-size:0.88em;background:{bg};margin-bottom:2px">'
            f'<span style="overflow:hidden;text-overflow:ellipsis;white-space:nowrap;max-width:72%">'
            f'{medal} {r["Nome"]} {icone}</span>'
            f'<span style="font-weight:700;color:#1d4ed8;white-space:nowrap">{_R(r["Total"])}</span>'
            f'</div>',
            unsafe_allow_html=True,
        )


# ── Slide 1: Premiações ────────────────────────────────────────────────────────

def _slide_premiacoes(todos_pedidos: list, hoje: date, ultima: str):
    from src.logic.premiacoes import calcular_ranking, load_premiacoes, verificar_colar

    mes, ano = hoje.month, hoje.year
    _header_bar("🏆 PREMIAÇÕES", f"{_MESES_PT[mes-1]} de {ano}", ultima)

    prems   = load_premiacoes()
    mes_key = f"{mes:02d}/{ano}"
    cfg     = prems.get(mes_key, {})
    meta    = cfg.get("meta", 0.0)
    premio  = cfg.get("premio", "")

    ranking    = calcular_ranking(todos_pedidos, mes, ano, meta)
    ganhadoras = [r for r in ranking if r.get("Categoria") == "ganhadora"]
    potenciais = [r for r in ranking if r.get("Categoria") == "potencial"]
    proximas   = [r for r in ranking if r.get("Categoria") == "proxima"]

    try:
        colar = verificar_colar(todos_pedidos, mes, ano)
    except Exception:
        colar = []

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("🎯 Meta do mês", _R(meta) if meta else "—")
    c2.metric("🎁 Prêmio", premio if premio else "—")
    c3.metric("✅ Ganhadoras", len(ganhadoras))
    c4.metric("🎯 Potenciais", len(potenciais))

    _sep()

    col_g, col_p, col_pr, col_c = st.columns(4)

    def _item_html(icone, nome, detalhe, bg):
        return (
            f'<div style="display:flex;justify-content:space-between;align-items:center;'
            f'padding:4px 10px;background:{bg};border-radius:5px;font-size:0.87em;margin-bottom:3px">'
            f'<span style="overflow:hidden;text-overflow:ellipsis;white-space:nowrap;max-width:65%">'
            f'{icone} <b>{nome}</b></span>'
            f'<span style="white-space:nowrap;font-weight:600;font-size:0.9em">{detalhe}</span>'
            f'</div>'
        )

    with col_g:
        st.markdown("**✅ Ganhadoras**")
        if ganhadoras:
            html = "".join(
                _item_html(
                    "🥇" if i == 0 else "✅",
                    r["Nome"],
                    _R(r.get("Baixado", 0)),
                    "#d1fae5",
                )
                for i, r in enumerate(ganhadoras)
            )
            st.markdown(html, unsafe_allow_html=True)
        else:
            st.caption("Nenhuma ainda")

    with col_p:
        st.markdown("**🎯 Potenciais**")
        if potenciais:
            html = "".join(
                _item_html(
                    "🎯",
                    r["Nome"],
                    f'falta {_R(r.get("Falta", 0))}',
                    "#fef9c3",
                )
                for r in potenciais
            )
            st.markdown(html, unsafe_allow_html=True)
        else:
            st.caption("Nenhuma")

    with col_pr:
        st.markdown("**🔜 Próximas**")
        if proximas:
            html = "".join(
                _item_html(
                    "🔜",
                    r["Nome"],
                    _R(r.get("Pré-baixa", r.get("Total", 0))),
                    "#eff6ff",
                )
                for r in proximas
            )
            st.markdown(html, unsafe_allow_html=True)
        else:
            st.caption("Nenhuma")

    with col_c:
        st.markdown("**💎 Colar**")
        if colar:
            html = "".join(
                _item_html(
                    "💎",
                    r["Nome"],
                    _R(r.get("Pré-baixa", r.get("Total", 0))),
                    "#fdf4ff",
                )
                for r in colar
            )
            st.markdown(html, unsafe_allow_html=True)
        else:
            st.caption("Nenhuma")


# ── Slide 2: Desempenho ────────────────────────────────────────────────────────

def _calcular_desemp_mes(todos_pedidos: list, mes: int, ano: int) -> list:
    from src.logic.niveis import nivel_por_pecas, _qtd_original
    from src.logic.revendedoras import parse_date
    rows = []
    for p in todos_pedidos:
        if p.get("status") != "Baixado":
            continue
        d = parse_date(p.get("data_baixa"))
        if not (d and d.month == mes and d.year == ano):
            continue
        vm = float(p.get("valor_total_antes_baixa") or 0)
        vb = float(p.get("valor_total") or 0)
        if vm == 0:
            continue
        nivel = nivel_por_pecas(_qtd_original(p))
        rows.append({"Nível": nivel, "Maleta": vm, "Baixa": vb, "Pct": vb / vm * 100})
    return rows


def _celula_desemp(rows: list, negrito: bool = False) -> str:
    if not rows:
        return '<span style="color:#cbd5e1">—</span>'
    vm  = sum(r["Maleta"] for r in rows)
    vb  = sum(r["Baixa"]  for r in rows)
    pct = vb / vm * 100 if vm > 0 else 0.0
    n   = len(rows)
    cor = "#16a34a" if pct >= 20 else "#ca8a04" if pct >= 15 else "#dc2626"
    fw  = "800" if negrito else "600"
    return (
        f'<span style="color:{cor};font-weight:{fw}">{pct:.1f}%</span>'
        f' <span style="color:#94a3b8;font-size:0.82em">({n})</span>'
    )


def _slide_desempenho(todos_pedidos: list, hoje: date, ultima: str):
    from src.logic.niveis import ICONE_NIVEL

    mes, ano = hoje.month, hoje.year
    _header_bar("📊 DESEMPENHO", f"{_MESES_PT[mes-1]} de {ano}", ultima)

    meses_range = list(range(1, mes + 1))
    NIVEIS_ORD  = ["Diamante", "Ouro", "Pérola"]

    dados = {m: _calcular_desemp_mes(todos_pedidos, m, ano) for m in meses_range}

    rows_atual = dados[mes]
    vm_t  = sum(r["Maleta"] for r in rows_atual)
    vb_t  = sum(r["Baixa"]  for r in rows_atual)
    pct_g = vb_t / vm_t * 100 if vm_t > 0 else 0.0

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Pedidos baixados", len(rows_atual))
    c2.metric("Total maleta", _R(vm_t))
    c3.metric("Total baixado", _R(vb_t))
    c4.metric("Desempenho geral", f"{pct_g:.1f}%")

    _sep()
    st.markdown("**📅 Desempenho anual por nível**")

    _HS = "font-size:0.72em;font-weight:700;color:#64748b;text-transform:uppercase;letter-spacing:0.4px"
    _PC = [2.0] + [1.0] * len(meses_range)

    hcols = st.columns(_PC)
    hcols[0].markdown(f'<span style="{_HS}">Nível</span>', unsafe_allow_html=True)
    for i, m in enumerate(meses_range):
        hcols[i + 1].markdown(f'<span style="{_HS}">{_MESES_ABR[m - 1]}</span>', unsafe_allow_html=True)
    st.markdown('<hr style="margin:2px 0 4px;border:none;border-top:2px solid #e2e8f0">', unsafe_allow_html=True)

    for nivel in NIVEIS_ORD:
        rcols = st.columns(_PC)
        icone = ICONE_NIVEL.get(nivel, "")
        rcols[0].markdown(f'<span style="font-size:0.88em">{icone} {nivel}</span>', unsafe_allow_html=True)
        for i, m in enumerate(meses_range):
            sub = [r for r in dados[m] if r["Nível"] == nivel]
            rcols[i + 1].markdown(_celula_desemp(sub), unsafe_allow_html=True)
        st.markdown('<hr style="margin:2px 0;border:none;border-top:1px solid #e2e8f0">', unsafe_allow_html=True)

    tcols = st.columns(_PC)
    tcols[0].markdown('<span style="font-size:0.88em;font-weight:700">🔢 Total</span>', unsafe_allow_html=True)
    for i, m in enumerate(meses_range):
        tcols[i + 1].markdown(_celula_desemp(dados[m], negrito=True), unsafe_allow_html=True)


# ── render() ───────────────────────────────────────────────────────────────────

def render():
    _css()

    # Auto-refresh a cada 60 s
    try:
        from streamlit_autorefresh import st_autorefresh
        count = st_autorefresh(interval=60_000, key="tv_autorefresh")
    except ImportError:
        count = 0

    # Inicializa controle de slide
    if "tv_slide" not in st.session_state:
        st.session_state.tv_slide = 0
    if "tv_count_prev" not in st.session_state:
        st.session_state.tv_count_prev = count

    # Avança automaticamente quando o autorefresh dispara (exceto se pausado)
    if count != st.session_state.tv_count_prev:
        if not st.session_state.get("tv_paused", False):
            st.session_state.tv_slide = (st.session_state.tv_slide + 1) % _N
        st.session_state.tv_count_prev = count

    slide_idx = st.session_state.tv_slide

    # Carrega dados comuns (cacheados por 1 h)
    from src.api.jueri_client import _get_lista_pedidos, _get_ultima_atualizacao_pedidos
    hoje   = date.today()
    ultima = _get_ultima_atualizacao_pedidos()

    try:
        todos_pedidos = _get_lista_pedidos()
    except Exception as e:
        st.error(f"Erro ao carregar dados da API: {e}")
        return

    # Renderiza slide atual
    if slide_idx == 0:
        _slide_vendas(todos_pedidos, hoje, ultima)
    elif slide_idx == 1:
        _slide_premiacoes(todos_pedidos, hoje, ultima)
    else:
        _slide_desempenho(todos_pedidos, hoje, ultima)

    # Barra de navegação inferior
    st.markdown('<hr style="margin:8px 0 4px;border:none;border-top:1px solid #f1f5f9">', unsafe_allow_html=True)
    _nav(slide_idx)
