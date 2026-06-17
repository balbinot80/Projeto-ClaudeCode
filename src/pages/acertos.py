import streamlit as st
import pandas as pd
from datetime import date, timedelta
from urllib.parse import quote
from src.api.jueri_client import _get_lista_pedidos
from src.logic.acertos import (
    FORMAS, DIAS_PT,
    montar_acertos, semana_de, proxima_semana_resumo,
    save_agendamento, remove_agendamento,
)

_R   = lambda v: f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
_Rmd = lambda v: f"R\\$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

_COR_SITUACAO = {
    "✅ Realizado":  "#27ae60",
    "📅 Agendado":   "#2980b9",
    "⬜ A agendar":  "#7f8c8d",
    "🔴 Vencido":    "#e74c3c",
}


def _cor(sit: str) -> str:
    for k, v in _COR_SITUACAO.items():
        if k in sit:
            return v
    if "Atrasou" in sit:
        return "#e67e22"
    return "#95a5a6"


def _nome_curto(nome: str) -> str:
    """Primeiro + último nome."""
    partes = nome.split()
    if len(partes) >= 2:
        return partes[0] + " " + partes[-1]
    return partes[0] if partes else "—"


def _card_open(row: pd.Series) -> str:
    cor   = _cor(row["Situação"])
    forma = FORMAS.get(row["Forma"], "")
    valor = _R(row["Valor"])
    nome  = _nome_curto(row["Nome"])
    sit   = row["Situação"]
    return (
        f'<div style="border-left:3px solid {cor};padding:3px 6px;'
        f'font-size:0.78em;line-height:1.4">'
        f'<b>{nome}</b> {forma}<br>'
        f'<span style="color:{cor};font-weight:bold">{sit}</span><br>'
        f'{valor}'
        f'</div>'
    )


def _card_closed(row: pd.Series) -> str:
    cor   = _cor(row["Situação"])
    forma = FORMAS.get(row["Forma"], "")
    valor = _R(row["Valor"])
    nome  = _nome_curto(row["Nome"])
    sit   = row["Situação"]
    return (
        f'<div style="background:{cor}18;border-left:3px solid {cor};'
        f'border-radius:4px;padding:4px 6px;margin:2px 0;font-size:0.78em;line-height:1.4">'
        f'<b>{nome}</b> {forma}<br>'
        f'<span style="color:{cor};font-weight:bold">{sit}</span><br>'
        f'{valor}'
        f'</div>'
    )


def _google_calendar_link(nome: str, data: date, forma: str, obs: str, valor: float) -> str:
    titulo   = f"Acerto · {nome}"
    data_ini = data.strftime("%Y%m%d")
    data_fim = (data + timedelta(days=1)).strftime("%Y%m%d")
    linhas   = [f"Forma: {FORMAS.get(forma, '')} {forma}", f"Valor pré-baixa: {_R(valor)}"]
    if obs:
        linhas.append(f"Obs: {obs}")
    return (
        "https://calendar.google.com/calendar/render?action=TEMPLATE"
        f"&text={quote(titulo)}"
        f"&dates={data_ini}/{data_fim}"
        f"&details={quote(chr(10).join(linhas))}"
        "&ctz=America%2FSao_Paulo&sf=true&output=xml"
    )


# ── Formulário de agendamento (aparece no topo da aba) ───────────────────────

def _form_topo(row: pd.Series):
    """
    Formulário exibido no TOPO da aba quando o usuário clica 'Agendar'.
    O Streamlit rola a página para o topo no rerun, então o formulário
    fica visível imediatamente sem o usuário precisar rolar a tela.
    """
    pid  = row["id"]
    nome = row["Nome"]

    with st.container(border=True):
        col_tit, col_fechar = st.columns([11, 1])
        with col_tit:
            st.markdown(f"#### 📅 Agendar acerto — **{nome}**")
        with col_fechar:
            if st.button("✖", key="_btn_fechar", help="Fechar"):
                st.session_state.pop("_ag_id", None)
                st.rerun()

        st.caption(
            f"Supervisora: **{row['Supervisor']}**  ·  "
            f"Acerto previsto: **{row['Data acerto'].strftime('%d/%m/%Y')}**  ·  "
            f"Pré-baixa: **{_R(row['Valor'])}**"
        )

        col_f, col_d, col_obs = st.columns([1, 1, 2])
        with col_f:
            idx_forma = list(FORMAS.keys()).index(row["Forma"]) if row["Forma"] in FORMAS else 0
            forma = st.selectbox(
                "Forma de envio",
                list(FORMAS.keys()),
                index=idx_forma,
                format_func=lambda f: f"{FORMAS[f]} {f}",
                key="_ff_forma",
            )
        with col_d:
            data_padrao = row["Data agendada"] or row["Data acerto"]
            data_ag = st.date_input(
                "Data agendada",
                value=data_padrao,
                format="DD/MM/YYYY",
                key="_ff_data",
            )
        with col_obs:
            obs = st.text_input(
                "Observação (opcional)",
                value=row["Obs"] or "",
                key="_ff_obs",
            )

        col_s, col_r = st.columns([3, 1])
        with col_s:
            if st.button(
                "💾 Salvar agendamento", type="primary",
                use_container_width=True, key="_ff_salvar"
            ):
                save_agendamento(pid, str(data_ag), forma, obs)
                st.session_state["_gcal_link"] = _google_calendar_link(
                    nome, data_ag, forma, obs, row["Valor"]
                )
                st.session_state["_gcal_nome"] = nome
                st.session_state["_gcal_data"] = data_ag.strftime("%d/%m/%Y")
                st.session_state.pop("_ag_id", None)
                st.rerun()
        with col_r:
            if row["Data agendada"] and st.button(
                "🗑️ Remover agendamento",
                use_container_width=True, key="_ff_remover"
            ):
                remove_agendamento(pid)
                st.session_state.pop("_ag_id", None)
                st.rerun()

    st.divider()


