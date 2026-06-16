import streamlit as st
import pandas as pd
from datetime import date, timedelta
from src.api.jueri_client import _get_lista_pedidos
from src.logic.acertos import (
    FORMAS, DIAS_PT,
    montar_acertos, semana_de, proxima_semana_resumo,
    save_agendamento, remove_agendamento,
)

_R = lambda v: f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
_Rmd = lambda v: f"R\\$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


# ── Cores de situação ─────────────────────────────────────────────────────────

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


# ── Card de um acerto no calendário ──────────────────────────────────────────

def _card(row: pd.Series) -> str:
    cor    = _cor(row["Situação"])
    forma  = FORMAS.get(row["Forma"], "")
    valor  = _R(row["Valor"])
    nome   = row["Nome"].split()[0]          # primeiro nome
    sit    = row["Situação"]
    return (
        f'<div style="background:{cor}22;border-left:3px solid {cor};'
        f'border-radius:4px;padding:4px 6px;margin:2px 0;font-size:0.78em;line-height:1.4">'
        f'<b>{nome}</b> {forma}<br>'
        f'<span style="color:{cor};font-weight:bold">{sit}</span><br>'
        f'{valor}'
        f'</div>'
    )


# ── Calendário semanal ────────────────────────────────────────────────────────

def _tab_calendario(df: pd.DataFrame, filtro_supervisor: str):
    hoje = date.today()

    # ── Resumo geral ─────────────────────────────────────────────────────────
    prox = proxima_semana_resumo(df, hoje)
    n_vencidos   = int((df["Situação"] == "🔴 Vencido").sum())       if not df.empty else 0
    n_a_agendar  = int((df["Situação"] == "⬜ A agendar").sum())     if not df.empty else 0

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("📅 Próxima semana",   prox["total"])
    c2.metric("✅ Já agendados",     prox["agendados"])
    c3.metric("⬜ A agendar (prox.)", prox["a_agendar"])
    c4.metric("🔴 Vencidos",         n_vencidos)

    if n_a_agendar:
        st.warning(f"⚠️ {n_a_agendar} pedido(s) sem data de acerto agendada — agende antes que vençam.")

    st.divider()

    # ── Navegação de semana ───────────────────────────────────────────────────
    if "acertos_semana_offset" not in st.session_state:
        st.session_state.acertos_semana_offset = 0

    col_prev, col_label, col_next = st.columns([1, 4, 1])
    with col_prev:
        if st.button("◀ Anterior"):
            st.session_state.acertos_semana_offset -= 1
    with col_next:
        if st.button("Próxima ▶"):
            st.session_state.acertos_semana_offset += 1

    offset  = st.session_state.acertos_semana_offset
    seg, dom = semana_de(hoje + timedelta(weeks=offset))

    with col_label:
        st.markdown(
            f"<h4 style='text-align:center;margin:0'>"
            f"Semana {seg.strftime('%d/%m')} – {dom.strftime('%d/%m/%Y')}"
            f"</h4>",
            unsafe_allow_html=True,
        )

    # ── Grade semanal ─────────────────────────────────────────────────────────
    dias = [seg + timedelta(days=i) for i in range(7)]
    cols = st.columns(7)

    for col, dia in zip(cols, dias):
        label_dia = f"**{DIAS_PT[dia.weekday()]}**  \n{dia.strftime('%d/%m')}"
        destaque  = "🔵 " if dia == hoje else ""
        col.markdown(f"{destaque}{label_dia}", unsafe_allow_html=False)

        if not df.empty:
            df_dia = df[df["Data ref"] == dia]
            if df_dia.empty:
                col.markdown(
                    '<div style="color:#bdc3c7;font-size:0.75em;text-align:center">—</div>',
                    unsafe_allow_html=True,
                )
            else:
                for _, row in df_dia.iterrows():
                    col.markdown(_card(row), unsafe_allow_html=True)
        else:
            col.markdown(
                '<div style="color:#bdc3c7;font-size:0.75em;text-align:center">—</div>',
                unsafe_allow_html=True,
            )

    # Legenda
    st.divider()
    st.caption(
        "**Legenda:** "
        "🟢 Realizado no prazo · "
        "🟠 Realizado com atraso · "
        "🔵 Agendado · "
        "⬜ A agendar · "
        "🔴 Vencido sem baixa"
    )


# ── Agendamento / edição ──────────────────────────────────────────────────────

