import streamlit as st
import pandas as pd
from datetime import date, timedelta, datetime as dt_cls, time as time_cls
from urllib.parse import quote
from src.api.jueri_client import _get_lista_pedidos
from src.logic.acertos import (
    FORMAS, DIAS_PT,
    montar_acertos, semana_de, proxima_semana_resumo,
    save_agendamento, remove_agendamento,
)

_R = lambda v: f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

_COR = {
    "✅ Realizado": "#27ae60",
    "📅 Agendado":  "#1976d2",
    "⬜ A agendar": "#7f8c8d",
    "🔴 Vencido":   "#e74c3c",
}


def _cor(sit: str) -> str:
    for k, v in _COR.items():
        if k in sit:
            return v
    return "#e67e22" if "Atrasou" in sit else "#95a5a6"


def _nome_curto(nome: str) -> str:
    p = nome.split()
    return (p[0] + " " + p[-1]) if len(p) >= 2 else (p[0] if p else "—")


def _card_open(row: pd.Series) -> str:
    cor  = _cor(row["Situação"])
    nome = _nome_curto(row["Nome"])
    sit  = row["Situação"]
    return (
        f'<div style="border-left:3px solid {cor};padding:3px 6px;'
        f'font-size:0.78em;line-height:1.4">'
        f'<b>{nome}</b> {FORMAS.get(row["Forma"], "")}<br>'
        f'<span style="color:{cor};font-weight:bold">{sit}</span><br>'
        f'{_R(row["Valor"])}</div>'
    )


def _card_agendado(row: pd.Series) -> str:
    nome   = _nome_curto(row["Nome"])
    hora_s = row.get("Hora agendada", "") or ""
    data_s = row["Data agendada"].strftime("%d/%m") if row["Data agendada"] else ""
    hora_t = f" {hora_s}" if hora_s else ""
    return (
        f'<div style="background:#1976d218;border:2px solid #1976d2;'
        f'border-radius:6px;padding:4px 7px;font-size:0.80em;line-height:1.5">'
        f'<b>{nome}</b> {FORMAS.get(row["Forma"], "")}<br>'
        f'<span style="color:#1976d2;font-weight:bold">📅 {data_s}{hora_t}</span><br>'
        f'<span style="color:#444">{_R(row["Valor"])}</span></div>'
    )


def _card_closed(row: pd.Series) -> str:
    cor  = _cor(row["Situação"])
    nome = _nome_curto(row["Nome"])
    return (
        f'<div style="background:{cor}18;border-left:3px solid {cor};'
        f'border-radius:4px;padding:4px 6px;font-size:0.78em;line-height:1.4">'
        f'<b>{nome}</b> {FORMAS.get(row["Forma"], "")}<br>'
        f'<span style="color:{cor};font-weight:bold">{row["Situação"]}</span><br>'
        f'{_R(row["Valor"])}</div>'
    )


def _gcal_link(nome, data, hora_str, forma, obs, valor):
    titulo = f"Acerto · {nome}"
    if hora_str:
        try:
            h, m    = map(int, hora_str.split(":"))
            dt_ini  = dt_cls(data.year, data.month, data.day, h, m)
            dt_fim  = dt_ini + timedelta(hours=1)
            datas   = f"{dt_ini.strftime('%Y%m%dT%H%M%S')}/{dt_fim.strftime('%Y%m%dT%H%M%S')}"
        except Exception:
            datas = f"{data.strftime('%Y%m%d')}/{(data + timedelta(days=1)).strftime('%Y%m%d')}"
    else:
        datas = f"{data.strftime('%Y%m%d')}/{(data + timedelta(days=1)).strftime('%Y%m%d')}"

    linhas = [f"Forma: {FORMAS.get(forma, '')} {forma}", f"Valor: {_R(valor)}"]
    if obs:
        linhas.append(f"Obs: {obs}")

    return (
        "https://calendar.google.com/calendar/render?action=TEMPLATE"
        f"&text={quote(titulo)}&dates={datas}"
        f"&details={quote(chr(10).join(linhas))}"
        "&ctz=America%2FSao_Paulo&sf=true&output=xml"
    )


