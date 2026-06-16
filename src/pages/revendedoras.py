import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import date
from src.api.jueri_client import _get_lista_pedidos
from src.logic.revendedoras import (
    MINIMO_REV, parse_date,
    meses_disponiveis, calcular_competencia,
    pedidos_abertos_sem_prebaixa, analise_periodo,
)
from src.logic.niveis import (
    NIVEIS_PECAS, MINIMO_VENDAS, NIVEL_SUPERIOR, LIMIAR_SUBIDA, ICONE_NIVEL,
    classificar_revendedoras, alertas_rebaixamento, alertas_subida,
)

_CORES_RISCO = {
    "🟢 No ritmo":           "#2ecc71",
    "🟢 OK":                 "#2ecc71",
    "🟡 Abaixo do ritmo":   "#f1c40f",
    "🟡 Abaixo do mínimo":  "#f39c12",
    "🟠 Abaixo do mínimo":  "#e67e22",
    "🔴 Sem vendas":         "#e74c3c",
}

_R    = lambda v: f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
_Rmd  = lambda v: f"R\\$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


# ── Helpers de estilo ─────────────────────────────────────────────────────────

def _estilo_risco(val):
    cor = _CORES_RISCO.get(str(val), "")
    if not cor:
        return ""
    return f"color: {cor}; font-weight: bold"


def _estilo_total(val):
    try:
        v = float(val)
        if v == 0:
            return "color: #e74c3c; font-weight: bold"
        if v < MINIMO_REV:
            return "color: #e67e22; font-weight: bold"
        return "color: #27ae60; font-weight: bold"
    except Exception:
        return ""


# ── Tab 1: Competência ────────────────────────────────────────────────────────

def _tab_competencia(df_res: pd.DataFrame, mes_label: str):
    st.subheader(f"Vendas por revendedora — {mes_label}")
    st.caption(
        "**Baixados no mês** = valor_total dos pedidos com data de baixa no mês. "
        "**Pré-baixa** = soma dos pedidos abertos com data de acerto no mês."
    )

    if df_res.empty:
        st.info("Nenhum dado para o mês selecionado.")
        return

    supervisoras = sorted(df_res["Supervisor"].unique())

    # Tabela por supervisora
    for sup in supervisoras:
        df_sup = df_res[df_res["Supervisor"] == sup].copy()
        total_sup = df_sup["Total"].sum()
        n_ok = (df_sup["Total"] >= MINIMO_REV).sum()
        n_risco = len(df_sup) - n_ok

        ticket_sup_val = total_sup / len(df_sup) if len(df_sup) > 0 else 0
        badge = f" — ⚠️ {n_risco} em risco" if n_risco else ""
        with st.expander(
            f"**{sup}** — {len(df_sup)} revendedoras · total {_Rmd(total_sup)} · ticket médio {_Rmd(ticket_sup_val)}{badge}",
            expanded=(n_risco > 0),
        ):
            exib = df_sup[["Nome", "Pedidos", "Baixado", "Pré-baixa", "Total", "Risco"]].copy()
            exib.columns = ["Nome", "Pedidos", "Baixado (R$)", "Pré-baixa (R$)", "Total (R$)", "Risco"]
            st.dataframe(
                exib.style
                    .map(_estilo_risco, subset=["Risco"])
                    .map(_estilo_total, subset=["Total (R$)"])
                    .format({"Baixado (R$)": _R, "Pré-baixa (R$)": _R, "Total (R$)": _R}),
                use_container_width=True, hide_index=True,
            )
            st.caption(f"Subtotal {sup}: **{_Rmd(total_sup)}**")

    st.divider()
    st.markdown(f"**Total geral do mês: {_Rmd(df_res['Total'].sum())}**")

    # Gráfico barras empilhadas (baixado + pré-baixa)
    df_graf = df_res.sort_values("Total", ascending=False).head(30)
    fig = go.Figure()
    fig.add_bar(
        x=df_graf["Nome"], y=df_graf["Baixado"],
        name="Baixado", marker_color="#6B2737",
    )
    fig.add_bar(
        x=df_graf["Nome"], y=df_graf["Pré-baixa"],
        name="Pré-baixa", marker_color="#AB6776",
    )
    fig.add_hline(y=MINIMO_REV, line_dash="dash", line_color="#e74c3c",
                  annotation_text=f"Mínimo R${MINIMO_REV:.0f}", annotation_position="top right")
    fig.update_layout(
        barmode="stack", title="Vendas por revendedora (Top 30)",
        xaxis_tickangle=-45, legend=dict(orientation="h"),
        height=420, margin=dict(b=120),
    )
    st.plotly_chart(fig, use_container_width=True)

    # Export
    csv = df_res.drop(columns=["fk_revendedor_id"]).to_csv(index=False).encode("utf-8")
    st.download_button("Exportar CSV", csv, f"competencia_{mes_label.replace('/', '-')}.csv", "text/csv")


