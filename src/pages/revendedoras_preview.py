"""
Preview: Acompanhamento de Revendedoras com identidade visual Aureum.
Versão paralela para avaliação — não altera a página original.
"""
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import date
from src.api.jueri_client import _get_lista_pedidos
from src.logic.revendedoras import (
    MINIMO_REV,
    meses_disponiveis, calcular_competencia,
    pedidos_abertos_sem_prebaixa, analise_periodo,
)
from src.logic.niveis import (
    MINIMO_VENDAS, NIVEL_SUPERIOR, LIMIAR_SUBIDA, ICONE_NIVEL,
    classificar_revendedoras, alertas_rebaixamento, alertas_subida,
)
from src.theme.aureum import inject, kpi_html, empty_state

# ── Constantes de formatação ──────────────────────────────────────────────────
_R     = lambda v: "R$ " + f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
_ini   = lambda n: "".join(w[0].upper() for w in n.split()[:2]) if n else "—"
_pnome = lambda n: (n.split()[0] + (" " + n.split()[-1] if len(n.split()) > 1 else "")) if n else "—"

_FONT_D = "Georgia,'Cormorant Garamond',serif"
_FONT_B = "Jost,'Helvetica Neue',sans-serif"
_ROSA   = "#AB6774"
_GOLD   = "#C4985A"
_INK    = "#2A1A1F"
_MUTED  = "#7A6068"

# Logo diamante — SVG baseado na identidade visual da Aureum Joias
_DIAMOND_SVG = (
    '<svg viewBox="0 0 44 46" width="44" height="46" style="display:block;flex-shrink:0">'
    # Girdle (linha do cinto — separa coroa de pavilhão)
    '<line x1="4" y1="17" x2="40" y2="17" stroke="#C4985A" stroke-width="1" opacity="0.7"/>'
    # Coroa (topo)
    '<polygon points="22,3 40,17 4,17" fill="rgba(196,152,90,0.18)" stroke="#C4985A" stroke-width="1.4"/>'
    # Pavilhão (base — vai ao culet)
    '<polygon points="4,17 40,17 22,43" fill="rgba(171,103,116,0.13)" stroke="#AB6774" stroke-width="1.4"/>'
    # Facetas da coroa
    '<line x1="22" y1="3" x2="22" y2="17" stroke="#C4985A" stroke-width="0.8" opacity="0.5"/>'
    '<line x1="22" y1="3" x2="13" y2="17" stroke="#C4985A" stroke-width="0.6" opacity="0.35"/>'
    '<line x1="22" y1="3" x2="31" y2="17" stroke="#C4985A" stroke-width="0.6" opacity="0.35"/>'
    # Facetas do pavilhão
    '<line x1="13" y1="17" x2="22" y2="43" stroke="#AB6774" stroke-width="0.6" opacity="0.3"/>'
    '<line x1="31" y1="17" x2="22" y2="43" stroke="#AB6774" stroke-width="0.6" opacity="0.3"/>'
    '</svg>'
)

_CORES_RISCO = {
    "🟢 No ritmo":          "#2ecc71",
    "🟢 OK":                "#2ecc71",
    "🟡 Abaixo do ritmo":  "#f1c40f",
    "🟡 Abaixo do mínimo": "#f39c12",
    "🟠 Abaixo do mínimo": "#e67e22",
    "🔴 Sem vendas":        "#e74c3c",
}

_TIER_STYLE = {
    "Diamante":  {"bg": "#AB6774", "text": "#fff",    "icon": "💎"},
    "Ouro":      {"bg": "#C4985A", "text": "#fff",    "icon": "✦"},
    "Pérola":    {"bg": "#EDE8E3", "text": "#5C4A3A", "icon": "○"},
    "Sem nível": {"bg": "#F0EDEB", "text": "#7A6068", "icon": "—"},
}


# ── Componentes visuais ───────────────────────────────────────────────────────

def _section_title(titulo: str, subtitulo: str = "") -> str:
    sub = (
        '<p style="font-family:' + _FONT_B + ';font-weight:300;font-size:10px;'
        'letter-spacing:.09em;text-transform:uppercase;color:' + _MUTED + ';margin:2px 0 14px">'
        + subtitulo + "</p>"
    ) if subtitulo else '<div style="margin-bottom:14px"></div>'
    return (
        '<p style="font-family:' + _FONT_D + ';font-size:20px;font-weight:400;'
        'letter-spacing:.03em;color:' + _INK + ';margin:0 0 2px">'
        + titulo + "</p>" + sub
    )


def _hr() -> str:
    return '<hr style="border:none;border-top:1px solid rgba(171,103,116,.15);margin:20px 0">'


