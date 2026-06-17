import os
from pathlib import Path
import streamlit as st
from dotenv import load_dotenv

def _logo(arquivo: str, **kwargs):
    """Exibe uma logo da pasta assets/ se o arquivo existir."""
    p = Path("assets") / arquivo
    if p.exists():
        st.image(str(p), **kwargs)
        return True
    return False

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
        # Logo principal rosa centralizada
        if not _logo("logo_rosa.png", use_container_width=True):
            st.title("💍 Aureum Joias")

        st.markdown("<br>", unsafe_allow_html=True)
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

_TIMES = {
    "yasmim": {
        "nome":  "Time Jade",
        "pedra": "Jade",
        "cor":   "#00A877",
        "cor2":  "#006b4e",
        "emoji": "💚",
    },
    "julia": {
        "nome":  "Time Ametista",
        "pedra": "Ametista",
        "cor":   "#9966CC",
        "cor2":  "#6a3d99",
        "emoji": "💜",
    },
}

_time_cfg = _TIMES.get(usuario.get("login", "")) if role == "supervisora" else None


# ── Sidebar ────────────────────────────────────────────────────────────────────

with st.sidebar:
    # Badge circular rosa no topo do sidebar
    if not _logo("badge_rosa.png", use_container_width=True):
        st.title("💍 Aureum Joias")

    if _time_cfg:
        st.markdown(
            f'<div style="text-align:center;padding:6px 0 2px">'
            f'<span style="font-size:1.6em">{_time_cfg["emoji"]}</span><br>'
            f'<span style="color:{_time_cfg["cor"]};font-weight:700;font-size:1.05em;'
            f'letter-spacing:1px">{_time_cfg["nome"].upper()}</span>'
            f'</div>',
            unsafe_allow_html=True,
        )
    else:
        st.caption(f"Olá, **{nome_usuario}**")

    st.divider()

    if role == "admin":
        paginas_disponiveis = [
            "🏠 Dashboard",
            "📦 Estoque",
            "🛒 Programação de Compras",
            "👥 Revendedoras",
            "📅 Controle de Acertos",
            "🔍 Diagnóstico",
        ]
    else:
        # Supervisoras: tela de revendedoras + controle de acertos
        paginas_disponiveis = ["👥 Revendedoras", "📅 Controle de Acertos"]

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


# ── Logo principal no topo do conteúdo ────────────────────────────────────────

with st.columns([1, 5])[0]:
    _logo("logo_rosa.png", use_container_width=True)


# ── Banner de time (supervisoras) ──────────────────────────────────────────────

if _time_cfg:
    cor  = _time_cfg["cor"]
    cor2 = _time_cfg["cor2"]
    nome_time  = _time_cfg["nome"]
    pedra      = _time_cfg["pedra"]
    emoji      = _time_cfg["emoji"]
    st.markdown(
        f'<div style="'
        f'background:linear-gradient(135deg,{cor} 0%,{cor2} 100%);'
        f'color:white;padding:18px 28px;border-radius:14px;'
        f'margin-bottom:8px;position:relative;overflow:hidden">'

        # Decoração de fundo — pedras estilizadas
        f'<div style="position:absolute;top:-12px;right:24px;'
        f'font-size:5.5em;opacity:0.13;transform:rotate(20deg)">◆</div>'
        f'<div style="position:absolute;bottom:-18px;right:90px;'
        f'font-size:3.5em;opacity:0.10;transform:rotate(-12deg)">◆</div>'
        f'<div style="position:absolute;top:8px;right:110px;'
        f'font-size:2em;opacity:0.08;transform:rotate(40deg)">◆</div>'

        # Conteúdo principal
        f'<div style="display:flex;align-items:center;gap:16px;position:relative;z-index:1">'
        f'<span style="font-size:2.4em;filter:drop-shadow(0 2px 4px rgba(0,0,0,0.3))">{emoji}</span>'
        f'<div>'
        f'<div style="font-size:1.55em;font-weight:800;letter-spacing:2px;'
        f'text-shadow:0 1px 3px rgba(0,0,0,0.2)">{nome_time.upper()}</div>'
        f'<div style="font-size:0.82em;opacity:0.88;margin-top:2px;letter-spacing:0.5px">'
        f'✦ Pedra: {pedra} &nbsp;·&nbsp; {nome_usuario}'
        f'</div>'
        f'</div>'
        f'</div>'
        f'</div>',
        unsafe_allow_html=True,
    )


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

    # ── Ticket médio por supervisora ──────────────────────────────────────────
    st.subheader("🎯 Ticket médio por supervisora — últimos 30 dias")
    st.caption("Valor médio por pedido baixado nos últimos 30 dias, agrupado por supervisora.")

    if baixados_30d:
        ticket_sup: dict = {}
        contagem_sup: dict = {}
        for p in baixados_30d:
            sup = p.get("supervisor_nome") or "Sem supervisora"
            val = float(p.get("valor_total") or 0)
            ticket_sup[sup] = ticket_sup.get(sup, 0) + val
            contagem_sup[sup] = contagem_sup.get(sup, 0) + 1

        # Cards por supervisora
        supervisoras = sorted(ticket_sup.keys())
        cols = st.columns(max(len(supervisoras), 1))
        for col, sup in zip(cols, supervisoras):
            total = ticket_sup[sup]
            qtd   = contagem_sup[sup]
            media = total / qtd if qtd else 0
            _fmt  = lambda v: f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
            col.metric(
                label=sup,
                value=_fmt(media),
                delta=f"{qtd} pedido(s) · total {_fmt(total)}",
                delta_color="off",
            )

        # Tabela resumo
        st.divider()
        df_ticket = pd.DataFrame([
            {
                "Supervisora": sup,
                "Pedidos baixados": contagem_sup[sup],
                "Total vendido": ticket_sup[sup],
                "Ticket médio": ticket_sup[sup] / contagem_sup[sup],
            }
            for sup in supervisoras
        ]).sort_values("Ticket médio", ascending=False)

        _fmt_br = lambda v: f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        st.dataframe(
            df_ticket.style.format({
                "Total vendido": _fmt_br,
                "Ticket médio":  _fmt_br,
            }),
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("Sem pedidos baixados nos últimos 30 dias.")

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

elif pagina == "📅 Controle de Acertos":
    from src.pages.acertos import render
    render(filtro_supervisor=sup_filtro)

elif pagina == "🔍 Diagnóstico":
    from src.pages.diagnostico import render
    render()

