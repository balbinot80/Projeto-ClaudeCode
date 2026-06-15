import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta
from src.api.jueri_client import get_revendedores, get_pedidos_abertos, get_vendas


def render():
    st.header("Revendedoras")

    with st.spinner("Carregando dados..."):
        try:
            todos = get_revendedores()
            pedidos_abertos = get_pedidos_abertos()
            data_ini = (datetime.now() - timedelta(days=180)).strftime("%Y-%m-%d")
            data_fim = datetime.now().strftime("%Y-%m-%d")
            vendas = get_vendas(data_inicial=data_ini, data_final=data_fim)
        except Exception as e:
            st.error(f"Erro ao carregar dados: {e}")
            return

    if not todos:
        st.warning("Nenhuma revendedora encontrada.")
        return

    # IDs de revendedoras com pedido aberto
    ids_com_pedido = {
        str(p.get("fk_revendedor_id") or p.get("revendedor_id", ""))
        for p in pedidos_abertos
    } - {""}

    # IDs de revendedoras com venda nos últimos 6 meses
    ids_com_venda = {
        str(v.get("fk_revendedor_id") or v.get("revendedor_id", ""))
        for v in vendas
    } - {""}

    rows = []
    for r in todos:
        rid = str(r.get("id", ""))
        ativo_api = str(r.get("fk_status_id", "1")) == "1"
        tem_pedido = rid in ids_com_pedido
        tem_venda = rid in ids_com_venda

        if not ativo_api:
            grupo = "Inativa"
        elif tem_pedido:
            grupo = "Com pedido aberto"
        elif tem_venda:
            grupo = "Ativa sem pedido (com histórico)"
        else:
            grupo = "Ativa sem pedido"

        rows.append({
            "ID": rid,
            "Nome": r.get("nome", ""),
            "Telefone": r.get("telefone", ""),
            "Cidade": r.get("cidade", ""),
            "Estado": r.get("estado", ""),
            "Cadastro": (r.get("data_criacao") or "")[:10],
            "Situação": grupo,
        })

    df = pd.DataFrame(rows)

    com_pedido = df[df["Situação"] == "Com pedido aberto"]
    ativa_sem_hist = df[df["Situação"] == "Ativa sem pedido (com histórico)"]
    ativa_sem = df[df["Situação"] == "Ativa sem pedido"]
    inativas = df[df["Situação"] == "Inativa"]

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Com pedido aberto", len(com_pedido), help="Estão ativamente com peças na rua")
    col2.metric("Ativas com histórico", len(ativa_sem_hist), help="Sem pedido aberto, mas compraram nos últimos 6 meses")
    col3.metric("Ativas sem atividade", len(ativa_sem), help="Sem pedido e sem venda nos últimos 6 meses")
    col4.metric("Inativas", len(inativas))

    st.divider()

    # Seção: com pedido aberto
    st.subheader("Com pedido aberto")
    st.caption("Revendedoras que possuem peças na rua agora.")

    busca_ativas = st.text_input("Buscar", placeholder="Nome, cidade...", key="busca_ativas")
    df_com = com_pedido.copy()
    if busca_ativas:
        mask = df_com["Nome"].str.contains(busca_ativas, case=False, na=False) | \
               df_com["Cidade"].str.contains(busca_ativas, case=False, na=False)
        df_com = df_com[mask]
    st.dataframe(df_com.drop(columns="Situação"), use_container_width=True, hide_index=True)

    # Seção: ativas sem pedido
    st.divider()
    with st.expander(f"**Ativas com histórico de vendas, sem pedido aberto** ({len(ativa_sem_hist)})",
                     expanded=False):
        st.caption("Compraram nos últimos 6 meses mas não têm pedido aberto no momento.")
        st.dataframe(ativa_sem_hist.drop(columns="Situação"), use_container_width=True, hide_index=True)

    with st.expander(f"**Ativas sem atividade recente** ({len(ativa_sem)})", expanded=False):
        st.caption("Cadastro ativo mas sem pedido e sem venda nos últimos 6 meses. Requer atenção.")
        st.dataframe(ativa_sem.drop(columns="Situação"), use_container_width=True, hide_index=True)

    with st.expander(f"**Inativas** ({len(inativas)})", expanded=False):
        st.dataframe(inativas.drop(columns="Situação"), use_container_width=True, hide_index=True)

    # Gráfico de crescimento
    st.divider()
    st.subheader("Crescimento da equipe ao longo do tempo")

    df_tempo = df[df["Cadastro"] != ""].copy()
    if not df_tempo.empty:
        df_tempo["Cadastro"] = pd.to_datetime(df_tempo["Cadastro"], errors="coerce")
        df_tempo = df_tempo.dropna(subset=["Cadastro"])
        df_tempo["Mês"] = df_tempo["Cadastro"].dt.to_period("M").astype(str)
        crescimento = df_tempo.groupby("Mês").size().reset_index(name="Novas")
        crescimento["Acumulado"] = crescimento["Novas"].cumsum()

        fig = px.bar(crescimento, x="Mês", y="Novas",
                     title="Novas revendedoras por mês",
                     color_discrete_sequence=["#AB6776"])
        st.plotly_chart(fig, use_container_width=True)

        fig2 = px.line(crescimento, x="Mês", y="Acumulado",
                       title="Crescimento acumulado da equipe", markers=True,
                       color_discrete_sequence=["#AB6776"])
        st.plotly_chart(fig2, use_container_width=True)

    # Ranking de vendas
    st.divider()
    st.subheader("Ranking de vendas — últimos 6 meses")

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
                df_rank, x="Revendedora", y="Total vendido (R$)",
                title="Top 20 por volume de vendas",
                color_discrete_sequence=["#AB6776"],
            )
            fig3.update_layout(xaxis_tickangle=-45)
            st.plotly_chart(fig3, use_container_width=True)
    else:
        st.info("Sem dados de vendas no período.")
