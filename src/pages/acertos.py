import streamlit as st
import pandas as pd
from datetime import date, timedelta, datetime as dt_cls, time as time_cls
from urllib.parse import quote
from src.api.jueri_client import _get_lista_pedidos
from src.logic.acertos import (
    FORMAS, DIAS_PT,
    montar_acertos, semana_de, proxima_semana_resumo,
    save_agendamento, save_envio_maleta, remove_agendamento,
)

_FORMAS_ENVIO = {"Correios", "Disk Tenha"}

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
    return (
        f'<div style="border-left:3px solid {cor};padding:3px 6px;'
        f'font-size:0.78em;line-height:1.4">'
        f'<b>{nome}</b> {FORMAS.get(row["Forma"], "")}<br>'
        f'<span style="color:{cor};font-weight:bold">{row["Situação"]}</span><br>'
        f'{_R(row["Valor"])}</div>'
    )


def _card_agendado(row: pd.Series) -> str:
    nome   = _nome_curto(row["Nome"])
    hora_s = row.get("Hora agendada", "") or ""
    data_s = row["Data agendada"].strftime("%d/%m") if row["Data agendada"] else ""
    hora_t = f" {hora_s}" if hora_s else ""

    envio_html = ""
    d_envio = row.get("Data envio maleta")
    h_envio = row.get("Hora envio maleta", "") or ""
    if pd.notna(d_envio) and d_envio:
        envio_s = d_envio.strftime("%d/%m") if hasattr(d_envio, "strftime") else str(d_envio)
        hora_env_t = f" {h_envio}" if h_envio else ""
        envio_html = f'<br><span style="color:#6a1b9a;font-size:0.9em">📦 Data de envio: {envio_s}{hora_env_t}</span>'

    return (
        f'<div style="background:#1976d218;border:2px solid #1976d2;'
        f'border-radius:6px;padding:4px 7px;font-size:0.80em;line-height:1.5">'
        f'<b>{nome}</b> {FORMAS.get(row["Forma"], "")}<br>'
        f'<span style="color:#1976d2;font-weight:bold">📅 {data_s}{hora_t}</span>'
        f'{envio_html}<br>'
        f'<span style="color:#444">{_R(row["Valor"])}</span></div>'
    )


