import streamlit as st
import pandas as pd
import plotly.express as px

from src.api.jueri_client import (
    get_produtos, get_categorias, get_itens_pedidos_abertos, get_itens_pedidos_baixados
)
from src.logic.estoque import montar_df_estoque
from src.logic.compras import top_vendidos_por_categoria

_DIAS_HIST = 90     # janela de vendas para calcular velocidade
_CRITICO_D = 7      # cobertura < 7 dias → ruptura iminente
_ATENCAO_D = 30     # cobertura < 30 dias → atenção
_CAP_QTD   = 200    # cap de unidades por item de pedido (evita lixo da API)


# ── Enriquecimento com velocidade de vendas ────────────────────────────────

def _enriquecer(df: pd.DataFrame, itens_vendidos: list) -> pd.DataFrame:
    """Adiciona Vendas(90d), Vendas/dia, Cobertura, Giro e Status enriquecido."""
    vendas_pid: dict = {}
    for item in itens_vendidos:
        pid = item.get("produto_id")
        qtd = min(float(item.get("quantidade") or 0), _CAP_QTD)
        vendas_pid[pid] = vendas_pid.get(pid, 0) + qtd

    df = df.copy()
    df["Vendas (90d)"]  = df["ID"].map(lambda p: int(round(vendas_pid.get(p, 0))))
    df["Vendas/dia"]    = (df["Vendas (90d)"] / _DIAS_HIST).round(3)

    def _cob(row):
        if row["Vendas/dia"] == 0:
            return None
        return int(round(row["Em estoque"] / row["Vendas/dia"]))

    def _giro(row):
        vendas_ano = row["Vendas (90d)"] * (365 / _DIAS_HIST)
        return round(vendas_ano / max(row["Total"], 1), 1)

    df["Cobertura (dias)"] = df.apply(_cob, axis=1)
    df["Giro anual"]       = df.apply(_giro, axis=1)

    def _status(r):
        if r["Em estoque"] == 0 and r["Na rua"] == 0:
            return "⚫ Zerado"
        if r["Em estoque"] == 0:
            return "🟡 Só na rua"
        if r["Vendas/dia"] == 0:
            return "🔵 Parado"
        cob = r["Cobertura (dias)"]
        if cob is not None and cob < _CRITICO_D:
            return "🔴 Ruptura iminente"
        if cob is not None and cob < _ATENCAO_D:
            return "🟡 Atenção"
        return "🟢 OK"

    df["Status"] = df.apply(_status, axis=1)
    return df


# ── Helpers de estilo ──────────────────────────────────────────────────────

def _cor_status(val):
    s = str(val)
    if "Ruptura"  in s: return "background-color:#ffd6d6;color:#c00"
    if "Parado"   in s: return "background-color:#e3f2fd"
    if "Só na rua" in s or "Atenção" in s: return "background-color:#fff9c4"
    if "Zerado"   in s: return "background-color:#eeeeee"
    return ""


# ── Sub-telas ──────────────────────────────────────────────────────────────

def _painel_alertas(df):
    """Cards de resumo de situação no topo da página."""
    n_rupt  = (df["Status"] == "🔴 Ruptura iminente").sum()
    n_aten  = (df["Status"] == "🟡 Atenção").sum()
    n_par   = (df["Status"] == "🔵 Parado").sum()
    n_rua   = (df["Status"] == "🟡 Só na rua").sum()
    n_zer   = (df["Status"] == "⚫ Zerado").sum()

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("🔴 Ruptura iminente", n_rupt,  help=f"Cobertura < {_CRITICO_D} dias — compre urgente")
    c2.metric("🟡 Atenção",          n_aten,  help=f"Cobertura entre {_CRITICO_D} e {_ATENCAO_D} dias")
    c3.metric("🔵 Parados (90d)",    n_par,   help="Estoque > 0 mas sem nenhuma venda nos últimos 90 dias")
    c4.metric("🟡 Só na rua",        n_rua,   help="0 unidades em depósito — risco se revendedora não devolver")
    c5.metric("⚫ Zerados",          n_zer,   help="Sem estoque em nenhum lugar")
    return n_rupt, n_aten, n_par, n_rua, n_zer


