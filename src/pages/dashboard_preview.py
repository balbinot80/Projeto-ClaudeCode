"""
Preview: Dashboard com identidade visual Aureum Joias.
Versão paralela para avaliação — não altera o Dashboard principal.
"""
import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from src.theme.aureum import inject, kpi_html, rev_card_html, empty_state

_R     = lambda v: "R$ " + f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
_ini   = lambda n: "".join(w[0].upper() for w in n.split()[:2]) if n else "—"
_pnome = lambda n: (n.split()[0] + (" " + n.split()[-1] if len(n.split()) > 1 else "")) if n else "—"


# ── Pódio: um card por lugar, renderizado via st.columns ──────────────────────

def _card_lugar(col, dados, pos_label: str, destaque: bool = False):
    """Renderiza um card de pódio dentro de `col` (st.column)."""
    nome, val = dados
    ini       = _ini(nome)
    nome_curto = _pnome(nome)
    valor_str  = _R(val)

    pad_top   = "22px" if destaque else "14px"
    av_size   = "52px" if destaque else "40px"
    av_fs     = "19px" if destaque else "14px"
    av_border = ";border:2px solid #C4985A" if destaque else ""
    pos_color = "#C4985A" if destaque else "#7A6068"
    shadow    = "0 6px 20px rgba(171,103,116,.18)" if destaque else "0 4px 12px rgba(171,103,116,.08)"
    border    = "2px solid #C4985A" if destaque else "1px solid rgba(171,103,116,.15)"
    margin_t  = "-10px" if destaque else "0"
    crown     = '<div style="font-size:14px;color:#C4985A;margin-bottom:6px">✦</div>' if destaque else ""

    html = (
        '<div style="margin-top:' + margin_t + ';background:#fff;border-radius:14px;'
        'padding:' + pad_top + ' 12px 12px;border:' + border + ';box-shadow:' + shadow + ';text-align:center">'
        + crown
        + '<div style="width:' + av_size + ';height:' + av_size + ';border-radius:50%;'
        'background:linear-gradient(135deg,#F5EBEC,#C89199);'
        'display:flex;align-items:center;justify-content:center;'
        'margin:0 auto 8px;font-family:var(--au-font-body);'
        'font-size:' + av_fs + ';font-weight:600;color:#AB6774' + av_border + '>'
        + ini
        + '</div>'
        '<div style="font-family:var(--au-font-body);font-size:12px;font-weight:600;'
        'color:#2A1A1F;margin-bottom:3px">' + nome_curto + '</div>'
        '<div style="font-family:var(--au-font-display);font-size:14px;font-weight:600;'
        'color:#AB6774;margin-bottom:4px">' + valor_str + '</div>'
        '<div style="font-family:var(--au-font-body);font-size:9px;font-weight:600;'
        'letter-spacing:.06em;color:' + pos_color + '">' + pos_label + '</div>'
        '</div>'
    )
    with col:
        st.markdown(html, unsafe_allow_html=True)


# ── Item de ranking (4º em diante) ───────────────────────────────────────────

def _rank_item_html(pos: int, nome: str, vendas: float, meta: float, label_meta: str) -> str:
    pct   = min(100, round(vendas / max(meta, 0.01) * 100))
    falta = max(0.0, meta - vendas)
    ini   = _ini(nome)
    nome_curto = _pnome(nome)
    valor_str  = _R(vendas)
    txt   = ("faltam " + _R(falta) + " p/ " + label_meta) if falta > 0 else ("✦ Meta " + label_meta + " atingida")
    pct_s = str(pct) + "%"

    return (
        '<div style="display:flex;align-items:center;gap:10px;background:#fff;border-radius:10px;'
        'padding:9px 14px;border:1px solid rgba(171,103,116,.1);margin-bottom:6px">'
        '<span style="font-family:var(--au-font-body);font-size:11px;font-weight:600;'
        'color:#AB6774;width:22px;flex-shrink:0">' + str(pos) + 'º</span>'
        '<div style="width:30px;height:30px;border-radius:50%;flex-shrink:0;'
        'background:linear-gradient(135deg,#F5EBEC,#C89199);'
        'display:flex;align-items:center;justify-content:center;'
        'font-family:var(--au-font-body);font-size:10px;font-weight:600;color:#AB6774">'
        + ini
        + '</div>'
        '<div style="flex:1;min-width:0">'
        '<div style="font-family:var(--au-font-body);font-size:12px;font-weight:600;color:#2A1A1F">' + nome_curto + '</div>'
        '<div style="display:flex;align-items:center;gap:6px;margin-top:3px">'
        '<div style="background:rgba(171,103,116,.1);border-radius:999px;height:4px;overflow:hidden;flex:1">'
        '<div style="height:100%;background:linear-gradient(90deg,#E8D5A3,#C4985A);'
        'border-radius:999px;width:' + pct_s + '"></div>'
        '</div>'
        '<span style="font-family:var(--au-font-body);font-size:9px;color:#7A6068;white-space:nowrap">' + txt + '</span>'
        '</div>'
        '</div>'
        '<div style="font-family:var(--au-font-display);font-size:14px;font-weight:600;'
        'color:#AB6774;white-space:nowrap">' + valor_str + '</div>'
        '</div>'
    )


# ── Render principal ──────────────────────────────────────────────────────────

