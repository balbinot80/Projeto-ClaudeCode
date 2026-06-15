import streamlit as st
import pandas as pd
import plotly.express as px
from src.api.jueri_client import get_produtos


def render():
    st.title("📦 Controle de Estoque")

    try:
        with st.spinner("Carregando produtos..."):
            produtos = get_produtos()
    except Exception as e:
        st.error(f"Erro ao carregar produtos: {e}")
        return

    if not produtos:
        st.warning("Nenhum produto encontrado.")
        return

    df = pd.DataFrame([{
        "ID": p.get("id"),
        "Produto": p.get("descricao", ""),
        "Referência": p.get("referencia", ""),
        "Nº Peça": p.get("numero_peca", ""),
        "Estoque": p.get("quantidade", 0),
        "Mínimo": p.get("estoque_minimo") or 0,
        "Máximo": p.get("estoque_maximo") or 0,
        "Localização": p.get("localizacao", ""),
    } for p in produtos])

    df["Estoque"] = pd.to_numeric(df["Estoque"], errors="coerce").fillna(0).astype(int)
    df["Mínimo"] = pd.to_numeric(df["Mínimo"], errors="coerce").fillna(0).astype(int)
    df["Máximo"] = pd.to_numeric(df["Máximo"], errors="coerce").fillna(0).astype(int)

    abaixo_minimo = df[df["Estoque"] < df["Mínimo"]]
    acima_maximo = df[(df["Máximo"] > 0) & (df["Estoque"] > df["Máximo"])]
    ok = df[(df["Estoque"] >= df["Mínimo"]) & ((df["Máximo"] == 0) | (df["Estoque"] <= df["Máximo"]))]

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total de produtos", len(df))
    col2.metric("🔴 Abaixo do mínimo", len(abaixo_minimo))
    col3.metric("🟡 Acima do máximo", len(acima_maximo))
    col4.metric("✅ Dentro do ideal", len(ok))

    st.divider()

    filtro = st.radio("Filtrar por:", ["Todos", "🔴 Abaixo do mínimo", "🟡 Acima do máximo", "✅ OK"], horizontal=True)
    busca = st.text_input("Buscar produto", placeholder="Nome, referência ou nº da peça...")

    if filtro == "🔴 Abaixo do mínimo":
        df_exibir = abaixo_minimo.copy()
    elif filtro == "🟡 Acima do máximo":
        df_exibir = acima_maximo.copy()
    elif filtro == "✅ OK":
        df_exibir = ok.copy()
    else:
        df_exibir = df.copy()

    if busca:
        mask = (
            df_exibir["Produto"].str.contains(busca, case=False, na=False) |
            df_exibir["Referência"].str.contains(busca, case=False, na=False) |
            df_exibir["Nº Peça"].str.contains(busca, case=False, na=False)
        )
        df_exibir = df_exibir[mask]

    def colorir_linha(row):
        if row["Estoque"] < row["Mínimo"]:
            return ["background-color: #ffcccc"] * len(row)
        elif row["Máximo"] > 0 and row["Estoque"] > row["Máximo"]:
            return ["background-color: #fff3cd"] * len(row)
        return [""] * len(row)

    st.dataframe(
        df_exibir.style.apply(colorir_linha, axis=1),
        use_container_width=True,
        hide_index=True,
    )

    st.divider()
    st.subheader("Distribuição do estoque")

    top20 = df.nlargest(20, "Estoque")
    fig = px.bar(
        top20,
        x="Produto",
        y="Estoque",
        color="Estoque",
        color_continuous_scale="RdYlGn",
        title="Top 20 produtos com maior estoque",
    )
    fig.update_layout(xaxis_tickangle=-45)
    st.plotly_chart(fig, use_container_width=True)