def _tab_alertas(df):
    urgentes = df[df["Status"].isin(
        ["🔴 Ruptura iminente", "🟡 Atenção", "🟡 Só na rua"]
    )].sort_values("Cobertura (dias)", na_position="last").copy()

    if urgentes.empty:
        st.success("Nenhum produto em situação crítica no momento.")
        return

    st.caption(
        f"**{len(urgentes)} produtos** precisam de atenção. "
        "Ordene por 'Cobertura (dias)' para ver os mais urgentes primeiro."
    )

    cols = ["Produto", "Categoria", "Em estoque", "Na rua",
            "Vendas/dia", "Cobertura (dias)", "Status"]
    st.dataframe(
        urgentes[cols].style.map(_cor_status, subset=["Status"]),
        use_container_width=True, hide_index=True,
    )

    csv = urgentes[cols].to_csv(index=False).encode("utf-8")
    st.download_button("⬇️ Exportar alertas (CSV)", csv, "alertas_estoque.csv", "text/csv")


def _tab_categorias(df):
    resumo = df.groupby("Categoria", as_index=False).agg(
        Produtos        = ("Produto",          "count"),
        Em_estoque      = ("Em estoque",        "sum"),
        Na_rua          = ("Na rua",            "sum"),
        Total           = ("Total",             "sum"),
        Cob_mediana     = ("Cobertura (dias)",  "median"),
        Criticos        = ("Status", lambda x: (x == "🔴 Ruptura iminente").sum()),
        Atencao         = ("Status", lambda x: (x == "🟡 Atenção").sum()),
        Parados         = ("Status", lambda x: (x == "🔵 Parado").sum()),
    )
    resumo["% na rua"] = (resumo["Na_rua"] / resumo["Total"].clip(lower=1) * 100).round(1)
    resumo = resumo.rename(columns={
        "Em_estoque": "Em estoque", "Na_rua": "Na rua",
        "Cob_mediana": "Cobertura mediana (dias)",
        "Criticos": "🔴", "Atencao": "🟡", "Parados": "🔵",
    })

    # Gráfico de cobertura por categoria — o mais útil para o dono
    fig = px.bar(
        resumo.sort_values("Cobertura mediana (dias)"),
        x="Cobertura mediana (dias)", y="Categoria", orientation="h",
        color="Cobertura mediana (dias)",
        color_continuous_scale=[[0, "#c00"], [0.12, "#ffb300"], [0.5, "#2e7d32"], [1, "#2e7d32"]],
        range_color=[0, 60],
        title="Cobertura mediana de estoque por categoria (dias até ruptura)",
        labels={"Cobertura mediana (dias)": "Dias de cobertura"},
    )
    fig.add_vline(x=_CRITICO_D, line_dash="dash", line_color="red",
                  annotation_text=f"Crítico ({_CRITICO_D}d)", annotation_position="top right")
    fig.add_vline(x=_ATENCAO_D, line_dash="dash", line_color="orange",
                  annotation_text=f"Atenção ({_ATENCAO_D}d)", annotation_position="top right")
    fig.update_layout(coloraxis_showscale=False)
    st.plotly_chart(fig, use_container_width=True)

    st.dataframe(
        resumo[["Categoria", "Produtos", "Em estoque", "Na rua", "% na rua",
                "Cobertura mediana (dias)", "🔴", "🟡", "🔵"]],
        use_container_width=True, hide_index=True,
    )

    st.divider()
    st.subheader("Detalhamento por categoria")

    for cat in sorted(df["Categoria"].unique()):
        df_c = df[df["Categoria"] == cat].copy()
        n_crit = (df_c["Status"] == "🔴 Ruptura iminente").sum()
        n_par  = (df_c["Status"] == "🔵 Parado").sum()
        badge  = (f" — 🔴 {n_crit} ruptura" if n_crit else "") + \
                 (f" — 🔵 {n_par} parado(s)" if n_par else "")

        with st.expander(
            f"**{cat}** — {len(df_c)} produtos{badge}",
            expanded=(n_crit > 0),
        ):
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Em estoque", int(df_c["Em estoque"].sum()))
            m2.metric("Na rua",     int(df_c["Na rua"].sum()))
            m3.metric("🔴 Rupturas", int(n_crit))
            m4.metric("🔵 Parados",  int(n_par))

            cols = ["Produto", "Em estoque", "Na rua",
                    "Vendas (90d)", "Cobertura (dias)", "Giro anual", "Status"]
            st.dataframe(
                df_c[cols].sort_values("Cobertura (dias)", na_position="last")
                .style.map(_cor_status, subset=["Status"]),
                use_container_width=True, hide_index=True,
            )


