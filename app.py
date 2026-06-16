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


# Informações dos usuários — senhas ficam apenas no Streamlit Cloud Secrets
_USUARIOS = {
    "admin": {
        "nome": "Administrador",
        "role": "admin",
        "supervisor_nome": "",
        "secret_key": "ADMIN_SENHA",
    },
    "yasmim": {
        "nome": "Yasmim Evellyn Ferreira",
        "role": "supervisora",
        "supervisor_nome": "Yasmim Evellyn Ferreira",
        "secret_key": "YASMIM_SENHA",
    },
    "julia": {
        "nome": "Julia Andreza de Souza",
        "role": "supervisora",
        "supervisor_nome": "Julia Andreza de Souza",
        "secret_key": "JULIA_SENHA",
    },
}


def _autenticar(login: str, senha: str):
    login = login.strip().lower()
    if login not in _USUARIOS:
        return None

    info = _USUARIOS[login]
    # Tenta a chave específica do usuário; fallback para APP_PASSWORD no admin
    senha_correta = _get_secret(info["secret_key"], "")
    if not senha_correta and login == "admin":
        senha_correta = _get_secret("APP_PASSWORD", "")

    if senha_correta and senha == senha_correta:
        return {
            "login": login,
            "nome": info["nome"],
            "role": info["role"],
            "supervisor_nome": info["supervisor_nome"],
        }
    return None


# ── Tela de login ──────────────────────────────────────────────────────────────

if "autenticado" not in st.session_state:
    st.session_state.autenticado = False
    st.session_state.usuario = {}

if not st.session_state.autenticado:
    col_c, col_f, col_c2 = st.columns([2, 3, 2])
    with col_f:
        st.title("💍 Aureum Joias")
        st.subheader("Sistema de Gestão")
        st.divider()

        login_input = st.text_input("Usuário", placeholder="Ex: admin")
        senha_input = st.text_input("Senha", type="password")

        if st.button("Entrar", type="primary", use_container_width=True):
            usuario = _autenticar(login_input, senha_input)
            if usuario:
                st.session_state.autenticado = True
                st.session_state.usuario = usuario
                st.rerun()
            else:
                st.error("Usuário ou senha incorretos.")

    st.stop()


# ── Usuário logado ─────────────────────────────────────────────────────────────

usuario = st.session_state.usuario
role = usuario.get("role", "admin")
nome_usuario = usuario.get("nome", "Usuário")
sup_filtro = usuario.get("supervisor_nome", "") if role == "supervisora" else ""


# ── Sidebar ────────────────────────────────────────────────────────────────────

with st.sidebar:
    st.title("💍 Aureum Joias")
    st.caption(f"Olá, **{nome_usuario}**")
    st.divider()

    if role == "admin":
        paginas_disponiveis = [
            "🏠 Dashboard",
            "📦 Estoque",
            "🛒 Programação de Compras",
            "👥 Revendedoras",
            "🔍 Diagnóstico",
        ]
    else:
        # Supervisoras: apenas a tela de revendedoras
        paginas_disponiveis = ["👥 Revendedoras"]

    pagina = st.radio("Navegação", paginas_disponiveis)

    st.divider()

    if role == "admin":
        if st.button("🔄 Atualizar dados"):
            from src.api.jueri_client import limpar_cache
            limpar_cache()
            st.success("Cache limpo! Dados serão recarregados.")
            st.rerun()

    if st.button("🚪 Sair"):
        st.session_state.autenticado = False
        st.session_state.usuario = {}
        st.rerun()


# ── Roteamento ─────────────────────────────────────────────────────────────────

if pagina == "🏠 Dashboard":
    from src.api.jueri_client import get_produtos, get_revendedores, get_pedidos_baixados, get_pedidos_abertos
    from datetime import datetime, timedelta
    import pandas as pd

    st.title("🏠 Dashboard — Visão Geral")

    try:
        with st.spinner("Carregando dados..."):
            produtos = get_produtos(status="1")
            revendedores = get_revendedores()
            pedidos_abertos = get_pedidos_abertos()
            baixados = get_pedidos_baixados()
    except Exception as e:
        st.error(f"Erro ao conectar com a API Jueri: {e}")
        st.info("Aguarde alguns instantes e clique em **🔄 Atualizar dados** no menu lateral.")
        st.stop()

    corte_30d = datetime.now() - timedelta(days=30)
    baixados_30d = []
    for p in baixados:
        try:
            data_str = (p.get("data_baixa") or p.get("data_criacao") or "2000-01-01")[:10]
            if datetime.fromisoformat(data_str) >= corte_30d:
                baixados_30d.append(p)
        except (ValueError, TypeError):
            pass

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

    col1.metric("Produtos ativos", len(produtos))
    col2.metric("🔴 Estoque crítico", criticos)
    col3.metric("👥 Revendedoras ativas",
                sum(1 for r in revendedores if str(r.get("fk_status_id", "1")) == "1"))
    col4.metric("📦 Pedidos baixados (30 dias)", len(baixados_30d))

    st.divider()

    if criticos > 0:
        st.error(
            f"⚠️ {criticos} produto(s) estão abaixo do estoque mínimo! "
            "Acesse **Programação de Compras** para ver as sugestões."
        )

    st.info("Use o menu lateral para navegar entre os módulos do sistema.")

elif pagina == "📦 Estoque":
    from src.pages.estoque import render
    render()

elif pagina == "🛒 Programação de Compras":
    from src.pages.compras import render
    render()

elif pagina == "👥 Revendedoras":
    from src.pages.revendedoras import render
    render(filtro_supervisor=sup_filtro)

elif pagina == "🔍 Diagnóstico":
    from src.pages.diagnostico import render
    render()