def _rev_card(row) -> str:
    """Card de revendedora para a lista de competência."""
    nome  = str(row.get("Nome", "—"))
    sup   = str(row.get("Supervisor", "—"))
    total = float(row.get("Total", 0))
    risco = str(row.get("Risco", ""))
    ini   = _ini(nome)
    cor   = _CORES_RISCO.get(risco, "#95a5a6")

    return (
        '<div style="display:flex;align-items:center;gap:10px;background:#fff;'
        'border-radius:10px;padding:10px 14px;'
        'border:1px solid rgba(171,103,116,.1);'
        'border-left:3px solid ' + cor + ';margin-bottom:5px">'
        '<div style="width:34px;height:34px;border-radius:50%;flex-shrink:0;'
        'background:linear-gradient(135deg,#F5EBEC,#C89199);'
        'display:flex;align-items:center;justify-content:center;'
        'font-family:' + _FONT_B + ';font-size:11px;font-weight:600;color:' + _ROSA + '">'
        + ini + '</div>'
        '<div style="flex:1;min-width:0">'
        '<div style="font-family:' + _FONT_B + ';font-size:12px;font-weight:600;color:' + _INK + '">' + nome + '</div>'
        '<div style="font-family:' + _FONT_B + ';font-size:10px;color:' + _MUTED + ';margin-top:1px">' + sup + '</div>'
        '</div>'
        '<div style="text-align:right;flex-shrink:0">'
        '<div style="font-family:' + _FONT_D + ';font-size:14px;font-weight:600;color:' + _ROSA + '">' + _R(total) + '</div>'
        '<div style="font-family:' + _FONT_B + ';font-size:9px;color:' + _MUTED + '">' + risco + '</div>'
        '</div>'
        '</div>'
    )


def _tier_card(nivel: str, qtd: int) -> str:
    s    = _TIER_STYLE.get(nivel, _TIER_STYLE["Sem nível"])
    meta = _R(MINIMO_VENDAS.get(nivel, MINIMO_REV)) if nivel != "Sem nível" else "—"
    return (
        '<div style="background:' + s["bg"] + ';border-radius:14px;padding:16px 14px;text-align:center">'
        '<div style="font-size:20px;margin-bottom:6px">' + s["icon"] + '</div>'
        '<div style="font-family:' + _FONT_B + ';font-size:11px;font-weight:600;'
        'letter-spacing:.06em;text-transform:uppercase;color:' + s["text"] + ';opacity:.8">' + nivel + '</div>'
        '<div style="font-family:' + _FONT_D + ';font-size:30px;font-weight:600;color:' + s["text"] + ';line-height:1.1;margin:4px 0">' + str(qtd) + '</div>'
        '<div style="font-family:' + _FONT_B + ';font-size:9px;color:' + s["text"] + ';opacity:.6">meta ' + meta + '</div>'
        '</div>'
    )


def _alert_card(icon: str, titulo: str, texto: str, cor: str) -> str:
    return (
        '<div style="background:#fff;border-radius:12px;padding:14px 16px;'
        'border-left:4px solid ' + cor + ';'
        'border:1px solid rgba(171,103,116,.1);margin-bottom:8px">'
        '<div style="display:flex;align-items:center;gap:8px;margin-bottom:4px">'
        '<span style="font-size:14px">' + icon + '</span>'
        '<span style="font-family:' + _FONT_B + ';font-size:12px;font-weight:600;color:' + _INK + '">' + titulo + '</span>'
        '</div>'
        '<div style="font-family:' + _FONT_B + ';font-size:11px;color:' + _MUTED + '">' + texto + '</div>'
        '</div>'
    )


# ── Tabs ──────────────────────────────────────────────────────────────────────