# ── Tab 2: Alertas ────────────────────────────────────────────────────────────

def _tab_alertas(df_zero: pd.DataFrame, df_res: pd.DataFrame):
    st.subheader("⚠️ Alertas do mês")

    # Alerta 1: Pré-baixa R$0
    col_a, col_b = st.columns(2)
    with col_a:
        st.markdown(f"#### 🔴 Sem pré-baixa — {len(df_zero)} pedido(s)")
        st.caption("Pedidos abertos com acerto neste mês e pré-baixa = R$0,00")
        if df_zero.empty:
            st.success("Nenhum pedido sem pré-baixa neste mês.")
        else:
            for sup in sorted(df_zero["Supervisor"].unique()):
                df_s = df_zero[df_zero["Supervisor"] == sup]
                st.markdown(f"**{sup}** — {len(df_s)} pedido(s)")
                st.dataframe(
                    df_s[["Nome", "Pedido", "Valor pedido", "Acerto"]].style
                        .format({"Valor pedido": _R}),
                    use_container_width=True, hide_index=True,
                )

    # Alerta 2: Abaixo do mínimo
    with col_b:
        df_abaixo = df_res[(df_res["Total"] > 0) & (df_res["Total"] < MINIMO_REV)].copy() if not df_res.empty else pd.DataFrame()
        st.markdown(f"#### 🟡 Abaixo do mínimo (< {_R(MINIMO_REV)}) — {len(df_abaixo)}")
        st.caption("Têm alguma venda, mas abaixo do mínimo de permanência na equipe.")
        if df_abaixo.empty:
            st.success("Nenhuma revendedora abaixo do mínimo neste mês.")
        else:
            exib = df_abaixo[["Nome", "Supervisor", "Total", "Pré-baixa", "Baixado"]].copy()
            exib.columns = ["Nome", "Supervisor", "Total (R$)", "Pré-baixa (R$)", "Baixado (R$)"]
            exib = exib.sort_values("Total (R$)")
            st.dataframe(
                exib.style
                    .map(_estilo_total, subset=["Total (R$)"])
                    .format({"Total (R$)": _R, "Pré-baixa (R$)": _R, "Baixado (R$)": _R}),
                use_container_width=True, hide_index=True,
            )



# ── Tab 3: Análise por período ────────────────────────────────────────────────