def render():
    inject()

    # Header de marca
    st.markdown(
        '<span class="au-preview-tag">Preview — versão paralela</span>'
        '<div class="au-header">'
        '<p class="au-header-sub">Sistema de Gestão</p>'
        '<h1 class="au-header-title">💍 Aureum Joias</h1>'
        '<p class="au-header-sub" style="margin-top:5px;opacity:.65">Dashboard · Visão Geral</p>'
        '</div>',
        unsafe_allow_html=True,
    )

    # Carregar dados
    from src.api.jueri_client import get_produtos, get_revendedores, get_pedidos_baixados

    try:
        with st.spinner(""):
            produtos     = get_produtos(status="1")
            revendedores = get_revendedores()
            baixados     = get_pedidos_baixados()
    except Exception as e:
        st.error("Erro ao carregar dados: " + str(e))
        return

    corte_30d = datetime.now() - timedelta(days=30)
    baixados_30d = []
    for p in baixados:
        try:
            ds = (p.get("data_baixa") or p.get("data_criacao") or "2000-01-01")[:10]
            if datetime.fromisoformat(ds) >= corte_30d:
                baixados_30d.append(p)
        except (ValueError, TypeError):
            pass

    # KPIs
    try:
        qtds    = pd.to_numeric(pd.DataFrame([{"q": p.get("quantidade", 0)} for p in produtos])["q"], errors="coerce").fillna(0)
        mins    = pd.to_numeric(pd.DataFrame([{"m": p.get("estoque_minimo") or 0} for p in produtos])["m"], errors="coerce").fillna(0)
        criticos = int((qtds < mins).sum())
    except Exception:
        criticos = 0

    ativas    = sum(1 for r in revendedores if str(r.get("fk_status_id", "1")) == "1")
    total_30d = sum(float(p.get("valor_total") or 0) for p in baixados_30d)

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown(kpi_html("Produtos Ativos", str(len(produtos))), unsafe_allow_html=True)
    with c2:
        st.markdown(kpi_html("Revendedoras Ativas", str(ativas)), unsafe_allow_html=True)
    with c3:
        st.markdown(kpi_html("Baixados · 30 dias", str(len(baixados_30d))), unsafe_allow_html=True)
    with c4:
        st.markdown(kpi_html("Faturamento · 30 dias", _R(total_30d)), unsafe_allow_html=True)

    if criticos > 0:
        st.warning("⚠️ " + str(criticos) + " produto(s) com estoque crítico — acesse **Programação de Compras**.")

    st.markdown('<hr class="au-divider">', unsafe_allow_html=True)

    # ── Colunas: Ticket médio | Top Revendedoras ──────────────────
    col_ticket, col_ranking = st.columns(2)

    # Ticket médio por supervisora
    ticket_sup: dict = {}
    contagem_sup: dict = {}
    for p in baixados_30d:
        sup = p.get("supervisor_nome") or "Sem supervisora"
        val = float(p.get("valor_total") or 0)
        ticket_sup[sup]    = ticket_sup.get(sup, 0) + val
        contagem_sup[sup]  = contagem_sup.get(sup, 0) + 1

    with col_ticket:
        st.markdown(
            '<p class="au-section-title">Ticket Médio</p>'
            '<p class="au-section-sub">Por supervisora · últimos 30 dias</p>',
            unsafe_allow_html=True,
        )
        if ticket_sup:
            for sup in sorted(ticket_sup.keys()):
                media = ticket_sup[sup] / contagem_sup[sup] if contagem_sup[sup] else 0
                meta_txt = str(contagem_sup[sup]) + " pedido(s) · total " + _R(ticket_sup[sup])
                st.markdown(rev_card_html(sup, meta_txt, _R(media)), unsafe_allow_html=True)
        else:
            st.markdown(empty_state("Nenhuma venda no período", "Sem pedidos baixados nos últimos 30 dias."), unsafe_allow_html=True)

    # Ranking por revendedora
    rev_vendas: dict = {}
    for p in baixados_30d:
        rid  = p.get("fk_revendedor_id")
        if not rid:
            continue
        comp = p.get("comprador") or {}
        nome = comp.get("nome") or ("Rev " + str(rid))
        val  = float(p.get("valor_total") or 0)
        rev_vendas[nome] = rev_vendas.get(nome, 0) + val

    ranking = sorted(rev_vendas.items(), key=lambda x: -x[1])[:10]

    with col_ranking:
        st.markdown(
            '<p class="au-section-title">Top Revendedoras</p>'
            '<p class="au-section-sub">Por faturamento · últimos 30 dias</p>',
            unsafe_allow_html=True,
        )

        if len(ranking) >= 3:
            # Pódio: 3 colunas nativas do Streamlit — sem f-string aninhada
            pc2, pc1, pc3 = st.columns([1, 1.2, 1])
            _card_lugar(pc2, ranking[1], "2º LUGAR", destaque=False)
            _card_lugar(pc1, ranking[0], "1º LUGAR", destaque=True)
            _card_lugar(pc3, ranking[2], "3º LUGAR", destaque=False)

            st.markdown('<div style="height:10px"></div>', unsafe_allow_html=True)

            # 4º em diante
            meta_diamante = 2500.0
            for i, (nome, val) in enumerate(ranking[3:], start=4):
                st.markdown(_rank_item_html(i, nome, val, meta_diamante, "Diamante"), unsafe_allow_html=True)

        elif ranking:
            for i, (nome, val) in enumerate(ranking, start=1):
                st.markdown(rev_card_html(nome, str(i) + "º lugar", _R(val)), unsafe_allow_html=True)
        else:
            st.markdown(
                empty_state("Ranking em formação", "Nenhuma venda registrada nos últimos 30 dias."),
                unsafe_allow_html=True,
            )

    # Rodapé
    st.markdown('<hr class="au-divider">', unsafe_allow_html=True)
    st.markdown(
        '<p style="font-family:var(--au-font-body);font-size:10px;color:#7A6068;text-align:center">'
        "🎨 Preview UI — versão paralela para avaliação. O Dashboard principal não foi alterado."
        "</p>",
        unsafe_allow_html=True,
    )