def _tab_competencia(df_res: pd.DataFrame, mes_label: str):
    st.markdown(_section_title("Competência · " + mes_label, "Vendas por revendedora no mês"), unsafe_allow_html=True)

    if df_res.empty:
        st.markdown(empty_state("Nenhum dado", "Sem registros para o mês selecionado."), unsafe_allow_html=True)
        return

    supervisoras = sorted(df_res["Supervisor"].unique())

    for sup in supervisoras:
        df_sup    = df_res[df_res["Supervisor"] == sup].copy()
        total_sup = df_sup["Total"].sum()
        n_risco   = int((df_sup["Total"] < MINIMO_REV).sum())
        badge_txt = "  ⚠️ " + str(n_risco) + " em risco" if n_risco else ""

        header = (
            "**" + sup + "**" +
            "  ·  " + str(len(df_sup)) + " revendedoras" +
            "  ·  " + _R(total_sup).replace("R$ ", "R\\$ ") + badge_txt
        )
        with st.expander(header, expanded=(n_risco > 0)):
            for _, row in df_sup.sort_values("Total", ascending=False).iterrows():
                st.markdown(_rev_card(row), unsafe_allow_html=True)

    st.markdown(_hr(), unsafe_allow_html=True)
    st.markdown(
        '<p style="font-family:' + _FONT_D + ';font-size:14px;color:' + _INK + ';font-weight:600">'
        'Total geral · ' + mes_label + ': '
        '<span style="color:' + _ROSA + '">' + _R(df_res["Total"].sum()) + '</span></p>',
        unsafe_allow_html=True,
    )

    # Gráfico com cores da marca
    df_graf = df_res.sort_values("Total", ascending=False).head(30)
    fig = go.Figure()
    fig.add_bar(x=df_graf["Nome"], y=df_graf["Baixado"],   name="Baixado",    marker_color=_ROSA)
    fig.add_bar(x=df_graf["Nome"], y=df_graf["Pré-baixa"], name="Pré-baixa",  marker_color=_GOLD)
    fig.add_hline(y=MINIMO_REV, line_dash="dash", line_color="#e74c3c",
                  annotation_text=f"Mínimo R${MINIMO_REV:.0f}", annotation_position="top right")
    fig.update_layout(
        barmode="stack", title="Top 30 revendedoras — mês selecionado",
        xaxis_tickangle=-45, legend=dict(orientation="h"),
        height=400, margin=dict(b=120),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family=_FONT_B, color=_INK),
    )
    st.plotly_chart(fig, use_container_width=True)

    csv = df_res.drop(columns=["fk_revendedor_id"], errors="ignore").to_csv(index=False).encode("utf-8")
    st.download_button("Exportar CSV", csv, f"competencia_{mes_label.replace('/', '-')}.csv", "text/csv")


def _tab_alertas(df_zero: pd.DataFrame, df_res: pd.DataFrame):
    st.markdown(_section_title("Alertas do mês", "Situações que exigem atenção imediata"), unsafe_allow_html=True)

    col_a, col_b = st.columns(2)

    with col_a:
        st.markdown(
            '<p style="font-family:' + _FONT_B + ';font-size:13px;font-weight:600;color:#e74c3c;margin-bottom:10px">'
            '🔴 Sem pré-baixa — ' + str(len(df_zero)) + ' pedido(s)</p>',
            unsafe_allow_html=True,
        )
        if df_zero.empty:
            st.markdown(
                _alert_card("✦", "Tudo em dia", "Nenhum pedido sem pré-baixa neste mês.", "#2ecc71"),
                unsafe_allow_html=True,
            )
        else:
            for sup in sorted(df_zero["Supervisor"].unique()):
                df_s = df_zero[df_zero["Supervisor"] == sup]
                for _, row in df_s.iterrows():
                    nome = str(row.get("Nome", "—"))
                    val  = row.get("Valor pedido", 0)
                    ac   = str(row.get("Acerto", "—"))
                    st.markdown(
                        _alert_card("🔴", nome,
                                    "Acerto: " + ac + " · Pedido: " + _R(float(val or 0)),
                                    "#e74c3c"),
                        unsafe_allow_html=True,
                    )

    with col_b:
        df_abaixo = df_res[(df_res["Total"] > 0) & (df_res["Total"] < MINIMO_REV)].copy() if not df_res.empty else pd.DataFrame()
        st.markdown(
            '<p style="font-family:' + _FONT_B + ';font-size:13px;font-weight:600;color:#e67e22;margin-bottom:10px">'
            '🟡 Abaixo do mínimo — ' + str(len(df_abaixo)) + ' revendedora(s)</p>',
            unsafe_allow_html=True,
        )
        if df_abaixo.empty:
            st.markdown(
                _alert_card("✦", "Ótimo resultado", "Nenhuma revendedora abaixo do mínimo neste mês.", "#2ecc71"),
                unsafe_allow_html=True,
            )
        else:
            for _, row in df_abaixo.sort_values("Total").iterrows():
                nome  = str(row.get("Nome", "—"))
                total = float(row.get("Total", 0))
                st.markdown(
                    _alert_card("🟡", nome,
                                "Total: " + _R(total) + " · Falta: " + _R(MINIMO_REV - total),
                                "#f39c12"),
                    unsafe_allow_html=True,
                )