def _tab_periodo(todos_pedidos: list, hoje: date):
    st.subheader("Pré-baixa por idade do pedido")
    st.caption(
        "Para cada janela de tempo, mostra os pedidos **abertos** criados naquele período "
        "e o valor já vendido (pré-baixa). O ritmo esperado é calculado proporcionalmente "
        "ao tempo decorrido desde a criação até a data de acerto."
    )

    periodos = [7, 15, 20, 30]
    subtabs = st.tabs([f"⏱ {d} dias" for d in periodos])

    for subtab, dias in zip(subtabs, periodos):
        with subtab:
            df = analise_periodo(todos_pedidos, dias, hoje)

            if df.empty:
                st.info(f"Nenhum pedido aberto criado nos últimos {dias} dias.")
                continue

            # Métricas do período
            n_total = len(df)
            n_ok    = (df["Risco"] == "🟢 No ritmo").sum()
            n_risco = (df["Risco"].isin(["🔴 Sem vendas", "🟠 Abaixo do mínimo"])).sum()
            total_pb = df["Pré-baixa"].sum()

            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Pedidos no período", n_total)
            c2.metric("🟢 No ritmo", n_ok)
            c3.metric("🔴🟠 Em risco", n_risco)
            c4.metric("Total pré-baixa", _R(total_pb))

            # Gráfico barras coloridas por risco
            df_graf = df.sort_values("Pré-baixa", ascending=False).head(40).copy()
            df_graf["Cor"] = df_graf["Risco"].map(_CORES_RISCO)

            fig = go.Figure()
            for risco, cor in [
                ("🟢 No ritmo",          "#2ecc71"),
                ("🟡 Abaixo do ritmo",   "#f1c40f"),
                ("🟠 Abaixo do mínimo",  "#e67e22"),
                ("🔴 Sem vendas",         "#e74c3c"),
            ]:
                df_r = df_graf[df_graf["Risco"] == risco]
                if df_r.empty:
                    continue
                fig.add_bar(
                    x=df_r["Nome"], y=df_r["Pré-baixa"],
                    name=risco, marker_color=cor,
                    customdata=df_r[["Ritmo esperado", "% do ritmo", "Dias do pedido"]].values,
                    hovertemplate=(
                        "<b>%{x}</b><br>"
                        "Pré-baixa: R$ %{y:,.0f}<br>"
                        "Ritmo esperado: R$ %{customdata[0]:,.0f}<br>"
                        "% do ritmo: %{customdata[1]:.1f}%<br>"
                        "Dias do pedido: %{customdata[2]}<br>"
                        "<extra></extra>"
                    ),
                )

            fig.add_hline(y=MINIMO_REV, line_dash="dash", line_color="#e74c3c",
                          annotation_text=f"Mínimo R${MINIMO_REV:.0f}")
            fig.update_layout(
                barmode="group",
                title=f"Pré-baixa — pedidos abertos (últimos {dias} dias)",
                xaxis_tickangle=-45,
                height=400,
                margin=dict(b=120),
                legend=dict(orientation="h", yanchor="bottom", y=1.02),
            )
            st.plotly_chart(fig, use_container_width=True)

            # Tabela detalhada
            cols_exib = ["Risco", "Nome", "Supervisor", "Criado", "Acerto",
                         "Dias do pedido", "Pré-baixa", "Valor pedido"]
            st.dataframe(
                df[cols_exib].style
                    .map(_estilo_risco, subset=["Risco"])
                    .format({"Pré-baixa": _R, "Valor pedido": _R}),
                use_container_width=True, hide_index=True,
            )

            # Por supervisora
            if "Supervisor" in df.columns:
                st.markdown("**Pré-baixa por supervisora**")
                df_sup = (
                    df.groupby("Supervisor", as_index=False)
                    .agg(
                        Pedidos=("Nome", "count"),
                        Pre_baixa=("Pré-baixa", "sum"),
                        No_ritmo=("Risco", lambda x: (x == "🟢 No ritmo").sum()),
                        Em_risco=("Risco", lambda x: x.isin(["🔴 Sem vendas", "🟠 Abaixo do mínimo"]).sum()),
                    )
                    .rename(columns={"Pre_baixa": "Pré-baixa (R$)", "No_ritmo": "No ritmo", "Em_risco": "Em risco"})
                    .sort_values("Pré-baixa (R$)", ascending=False)
                )
                st.dataframe(
                    df_sup.style.format({"Pré-baixa (R$)": _R}),
                    use_container_width=True, hide_index=True,
                )


# ── Tab 4: Visão gerencial ────────────────────────────────────────────────────

