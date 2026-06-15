import streamlit as st
import json
from src.api.jueri_client import get_pedidos_abertos, get_pedidos_baixados


def render():
    st.header("🔍 Diagnóstico da API")
    st.caption("Página temporária para verificar a estrutura dos dados retornados pela API.")

    st.subheader("Pedidos Baixados")
    with st.spinner("Buscando pedidos baixados..."):
        try:
            baixados = get_pedidos_baixados()
        except Exception as e:
            st.error(f"Erro ao buscar pedidos baixados: {e}")
            baixados = []

    st.metric("Total de pedidos baixados", len(baixados))

    if baixados:
        primeiro = baixados[0]
        st.write("**Campos disponíveis no primeiro pedido:**")
        st.code(json.dumps(list(primeiro.keys()), ensure_ascii=False, indent=2))

        st.write("**Conteúdo completo do primeiro pedido:**")
        st.json(primeiro)

        # Verifica presença de itens
        tem_itens = sum(1 for p in baixados if p.get("itens"))
        st.metric("Pedidos com campo 'itens' preenchido", tem_itens)
    else:
        st.warning("Nenhum pedido baixado retornado. Verifique se o status 'Baixado' está correto.")

    st.divider()
    st.subheader("Pedidos Abertos")
    with st.spinner("Buscando pedidos abertos..."):
        try:
            abertos = get_pedidos_abertos()
        except Exception as e:
            st.error(f"Erro ao buscar pedidos abertos: {e}")
            abertos = []

    st.metric("Total de pedidos abertos", len(abertos))

    if abertos:
        primeiro_aberto = abertos[0]
        st.write("**Conteúdo completo do primeiro pedido aberto:**")
        st.json(primeiro_aberto)

        tem_itens = sum(1 for p in abertos if p.get("itens"))
        st.metric("Pedidos abertos com campo 'itens' preenchido", tem_itens)