def _tab_agendar(df: pd.DataFrame, todos_pedidos: list, filtro_supervisor: str):
    st.subheader("Agendar ou editar acerto")
    st.caption("Selecione um pedido aberto para registrar a data e forma do acerto.")

    if df.empty:
        st.info("Nenhum pedido disponível para agendamento.")
        return

    # Pedidos abertos — prioriza vencidos e sem agendamento
    abertos = df[df["Status"] == "Aberto"].copy()
    if abertos.empty:
        st.info("Não há pedidos abertos no período exibido.")
        return

    abertos = abertos.sort_values(["Situação", "Data acerto"])

    # Monta opções de seleção
    opcoes = {}
    for _, row in abertos.iterrows():
        sit   = row["Situação"]
        forma = f" {FORMAS.get(row['Forma'], '')} {row['Forma']}" if row["Forma"] else ""
        label = (
            f"{row['Nome']} | Acerto: {row['Data acerto'].strftime('%d/%m/%y')} "
            f"| {sit}{forma}"
        )
        opcoes[label] = row

    escolhido_label = st.selectbox("Pedido", list(opcoes.keys()))
    row_sel = opcoes[escolhido_label]

    col_f, col_d = st.columns(2)
    with col_f:
        forma_atual = row_sel["Forma"] if row_sel["Forma"] else list(FORMAS.keys())[0]
        forma = st.selectbox(
            "Forma de acerto",
            list(FORMAS.keys()),
            index=list(FORMAS.keys()).index(forma_atual) if forma_atual in FORMAS else 0,
            format_func=lambda f: f"{FORMAS[f]} {f}",
        )

    with col_d:
        data_padrao = row_sel["Data agendada"] or row_sel["Data acerto"]
        data_ag = st.date_input("Data agendada", value=data_padrao, format="DD/MM/YYYY")

    obs = st.text_input("Observação (opcional)", value=row_sel["Obs"] or "")

    col_salvar, col_remover = st.columns([2, 1])
    with col_salvar:
        if st.button("💾 Salvar agendamento", type="primary", use_container_width=True):
            save_agendamento(row_sel["id"], str(data_ag), forma, obs)
            st.success(f"Agendamento salvo: {row_sel['Nome']} — {data_ag.strftime('%d/%m/%Y')} — {FORMAS[forma]} {forma}")
            st.rerun()

    with col_remover:
        if row_sel["Data agendada"] and st.button("🗑️ Remover agendamento", use_container_width=True):
            remove_agendamento(row_sel["id"])
            st.info("Agendamento removido.")
            st.rerun()

    # Preview do pedido selecionado
    with st.expander("Detalhes do pedido selecionado"):
        info = {
            "Revendedora":   row_sel["Nome"],
            "Supervisora":   row_sel["Supervisor"],
            "Data acerto":   row_sel["Data acerto"].strftime("%d/%m/%Y"),
            "Pré-baixa":     _R(row_sel["Valor"]),
            "Situação":      row_sel["Situação"],
        }
        for k, v in info.items():
            st.markdown(f"**{k}:** {v}")


# ── Lista geral ───────────────────────────────────────────────────────────────

def _tab_lista(df: pd.DataFrame):
    st.subheader("Lista geral de acertos")

    if df.empty:
        st.info("Nenhum acerto no período.")
        return

    # Filtros
    col_sit, col_sup = st.columns(2)
    with col_sit:
        situacoes = ["Todas"] + sorted(df["Situação"].unique().tolist())
        sit_filtro = st.selectbox("Situação", situacoes)
    with col_sup:
        sups = ["Todas"] + sorted(df["Supervisor"].unique().tolist())
        sup_filtro = st.selectbox("Supervisora", sups)

    df_f = df.copy()
    if sit_filtro != "Todas":
        df_f = df_f[df_f["Situação"] == sit_filtro]
    if sup_filtro != "Todas":
        df_f = df_f[df_f["Supervisor"] == sup_filtro]

    # Métricas da listagem filtrada
    n_real  = (df_f["Situação"] == "✅ Realizado").sum()
    n_atr   = df_f["Situação"].str.contains("Atrasou").sum()
    n_ag    = (df_f["Situação"] == "📅 Agendado").sum()
    n_venc  = (df_f["Situação"] == "🔴 Vencido").sum()

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("✅ Realizados", n_real)
    c2.metric("⚠️ Com atraso", n_atr)
    c3.metric("📅 Agendados",  n_ag)
    c4.metric("🔴 Vencidos",   n_venc)

    st.divider()

    exib = df_f[[
        "Nome", "Supervisor", "Situação", "Forma",
        "Data acerto", "Data agendada", "Data baixa", "Valor",
    ]].copy()
    exib["Data acerto"]   = exib["Data acerto"].apply(
        lambda d: d.strftime("%d/%m/%y") if pd.notna(d) else "—"
    )
    exib["Data agendada"] = exib["Data agendada"].apply(
        lambda d: d.strftime("%d/%m/%y") if pd.notna(d) and d is not None else "—"
    )
    exib["Data baixa"] = exib["Data baixa"].apply(
        lambda d: d.strftime("%d/%m/%y") if pd.notna(d) and d is not None else "—"
    )

    def _estilo_sit(val):
        c = _cor(str(val))
        return f"color:{c};font-weight:bold"

    st.dataframe(
        exib.style
            .map(_estilo_sit, subset=["Situação"])
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

    if filtro_supervisor:
        todos = [p for p in todos_bruto if (p.get("supervisor_nome") or "") == filtro_supervisor]
    else:
        todos = todos_bruto

    df = montar_acertos(todos)

    tab1, tab2, tab3 = st.tabs(["📅 Calendário", "✏️ Agendar acerto", "📋 Lista geral"])

    with tab1:
        _tab_calendario(df, filtro_supervisor)

    with tab2:
        _tab_agendar(df, todos, filtro_supervisor)

    with tab3:
        _tab_lista(df)