def _tab_periodo(todos_pedidos: list, hoje: date):
    st.markdown(_section_title("Pré-baixa por idade do pedido", "Pedidos abertos agrupados por janela de tempo"), unsafe_allow_html=True)

    periodos = [7, 15, 20, 30]
    subtabs  = st.tabs([f"⏱ {d} dias" for d in periodos])

    for subtab, dias in zip(subtabs, periodos):
        with subtab:
            df = analise_periodo(todos_pedidos, dias, hoje)
            if df.empty:
                st.markdown(
                    empty_state("Sem pedidos", f"Nenhum pedido aberto criado nos últimos {dias} dias."),
                    unsafe_allow_html=True,
                )
                continue

            n_total  = len(df)
            n_ok     = (df["Risco"] == "🟢 No ritmo").sum()
            n_risco  = (df["Risco"].isin(["🔴 Sem vendas", "🟠 Abaixo do mínimo"])).sum()
            total_pb = df["Pré-baixa"].sum()

            c1, c2, c3, c4 = st.columns(4)
            with c1:
                st.markdown(kpi_html("Pedidos no período", str(n_total)), unsafe_allow_html=True)
            with c2:
                st.markdown(kpi_html("No ritmo", str(n_ok)), unsafe_allow_html=True)
            with c3:
                st.markdown(kpi_html("Em risco", str(n_risco), alerta=(n_risco > 0)), unsafe_allow_html=True)
            with c4:
                st.markdown(kpi_html("Total pré-baixa", _R(total_pb)), unsafe_allow_html=True)

            st.markdown('<div style="height:12px"></div>', unsafe_allow_html=True)

            df_graf = df.sort_values("Pré-baixa", ascending=False).head(40).copy()
            fig = go.Figure()
            for risco, cor in [
                ("🟢 No ritmo", "#2ecc71"), ("🟡 Abaixo do ritmo", "#f1c40f"),
                ("🟠 Abaixo do mínimo", "#e67e22"), ("🔴 Sem vendas", "#e74c3c"),
            ]:
                df_r = df_graf[df_graf["Risco"] == risco]
                if df_r.empty:
                    continue
                fig.add_bar(
                    x=df_r["Nome"], y=df_r["Pré-baixa"], name=risco, marker_color=cor,
                    customdata=df_r[["Ritmo esperado", "% do ritmo", "Dias do pedido"]].values,
                    hovertemplate=(
                        "<b>%{x}</b><br>Pré-baixa: R$ %{y:,.0f}<br>"
                        "Ritmo esperado: R$ %{customdata[0]:,.0f}<br>"
                        "% do ritmo: %{customdata[1]:.1f}%<br>"
                        "Dias: %{customdata[2]}<extra></extra>"
                    ),
                )
            fig.add_hline(y=MINIMO_REV, line_dash="dash", line_color="#e74c3c",
                          annotation_text=f"Mínimo R${MINIMO_REV:.0f}")
            fig.update_layout(
                barmode="group", title=f"Pré-baixa — pedidos abertos (últimos {dias} dias)",
                xaxis_tickangle=-45, height=380, margin=dict(b=100),
                legend=dict(orientation="h", yanchor="bottom", y=1.02),
                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                font=dict(family=_FONT_B, color=_INK),
            )
            st.plotly_chart(fig, use_container_width=True)

            _R_fmt = lambda v: _R(float(v)) if isinstance(v, (int, float)) else str(v)
            st.dataframe(
                df[["Risco", "Nome", "Supervisor", "Criado", "Acerto",
                    "Dias do pedido", "Pré-baixa", "Valor pedido"]]
                .style.format({"Pré-baixa": _R_fmt, "Valor pedido": _R_fmt}),
                use_container_width=True, hide_index=True,
            )


