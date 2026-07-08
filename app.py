import os
import base64
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

def _logo_sidebar_bottom(arquivo: str):
    """Renderiza logo no final do sidebar, ajustando à largura da barra."""
    p = Path("assets") / arquivo
    if not p.exists():
        return
    try:
        from PIL import Image
        import io
        img = Image.open(p).convert("RGBA")
        bbox = img.getbbox()
        if bbox:
            img = img.crop(bbox)
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)
        st.markdown("<div style='margin-top:32px'></div>", unsafe_allow_html=True)
        st.image(buf, use_container_width=True)
    except Exception:
        st.markdown("<div style='margin-top:32px'></div>", unsafe_allow_html=True)
        st.image(str(p), use_container_width=True)

load_dotenv()

st.set_page_config(
    page_title="Aureum Joias - Gestão",
    page_icon="💍",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
[data-testid="stSidebar"] [data-testid="stRadio"] label p {
    font-size: 1.05rem !important;
    line-height: 1.4 !important;
}
[data-testid="stSidebar"] [data-testid="stRadio"] label {
    padding: 2px 0 !important;
}
</style>
""", unsafe_allow_html=True)


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
        "cor": "#00A36C",   # Time Jade
        "secret_key": "YASMIM_SENHA",
    },
    "julia": {
        "nome": "Julia Andreza de Souza",
        "role": "supervisora",
        "supervisor_nome": "Julia Andreza de Souza",
        "cor": "#1D4ED8",   # Time Julia
        "secret_key": "JULIA_SENHA",
    },
    "dashboard": {
        "nome": "Dashboard TV",
        "role": "dashboard",
        "supervisor_nome": "",
        "secret_key": "DASHBOARD_SENHA",
    },
    "teste": {
        "nome": "Supervisora Teste",
        "role": "supervisora_teste",
        "supervisor_nome": "Yasmim Evellyn Ferreira",
        "secret_key": "TESTE_SENHA",
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
    # Pattern rosa como fundo com 10% de opacidade (90% transparente)
    _p = Path("assets") / "Pattern rosa.png"
    if _p.exists():
        _pb64 = base64.b64encode(_p.read_bytes()).decode()
        _pext = _p.suffix.lstrip(".")
        st.markdown(
            f'<style>'
            f'[data-testid="stAppViewContainer"]::before {{'
            f'  content: "";'
            f'  position: fixed; top: 0; left: 0; right: 0; bottom: 0;'
            f'  background-image: url("data:image/{_pext};base64,{_pb64}");'
            f'  background-repeat: repeat;'
            f'  background-size: auto;'
            f'  opacity: 0.10;'
            f'  z-index: 0;'
            f'  pointer-events: none;'
            f'}}'
            f'[data-testid="stAppViewContainer"] > * {{ position: relative; z-index: 1; }}'
            f'</style>',
            unsafe_allow_html=True,
        )

    # Carrega fonte Argue se o arquivo existir em assets/
    _font_css = ""
    for _fname in (
        "Argue DEMO.otf", "Argue Regular.otf", "Argue-Regular.otf",
        "Argue Regular.ttf", "Argue-Regular.ttf",
        "Argue Regular.woff2", "Argue-Regular.woff2",
    ):
        _fp = Path("assets") / _fname
        if _fp.exists():
            _fb64 = base64.b64encode(_fp.read_bytes()).decode()
            _fmt  = "woff2" if _fp.suffix == ".woff2" else ("opentype" if _fp.suffix == ".otf" else "truetype")
            _font_css = (
                f'@font-face {{'
                f'  font-family: "Argue";'
                f'  src: url("data:font/{_fmt};base64,{_fb64}") format("{_fmt}");'
                f'  font-weight: normal; font-style: normal;'
                f'}}'
            )
            break

    st.markdown(
        f'<style>{_font_css}'
        f'.aureum-title {{'
        f'  font-family: "Argue", "Cormorant Garamond", "Playfair Display", Georgia, serif;'
        f'  color: #AB6776;'
        f'  font-size: 5.1rem;'
        f'  font-weight: 400;'
        f'  letter-spacing: 2px;'
        f'  margin-bottom: 4px;'
        f'}}'
        f'</style>',
        unsafe_allow_html=True,
    )

    st.markdown("<div style='margin-top:100px'></div>", unsafe_allow_html=True)

    _, col_f, _ = st.columns([3, 4, 3])
    with col_f:
        st.markdown('<p class="aureum-title">Aureum Joias</p>', unsafe_allow_html=True)
        st.subheader("Sistema de Gestão", anchor=False)
        st.divider()

        with st.form("form_login"):
            login_input = st.text_input("Usuário", placeholder="Ex: admin")
            senha_input = st.text_input("Senha", type="password")
            submitted  = st.form_submit_button("Entrar", type="primary", use_container_width=True)

        if submitted:
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
_e_supervisora = role in ("supervisora", "supervisora_teste")
sup_filtro = usuario.get("supervisor_nome", "") if _e_supervisora else ""

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

# ── Dashboard TV (role exclusivo, sem sidebar) ─────────────────────────────────
if role == "dashboard":
    from src.pages import dashboard_tv
    dashboard_tv.render()
    st.stop()

# ── Sidebar ────────────────────────────────────────────────────────────────────

with st.sidebar:
    if _time_cfg:
        st.markdown(
            f'<div style="text-align:center;padding:10px 0 4px">'
            f'<span style="font-size:2.4em">{_time_cfg["emoji"]}</span><br>'
            f'<span style="color:{_time_cfg["cor"]};font-weight:700;font-size:1.58em;'
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
            "📊 Entradas e Saídas",
            "🔍 Diagnóstico",
        ]
    elif role == "supervisora_teste":
        paginas_disponiveis = [
            "🏠 Hoje",
            "👥 Revendedoras",
            "📅 Controle de Acertos",
        ]
    else:
        # Supervisoras: tela de revendedoras + controle de acertos
        paginas_disponiveis = ["👥 Revendedoras", "📅 Controle de Acertos"]

    # Navegação programática: _nav_goto é definido por outras telas antes do rerun
    # Precisa ser aplicado ANTES do st.radio para não conflitar com a chave do widget
    if "_nav_goto" in st.session_state:
        destino = st.session_state.pop("_nav_goto")
        if destino in paginas_disponiveis:
            st.session_state["_nav_page"] = destino

    if "_nav_page" not in st.session_state or st.session_state["_nav_page"] not in paginas_disponiveis:
        st.session_state["_nav_page"] = paginas_disponiveis[0]

    pagina = st.radio("Navegação", paginas_disponiveis, key="_nav_page")

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
        st.session_state.pop("_acomp_nome", None)
        st.session_state.pop("_acomp_prebaixa", None)
        st.rerun()

    # Submarca circular no rodapé do sidebar
    _logo_sidebar_bottom("Submarca rosa.png")


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

        # Conteúdo principal centralizado
        f'<div style="display:flex;align-items:center;justify-content:center;gap:18px;'
        f'position:relative;z-index:1;text-align:center">'
        f'<span style="font-size:2.8em;filter:drop-shadow(0 2px 4px rgba(0,0,0,0.3))">{emoji}</span>'
        f'<div style="font-size:2em;font-weight:800;letter-spacing:3px;'
        f'text-shadow:0 1px 3px rgba(0,0,0,0.2)">{nome_time.upper()}</div>'
        f'<span style="font-size:2.8em;filter:drop-shadow(0 2px 4px rgba(0,0,0,0.3))">{emoji}</span>'
        f'</div>'
        f'</div>',
        unsafe_allow_html=True,
    )


# ── Roteamento ─────────────────────────────────────────────────────────────────

if pagina == "🏠 Hoje":
    from src.pages.hoje import render
    render(filtro_supervisor=sup_filtro, nome_usuario=nome_usuario)

elif pagina == "🏠 Dashboard":
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

elif pagina == "📊 Entradas e Saídas":
    from src.pages.entradas_saidas import render
    render()

elif pagina == "🔍 Diagnóstico":
    from src.pages.diagnostico import render
    render()