def _card_vencido_agendado(row: pd.Series) -> str:
    nome   = _nome_curto(row["Nome"])
    hora_s = row.get("Hora agendada", "") or ""
    data_s = row["Data agendada"].strftime("%d/%m") if pd.notna(row["Data agendada"]) and row["Data agendada"] else ""
    hora_t = f" {hora_s}" if hora_s else ""
    return (
        f'<div style="background:#fff3cd;border:2px solid #f57c00;'
        f'border-radius:6px;padding:4px 7px;font-size:0.80em;line-height:1.5">'
        f'<b>{nome}</b> {FORMAS.get(row["Forma"], "")}<br>'
        f'<span style="color:#e74c3c;font-weight:bold">🔴 Vencido</span><br>'
        f'<span style="color:#e65100;font-weight:bold">📅 Reagendado: {data_s}{hora_t}</span><br>'
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


def _gcal_url(nome, data, hora_str, forma, obs, valor):
    titulo = f"Coleta · {nome}"
    if hora_str:
        try:
            h, m   = map(int, hora_str.split(":"))
            dt_ini = dt_cls(data.year, data.month, data.day, h, m)
            dt_fim = dt_ini + timedelta(hours=1)
            datas  = f"{dt_ini.strftime('%Y%m%dT%H%M%S')}/{dt_fim.strftime('%Y%m%dT%H%M%S')}"
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


# ── Dialog: Google Agenda — dois eventos (acerto + envio da maleta) ──────────

@st.dialog("📅 Adicionar ao Google Agenda?", width="small")
def _dialog_gcal_duplo():
    duplo       = st.session_state.get("_gcal_duplo_active", {})
    gcal_acerto = duplo.get("acerto") or {}
    gcal_envio  = duplo.get("envio")  or {}

    st.success("✅ Agendamentos salvos!")
    st.divider()

    if gcal_acerto.get("link"):
        st.markdown(
            f"📅 **Data de coleta** · "
            f"{gcal_acerto.get('data_str', '')} "
            f"{'às ' + gcal_acerto['hora_str'] if gcal_acerto.get('hora_str') else ''}"
        )
        st.link_button(
            "📅 Adicionar Data de Coleta ao Google Agenda",
            url=gcal_acerto["link"],
            type="primary",
            use_container_width=True,
        )
        st.markdown("")

    if gcal_envio.get("link"):
        st.markdown(
            f"📦 **Data de envio** · "
            f"{gcal_envio.get('data_str', '')} "
            f"{'às ' + gcal_envio['hora_str'] if gcal_envio.get('hora_str') else ''}"
        )
        st.link_button(
            "📦 Adicionar Data de Envio ao Google Agenda",
            url=gcal_envio["link"],
            use_container_width=True,
        )

    st.divider()
    if st.button("❌ Fechar", use_container_width=True, key="gcal_duplo_fechar"):
        st.session_state.pop("_gcal_duplo_active", None)
        st.rerun()

    st.caption("Após clicar em um link, feche esta janela clicando em **❌ Fechar**.")


# ── Dialog: confirmação Google Agenda ─────────────────────────────────────────
# Chamado com pop() do _gcal_dict — não reabre ao fechar por Esc/X

@st.dialog("📅 Adicionar ao Google Agenda?", width="small")
def _dialog_gcal_confirm():
    gcal   = st.session_state.get("_gcal_active", {})
    link   = gcal.get("link", "")
    nome   = gcal.get("nome", "")
    data_s = gcal.get("data_str", "")
    hora_s = gcal.get("hora_str", "")

    hora_info = f" às **{hora_s}**" if hora_s else ""
    st.success(f"✅ Agendamento salvo!")
    st.markdown(f"**{nome}** · {data_s}{hora_info}")
    st.divider()
    st.markdown("**Você deseja colocar o acerto na agenda?**")

    col_s, col_n = st.columns(2)
    with col_s:
        # Abre em nova aba sem fechar o dialog
        st.link_button("✅ Sim", url=link, type="primary", use_container_width=True)
    with col_n:
        # Clicar em Não dispara rerun; como _gcal_dict já foi "pop()", o dialog não reabre
        if st.button("❌ Não", use_container_width=True, key="gcal_nao_btn"):
            st.session_state.pop("_gcal_active", None)
            st.rerun()

    st.caption("Após clicar em **✅ Sim**, feche esta janela clicando em **❌ Não**.")


# ── Dialog: agendamento ───────────────────────────────────────────────────────

@st.dialog("📅 Agendar Acerto", width="large")
def _dialog_agendar(row: pd.Series):
    pid     = row["id"]
    nome    = row["Nome"]
    vencido = row["Data acerto"] < date.today()

    st.markdown(f"### {nome}")
    st.caption(
        f"Supervisora: **{row['Supervisor']}**  ·  "
        f"Acerto previsto: **{row['Data acerto'].strftime('%d/%m/%Y')}**  ·  "
        f"Pré-baixa: **{_R(row['Valor'])}**"
    )

    if vencido:
        dias_atraso = (date.today() - row["Data acerto"]).days
        st.error(f"⚠️ Acerto vencido há **{dias_atraso} dia(s)**. O motivo do atraso é obrigatório.")

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
        data_ag = st.date_input(
            "Data agendada",
            value=date.today(),
            format="DD/MM/YYYY",
            key=f"dlg_data_{pid}",
        )

    with col_h:
        hora_existente = row.get("Hora agendada", "") or ""
        if hora_existente:
            try:
                h, m        = map(int, hora_existente.split(":"))
                hora_padrao = time_cls(h, m)
            except Exception:
                hora_padrao = time_cls(9, 0)
        else:
            hora_padrao = time_cls(9, 0)
        hora_ag = st.time_input("Horário", value=hora_padrao, key=f"dlg_hora_{pid}")

    obs_label = "Motivo do atraso no agendamento *" if vencido else "Observação (opcional)"
    obs = st.text_area(
        obs_label,
        value=row["Obs"] or "",
        placeholder="Informe o motivo do atraso..." if vencido else "",
        key=f"dlg_obs_{pid}",
        height=80,
    )

    st.divider()
    col_s, col_r, col_c = st.columns([3, 1, 1])

    with col_s:
        if st.button("💾 Salvar agendamento", type="primary",
                     use_container_width=True, key=f"dlg_salvar_{pid}"):
            if vencido and not obs.strip():
                st.error("⚠️ Informe o motivo do atraso antes de salvar.")
            else:
                hora_str = hora_ag.strftime("%H:%M") if hora_ag else ""
                save_agendamento(pid, str(data_ag), forma, obs, hora_str)
                gcal = {
                    "nome":     nome,
                    "data_str": data_ag.strftime("%d/%m/%Y"),
                    "hora_str": hora_str,
                    "link":     _gcal_url(nome, data_ag, hora_str, forma, obs, row["Valor"]),
                }
                st.session_state.pop("_ag_id", None)
                if forma in _FORMAS_ENVIO:
                    # Fluxo especial: perguntar se a troca é no mesmo dia
                    st.session_state["_troca_check"] = {
                        "pid":   pid,
                        "nome":  nome,
                        "valor": row["Valor"],
                        "forma": forma,
                        "gcal":  gcal,
                    }
                else:
                    st.session_state["_gcal_dict"] = gcal
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


# ── Dialog: troca no mesmo dia? ──────────────────────────────────────────────

@st.dialog("📦 Troca da maleta", width="small")
def _dialog_troca_mesmo_dia():
    check = st.session_state.get("_troca_check", {})
    forma = check.get("forma", "")
    nome  = check.get("nome", "")

    st.markdown(f"**{FORMAS.get(forma, '')} {forma}** · {nome}")
    st.divider()
    st.markdown("### A troca da maleta será no mesmo dia?")
    st.caption("Se a nova maleta será entregue junto com o acerto, responda Sim. Caso contrário, agende o envio separadamente.")

    col_s, col_n = st.columns(2)
    with col_s:
        if st.button("✅ Sim", type="primary", use_container_width=True, key="troca_sim"):
            st.session_state["_gcal_dict"] = check.get("gcal")
            st.session_state.pop("_troca_check", None)
            st.rerun()
    with col_n:
        if st.button("❌ Não", use_container_width=True, key="troca_nao"):
            st.session_state["_envio_maleta"] = check
            st.session_state.pop("_troca_check", None)
            st.rerun()


# ── Dialog: agendar envio da maleta ──────────────────────────────────────────

@st.dialog("📦 Agendar Envio da Maleta", width="large")
def _dialog_agendar_envio_maleta():
    info  = st.session_state.get("_envio_maleta", {})
    pid   = info.get("pid")
    nome  = info.get("nome", "")
    forma = info.get("forma", "")

    st.markdown(f"### {FORMAS.get(forma, '')} {forma} · {nome}")
    st.caption(
        "O acerto já foi agendado. Agora defina quando a maleta será enviada/retirada."
    )
    st.divider()

    col_d, col_h = st.columns(2)
    with col_d:
        data_envio = st.date_input(
            "Data de envio",
            value=date.today(),
            format="DD/MM/YYYY",
            key=f"dlg_envio_data_{pid}",
        )
    with col_h:
        hora_envio = st.time_input(
            "Horário", value=time_cls(9, 0), key=f"dlg_envio_hora_{pid}"
        )

    obs_envio = st.text_area(
        "Observação (opcional)", key=f"dlg_envio_obs_{pid}", height=70
    )

    st.divider()
    col_s, col_c = st.columns([3, 1])

    with col_s:
        if st.button("💾 Salvar envio", type="primary", use_container_width=True, key=f"dlg_envio_salvar_{pid}"):
            hora_str = hora_envio.strftime("%H:%M") if hora_envio else ""
            save_envio_maleta(pid, str(data_envio), hora_str)
            gcal_envio = {
                "nome":     f"Envio · {nome}",
                "data_str": data_envio.strftime("%d/%m/%Y"),
                "hora_str": hora_str,
                "link":     _gcal_url(
                    f"Envio · {nome}",
                    data_envio, hora_str, forma,
                    obs_envio, info.get("valor", 0),
                ),
            }
            # Abre dialog com os dois links (envio + acerto)
            st.session_state["_gcal_duplo"] = {
                "acerto": info.get("gcal"),
                "envio":  gcal_envio,
            }
            st.session_state.pop("_envio_maleta", None)
            st.rerun()

    with col_c:
        if st.button("✖ Cancelar", use_container_width=True, key=f"dlg_envio_cancel_{pid}"):
            # Pula agendamento do envio — só mostra o Google Agenda do acerto
            st.session_state["_gcal_dict"] = info.get("gcal")
            st.session_state.pop("_envio_maleta", None)
            st.rerun()


# ── Helpers de grade ──────────────────────────────────────────────────────────

def _label_sem(off: int) -> str:
    if off == -1: return "Semana anterior"
    if off ==  0: return "Semana atual"
    if off ==  1: return "Próxima semana"
    return f"Semana {off:+d}"


def _grade_semana(df: pd.DataFrame, seg: date, hoje: date):
    dias = [seg + timedelta(days=i) for i in range(7)]
    cols = st.columns(7)

    for col, dia in zip(cols, dias):
        with col:
            destaque = "🔵 " if dia == hoje else ""
            st.markdown(f"{destaque}**{DIAS_PT[dia.weekday()]}**  \n{dia.strftime('%d/%m')}")

            df_dia = df[df["Data ref"] == dia] if not df.empty else pd.DataFrame()

            # Cards de envio de maleta agendados para este dia
            if not df.empty and "Data envio maleta" in df.columns:
                df_envio_dia = df[df["Data envio maleta"] == dia]
                for _, row_e in df_envio_dia.iterrows():
                    h_env = row_e.get("Hora envio maleta", "") or ""
                    hora_t = f" {h_env}" if h_env else ""
                    st.markdown(
                        f'<div style="background:#f3e5f5;border:2px solid #9c27b0;'
                        f'border-radius:6px;padding:4px 7px;font-size:0.78em;'
                        f'line-height:1.4;margin-bottom:4px">'
                        f'<b>{_nome_curto(row_e["Nome"])}</b><br>'
                        f'<span style="color:#9c27b0;font-weight:bold">'
                        f'📦 Data de envio{hora_t}</span><br>'
                        f'<span style="color:#444">{FORMAS.get(row_e["Forma"], "")} '
                        f'{row_e["Forma"]}</span>'
                        f'</div>',
                        unsafe_allow_html=True,
                    )

            if df_dia.empty:
                st.markdown(
                    '<div style="color:#bdc3c7;font-size:0.75em;text-align:center">—</div>',
                    unsafe_allow_html=True,
                )
            else:
                for _, row in df_dia.iterrows():
                    if row["Status"] != "Baixado":
                        is_vencido = row["Data acerto"] < hoje
                        tem_agenda = pd.notna(row["Data agendada"]) and bool(row["Data agendada"])
                        is_ag      = "Agendado" in str(row["Situação"])

                        if is_vencido and tem_agenda:
                            card_html = _card_vencido_agendado(row)
                            btn_lbl   = "🔄 Reagendar"
                        elif is_ag:
                            card_html = _card_agendado(row)
                            btn_lbl   = "🔄 Reagendar"
                        else:
                            card_html = _card_open(row)
                            btn_lbl   = "📅 Agendar"

                        with st.container(border=True):
                            st.markdown(card_html, unsafe_allow_html=True)
                            if st.button(btn_lbl, key=f"ag_{row['id']}", use_container_width=True):
                                st.session_state["_ag_id"] = row["id"]
                                st.rerun()
                    else:
                        st.markdown(_card_closed(row), unsafe_allow_html=True)


# ── Aba: Calendário ───────────────────────────────────────────────────────────

def _tab_calendario(df: pd.DataFrame):
    hoje = date.today()

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
            st.session_state.pop("_ag_id", None)
            st.rerun()
    with col_next:
        if st.button("Próxima ▶", use_container_width=True, key="nav_next"):
            st.session_state.acertos_offset += 1
            st.session_state.pop("_ag_id", None)
            st.rerun()
    with col_hoje:
        if st.button("Hoje", use_container_width=True, key="nav_hoje",
                     disabled=(offset == 0)):
            st.session_state.acertos_offset = 0
            st.session_state.pop("_ag_id", None)
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


# ── Aba: Vencidos ─────────────────────────────────────────────────────────────

def _tab_vencidos(df: pd.DataFrame):
    hoje = date.today()

    df_venc = (
        df[df["Situação"] == "🔴 Vencido"].sort_values("Data acerto").copy()
        if not df.empty else pd.DataFrame()
    )

    if df_venc.empty:
        st.success("✅ Nenhum acerto vencido no momento.")
        return

    st.warning(f"⚠️ {len(df_venc)} acerto(s) vencido(s) — clique em **📅 Agendar** para regularizar.")

    supervisoras = sorted(df_venc["Supervisor"].unique())

    for sup in supervisoras:
        df_sup = df_venc[df_venc["Supervisor"] == sup]
        with st.expander(f"👤 {sup} — {len(df_sup)} vencido(s)", expanded=True):
            rows_list = list(df_sup.iterrows())
            for i in range(0, len(rows_list), 3):
                grupo = rows_list[i:i + 3]
                cols  = st.columns(3)
                for j, (_, row) in enumerate(grupo):
                    with cols[j]:
                        dias = (hoje - row["Data acerto"]).days
                        nome = _nome_curto(row["Nome"])
                        forma_icon = FORMAS.get(row["Forma"], "")
                        forma_txt  = row["Forma"] or "—"
                        tem_agenda = pd.notna(row["Data agendada"]) and bool(row["Data agendada"])

                        if tem_agenda:
                            hora_s = row.get("Hora agendada", "") or ""
                            hora_t = f" às {hora_s}" if hora_s else ""
                            agenda_html = (
                                f'<div style="margin-top:4px;background:#e3f2fd;'
                                f'border-left:3px solid #1976d2;padding:3px 6px;'
                                f'border-radius:4px;font-size:0.85em;">'
                                f'📅 <b>Agendado:</b> '
                                f'{row["Data agendada"].strftime("%d/%m/%Y")}{hora_t}'
                                f'</div>'
                            )
                            btn_lbl = "🔄 Reagendar"
                        else:
                            agenda_html = ""
                            btn_lbl = "📅 Agendar"

                        with st.container(border=True):
                            st.markdown(
                                f'<div style="font-size:0.85em;line-height:1.6">'
                                f'<b>{nome}</b><br>'
                                f'<span style="color:#e74c3c;font-weight:bold">'
                                f'🔴 Vencido há {dias} dia(s)</span><br>'
                                f'Previsto: {row["Data acerto"].strftime("%d/%m/%Y")}<br>'
                                f'{forma_icon} {forma_txt}<br>'
                                f'{_R(row["Valor"])}<br>'
                                f'<span style="color:#888;font-size:0.9em">'
                                f'Pedido: {row["Código"] or row["id"]}'
                                f'</span>'
                                f'</div>'
                                f'{agenda_html}',
                                unsafe_allow_html=True,
                            )
                            if st.button(
                                btn_lbl,
                                key=f"venc_{row['id']}",
                                use_container_width=True,
                            ):
                                st.session_state["_ag_id"] = row["id"]
                                st.rerun()


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

    # ── Dialogs chamados aqui (nível de render, fora de qualquer tab/coluna) ──

    # Dialog: troca no mesmo dia? (Correios / Disk Tenha)
    if "_troca_check" in st.session_state:
        _dialog_troca_mesmo_dia()

    # Dialog: agendar envio da maleta
    elif "_envio_maleta" in st.session_state:
        _dialog_agendar_envio_maleta()

    # Google Agenda duplo (acerto + envio da maleta)
    elif "_gcal_duplo" in st.session_state or "_gcal_duplo_active" in st.session_state:
        duplo = st.session_state.pop("_gcal_duplo", None)
        if duplo:
            st.session_state["_gcal_duplo_active"] = duplo
        _dialog_gcal_duplo()

    # Confirmação Google Agenda simples (Presencial / Motoboy)
    else:
        gcal = st.session_state.pop("_gcal_dict", None)
        if gcal:
            st.session_state["_gcal_active"] = gcal
            _dialog_gcal_confirm()

    # Dialog de agendamento
    ag_id = st.session_state.get("_ag_id")
    if ag_id is not None:
        # Limpa a chave de data quando o dialog abre para um pedido diferente do anterior,
        # garantindo que o date_input sempre inicie com a data de hoje
        if st.session_state.get("_ag_id_prev") != ag_id:
            st.session_state.pop(f"dlg_data_{ag_id}", None)
            st.session_state["_ag_id_prev"] = ag_id
        rows = df[df["id"] == ag_id]
        if not rows.empty:
            _dialog_agendar(rows.iloc[0])
        else:
            st.session_state.pop("_ag_id", None)
            st.session_state.pop("_ag_id_prev", None)

    # ── Guias ─────────────────────────────────────────────────────────────────
    n_venc = int((df["Situação"] == "🔴 Vencido").sum()) if not df.empty else 0
    lbl_venc = f"🔴 Vencidos ({n_venc})" if n_venc else "🔴 Vencidos"

    tab1, tab2 = st.tabs(["📅 Calendário", lbl_venc])

    with tab1:
        _tab_calendario(df)

    with tab2:
        _tab_vencidos(df)