def _tab_gerencial(df_res: pd.DataFrame, todos_pedidos: list, hoje: date):
    st.markdown(_section_title("Visão Gerencial", "Painéis de controle de desempenho da equipe"), unsafe_allow_html=True)

    if df_res.empty:
        st.markdown(empty_state("Sem dados", "Sem registros para o mês selecionado."), unsafe_allow_html=True)
        return

    df_res = df_res.copy()

    # Leaderboard
    st.markdown(
        '<p style="font-family:' + _FONT_D + ';font-size:16px;color:' + _INK + ';margin:0 0 4px">Leaderboard</p>'
        '<p style="font-family:' + _FONT_B + ';font-size:10px;color:' + _MUTED + ';margin:0 0 14px;letter-spacing:.07em;text-transform:uppercase">'
        'Ranking de revendedoras · total vendido no mês</p>',
        unsafe_allow_html=True,
    )
    df_rank = df_res.sort_values("Total", ascending=True).copy()
    cor_map = {
        "🟢 No ritmo": _ROSA, "🟢 OK": _ROSA,
        "🟡 Abaixo do ritmo": _GOLD, "🟡 Abaixo do mínimo": _GOLD,
        "🟠 Abaixo do mínimo": "#e67e22", "🔴 Sem vendas": "#e74c3c",
    }
    df_rank["Cor"] = df_rank["Risco"].map(cor_map).fillna("#95a5a6")
    fig_rank = go.Figure()
    fig_rank.add_bar(
        x=df_rank["Total"], y=df_rank["Nome"], orientation="h",
        marker_color=df_rank["Cor"].tolist(),
        text=df_rank["Total"].apply(_R), textposition="outside",
        customdata=df_rank[["Supervisor", "Risco"]].values,
        hovertemplate="<b>%{y}</b><br>Total: %{text}<br>Supervisora: %{customdata[0]}<br>Situação: %{customdata[1]}<extra></extra>",
    )
    fig_rank.add_vline(x=MINIMO_REV, line_dash="dash", line_color="#e74c3c",
                       annotation_text=f"Mínimo R${MINIMO_REV:.0f}", annotation_position="top right")
    fig_rank.update_layout(
        height=max(400, len(df_rank) * 22), xaxis_title="Total vendido",
        xaxis=dict(tickformat=",.0f", tickprefix="R$ "), yaxis_title="",
        showlegend=False, margin=dict(l=220, r=100),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family=_FONT_B, color=_INK),
    )
    st.plotly_chart(fig_rank, use_container_width=True)

    st.markdown(_hr(), unsafe_allow_html=True)

    col_l, col_r = st.columns(2)
    with col_l:
        st.markdown(
            '<p style="font-family:' + _FONT_D + ';font-size:16px;color:' + _INK + ';margin:0 0 12px">'
            'Distribuição por faixa</p>', unsafe_allow_html=True,
        )
        faixas  = [0, 300, 600, 1000, 2000, 5000, float("inf")]
        rotulos = ["R$0–300", "R$301–600", "R$601–1K", "R$1K–2K", "R$2K–5K", "> R$5K"]
        cores_f = ["#e74c3c", "#f39c12", "#f1c40f", _ROSA, "#8B4A54", "#5C2E36"]
        df_res["Faixa"] = pd.cut(df_res["Total"], bins=faixas, labels=rotulos, right=True, include_lowest=True)
        dist = df_res.groupby("Faixa", observed=True).size().reset_index(name="Qtd")
        fig_d = px.bar(dist, x="Faixa", y="Qtd", color="Faixa",
                       color_discrete_sequence=cores_f, text="Qtd")
        fig_d.update_traces(textposition="outside")
        fig_d.update_layout(showlegend=False, height=320,
                             paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                             font=dict(family=_FONT_B, color=_INK))
        st.plotly_chart(fig_d, use_container_width=True)

    with col_r:
        st.markdown(
            '<p style="font-family:' + _FONT_D + ';font-size:16px;color:' + _INK + ';margin:0 0 12px">'
            'Desempenho por supervisora</p>', unsafe_allow_html=True,
        )
        df_sup_agg = (
            df_res.groupby("Supervisor", as_index=False)
            .agg(Total=("Total", "sum"), Media=("Total", "mean"), Revendedoras=("Nome", "count"))
            .sort_values("Total", ascending=False)
        )
        fig_s = go.Figure()
        fig_s.add_bar(x=df_sup_agg["Supervisor"], y=df_sup_agg["Total"],
                      name="Total equipe", marker_color=_ROSA,
                      text=df_sup_agg["Total"].apply(_R), textposition="outside")
        fig_s.add_scatter(x=df_sup_agg["Supervisor"], y=df_sup_agg["Media"],
                          mode="markers+text", name="Média/rev",
                          marker=dict(size=12, color=_GOLD, symbol="diamond"),
                          text=df_sup_agg["Media"].apply(_R), textposition="top center")
        fig_s.add_hline(y=MINIMO_REV, line_dash="dot", line_color="#e74c3c",
                        annotation_text="Mínimo/rev", annotation_position="top right")
        fig_s.update_layout(
            height=350, xaxis_tickangle=-20, legend=dict(orientation="h"),
            yaxis=dict(tickformat=",.0f", tickprefix="R$ "),
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            font=dict(family=_FONT_B, color=_INK),
        )
        st.plotly_chart(fig_s, use_container_width=True)

    st.markdown(_hr(), unsafe_allow_html=True)
    st.markdown(
        '<p style="font-family:' + _FONT_D + ';font-size:16px;color:' + _INK + ';margin:0 0 12px">'
        'Funil de atividade — pedidos abertos (30 dias)</p>', unsafe_allow_html=True,
    )
    df30 = analise_periodo(todos_pedidos, 30, hoje)
    if not df30.empty:
        fig_f = go.Figure(go.Funnel(
            y=["Pedidos abertos", "Com alguma venda",
               f"Acima do mínimo (≥ R${MINIMO_REV:.0f})", "No ritmo"],
            x=[len(df30), (df30["Pré-baixa"] > 0).sum(),
               (df30["Pré-baixa"] >= MINIMO_REV).sum(), (df30["Risco"] == "🟢 No ritmo").sum()],
            textinfo="value+percent initial",
            marker_color=[_INK, _ROSA, _GOLD, "#2ecc71"],
        ))
        fig_f.update_layout(height=300, paper_bgcolor="rgba(0,0,0,0)",
                             font=dict(family=_FONT_B, color=_INK))
        st.plotly_chart(fig_f, use_container_width=True)