def _tab_parados(df):
    parados = df[df["Status"] == "🔵 Parado"].sort_values("Em estoque", ascending=False)

    if parados.empty:
        st.success("Todos os produtos com estoque tiveram pelo menos uma venda nos últimos 90 dias.")
        return

    total_unidades = int(parados["Em estoque"].sum())
    st.warning(
        f"**{len(parados)} produtos** têm estoque mas **zero vendas nos últimos 90 dias**. "
        f"Total de **{total_unidades} unidades** imobilizadas sem giro."
    )

    fig = px.bar(
        parados.head(20),
        x="Em estoque", y="Produto", orientation="h",
        color="Categoria",
        title="Top 20 produtos parados (por quantidade em estoque)",
    )
    fig.update_layout(yaxis={"categoryorder": "total ascending"}, margin={"l": 260})
    st.plotly_chart(fig, use_container_width=True)

    # Parados por categoria
    cat_parados = parados.groupby("Categoria").agg(
        Produtos=("Produto", "count"),
        Unidades=("Em estoque", "sum"),
    ).sort_values("Unidades", ascending=False)
    st.dataframe(cat_parados, use_container_width=True)

    st.divider()
    cols = ["Produto", "Categoria", "Em estoque", "Na rua", "Total"]
    st.dataframe(parados[cols], use_container_width=True, hide_index=True)

    csv = parados[cols].to_csv(index=False).encode("utf-8")
    st.download_button("⬇️ Exportar parados (CSV)", csv, "estoque_parado.csv", "text/csv")


def _tab_velocidade(df, itens_vendidos, produtos_map, categorias_map):
    com_vendas = df[df["Vendas/dia"] > 0].copy()

    if com_vendas.empty:
        st.info("Sem dados de vendas para calcular velocidade.")
        return

    # Distribuição de giro
    bins   = [0, 1, 4, 12, float("inf")]
    labels = ["< 1 (muito lento)", "1–4 (lento)", "4–12 (normal)", "> 12 (rápido)"]
    com_vendas["Faixa de giro"] = pd.cut(com_vendas["Giro anual"], bins=bins, labels=labels)

    fig_pizza = px.pie(
        com_vendas.groupby("Faixa de giro", as_index=False).size(),
        names="Faixa de giro", values="size",
        title="Distribuição de giro anual dos produtos",
        color_discrete_sequence=["#c00", "#ffb300", "#66bb6a", "#1565c0"],
    )
    st.plotly_chart(fig_pizza, use_container_width=True)

    col_r, col_l = st.columns(2)
    cols_vel = ["Produto", "Categoria", "Vendas/dia", "Giro anual", "Cobertura (dias)"]

    with col_r:
        st.markdown("**⚡ 20 maiores velocidades de venda**")
        st.dataframe(
            com_vendas.nlargest(20, "Vendas/dia")[cols_vel],
            use_container_width=True, hide_index=True,
        )

    with col_l:
        st.markdown("**🐢 20 menores velocidades (com vendas)**")
        st.dataframe(
            com_vendas.nsmallest(20, "Vendas/dia")[cols_vel],
            use_container_width=True, hide_index=True,
        )

    st.divider()
    st.subheader("Top 10 estilos mais vendidos por categoria — últimos 90 dias")
    top_cat = top_vendidos_por_categoria(itens_vendidos, produtos_map, categorias_map, top_n=10)
    if top_cat:
        tabs = st.tabs(sorted(top_cat.keys())[:12])
        for tab, cat in zip(tabs, sorted(top_cat.keys())[:12]):
            with tab:
                top_df = top_cat[cat][["modelo", "total_vendido"]].copy()
                top_df.columns = ["Estilo", "Unidades vendidas"]
                fig = px.bar(
                    top_df, x="Unidades vendidas", y="Estilo", orientation="h",
                    color_discrete_sequence=["#AB6776"],
                )
                fig.update_layout(yaxis={"categoryorder": "total ascending"}, margin={"l": 220})
                st.plotly_chart(fig, use_container_width=True)