# ── Grade de uma semana ───────────────────────────────────────────────────────

def _grade_semana(df: pd.DataFrame, seg: date, hoje: date):
    dias = [seg + timedelta(days=i) for i in range(7)]
    cols = st.columns(7)

    for col, dia in zip(cols, dias):
        with col:
            destaque = "🔵 " if dia == hoje else ""
            st.markdown(f"{destaque}**{DIAS_PT[dia.weekday()]}**  \n{dia.strftime('%d/%m')}")

            df_dia = df[df["Data ref"] == dia] if not df.empty else pd.DataFrame()

            if df_dia.empty:
                st.markdown(
                    '<div style="color:#bdc3c7;font-size:0.75em;text-align:center">—</div>',
                    unsafe_allow_html=True,
                )
            else:
                for _, row in df_dia.iterrows():
                    if row["Status"] == "Aberto":
                        with st.container(border=True):
                            st.markdown(_card_open(row), unsafe_allow_html=True)
                            if st.button(
                                "📅 Agendar",
                                key=f"ag_{row['id']}",
                                use_container_width=True,
                            ):
                                st.session_state["_ag_id"] = row["id"]
                                st.rerun()
                    else:
                        st.markdown(_card_closed(row), unsafe_allow_html=True)


# ── Calendário (2 semanas fixas) ──────────────────────────────────────────────

def _tab_calendario(df: pd.DataFrame, filtro_supervisor: str):
    hoje = date.today()

    # ── Formulário aparece aqui quando um card é selecionado ─────────────────
    ag_id = st.session_state.get("_ag_id")
    if ag_id:
        rows = df[df["id"] == ag_id]
        if not rows.empty:
            _form_topo(rows.iloc[0])
        else:
            st.session_state.pop("_ag_id", None)

    # ── Notificação + link Google Agenda ─────────────────────────────────────
    if st.session_state.get("_gcal_link"):
        gcal_link = st.session_state["_gcal_link"]
        gcal_nome = st.session_state.get("_gcal_nome", "")
        gcal_data = st.session_state.get("_gcal_data", "")
        col_msg, col_fechar = st.columns([8, 1])
        with col_msg:
            st.success(f"✅ Agendamento salvo — **{gcal_nome}** · {gcal_data}")
            st.markdown(
                f"📅 [**Adicionar ao Google Agenda →**]({gcal_link})  "
                "Clique para registrar na agenda compartilhada da Aureum."
            )
        with col_fechar:
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("✖", key="_fechar_gcal"):
                st.session_state.pop("_gcal_link", None)
                st.session_state.pop("_gcal_nome", None)
                st.session_state.pop("_gcal_data", None)
                st.rerun()
        st.divider()

    # ── Métricas rápidas ──────────────────────────────────────────────────────
    prox        = proxima_semana_resumo(df, hoje)
    n_vencidos  = int((df["Situação"] == "🔴 Vencido").sum())   if not df.empty else 0
    n_a_agendar = int((df["Situação"] == "⬜ A agendar").sum()) if not df.empty else 0

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("📅 Próxima semana",    prox["total"])
    c2.metric("✅ Já agendados",      prox["agendados"])
    c3.metric("⬜ A agendar (prox.)", prox["a_agendar"])
    c4.metric("🔴 Vencidos",          n_vencidos)

    if n_a_agendar:
        st.warning(
            f"⚠️ {n_a_agendar} pedido(s) sem data de acerto — "
            "clique em **📅 Agendar** dentro do card."
        )

    st.divider()

    # ── Semana atual ──────────────────────────────────────────────────────────
    seg1, dom1 = semana_de(hoje)
    st.markdown(f"**Semana atual** · {seg1.strftime('%d/%m')} – {dom1.strftime('%d/%m/%Y')}")
    _grade_semana(df, seg1, hoje)

    st.divider()

    # ── Próxima semana ────────────────────────────────────────────────────────
    seg2 = seg1 + timedelta(weeks=1)
    dom2 = seg2 + timedelta(days=6)
    st.markdown(f"**Próxima semana** · {seg2.strftime('%d/%m')} – {dom2.strftime('%d/%m/%Y')}")
    _grade_semana(df, seg2, hoje)

    st.divider()
    st.caption(
        "**Legenda:** "
        "🟢 Realizado no prazo · "
        "🟠 Realizado com atraso · "
        "🔵 Agendado · "
        "⬜ A agendar · "
        "🔴 Vencido — "
        "🔵 = hoje"
    )