def _tab_gerencial(df_res: pd.DataFrame, todos_pedidos: list, hoje: date):
    """
    Visualizações gerenciais baseadas em boas práticas de gestão de equipes de vendas:
    - Leaderboard com ranking e metas (identifica top e bottom performers)
    - Distribuição por faixa de receita (entende a saúde da equipe)
    - Comparativo por supervisora (benchmarking de times)
    - Funil de atividade (pedido → pré-baixa → acima do mínimo)
    """
    df_res = df_res.copy()  # evita mutação do DataFrame original
    if df_res.empty:
        st.info("Sem dados disponíveis para o mês selecionado.")
        return

    st.subheader("Visão gerencial")
    st.caption(
        "Painéis de controle baseados em metodologias de gestão de equipes de vendas "
        "por consignação (Sales Performance Management — KPI tracking, risk segmentation, "
        "team benchmarking)."
    )

    # ── Leaderboard ─────────────────────────────────────────────────────────
    st.markdown("#### 🏆 Leaderboard — ranking de revendedoras")
    st.caption(
        "As barras mostram o total vendido (baixado + pré-baixa). "
        "A linha vermelha é o mínimo de permanência (R$300). "
        "Use este gráfico para identificar as top performers e aquelas que precisam de atenção."
    )

    df_rank = df_res.sort_values("Total", ascending=True).copy()
    df_rank["Cor"] = df_rank["Risco"].map(_CORES_RISCO).fillna("#95a5a6")

    fig_rank = go.Figure()
    fig_rank.add_bar(
        x=df_rank["Total"],
        y=df_rank["Nome"],
        orientation="h",
        marker_color=df_rank["Cor"],
        text=df_rank["Total"].apply(lambda v: _R(v)),
        textposition="outside",
        customdata=df_rank[["Supervisor", "Risco"]].values,
        hovertemplate=(
            "<b>%{y}</b><br>"
            "Total: %{text}<br>"
            "Supervisora: %{customdata[0]}<br>"
            "Situação: %{customdata[1]}<br>"
            "<extra></extra>"
        ),
    )
    fig_rank.add_vline(x=MINIMO_REV, line_dash="dash", line_color="#e74c3c",
                       annotation_text=f"Mínimo R${MINIMO_REV:.0f}", annotation_position="top right")
    fig_rank.update_layout(
        height=max(400, len(df_rank) * 22),
        xaxis_title="Total vendido",
        xaxis=dict(tickformat=",.0f", tickprefix="R$ "),
        yaxis_title="",
        showlegend=False,
        margin=dict(l=220, r=100),
    )
    st.plotly_chart(fig_rank, use_container_width=True)

    st.divider()

    # ── Distribuição por faixa de receita ────────────────────────────────────
    col_l, col_r = st.columns(2)

    with col_l:
        st.markdown("#### 📊 Distribuição por faixa de receita")
        st.caption(
            "Histograma que mostra quantas revendedoras estão em cada faixa de receita. "
            "Uma equipe saudável tem a maior concentração acima do mínimo."
        )
        faixas = [0, 300, 600, 1000, 2000, 5000, float("inf")]
        rotulos = ["R$0–300", "R$301–600", "R$601–1K", "R$1K–2K", "R$2K–5K", "> R$5K"]
        cores_faixa = ["#e74c3c", "#f39c12", "#f1c40f", "#2ecc71", "#27ae60", "#1a7a4a"]

        df_res["Faixa"] = pd.cut(
            df_res["Total"],
            bins=faixas,
            labels=rotulos,
            right=True,
            include_lowest=True,
        )
        dist = df_res.groupby("Faixa", observed=True).size().reset_index(name="Qtd")

        fig_dist = px.bar(
            dist, x="Faixa", y="Qtd",
            color="Faixa",
            color_discrete_sequence=cores_faixa,
            text="Qtd",
            title="Revendedoras por faixa de receita",
        )
        fig_dist.update_traces(textposition="outside")
        fig_dist.update_layout(showlegend=False, height=350)
        st.plotly_chart(fig_dist, use_container_width=True)

    # ── Comparativo por supervisora ───────────────────────────────────────────
    with col_r:
        st.markdown("#### 👥 Desempenho por supervisora")
        st.caption(
            "Compara a soma e a média de vendas por equipe. "
            "Permite identificar supervisoras com equipes acima ou abaixo da média geral."
        )
        df_sup_agg = (
            df_res.groupby("Supervisor", as_index=False)
            .agg(
                Total=("Total", "sum"),
                Media=("Total", "mean"),
                Revendedoras=("Nome", "count"),
                OK=("Risco", lambda x: (x == "🟢 OK").sum()),
            )
            .sort_values("Total", ascending=False)
        )
        df_sup_agg["Média por rev."] = df_sup_agg["Media"].round(2)

        fig_sup = go.Figure()
        fig_sup.add_bar(
            x=df_sup_agg["Supervisor"], y=df_sup_agg["Total"],
            name="Total equipe", marker_color="#6B2737",
            text=df_sup_agg["Total"].apply(_R),
            textposition="outside",
        )
        fig_sup.add_scatter(
            x=df_sup_agg["Supervisor"], y=df_sup_agg["Media"],
            mode="markers+text", name="Média por rev.",
            marker=dict(size=12, color="#AB6776", symbol="diamond"),
            text=df_sup_agg["Media"].apply(_R),
            textposition="top center",
        )
        fig_sup.add_hline(y=MINIMO_REV, line_dash="dot", line_color="#e74c3c",
                          annotation_text="Mínimo/rev", annotation_position="top right")
        fig_sup.update_layout(
            title="Total e média por supervisora",
            xaxis_tickangle=-20, height=380,
            legend=dict(orientation="h"),
            yaxis=dict(tickformat=",.0f", tickprefix="R$ "),
        )
        st.plotly_chart(fig_sup, use_container_width=True)

    st.divider()

    # ── Funil de atividade ────────────────────────────────────────────────────
    st.markdown("#### 🔽 Funil de atividade — pedidos abertos (últimos 30 dias)")
    st.caption(
        "Mostra a conversão dos pedidos abertos recentes: do total de pedidos, "
        "quantos já têm alguma venda, e quantos estão acima do mínimo de R$300. "
        "Referência: modelo de funil de vendas por consignação (Sales Funnel Analysis)."
    )
    df30 = analise_periodo(todos_pedidos, 30, hoje)
    if not df30.empty:
        n_total30 = len(df30)
        n_com_venda = (df30["Pré-baixa"] > 0).sum()
        n_acima_min = (df30["Pré-baixa"] >= MINIMO_REV).sum()
        n_no_ritmo  = (df30["Risco"] == "🟢 No ritmo").sum()

        fig_funil = go.Figure(go.Funnel(
            y=["Pedidos abertos (30 dias)", "Com alguma venda", f"Acima do mínimo (≥ R${MINIMO_REV:.0f})", "No ritmo de vendas"],
            x=[n_total30, n_com_venda, n_acima_min, n_no_ritmo],
            textinfo="value+percent initial",
            marker_color=["#6B2737", "#AB6776", "#f39c12", "#2ecc71"],
        ))
        fig_funil.update_layout(title="Funil de atividade das revendedoras", height=320)
        st.plotly_chart(fig_funil, use_container_width=True)
    else:
        st.info("Sem pedidos abertos nos últimos 30 dias para o funil.")



