import streamlit as st
import pandas as pd
import plotly.express as px
from src.api.jueri_client import get_revendedores, get_vendas
from datetime import datetime, timedelta


def render():
    st.title("👥 Gestão de Revendedoras")

    with st.spinner("Carregando revendedoras..."):
        todos = get_revendedores()

    if not todos:
        st.warning("Nenhuma revendedora encontrada.")
        return

    df = pd.DataFrame([{
        "ID": r.get("id"),
        "Nome": r.get("nome", ""),
        "CPF": r.get("cpf", ""),
        "Telefone": r.get("telefone", ""),
        "E-mail": r.get("email", ""),
        "Cidade": r.get("cidade", ""),
        "Estado": r.get("estado", ""),
        "Status": "✅ Ativa" if str(r.get("fk_status_id", "1")) == "1" else "❌ Inativa",
        "Cadastro": r.get("data_criacao", "")[:10] if r.get("data_criacao") else "",
    } for r in todos])

    ativas = df[df["Status"] == "✅ Ativa"]
    inativas = df[df["Status"] == "❌ Inativa"]

    col1, col2, col3 = st.columns(3)
    col1.metric("Total de revendedoras", len(df))
    col2.metric("✅ Ativas", len(ativas))
    col3.metric("❌ Inativas", len(inativas))

    st.divider()

    filtro_status = st.radio("Exibir:", ["Todas", "✅ Ativas", "❌ Inativas"], horizontal=True)
    busca = st.text_input("Buscar revendedora", placeholder="Nome, CPF ou cidade...")

    if filtro_status == "✅ Ativas":
        df_exibir = ativas.copy()
    elif filtro_status == "❌ Inativas":
        df_exibir = inativas.copy()
    else:
        df_exibir = df.copy()

    if busca:
        mask = (
            df_exibir["Nome"].str.contains(busca, case=False, na=False) |
            df_exibir["CPF"].str.contains(busca, case=False, na=False) |
            df_exibir["Cidade"].str.contains(busca, case=False, na=False)
        )
        df_exibir = df_exibir[mask]

    st.dataframe(df_exibir, use_container_width=True, hide_index=True)

    st.divider()
    st.subheader("📊 Crescimento da equipe ao longo do tempo")

    df_tempo = df[df["Cadastro"] != ""].copy()
    if not df_tempo.empty:
        df_tempo["Cadastro"] = pd.to_datetime(df_tempo["Cadastro"], errors="coerce")
        df_tempo = df_tempo.dropna(subset=["Cadastro"])
        df_tempo["Mes"] = df_tempo["Cadastro"].dt.to_period("M").astype(str)
        crescimento = df_tempo.groupby("Mes").size().reset_index(name="Novas revendedoras")
        crescimento["Acumulado"] = crescimento["Novas revendedoras"].cumsum()

        fig = px.bar(
            crescimento,
            x="Mes",
            y="Novas revendedoras",
            title="Novas revendedoras por mês",
            labels={"Mes": "Mês"},
        )
        st.plotly_chart(fig, use_container_width=True)

        fig2 = px.line(
            crescimento,
            x="Mes",
            y="Acumulado",
            title="Crescimento acumulado da equipe",
            markers=True,
        )
        st.plotly_chart(fig2, use_container_width=True)

    st.divider()
    st.subheader("🏆 Ranking de vendas por revendedora (últimos 90 dias)")

    data_inicial = (datetime.now() - timedelta(days=90)).strftime("%Y-%m-%d")
    data_final = datetime.now().strftime("%Y-%m-%d")

    with st.spinner("Carregando vendas..."):
        vendas = get_vendas(data_inicial=data_inicial, data_final=data_final)

    if vendas:
        rev_map = {str(r.get("id")): r.get("nome", f"ID {r.get('id')}") for r in todos}
        ranking = {}
        for v in vendas:
            rid = str(v.get("fk_revendedor_id") or v.get("revendedor_id", ""))
            nome = rev_map.get(rid, f"Revendedora {rid}")
            total = sum(float(i.get("valor_total", 0)) for i in v.get("itens", []))
            ranking[nome] = ranking.get(nome, 0) + total

        if ranking:
            df_rank = pd.DataFrame(
                [{"Revendedora": k, "Total vendido (R$)": round(v, 2)} for k, v in ranking.items()]
            ).sort_values("Total vendido (R$)", ascending=False).head(20)

            fig3 = px.bar(
                df_rank,
                x="Revendedora",
                y="Total vendido (R$)",
                title="Top 20 revendedoras por volume de vendas",
                color="Total vendido (R$)",
                color_continuous_scale="Greens",
            )
            fig3.update_layout(xaxis_tickangle=-45)
            st.plotly_chart(fig3, use_container_width=True)
    else:
        st.info("Sem dados de vendas no período.")