def _tab_busca(df):
    busca  = st.text_input("Nome do produto", placeholder="Ex: Argola Prata, Gota Dourado...")
    col_f1, col_f2 = st.columns(2)
    with col_f1:
        cat_f = st.multiselect("Categoria", sorted(df["Categoria"].unique()))
    with col_f2:
        status_f = st.multiselect("Status", sorted(df["Status"].unique()))

    df_f = df.copy()
    if busca:
        df_f = df_f[df_f["Produto"].str.contains(busca, case=False, na=False)]
    if cat_f:
        df_f = df_f[df_f["Categoria"].isin(cat_f)]
    if status_f:
        df_f = df_f[df_f["Status"].isin(status_f)]

    st.caption(f"{len(df_f)} produto(s) encontrado(s)")

    if df_f.empty:
        return

    cols = ["Produto", "Categoria", "Em estoque", "Na rua",
            "Vendas (90d)", "Cobertura (dias)", "Giro anual", "Status"]
    st.dataframe(
        df_f[cols].style.map(_cor_status, subset=["Status"]),
        use_container_width=True, hide_index=True,
    )

    csv = df_f[cols].to_csv(index=False).encode("utf-8")
    st.download_button("⬇️ Exportar busca (CSV)", csv, "busca_estoque.csv", "text/csv")


# ── Visão básica (sem velocidade carregada) ────────────────────────────────

def _visao_basica(df_base):
    n_crit = (df_base["Situação"] == "🔴 Crítico").sum()
    n_zer  = (df_base["Situação"] == "⚫ Zerado").sum()
    if n_crit: st.error(f"🔴 {n_crit} produto(s) abaixo do estoque mínimo cadastrado.")
    if n_zer:  st.warning(f"⚫ {n_zer} produto(s) com estoque zerado.")

    resumo = df_base.groupby("Categoria", as_index=False).agg(
        Em_estoque=("Em estoque", "sum"), Na_rua=("Na rua", "sum"),
    ).sort_values("Em_estoque", ascending=False)

    fig = px.bar(
        resumo, x="Categoria", y=["Em_estoque", "Na_rua"],
        barmode="stack",
        color_discrete_map={"Em_estoque": "#AB6776", "Na_rua": "#D4A0AA"},
        labels={"value": "Quantidade", "variable": ""},
        title="Estoque em depósito vs. com revendedoras",
    )
    fig.for_each_trace(lambda t: t.update(
        name={"Em_estoque": "Em estoque", "Na_rua": "Na rua"}.get(t.name, t.name)
    ))
    st.plotly_chart(fig, use_container_width=True)

    busca = st.text_input("Buscar produto", placeholder="Nome do produto...")
    df_f = df_base if not busca else df_base[
        df_base["Produto"].str.contains(busca, case=False, na=False)
    ]

    for cat in sorted(df_f["Categoria"].unique()):
        df_c = df_f[df_f["Categoria"] == cat].copy()
        n_c = (df_c["Situação"] == "🔴 Crítico").sum()
        n_z = (df_c["Situação"] == "⚫ Zerado").sum()
        badge = (f" 🔴 {n_c}" if n_c else "") + (f" ⚫ {n_z}" if n_z else "")
        with st.expander(f"**{cat}** ({len(df_c)} produtos){badge}", expanded=(n_c > 0)):
            m1, m2, m3 = st.columns(3)
            m1.metric("Em estoque", int(df_c["Em estoque"].sum()))
            m2.metric("Na rua", int(df_c["Na rua"].sum()))
            m3.metric("Total", int(df_c["Total"].sum()))
            cols = ["Produto", "Em estoque", "Na rua", "Total", "Mínimo", "Situação"]

            def _cor(val):
                if "Crítico" in str(val): return "background-color:#ffd6d6;color:#c00"
                if "Zerado"  in str(val): return "background-color:#eeeeee"
                if "Só na rua" in str(val): return "background-color:#fff9c4"
                return ""

            st.dataframe(
                df_c[cols].style.map(_cor, subset=["Situação"]),
                use_container_width=True, hide_index=True,
            )


