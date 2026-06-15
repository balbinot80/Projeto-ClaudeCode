import streamlit as st
import plotly.express as px
from datetime import datetime, timedelta
from src.api.jueri_client import get_produtos, get_vendas
from src.logic.compras import sugerir_compras, calcular_velocidade_vendas


def render():
    st.title("🛒 Programação de Compras")

    col1, col2 = st.columns(2)
    with col1:
        dias_cobertura = st.slider("Dias de cobertura desejados", 30, 180, 60,
                                   help="Quantos dias de estoque você quer ter após a compra")
    with col2:
        dias_historico = st.slider("Histórico de vendas (dias)", 30, 180, 90,
                                   help="Período usado para calcular a velocidade de vendas")

    data_inicial = (datetime.now() - timedelta(days=dias_historico)).strftime("%Y-%m-%d")
    data_final = datetime.now().strftime("%Y-%m-%d")

    try:
        with st.spinner("Carregando dados..."):
            produtos = get_produtos()
            vendas = get_vendas(data_inicial=data_inicial, data_final=data_final)
    except Exception as e:
        st.error(f"Erro ao carregar dados: {e}")
        return

    st.info(f"Analisando {len(produtos)} produtos e {len(vendas)} vendas dos últimos {dias_historico} dias.")

    df = sugerir_compras(produtos, vendas, dias_cobertura=dias_cobertura, dias_historico=dias_historico)

    apenas_necessarios = st.checkbox("Mostrar apenas produtos que precisam de compra", value=True)
    if apenas_necessarios:
        df_exibir = df[df["Sugestão de compra"] > 0].copy()
    else:
        df_exibir = df.copy()

    busca = st.text_input("Buscar produto", placeholder="Nome do produto...")
    if busca:
        df_exibir = df_exibir[df_exibir["Produto"].str.contains(busca, case=False, na=False)]

    st.subheader(f"📋 {len(df_exibir)} produtos para comprar")

    col1, col2, col3 = st.columns(3)
    col1.metric("🔴 Críticos (abaixo do mínimo)", len(df[df["Status"] == "🔴 Crítico"]))
    col2.metric("🟡 Atenção (< 30 dias)", len(df[df["Status"] == "🟡 Atenção"]))
    col3.metric("🟢 Planejar", len(df[df["Status"] == "🟢 Planejar"]))

    st.dataframe(df_exibir, use_container_width=True, hide_index=True)

    if not df_exibir.empty:
        csv = df_exibir.to_csv(index=False).encode("utf-8")
        st.download_button(
            "⬇️ Exportar lista de compras (CSV)",
            csv,
            f"compras_{datetime.now().strftime('%Y%m%d')}.csv",
            "text/csv",
        )

    st.divider()
    st.subheader("📈 Peças mais vendidas no período")

    vel = calcular_velocidade_vendas(vendas, dias=dias_historico)
    if not vel.empty:
        top15 = vel.head(15)
        fig = px.bar(
            top15,
            x="descricao",
            y="total_vendido",
            title=f"Top 15 peças mais vendidas (últimos {dias_historico} dias)",
            labels={"descricao": "Produto", "total_vendido": "Unidades vendidas"},
            color="total_vendido",
            color_continuous_scale="Blues",
        )
        fig.update_layout(xaxis_tickangle=-45)
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Sem dados de vendas no período para exibir o ranking.")