# ── Tab 5: Níveis ─────────────────────────────────────────────────────────────

def _tab_niveis(todos_pedidos: list, mes: int, ano: int):
    st.subheader("Classificação por nível — " + f"{mes:02d}/{ano}")
    st.caption(
        "Nível determinado pela quantidade de peças do pedido de consignação ativo. "
        "**Pérola**: 40–54 peças · **Ouro**: 55–75 peças · **Diamante**: 76–500 peças."
    )

    df_cls = classificar_revendedoras(todos_pedidos, mes, ano)

    # ── Resumo por nível ──────────────────────────────────────────────────────
    niveis_ordem = ["Diamante", "Ouro", "Pérola", "Sem nível"]
    cols_nv = st.columns(4)
    for col, nv in zip(cols_nv, niveis_ordem):
        qtd = int((df_cls["Nível"] == nv).sum()) if not df_cls.empty else 0
        col.metric(f"{ICONE_NIVEL.get(nv, '')} {nv}", qtd)

    st.divider()

    if df_cls.empty:
        st.info("Nenhuma revendedora com pedido aberto no mês selecionado.")
        return

    # ── Tabela por nível ──────────────────────────────────────────────────────
    def _estilo_status(val):
        cores = {
            "✅ Mantendo nível":    "color: #27ae60; font-weight: bold",
            "⚠️ Abaixo do mínimo": "color: #e67e22; font-weight: bold",
            "🔴 Sem vendas":        "color: #e74c3c; font-weight: bold",
        }
        return cores.get(str(val), "")

    for nv in ["Diamante", "Ouro", "Pérola", "Sem nível"]:
        df_nv = df_cls[df_cls["Nível"] == nv].copy()
        if df_nv.empty:
            continue
        with st.expander(
            f"{ICONE_NIVEL.get(nv, '')} **{nv}** — {len(df_nv)} revendedora(s)",
            expanded=True,
        ):
            exib = df_nv[["Nome", "Supervisor", "Peças pedido", "Vendas mês", "Mínimo nível", "Status"]].copy()
            exib.columns = ["Nome", "Supervisor", "Peças", "Vendas mês (R$)", "Mínimo (R$)", "Status"]
            st.dataframe(
                exib.style
                    .map(_estilo_status, subset=["Status"])
                    .format({"Vendas mês (R$)": _R, "Mínimo (R$)": _R}),
                use_container_width=True, hide_index=True,
            )

    st.divider()

    # ── Alerta: risco de rebaixamento ─────────────────────────────────────────
    st.markdown("#### ⬇️ Risco de rebaixamento")
    st.caption(
        "Revendedoras que ficaram abaixo do mínimo do seu nível nos **2 meses anteriores consecutivos**. "
        "Se mantiverem esse desempenho, devem retornar ao nível anterior no próximo mês."
    )
    df_reb = alertas_rebaixamento(todos_pedidos, mes, ano)
    if df_reb.empty:
        st.success("Nenhuma revendedora em risco de rebaixamento nos últimos 2 meses.")
    else:
        # identifica colunas de vendas dinamicamente
        cols_vendas = [c for c in df_reb.columns if c.startswith("Vendas ")]
        fmt_cols = {"Mínimo do nível": _R}
        for c in cols_vendas:
            fmt_cols[c] = _R
        st.error(f"⚠️ {len(df_reb)} revendedora(s) em risco de rebaixamento!")
        st.dataframe(
            df_reb.style.format(fmt_cols),
            use_container_width=True, hide_index=True,
        )

    st.divider()

    # ── Alerta: potencial de subida ───────────────────────────────────────────
    st.markdown("#### ⬆️ Potencial de subida de nível")
    st.caption(
        "Revendedoras que já atingiram **75% ou mais** da meta de vendas do próximo nível. "
        "Priorize o acompanhamento para que cheguem à meta e subam de nível no próximo mês."
    )
    df_sub = alertas_subida(todos_pedidos, mes, ano)
    if df_sub.empty:
        st.info("Nenhuma revendedora próxima de subir de nível neste mês.")
    else:
        st.success(f"🚀 {len(df_sub)} revendedora(s) com potencial de subida!")
        st.dataframe(
            df_sub.style.format({
                "Vendas mês":  _R,
                "Meta subida": _R,
                "Falta":       _R,
            }),
            use_container_width=True, hide_index=True,
        )