# ── Lista geral ───────────────────────────────────────────────────────────────

def _tab_lista(df: pd.DataFrame):
    st.subheader("Lista geral de acertos")

    if df.empty:
        st.info("Nenhum acerto no período.")
        return

    col_sit, col_sup = st.columns(2)
    with col_sit:
        situacoes  = ["Todas"] + sorted(df["Situação"].unique().tolist())
        sit_filtro = st.selectbox("Situação", situacoes)
    with col_sup:
        sups       = ["Todas"] + sorted(df["Supervisor"].unique().tolist())
        sup_filtro = st.selectbox("Supervisora", sups)

    df_f = df.copy()
    if sit_filtro != "Todas":
        df_f = df_f[df_f["Situação"] == sit_filtro]
    if sup_filtro != "Todas":
        df_f = df_f[df_f["Supervisor"] == sup_filtro]

    n_real = (df_f["Situação"] == "✅ Realizado").sum()
    n_atr  = df_f["Situação"].str.contains("Atrasou").sum()
    n_ag   = (df_f["Situação"] == "📅 Agendado").sum()
    n_venc = (df_f["Situação"] == "🔴 Vencido").sum()

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("✅ Realizados", n_real)
    c2.metric("⚠️ Com atraso", n_atr)
    c3.metric("📅 Agendados",  n_ag)
    c4.metric("🔴 Vencidos",   n_venc)

    st.divider()

    exib = df_f[["Nome", "Supervisor", "Situação", "Forma",
                 "Data acerto", "Data agendada", "Data baixa", "Valor"]].copy()
    exib["Nome"] = exib["Nome"].apply(_nome_curto)
    exib["Data acerto"]   = exib["Data acerto"].apply(
        lambda d: d.strftime("%d/%m/%y") if pd.notna(d) else "—"
    )
    exib["Data agendada"] = exib["Data agendada"].apply(
        lambda d: d.strftime("%d/%m/%y") if pd.notna(d) and d is not None else "—"
    )
    exib["Data baixa"] = exib["Data baixa"].apply(
        lambda d: d.strftime("%d/%m/%y") if pd.notna(d) and d is not None else "—"
    )

    st.dataframe(
        exib.style
            .map(lambda v: f"color:{_cor(str(v))};font-weight:bold", subset=["Situação"])
            .format({"Valor": _R}),
        use_container_width=True,
        hide_index=True,
    )

    csv = df_f.drop(columns=["id"], errors="ignore").to_csv(index=False).encode("utf-8")
    st.download_button("Exportar CSV", csv, "acertos.csv", "text/csv")


# ── Render principal ──────────────────────────────────────────────────────────

def render(filtro_supervisor: str = ""):
    if filtro_supervisor:
        st.header(f"📅 Controle de Acertos — {filtro_supervisor}")
    else:
        st.header("📅 Controle de Acertos")

    st.caption(
        "Acompanhamento e agendamento dos acertos de consignação. "
        "Exibe os últimos 90 dias de baixados + todos os pedidos abertos."
    )

    with st.spinner("Carregando pedidos..."):
        try:
            todos_bruto = _get_lista_pedidos()
        except Exception as e:
            st.error(f"Erro ao carregar dados: {e}")
            return

    todos = (
        [p for p in todos_bruto if (p.get("supervisor_nome") or "") == filtro_supervisor]
        if filtro_supervisor else todos_bruto
    )

    df = montar_acertos(todos)

    tab1, tab2 = st.tabs(["📅 Calendário", "📋 Lista geral"])

    with tab1:
        _tab_calendario(df, filtro_supervisor)

    with tab2:
        _tab_lista(df)
