import streamlit as st
import plotly.express as px
from datetime import datetime, timedelta
from src.api.jueri_client import (
    get_produtos, get_vendas, get_pedidos_baixados,
    get_pedidos_abertos, get_categorias
)
from src.logic.compras import sugerir_compras, extrair_itens_vendidos, top_vendidos_por_categoria


def render():
    st.header("Programação de Compras")

    col1, col2 = st.columns(2)
    with col1:
        dias_cobertura = st.slider(
            "Dias de cobertura desejados", 30, 180, 60,
            help="Quantidade de dias de estoque que você quer ter após a compra"
        )
    with col2:
        dias_historico = st.slider(
            "Histórico de vendas (dias)", 90, 365, 180,
            help="Período para calcular a velocidade de vendas. Padrão: 6 meses"
        )

    data_ini = (datetime.now() - timedelta(days=dias_historico)).strftime("%Y-%m-%d")
    data_fim = datetime.now().strftime("%Y-%m-%d")

    with st.spinner("Carregando dados..."):
        try:
            produtos = get_produtos(status="1")
            vendas = get_vendas(data_inicial=data_ini, data_final=data_fim)
            baixados = get_pedidos_baixados(data_inicial=data_ini, data_final=data_fim)
            pedidos_abertos = get_pedidos_abertos()
            categorias_map = get_categorias()
        except Exception as e:
            st.error(f"Erro ao carregar dados: {e}")
            return

    st.info(
        f"{len(produtos)} produtos ativos · {len(vendas)} vendas · "
        f"{len(baixados)} pedidos baixados nos últimos {dias_historico} dias"
    )

    df = sugerir_compras(
        produtos, vendas, baixados, pedidos_abertos, categorias_map,
        dias_cobertura=dias_cobertura, dias_historico=dias_historico
    )

    if df.empty:
        st.warning("Nenhum produto com necessidade de compra identificado no período.")
        return

    # Métricas gerais
    col1, col2, col3 = st.columns(3)
    col1.metric("Críticos", len(df[df["Status"] == "🔴 Crítico"]))
    col2.metric("Atenção (< 30 dias)", len(df[df["Status"] == "🟡 Atenção"]))
    col3.metric("Planejar", len(df[df["Status"] == "🟢 Planejar"]))

    # Filtros
    st.divider()
    apenas_necessarios = st.checkbox("Mostrar apenas produtos que precisam de compra", value=True)
    if apenas_necessarios:
        df_exibir = df[df["Sugestão de compra"] > 0].copy()
    else:
        df_exibir = df.copy()

    col_f1, col_f2 = st.columns(2)
    with col_f1:
        cats = sorted(df_exibir["Categoria"].unique())
        cat_sel = st.multiselect("Filtrar por categoria", cats)
        if cat_sel:
            df_exibir = df_exibir[df_exibir["Categoria"].isin(cat_sel)]
    with col_f2:
        busca = st.text_input("Buscar produto", placeholder="Nome do modelo...")
        if busca:
            df_exibir = df_exibir[df_exibir["Produto"].str.contains(busca, case=False, na=False)]

    # Tabela por categoria
    st.subheader(f"{len(df_exibir)} produtos na lista de compras")

    for cat in sorted(df_exibir["Categoria"].unique()):
        df_cat = df_exibir[df_exibir["Categoria"] == cat].drop(columns="Categoria").copy()
        criticos = (df_cat["Status"] == "🔴 Crítico").sum()

        badge = f" — {criticos} crítico(s) 🔴" if criticos else ""
        with st.expander(f"**{cat}** ({len(df_cat)} itens){badge}", expanded=(criticos > 0)):
            total_sugerido = int(df_cat["Sugestão de compra"].sum())
            st.caption(f"Total sugerido para compra nesta categoria: **{total_sugerido} unidades**")

            def _cor(val):
                if "Crítico" in str(val):
                    return "background-color: #ffd6d6; color: #c00"
                if "Atenção" in str(val):
                    return "background-color: #fff3cd"
                return ""

            st.dataframe(
                df_cat.style.applymap(_cor, subset=["Status"]),
                use_container_width=True,
                hide_index=True,
            )

    # Exportação
    if not df_exibir.empty:
        csv = df_exibir.to_csv(index=False).encode("utf-8")
        st.download_button(
            "Exportar lista de compras (CSV)",
            csv,
            f"compras_{datetime.now().strftime('%Y%m%d')}.csv",
            "text/csv",
        )

    # Top 10 por categoria
    st.divider()
    st.subheader(f"Modelos mais vendidos por categoria — últimos {dias_historico} dias")
    st.caption("Use este ranking para priorizar os modelos na hora de comprar.")

    produtos_map = {p["id"]: p for p in produtos}
    itens_df = extrair_itens_vendidos(vendas, baixados, produtos_map)
    top_por_cat = top_vendidos_por_categoria(itens_df, categorias_map, top_n=10)

    if top_por_cat:
        cats_com_vendas = sorted(top_por_cat.keys())
        tabs = st.tabs(cats_com_vendas[:12])
        for tab, cat in zip(tabs, cats_com_vendas[:12]):
            with tab:
                top_df = top_por_cat[cat][["descricao", "total_vendido"]].copy()
                top_df.columns = ["Modelo", "Unidades vendidas"]
                fig = px.bar(
                    top_df,
                    x="Unidades vendidas",
                    y="Modelo",
                    orientation="h",
                    color_discrete_sequence=["#AB6776"],
                    title=f"Top 10 modelos — {cat}",
                )
                fig.update_layout(yaxis={"categoryorder": "total ascending"}, margin={"l": 200})
                st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Sem histórico de vendas no período para exibir ranking.")