# ── Dialog de agendamento ─────────────────────────────────────────────────────

@st.dialog("📅 Agendar Acerto", width="large")
def _dialog_agendar(row: pd.Series):
    pid  = row["id"]
    nome = row["Nome"]

    st.markdown(f"### {nome}")
    st.caption(
        f"Supervisora: **{row['Supervisor']}**  ·  "
        f"Acerto previsto: **{row['Data acerto'].strftime('%d/%m/%Y')}**  ·  "
        f"Pré-baixa: **{_R(row['Valor'])}**"
    )
    st.divider()

    col_f, col_d, col_h = st.columns(3)

    with col_f:
        idx = list(FORMAS.keys()).index(row["Forma"]) if row["Forma"] in FORMAS else 0
        forma = st.selectbox(
            "Forma de envio",
            list(FORMAS.keys()),
            index=idx,
            format_func=lambda f: f"{FORMAS[f]} {f}",
            key=f"dlg_forma_{pid}",
        )

    with col_d:
        data_padrao = row["Data agendada"] or row["Data acerto"]
        data_ag = st.date_input(
            "Data agendada",
            value=data_padrao,
            format="DD/MM/YYYY",
            key=f"dlg_data_{pid}",
        )

    with col_h:
        hora_existente = row.get("Hora agendada", "") or ""
        if hora_existente:
            try:
                h, m       = map(int, hora_existente.split(":"))
                hora_padrao = time_cls(h, m)
            except Exception:
                hora_padrao = time_cls(9, 0)
        else:
            hora_padrao = time_cls(9, 0)
        hora_ag = st.time_input("Horário", value=hora_padrao, key=f"dlg_hora_{pid}")

    obs = st.text_input(
        "Observação (opcional)",
        value=row["Obs"] or "",
        key=f"dlg_obs_{pid}",
    )

    st.divider()

    col_s, col_r, col_c = st.columns([3, 1, 1])

    with col_s:
        if st.button("💾 Salvar agendamento", type="primary",
                     use_container_width=True, key=f"dlg_salvar_{pid}"):
            hora_str = hora_ag.strftime("%H:%M") if hora_ag else ""
            save_agendamento(pid, str(data_ag), forma, obs, hora_str)
            st.session_state["_gcal_dict"] = {
                "nome":     nome,
                "data_str": data_ag.strftime("%d/%m/%Y"),
                "hora_str": hora_str,
                "link":     _gcal_link(nome, data_ag, hora_str, forma, obs, row["Valor"]),
            }
            st.session_state.pop("_ag_id", None)
            st.rerun()

    with col_r:
        if row["Data agendada"] and st.button(
            "🗑️ Remover", use_container_width=True, key=f"dlg_rem_{pid}"
        ):
            remove_agendamento(pid)
            st.session_state.pop("_ag_id", None)
            st.rerun()

    with col_c:
        if st.button("✖ Cancelar", use_container_width=True, key=f"dlg_cancel_{pid}"):
            st.session_state.pop("_ag_id", None)
            st.rerun()


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
                    if row["Status"] != "Baixado":
                        is_agendado = "Agendado" in str(row["Situação"])
                        card_html   = _card_agendado(row) if is_agendado else _card_open(row)
                        btn_label   = "🔄 Reagendar" if is_agendado else "📅 Agendar"
                        with st.container(border=True):
                            st.markdown(card_html, unsafe_allow_html=True)
                            if st.button(
                                btn_label,
                                key=f"ag_{row['id']}",
                                use_container_width=True,
                            ):
                                st.session_state["_ag_id"] = row["id"]
                                st.rerun()
                    else:
                        st.markdown(_card_closed(row), unsafe_allow_html=True)


# ── Label de semana por offset ────────────────────────────────────────────────

def _label_sem(off: int) -> str:
    if off == -1: return "Semana anterior"
    if off ==  0: return "Semana atual"
    if off ==  1: return "Próxima semana"
    return f"Semana {off:+d}"