# ── Ponto de entrada ───────────────────────────────────────────────────────

def render():
    st.header("Estoque")

    # Carrega dados básicos (rápido — usa cache)
    with st.spinner("Carregando estoque..."):
        try:
            produtos      = get_produtos(status="1")
            categorias_map = get_categorias()
            na_rua_map    = get_itens_pedidos_abertos()
        except Exception as e:
            st.error(f"Erro ao carregar dados: {e}")
            return

    if not produtos:
        st.warning("Nenhum produto ativo encontrado.")
        return

    df_base = montar_df_estoque(produtos, na_rua_map, categorias_map)

    # ── Métricas globais ──────────────────────────────────────────────────
    total_unid = int(df_base["Total"].sum())
    pct_rua    = int(df_base["Na rua"].sum() / max(total_unid, 1) * 100)

    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Produtos ativos",  len(df_base))
    m2.metric("Em depósito",      int(df_base["Em estoque"].sum()))
    m3.metric("Na rua",           int(df_base["Na rua"].sum()))
    m4.metric("Total geral",      total_unid)
    m5.metric("% na rua",         f"{pct_rua}%",
              help="Percentual do estoque total que está com revendedoras")

    st.divider()

    # ── Carregamento da análise de velocidade ─────────────────────────────
    tem_vel = "estoque_enriched" in st.session_state

    col_b1, col_b2, col_b3 = st.columns([2, 1, 2])
    with col_b1:
        if not tem_vel:
            if st.button("📊 Carregar análise completa de vendas", type="primary",
                         help="Busca histórico de 90 dias para calcular cobertura, giro e produtos parados"):
                with st.spinner("Buscando histórico de vendas (aguarde)..."):
                    try:
                        itens = get_itens_pedidos_baixados(dias=_DIAS_HIST)
                        st.session_state["estoque_enriched"] = _enriquecer(df_base, itens)
                        st.session_state["estoque_itens"]    = itens
                        st.rerun()
                    except Exception as e:
                        st.error(f"Erro: {e}")
        else:
            if st.button("🔄 Atualizar análise"):
                del st.session_state["estoque_enriched"]
                del st.session_state["estoque_itens"]
                st.rerun()

    if not tem_vel:
        st.info(
            "Clique em **Carregar análise completa** para ver: "
            "cobertura em dias, produtos parados, giro de estoque e alertas de ruptura."
        )
        _visao_basica(df_base)
        return

    df = st.session_state["estoque_enriched"]

    # ── Painel de alertas ─────────────────────────────────────────────────
    st.subheader("Situação atual do estoque")
    n_rupt, n_aten, n_par, n_rua, n_zer = _painel_alertas(df)

    if n_rupt > 0:
        st.error(
            f"⚠️ {n_rupt} produto(s) com **ruptura iminente** (menos de {_CRITICO_D} dias de estoque). "
            "Acesse a aba **⚠️ Alertas** para ver a lista."
        )

    # ── Abas principais ───────────────────────────────────────────────────
    st.divider()
    tab_al, tab_cat, tab_par, tab_vel, tab_bus = st.tabs([
        f"⚠️ Alertas  ({n_rupt + n_aten})",
        "📦 Por categoria",
        f"🐌 Parados  ({n_par})",
        "⚡ Velocidade de venda",
        "🔍 Busca",
    ])

    with tab_al:
        _tab_alertas(df)

    with tab_cat:
        _tab_categorias(df)

    with tab_par:
        _tab_parados(df)

    with tab_vel:
        produtos_map = {p["id"]: p for p in produtos}
        _tab_velocidade(df, st.session_state["estoque_itens"], produtos_map, categorias_map)

    with tab_bus:
        _tab_busca(df)