def _tab_niveis(todos_pedidos: list, mes: int, ano: int):
    st.markdown(_section_title(f"Classificação por nível · {mes:02d}/{ano}",
                               "Pérola 40–54 · Ouro 55–75 · Diamante 76–500 peças"), unsafe_allow_html=True)

    df_cls = classificar_revendedoras(todos_pedidos, mes, ano)

    # ── Cards de resumo por tier ──────────────────────────────────────────────
    niveis_ordem = ["Diamante", "Ouro", "Pérola", "Sem nível"]
    cols_nv = st.columns(4)
    for col, nv in zip(cols_nv, niveis_ordem):
        qtd = int((df_cls["Nível"] == nv).sum()) if not df_cls.empty else 0
        with col:
            st.markdown(_tier_card(nv, qtd), unsafe_allow_html=True)

    st.markdown('<div style="height:16px"></div>', unsafe_allow_html=True)

    if df_cls.empty:
        st.markdown(empty_state("Sem dados", "Nenhuma revendedora com pedido no mês selecionado."), unsafe_allow_html=True)
        return

    # ── Pedidos fechados ──────────────────────────────────────────────────────
    df_bx = df_cls[df_cls["Tipo"] == "🔒 Baixado (fechado)"].copy()
    if not df_bx.empty:
        st.markdown(
            '<p style="font-family:' + _FONT_D + ';font-size:16px;color:' + _INK + ';margin:0 0 4px">'
            '🔒 Pedidos fechados — resultado definitivo</p>'
            '<p style="font-family:' + _FONT_B + ';font-size:10px;color:' + _MUTED + ';margin:0 0 12px;letter-spacing:.07em;text-transform:uppercase">'
            'Nível pelo campo quantidade_antes_baixa · valor = valor_total vendido</p>',
            unsafe_allow_html=True,
        )
        for nv in niveis_ordem:
            df_nv = df_bx[df_bx["Nível"] == nv]
            if df_nv.empty:
                continue
            s = _TIER_STYLE.get(nv, _TIER_STYLE["Sem nível"])
            label = ICONE_NIVEL.get(nv, "") + " **" + nv + "** — " + str(len(df_nv)) + " pedido(s)"
            with st.expander(label, expanded=True):
                exib = df_nv[["Nome", "Supervisor", "Peças pedido", "Vendas mês", "Mínimo nível", "Status"]].copy()
                exib.columns = ["Nome", "Supervisor", "Peças", "Vendas (R$)", "Mínimo (R$)", "Status"]
                st.dataframe(
                    exib.style.format({"Vendas (R$)": _R, "Mínimo (R$)": _R}),
                    use_container_width=True, hide_index=True,
                )

    # ── Pedidos em aberto ─────────────────────────────────────────────────────
    df_ab = df_cls[df_cls["Tipo"] == "🔓 Em aberto"].copy()
    if not df_ab.empty:
        st.markdown(_hr(), unsafe_allow_html=True)
        st.markdown(
            '<p style="font-family:' + _FONT_D + ';font-size:16px;color:' + _INK + ';margin:0 0 4px">'
            '🔓 Pedidos em aberto — parcial (pré-baixa)</p>'
            '<p style="font-family:' + _FONT_B + ';font-size:10px;color:' + _MUTED + ';margin:0 0 12px;letter-spacing:.07em;text-transform:uppercase">'
            'Valor parcial vendido até agora · ainda podem melhorar</p>',
            unsafe_allow_html=True,
        )
        for nv in niveis_ordem:
            df_nv = df_ab[df_ab["Nível"] == nv]
            if df_nv.empty:
                continue
            label = ICONE_NIVEL.get(nv, "") + " **" + nv + "** — " + str(len(df_nv)) + " em aberto"
            with st.expander(label, expanded=True):
                exib = df_nv[["Nome", "Supervisor", "Peças pedido", "Vendas mês", "Mínimo nível", "Status"]].copy()
                exib.columns = ["Nome", "Supervisor", "Peças", "Pré-baixa (R$)", "Mínimo (R$)", "Status"]
                st.dataframe(
                    exib.style.format({"Pré-baixa (R$)": _R, "Mínimo (R$)": _R}),
                    use_container_width=True, hide_index=True,
                )

    st.markdown(_hr(), unsafe_allow_html=True)

    # ── Risco de rebaixamento ─────────────────────────────────────────────────
    st.markdown(
        '<p style="font-family:' + _FONT_D + ';font-size:16px;color:' + _INK + ';margin:0 0 4px">'
        '⬇️ Risco de rebaixamento</p>'
        '<p style="font-family:' + _FONT_B + ';font-size:10px;color:' + _MUTED + ';margin:0 0 12px;letter-spacing:.07em;text-transform:uppercase">'
        'Análise dos 3 meses (M-2, M-1 e atual) · 2 meses abaixo = rebaixamento</p>',
        unsafe_allow_html=True,
    )
    df_reb = alertas_rebaixamento(todos_pedidos, mes, ano)
    if df_reb.empty:
        st.markdown(_alert_card("✦", "Equipe estável", "Nenhuma revendedora com sinal de risco nos últimos 3 meses.", "#2ecc71"), unsafe_allow_html=True)
    else:
        n_alto = df_reb.apply(lambda r: any("🔴" in str(v) for v in r), axis=1).sum()
        if n_alto:
            st.error(f"🔴 {n_alto} revendedora(s) com risco confirmado de rebaixamento no próximo mês!")
        cols_vendas = [c for c in df_reb.columns if c.startswith("Vendas ")]
        proj_col    = [c for c in df_reb.columns if c.startswith("Projeção")]
        fmt_cols    = {"Mínimo do nível": _R}
        for c in cols_vendas:
            fmt_cols[c] = lambda v: _R(v) if isinstance(v, (int, float)) else str(v)
        st.dataframe(df_reb.style.format(fmt_cols), use_container_width=True, hide_index=True)

    st.markdown(_hr(), unsafe_allow_html=True)

    # ── Potencial de subida ───────────────────────────────────────────────────
    st.markdown(
        '<p style="font-family:' + _FONT_D + ';font-size:16px;color:' + _INK + ';margin:0 0 4px">'
        '⬆️ Potencial de subida</p>'
        '<p style="font-family:' + _FONT_B + ';font-size:10px;color:' + _MUTED + ';margin:0 0 12px;letter-spacing:.07em;text-transform:uppercase">'
        'Revendedoras com vendas ≥ 75% da meta do próximo nível</p>',
        unsafe_allow_html=True,
    )
    df_sub = alertas_subida(todos_pedidos, mes, ano)
    if df_sub.empty:
        st.markdown(empty_state("Nenhuma revendedora próxima de subir", "Continue acompanhando as Preciosas mais próximas da meta."), unsafe_allow_html=True)
    else:
        ja = (df_sub["Situação"] == "✅ Já atingiu a meta").sum()
        st.success(f"🚀 {len(df_sub)} Preciosa(s) com potencial — {ja} já atingiram a meta do próximo nível!")
        st.dataframe(
            df_sub.style.format({"Vendas mês": _R, "Meta subida": _R, "Falta": _R}),
            use_container_width=True, hide_index=True,
        )


