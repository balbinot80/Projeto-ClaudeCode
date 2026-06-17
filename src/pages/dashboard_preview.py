"""
Preview: Dashboard com identidade visual Aureum Joias.
Versão paralela para avaliação — não altera o Dashboard principal.
"""
import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from src.theme.aureum import inject, kpi_html, rev_card_html, empty_state

_R = lambda v: f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
_ini = lambda n: "".join(w[0].upper() for w in n.split()[:2]) if n else "—"
_pnome = lambda n: (n.split()[0] + (" " + n.split()[-1] if len(n.split()) > 1 else "")) if n else "—"


def _podio_html(top3: list) -> str:
    def lugar(dados, ordem, cls_extra=""):
        nome, val = dados
        return f"""
        <div class="au-podio-lugar {cls_extra}" style="order:{ordem}">
          {'<div class="au-coroa">✦</div>' if cls_extra else ''}
          <div class="au-podio-avatar">{_ini(nome)}</div>
          <div class="au-podio-nome">{_pnome(nome)}</div>
          <div class="au-podio-valor">{_R(val)}</div>
          <div class="au-podio-pos">{ordem}º lugar</div>
        </div>
        """

    ordem_visual = [(top3[1], 1, "au-podio-2"), (top3[0], 2, "au-podio-1"), (top3[2], 3, "au-podio-3")]
    return f"""
    <div class="au-podio">
      {"".join(lugar(d, o, c) for d, o, c in ordem_visual)}
    </div>
    """


def _rank_item_html(pos: int, nome: str, vendas: float, meta: float, label_meta: str) -> str:
    pct = min(100, round(vendas / max(meta, 0.01) * 100))
    falta = max(0, meta - vendas)
    txt = f"faltam {_R(falta)} p/ {label_meta}" if falta > 0 else f"✦ Meta {label_meta} atingida"
    return f"""
    <div class="au-rank-item">
      <span style="font-family:'Jost',sans-serif;font-size:11px;font-weight:600;
                   color:#AB6774;width:22px;flex-shrink:0">{pos}º</span>
      <div style="width:30px;height:30px;border-radius:50%;flex-shrink:0;
                  background:linear-gradient(135deg,#F5EBEC,#C89199);
                  display:flex;align-items:center;justify-content:center;
                  font-family:'Cormorant Garamond',serif;font-size:11px;font-weight:600;color:#AB6774">
        {_ini(nome)}
      </div>
      <div style="flex:1;min-width:0">
        <div style="font-family:'Jost',sans-serif;font-size:12px;font-weight:600;color:#2A1A1F">{_pnome(nome)}</div>
        <div style="display:flex;align-items:center;gap:6px;margin-top:3px">
          <div class="au-barra-wrap"><div class="au-barra-fill" style="width:{pct}%"></div></div>
          <span style="font-family:'Jost',sans-serif;font-size:9px;color:#7A6068;white-space:nowrap">{txt}</span>
        </div>
      </div>
      <div style="font-family:'Cormorant Garamond',serif;font-size:14px;font-weight:600;
                  color:#AB6774;white-space:nowrap">{_R(vendas)}</div>
    </div>
    """