# ── Render principal ──────────────────────────────────────────────────────────

def render(filtro_supervisor: str = ""):
    """
    filtro_supervisor: se preenchido, restringe todos os dados à equipe desta supervisora.
    Passado automaticamente pelo app.py quando o usuário logado tem role='supervisora'.
    """
    if filtro_supervisor:
        st.header(f"👥 Minha Equipe — {filtro_supervisor}")
        st.info(f"Exibindo apenas revendedoras da equipe de **{filtro_supervisor}**.")
    else:
        st.header("👥 Acompanhamento de Revendedoras")

    with st.spinner("Carregando pedidos..."):
        try:
            todos_pedidos_bruto = _get_lista_pedidos()
        except Exception as e:
            st.error(f"Erro ao carregar dados: {e}")
            return

    if not todos_pedidos_bruto:
        st.warning("Nenhum pedido encontrado.")
        return

    # Aplica filtro de supervisora: se definido, mantém apenas pedidos da sua equipe
    if filtro_supervisor:
        todos_pedidos = [
            p for p in todos_pedidos_bruto
            if (p.get("supervisor_nome") or "") == filtro_supervisor
        ]
        if not todos_pedidos:
            st.warning("Nenhum pedido encontrado para sua equipe.")
            return
    else:
        todos_pedidos = todos_pedidos_bruto

    hoje = date.today()

    # ── Filtro de mês ─────────────────────────────────────────────────────────
    meses = meses_disponiveis(7)
    opcoes = [f"{m:02d}/{y}" for y, m in meses]

    col_f, col_info = st.columns([2, 5])
    with col_f:
        mes_sel = st.selectbox("Mês de competência", opcoes, index=0)
    mes_num = int(mes_sel[:2])
    ano_num = int(mes_sel[3:])

    with col_info:
        st.caption(
            f"**Regra:** pedidos **Baixados** com data_baixa em {mes_sel} + "
            f"pedidos **Abertos** com previsão de acerto em {mes_sel} (soma da pré-baixa)."
        )

    # ── Calcular dados ────────────────────────────────────────────────────────
    df_res, df_det = calcular_competencia(todos_pedidos, mes_num, ano_num)
    df_zero = pedidos_abertos_sem_prebaixa(todos_pedidos, mes_num, ano_num)

    # ── Métricas globais ──────────────────────────────────────────────────────
    total_mes   = df_res["Total"].sum()    if not df_res.empty else 0
    total_pb    = df_res["Pré-baixa"].sum() if not df_res.empty else 0
    total_bx    = df_res["Baixado"].sum()   if not df_res.empty else 0
    n_rev       = len(df_res)
    n_zero      = len(df_zero)
    n_abaixo    = int(((df_res["Total"] > 0) & (df_res["Total"] < MINIMO_REV)).sum()) if not df_res.empty else 0
    n_sem_res   = int((df_res["Total"] == 0).sum()) if not df_res.empty else 0

    ticket_medio = total_mes / n_rev if n_rev > 0 else 0

    # Linha 1 — valores financeiros (colunas largas para não truncar)
    c1, c2, c3, c4, c5 = st.columns([1, 2, 2, 2, 2])
    c1.metric("Revendedoras", n_rev)
    c2.metric("Total vendido", _R(total_mes))
    c3.metric("↳ Baixados", _R(total_bx))
    c4.metric("↳ Pré-baixa", _R(total_pb))
    c5.metric("🎯 Ticket médio", _R(ticket_medio))

    # Linha 2 — alertas de risco
    c6, c7, _esp = st.columns([2, 2, 5])
    c6.metric("🟡 Abaixo do mínimo", n_abaixo)
    c7.metric("🔴 Sem vendas", n_zero + n_sem_res,
              help="Pedidos abertos com R$0 + revendedoras com total = R$0")

    # ── Tabs ──────────────────────────────────────────────────────────────────
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "📅 Competência",
        "⚠️ Alertas",
        "⏱️ Análise por período",
        "📈 Visão gerencial",
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