# ── Calendário ────────────────────────────────────────────────────────────────

def _tab_calendario(df: pd.DataFrame):
    hoje = date.today()

    # Dialog de agendamento — chamado aqui (fora de qualquer coluna/container)
    ag_id = st.session_state.get("_ag_id")
    if ag_id is not None:
        rows = df[df["id"] == ag_id]
        if not rows.empty:
            _dialog_agendar(rows.iloc[0])
        else:
            st.session_state.pop("_ag_id", None)

    # Confirmação de Google Agenda após salvar agendamento
    gcal = st.session_state.get("_gcal_dict")
    if gcal:
        hora_info = f" às **{gcal['hora_str']}**" if gcal.get("hora_str") else ""
        with st.container(border=True):
            st.markdown(
                f"✅ Agendamento salvo — **{gcal['nome']}** · {gcal['data_str']}{hora_info}"
            )
            st.markdown("**Você deseja colocar o acerto na agenda?**")
            col_s, col_n, _ = st.columns([2, 2, 5])
            with col_s:
                st.link_button(
                    "✅ Sim, abrir Google Agenda",
                    url=gcal["link"],
                    type="primary",
                    use_container_width=True,
                )
            with col_n:
                if st.button("❌ Não", use_container_width=True, key="gcal_nao"):
                    st.session_state.pop("_gcal_dict", None)
                    st.rerun()
        st.divider()

    # Métricas
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
            f"⚠️ {n_a_agendar} pedido(s) sem agendamento — "
            "clique em **📅 Agendar** dentro do card."
        )

    st.divider()

    # Navegação de semanas
    if "acertos_offset" not in st.session_state:
        st.session_state.acertos_offset = 0

    seg_base, _ = semana_de(hoje)
    offset       = st.session_state.acertos_offset
    seg1         = seg_base + timedelta(weeks=offset)
    dom1         = seg1 + timedelta(days=6)
    seg2         = seg1 + timedelta(weeks=1)
    dom2         = seg2 + timedelta(days=6)

    col_prev, col_lbl, col_hoje, col_next = st.columns([1, 4, 1, 1])
    with col_prev:
        if st.button("◀ Anterior", use_container_width=True, key="nav_prev"):
            st.session_state.acertos_offset -= 1
            st.rerun()
    with col_next:
        if st.button("Próxima ▶", use_container_width=True, key="nav_next"):
            st.session_state.acertos_offset += 1
            st.rerun()
    with col_hoje:
        if st.button("Hoje", use_container_width=True, key="nav_hoje",
                     disabled=(offset == 0)):
            st.session_state.acertos_offset = 0
            st.rerun()
    with col_lbl:
        st.markdown(
            f"<div style='text-align:center;font-weight:600'>"
            f"{seg1.strftime('%d/%m')} – {dom1.strftime('%d/%m')}  ·  "
            f"{seg2.strftime('%d/%m')} – {dom2.strftime('%d/%m/%Y')}"
            f"</div>",
            unsafe_allow_html=True,
        )

    st.divider()

    st.markdown(f"**{_label_sem(offset)}** · {seg1.strftime('%d/%m')} – {dom1.strftime('%d/%m/%Y')}")
    _grade_semana(df, seg1, hoje)

    st.divider()

    st.markdown(f"**{_label_sem(offset + 1)}** · {seg2.strftime('%d/%m')} – {dom2.strftime('%d/%m/%Y')}")
    _grade_semana(df, seg2, hoje)

    st.divider()
    st.caption(
        "**Legenda:** 🔵 Agendado (azul destacado) · ⬜ A agendar · 🔴 Vencido · "
        "✅ Realizado · ⚠️ Atrasado  |  🔵 = hoje"
    )


# ── Render principal ──────────────────────────────────────────────────────────

def render(filtro_supervisor: str = ""):
    if filtro_supervisor:
        st.header(f"📅 Controle de Acertos — {filtro_supervisor}")
    else:
        st.header("📅 Controle de Acertos")

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
    _tab_calendario(df)