def render():
    inject()

    # ── Header de marca ──────────────────────────────────────────
    st.markdown("""
    <span class="au-preview-tag">Preview — versão paralela</span>
    <div class="au-header">
      <p class="au-header-sub">Sistema de Gestão</p>
      <h1 class="au-header-title">💍 Aureum Joias</h1>
      <p class="au-header-sub" style="margin-top:5px;opacity:.65">Dashboard · Visão Geral</p>
    </div>
    """, unsafe_allow_html=True)

    # ── Carregar dados ────────────────────────────────────────────
    from src.api.jueri_client import get_produtos, get_revendedores, get_pedidos_baixados, get_pedidos_abertos

    try:
        with st.spinner(""):
            produtos = get_produtos(status="1")
            revendedores = get_revendedores()
            pedidos_abertos = get_pedidos_abertos()
            baixados = get_pedidos_baixados()
    except Exception as e:
        st.error(f"Erro ao carregar dados: {e}")
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

    # ── KPIs ──────────────────────────────────────────────────────
    try:
        qtds = pd.to_numeric(
            pd.DataFrame([{"q": p.get("quantidade", 0)} for p in produtos])["q"], errors="coerce"
        ).fillna(0)
        mins = pd.to_numeric(
            pd.DataFrame([{"m": p.get("estoque_minimo") or 0} for p in produtos])["m"], errors="coerce"
        ).fillna(0)
        criticos = int((qtds < mins).sum())
    except Exception:
        criticos = 0

    ativas = sum(1 for r in revendedores if str(r.get("fk_status_id", "1")) == "1")
    total_30d = sum(float(p.get("valor_total") or 0) for p in baixados_30d)

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown(kpi_html("Produtos Ativos", str(len(produtos))), unsafe_allow_html=True)
    with c2:
        st.markdown(kpi_html("Revendedoras Ativas", str(ativas)), unsafe_allow_html=True)
    with c3:
        st.markdown(kpi_html("Baixados · 30 dias", str(len(baixados_30d))), unsafe_allow_html=True)
    with c4:
        st.markdown(kpi_html("Faturamento · 30 dias", _R(total_30d), alerta=False), unsafe_allow_html=True)

    if criticos > 0:
        st.warning(f"⚠️ {criticos} produto(s) com estoque crítico — acesse **Programação de Compras**.")

    st.markdown("<hr class='au-divider'>", unsafe_allow_html=True)

    # ── Ticket médio + Ranking ────────────────────────────────────
    col_ticket, col_ranking = st.columns(2)

    # Montar dados de ticket por supervisora
    ticket_sup: dict = {}
    contagem_sup: dict = {}
    for p in baixados_30d:
        sup = p.get("supervisor_nome") or "Sem supervisora"
        val = float(p.get("valor_total") or 0)
        ticket_sup[sup] = ticket_sup.get(sup, 0) + val
        contagem_sup[sup] = contagem_sup.get(sup, 0) + 1

    with col_ticket:
        st.markdown("""
        <p class="au-section-title">Ticket Médio</p>
        <p class="au-section-sub">Por supervisora · últimos 30 dias</p>
        """, unsafe_allow_html=True)

        if ticket_sup:
            for sup in sorted(ticket_sup.keys()):
                media = ticket_sup[sup] / contagem_sup[sup] if contagem_sup[sup] else 0
                qtd = contagem_sup[sup]
                total = ticket_sup[sup]
                st.markdown(
                    rev_card_html(sup, f"{qtd} pedido(s) · total {_R(total)}", _R(media)),
                    unsafe_allow_html=True,
                )
        else:
            st.markdown(
                empty_state("Nenhuma venda no período", "Sem pedidos baixados nos últimos 30 dias."),
                unsafe_allow_html=True,
            )

    # Montar ranking por revendedora
    rev_vendas: dict = {}
    for p in baixados_30d:
        rid = p.get("fk_revendedor_id")
        if not rid:
            continue
        comp = p.get("comprador") or {}
        nome = comp.get("nome") or f"Rev {rid}"
        val = float(p.get("valor_total") or 0)
        rev_vendas[nome] = rev_vendas.get(nome, 0) + val

    ranking = sorted(rev_vendas.items(), key=lambda x: -x[1])[:10]

    with col_ranking:
        st.markdown("""
        <p class="au-section-title">Top Revendedoras</p>
        <p class="au-section-sub">Por faturamento · últimos 30 dias</p>
        """, unsafe_allow_html=True)

        if len(ranking) >= 3:
            st.markdown(_podio_html(ranking[:3]), unsafe_allow_html=True)
            st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)
            meta_prox = 2500.0
            for i, (nome, val) in enumerate(ranking[3:], start=4):
                st.markdown(
                    _rank_item_html(i, nome, val, meta_prox, "Diamante"),
                    unsafe_allow_html=True,
                )
        elif ranking:
            for i, (nome, val) in enumerate(ranking, start=1):
                st.markdown(
                    rev_card_html(nome, f"{i}º lugar", _R(val)),
                    unsafe_allow_html=True,
                )
        else:
            st.markdown(
                empty_state(
                    "Ranking em formação",
                    "Nenhuma venda registrada nos últimos 30 dias.",
                ),
                unsafe_allow_html=True,
            )

    # ── Rodapé de preview ─────────────────────────────────────────
    st.markdown("<hr class='au-divider'>", unsafe_allow_html=True)
    st.markdown(
        '<p style="font-family:\'Jost\',sans-serif;font-size:10px;color:#7A6068;text-align:center">'
        "🎨 Preview UI — versão paralela para avaliação. O Dashboard principal não foi alterado."
        "</p>",
        unsafe_allow_html=True,
    )
