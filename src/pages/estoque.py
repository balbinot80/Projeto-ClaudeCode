import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta

from src.api.jueri_client import (
    get_produtos, get_pedidos_abertos, get_categorias,
    get_vendas, get_pedidos_baixados
)
from src.logic.estoque import montar_df_estoque
from src.logic.compras import extrair_itens_vendidos, top_vendidos_por_categoria


def render():
    st.header("Estoque")

    with st.spinner("Carregando dados de estoque..."):
        try:
            produtos = get_produtos(status="1")
            pedidos_abertos = get_pedidos_abertos()
            categorias_map = get_categorias()
            hoje = datetime.today()
            data_ini = (hoje - timedelta(days=180)).strftime("%Y-%m-%d")
            data_fim = hoje.strftime("%Y-%m-%d")
            vendas = get_vendas(data_ini, data_fim)
            baixados = get_pedidos_baixados(data_ini, data_fim)
        except Exception as e:
            st.error(f"Erro ao carregar dados: {e}")
            return

    if not produtos:
        st.warning("Nenhum produto ativo encontrado.")
        return

    df = montar_df_estoque(produtos, pedidos_abertos, categorias_map)

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Produtos ativos", len(df))
    col2.metric("Em estoque", int(df["Em estoque"].sum()))
    col3.metric("Na rua", int(df["Na rua"].sum()))
    col4.metric("Total geral", int(df["Total"].sum()))

    st.divider()

    # Filtros
    categorias = sorted(df["Categoria"].unique())
    col_f1, col_f2 = st.columns(2)
    with col_f1:
        cat_sel = st.multiselect("Filtrar por categoria", categorias)
    with col_f2:
        situacoes = sorted(df["Situação"].unique())
        sit_sel = st.multiselect("Filtrar por situação", situacoes)

    df_filtrado = df.copy()
    if cat_sel:
        df_filtrado = df_filtrado[df_filtrado["Categoria"].isin(cat_sel)]
    if sit_sel:
        df_filtrado = df_filtrado[df_filtrado["Situação"].isin(sit_sel)]

    busca = st.text_input("Buscar produto", placeholder="Nome do produto...")
    if busca:
        df_filtrado = df_filtrado[df_filtrado["Produto"].str.contains(busca, case=False, na=False)]

    # Gráfico por categoria
    st.subheader("Estoque por categoria")
    resumo_cat = df.groupby("Categoria", as_index=False).agg(
        Em_estoque=("Em estoque", "sum"),
        Na_rua=("Na rua", "sum"),
    ).sort_values("Em_estoque", ascending=False)

    fig = px.bar(
        resumo_cat,
        x="Categoria",
        y=["Em_estoque", "Na_rua"],
        barmode="stack",
        labels={"value": "Quantidade", "variable": ""},
        color_discrete_map={"Em_estoque": "#AB6776", "Na_rua": "#D4A0AA"},
        title="Em depósito vs. com revendedoras",
    )
    fig.for_each_trace(lambda t: t.update(
        name={"Em_estoque": "Em estoque", "Na_rua": "Na rua"}.get(t.name, t.name)
    ))
    st.plotly_chart(fig, use_container_width=True)

    # Top 10 mais vendidos por categoria
    st.subheader("Top 10 mais vendidos por categoria — últimos 6 meses")
    produtos_map = {p["id"]: p for p in produtos}
    itens_df = extrair_itens_vendidos(vendas, baixados, produtos_map)
    top_por_cat = top_vendidos_por_categoria(itens_df, categorias_map, top_n=10)

    if top_por_cat:
        cats_com_vendas = sorted(top_por_cat.keys())
        exibir_cats = cats_com_vendas[:12]
        tabs = st.tabs(exibir_cats)
        for tab, cat in zip(tabs, exibir_cats):
            with tab:
                top_df = top_por_cat[cat][["descricao", "total_vendido"]].copy()
                top_df.columns = ["Produto", "Total vendido"]
                fig2 = px.bar(
                    top_df,
                    x="Total vendido",
                    y="Produto",
                    orientation="h",
                    color_discrete_sequence=["#AB6776"],
                )
                fig2.update_layout(yaxis={"categoryorder": "total ascending"}, margin={"l": 180})
                st.plotly_chart(fig2, use_container_width=True)
    else:
        st.info("Sem histórico de vendas nos últimos 6 meses.")

    # Tabela por categoria
    st.divider()
    st.subheader("Detalhamento por categoria")

    for cat in sorted(df_filtrado["Categoria"].unique()):
        df_cat = df_filtrado[df_filtrado["Categoria"] == cat].drop(columns="Categoria").copy()
        criticos = (df_cat["Situação"] == "🔴 Crítico").sum()
        zerados = (df_cat["Situação"] == "⚫ Zerado").sum()

        badge = ""
        if criticos:
            badge = f" — {criticos} crítico(s) 🔴"
        elif zerados:
            badge = f" — {zerados} zerado(s) ⚫"

        with st.expander(f"**{cat}** ({len(df_cat)} produtos){badge}", expanded=(criticos > 0)):
            c1, c2, c3 = st.columns(3)
            c1.metric("Em estoque", int(df_cat["Em estoque"].sum()))
            c2.metric("Na rua", int(df_cat["Na rua"].sum()))
            c3.metric("Total", int(df_cat["Total"].sum()))

            def _cor_cel(val):
                if "Crítico" in str(val):
                    return "background-color: #ffd6d6; color: #c00"
                if "Zerado" in str(val):
                    return "background-color: #e0e0e0"
                if "Só na rua" in str(val):
                    return "background-color: #fff3cd"
                return ""

            st.dataframe(
                df_cat.style.applymap(_cor_cel, subset=["Situação"]),
                use_container_width=True,
                hide_index=True,
            )