# ── Render principal ──────────────────────────────────────────────────────────

def render(filtro_supervisor: str = ""):
    inject()

    # ── Header com logo SVG ───────────────────────────────────────────────────
    sub_txt = "Equipe de " + filtro_supervisor if filtro_supervisor else "Visão administrativa completa"
    st.markdown(
        '<div style="background:linear-gradient(135deg,#AB6774 0%,#C89199 50%,#D4A5AC 100%);'
        'border-radius:16px;padding:24px 28px;margin-bottom:20px;'
        'box-shadow:0 8px 32px rgba(171,103,116,.25)">'
        '<div style="display:flex;align-items:center;gap:16px">'
        + _DIAMOND_SVG +
        '<div>'
        '<p style="font-family:Jost,sans-serif;font-weight:300;font-size:10px;'
        'letter-spacing:.12em;text-transform:uppercase;color:rgba(255,255,255,.7);margin:0 0 5px">Sistema de Gestão</p>'
        '<h1 style="font-family:Georgia,serif;font-size:26px;font-weight:400;'
        'letter-spacing:.04em;color:#fff;margin:0;line-height:1.1">Acompanhamento de Revendedoras</h1>'
        '<p style="font-family:Jost,sans-serif;font-weight:300;font-size:11px;'
        'letter-spacing:.06em;text-transform:uppercase;color:rgba(255,255,255,.6);margin:5px 0 0">'
        + sub_txt + '</p>'
        '</div>'
        '</div>'
        '</div>',
        unsafe_allow_html=True,
    )

    if filtro_supervisor:
        st.info("Exibindo apenas revendedoras da equipe de **" + filtro_supervisor + "**.")

    with st.spinner(""):
        try:
            todos_pedidos_bruto = _get_lista_pedidos()
        except Exception as e:
            st.error("Erro ao carregar dados: " + str(e))
            return

    if not todos_pedidos_bruto:
        st.markdown(empty_state("Nenhum pedido encontrado", "Verifique a conexão com a API e tente novamente."), unsafe_allow_html=True)
        return

    todos_pedidos = (
        [p for p in todos_pedidos_bruto if (p.get("supervisor_nome") or "") == filtro_supervisor]
        if filtro_supervisor else todos_pedidos_bruto
    )

    if filtro_supervisor and not todos_pedidos:
        st.markdown(empty_state("Sem pedidos na sua equipe", "Nenhum pedido encontrado para " + filtro_supervisor + "."), unsafe_allow_html=True)
        return

    hoje = date.today()

    # ── Seletor de mês ────────────────────────────────────────────────────────
    meses   = meses_disponiveis(7, futuros=1)
    opcoes  = [f"{m:02d}/{y}" for y, m in meses]
    col_f, col_info = st.columns([2, 5])
    with col_f:
        mes_sel = st.selectbox("Mês de competência", opcoes, index=0, key="rv_preview_mes")
    mes_num = int(mes_sel[:2])
    ano_num = int(mes_sel[3:])
    with col_info:
        st.caption(
            f"**Baixados** com data_baixa em {mes_sel} + "
            f"**abertos** com previsão de acerto em {mes_sel} (pré-baixa)."
        )

    # ── Calcular dados ────────────────────────────────────────────────────────
    df_res, df_det = calcular_competencia(todos_pedidos, mes_num, ano_num)
    df_zero = pedidos_abertos_sem_prebaixa(todos_pedidos, mes_num, ano_num)

    total_mes  = df_res["Total"].sum()    if not df_res.empty else 0
    total_pb   = df_res["Pré-baixa"].sum() if not df_res.empty else 0
    total_bx   = df_res["Baixado"].sum()   if not df_res.empty else 0
    n_rev      = len(df_res)
    n_abaixo   = int(((df_res["Total"] > 0) & (df_res["Total"] < MINIMO_REV)).sum()) if not df_res.empty else 0
    n_zero_v   = int((df_res["Total"] == 0).sum()) if not df_res.empty else 0
    ticket_m   = total_mes / n_rev if n_rev > 0 else 0

    # ── KPI cards (marca Aureum) ──────────────────────────────────────────────
    c1, c2, c3, c4, c5 = st.columns(5)
    with c1:
        st.markdown(kpi_html("Revendedoras", str(n_rev)), unsafe_allow_html=True)
    with c2:
        st.markdown(kpi_html("Total vendido", _R(total_mes)), unsafe_allow_html=True)
    with c3:
        st.markdown(kpi_html("Baixados", _R(total_bx)), unsafe_allow_html=True)
    with c4:
        st.markdown(kpi_html("Pré-baixa", _R(total_pb)), unsafe_allow_html=True)
    with c5:
        st.markdown(kpi_html("Ticket médio", _R(ticket_m)), unsafe_allow_html=True)

    # Alertas de risco (compactos, abaixo dos KPIs)
    if n_abaixo or (n_zero_v + len(df_zero)) > 0:
        ca, cb, _ = st.columns([2, 2, 5])
        with ca:
            st.markdown(kpi_html("Abaixo do mínimo", str(n_abaixo), alerta=True), unsafe_allow_html=True)
        with cb:
            st.markdown(kpi_html("Sem vendas", str(n_zero_v + len(df_zero)), alerta=True), unsafe_allow_html=True)

    st.markdown('<div style="height:8px"></div>', unsafe_allow_html=True)

    # ── Tabs ──────────────────────────────────────────────────────────────────
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "📅 Competência",
        "⚠️ Alertas",
        "⏱️ Por período",
        "📈 Gerencial",
        "🏅 Níveis",
    ])

    with tab1:
        _tab_competencia(df_res, mes_sel)
    with tab2:
        _tab_alertas(df_zero, df_res)
    with tab3:
        _tab_periodo(todos_pedidos, hoje)
    with tab4:
        _tab_gerencial(df_res, todos_pedidos, hoje)
    with tab5:
        _tab_niveis(todos_pedidos, mes_num, ano_num)

    # Rodapé
    st.markdown(
        _hr() +
        '<p style="font-family:Jost,sans-serif;font-size:10px;color:#7A6068;text-align:center">'
        "🎨 Preview UI — versão paralela para avaliação. A página original não foi alterada."
        "</p>",
        unsafe_allow_html=True,
    )
