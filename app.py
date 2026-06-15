import os
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

st.set_page_config(
    page_title="Aureum Joias - Gestão",
    page_icon="💍",
    layout="wide",
    initial_sidebar_state="expanded",
)

def _get_secret(key: str, default: str = "") -> str:
    try:
        return st.secrets[key]
    except Exception:
        return os.getenv(key, default)

APP_PASSWORD = _get_secret("APP_PASSWORD", "aureum2024")

if "autenticado" not in st.session_state:
    st.session_state.autenticado = False

if not st.session_state.autenticado:
    st.title("💍 Aureum Joias - Sistema de Gestão")
    st.subheader("Acesso restrito")
    senha = st.text_input("Senha", type="password")
    if st.button("Entrar"):
        if senha == APP_PASSWORD:
            st.session_state.autenticado = True
            st.rerun()
        else:
            st.error("Senha incorreta.")
    st.stop()


def render_dashboard():
    from src.api.jueri_client import get_produtos, get_revendedores, get_vendas
    from datetime import datetime, timedelta
    import pandas as pd

    st.title("🏠 Dashboard — Visão Geral")

    try:
        with st.spinner("Carregando dados..."):
            produtos = get_produtos()
            revendedores = get_revendedores()
            data_ini = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
            vendas_30d = get_vendas(data_inicial=data_ini)
    except Exception as e:
        st.error(f"Erro ao conectar com a API Jueri: {e}")
        st.info("Aguarde alguns instantes e clique em **🔄 Atualizar dados** no menu lateral.")
        return

    col1, col2, col3, col4 = st.columns(4)

    qtds = pd.to_numeric(
        pd.DataFrame([{"qtd": p.get("quantidade", 0), "min": p.get("estoque_minimo") or 0} for p in produtos])["qtd"],
        errors="coerce",
    ).fillna(0)
    mins = pd.to_numeric(
        pd.DataFrame([{"qtd": p.get("quantidade", 0), "min": p.get("estoque_minimo") or 0} for p in produtos])["min"],
        errors="coerce",
    ).fillna(0)
    criticos = int((qtds < mins).sum())

    col1.metric("Total de produtos", len(produtos))
    col2.metric("🔴 Estoque crítico", criticos)
    col3.metric("👥 Revendedoras ativas",
                sum(1 for r in revendedores if str(r.get("fk_status_id", "1")) == "1"))
    col4.metric("📦 Vendas (30 dias)", len(vendas_30d))

    st.divider()

    if criticos > 0:
        st.error(
            f"⚠️ {criticos} produto(s) estão abaixo do estoque mínimo! "
            "Acesse **Programação de Compras** para ver as sugestões."
        )

    st.info("Use o menu lateral para navegar entre os módulos do sistema.")


# Sidebar de navegação
with st.sidebar:
    st.title("💍 Aureum Joias")
    st.caption("Sistema de Gestão")
    st.divider()

    pagina = st.radio(
        "Navegação",
        ["🏠 Dashboard", "📦 Estoque", "🛒 Programação de Compras", "👥 Revendedoras"],
    )

    st.divider()
    if st.button("🔄 Atualizar dados"):
        from src.api.jueri_client import limpar_cache
        limpar_cache()
        st.success("Cache limpo! Dados serão recarregados.")
        st.rerun()

    if st.button("🚪 Sair"):
        st.session_state.autenticado = False
        st.rerun()

# Roteamento de páginas
if pagina == "🏠 Dashboard":
    render_dashboard()
elif pagina == "📦 Estoque":
    from src.pages.estoque import render
    render()
elif pagina == "🛒 Programação de Compras":
    from src.pages.compras import render
    render()
elif pagina == "👥 Revendedoras":
    from src.pages.revendedoras import render
    render()
