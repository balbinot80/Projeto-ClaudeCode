import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import date, timedelta
from src.api.jueri_client import _get_lista_pedidos
from src.logic.revendedoras import (
    MINIMO_REV, parse_date,
    meses_disponiveis, calcular_competencia,
    pedidos_abertos_sem_prebaixa, analise_periodo,
)
from src.logic.niveis import (
    NIVEIS_PECAS, MINIMO_VENDAS, NIVEL_SUPERIOR, LIMIAR_SUBIDA, ICONE_NIVEL,
    classificar_revendedoras, alertas_rebaixamento, alertas_subida,
)

_CORES_RISCO = {
    "🟢 No ritmo":           "#2ecc71",
    "🟢 OK":                 "#2ecc71",
    "🟡 Abaixo do ritmo":   "#f1c40f",
    "🟡 Abaixo do mínimo":  "#f39c12",
    "🟠 Abaixo do mínimo":  "#e67e22",
    "🔴 Sem vendas":         "#e74c3c",
}

_R    = lambda v: f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
_Rmd  = lambda v: f"R\\$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


# ── Helpers de estilo ─────────────────────────────────────────────────────────

def _estilo_risco(val):
    cor = _CORES_RISCO.get(str(val), "")
    if not cor:
        return ""
    return f"color: {cor}; font-weight: bold"


def _estilo_total(val):
    try:
        v = float(val)
        if v == 0:
            return "color: #e74c3c; font-weight: bold"
        if v < MINIMO_REV:
            return "color: #e67e22; font-weight: bold"
        return "color: #27ae60; font-weight: bold"
    except Exception:
        return ""


# ── Tab 1: Competência ────────────────────────────────────────────────────────

def _tab_competencia(df_res: pd.DataFrame, mes_label: str):
    st.subheader(f"Vendas por revendedora — {mes_label}")
    st.caption(
        "**Baixados no mês** = valor_total dos pedidos com data de baixa no mês. "
        "**Pré-baixa** = soma dos pedidos abertos com data de acerto no mês."
    )

    if df_res.empty:
        st.info("Nenhum dado para o mês selecionado.")
        return

    supervisoras = sorted(df_res["Supervisor"].unique())

    # Tabela por supervisora
    for sup in supervisoras:
        df_sup = df_res[df_res["Supervisor"] == sup].copy()
        total_sup = df_sup["Total"].sum()
        n_ok = (df_sup["Total"] >= MINIMO_REV).sum()
        n_risco = len(df_sup) - n_ok

        ticket_sup_val = total_sup / len(df_sup) if len(df_sup) > 0 else 0
        badge = f" — ⚠️ {n_risco} em risco" if n_risco else ""
        with st.expander(
            f"**{sup}** — {len(df_sup)} revendedoras · total {_Rmd(total_sup)} · ticket médio {_Rmd(ticket_sup_val)}{badge}",
            expanded=False,
        ):
            exib = df_sup[["Nome", "Pedidos", "Baixado", "Pré-baixa", "Total", "Risco"]].copy()
            exib.columns = ["Nome", "Pedidos", "Baixado (R$)", "Pré-baixa (R$)", "Total (R$)", "Risco"]
            st.dataframe(
                exib.style
                    .map(_estilo_risco, subset=["Risco"])
                    .map(_estilo_total, subset=["Total (R$)"])
                    .format({"Baixado (R$)": _R, "Pré-baixa (R$)": _R, "Total (R$)": _R}),
                use_container_width=True, hide_index=True,
            )
            st.caption(f"Subtotal {sup}: **{_Rmd(total_sup)}**")

    st.divider()
    st.markdown(f"**Total geral do mês: {_Rmd(df_res['Total'].sum())}**")

    # Gráfico barras empilhadas (baixado + pré-baixa)
    df_graf = df_res.sort_values("Total", ascending=False).head(30)
    fig = go.Figure()
    fig.add_bar(
        x=df_graf["Nome"], y=df_graf["Baixado"],
        name="Baixado", marker_color="#6B2737",
    )
    fig.add_bar(
        x=df_graf["Nome"], y=df_graf["Pré-baixa"],
        name="Pré-baixa", marker_color="#AB6776",
    )
    fig.add_hline(y=MINIMO_REV, line_dash="dash", line_color="#e74c3c",
                  annotation_text=f"Mínimo R${MINIMO_REV:.0f}", annotation_position="top right")
    fig.update_layout(
        barmode="stack", title="Vendas por revendedora (Top 30)",
        xaxis_tickangle=-45, legend=dict(orientation="h"),
        height=420, margin=dict(b=120),
    )
    st.plotly_chart(fig, use_container_width=True)

    # Export
    csv = df_res.drop(columns=["fk_revendedor_id"]).to_csv(index=False).encode("utf-8")
    st.download_button("Exportar CSV", csv, f"competencia_{mes_label.replace('/', '-')}.csv", "text/csv")


# ── Tab 2: Alertas ────────────────────────────────────────────────────────────

def _tab_alertas(df_zero: pd.DataFrame, df_res: pd.DataFrame):
    st.subheader("⚠️ Alertas do mês")

    # Alerta 1: Pré-baixa R$0
    col_a, col_b = st.columns(2)
    with col_a:
        st.markdown(f"#### 🔴 Sem pré-baixa — {len(df_zero)} pedido(s)")
        st.caption("Pedidos abertos com acerto neste mês e pré-baixa = R$0,00")
        if df_zero.empty:
            st.success("Nenhum pedido sem pré-baixa neste mês.")
        else:
            for sup in sorted(df_zero["Supervisor"].unique()):
                df_s = df_zero[df_zero["Supervisor"] == sup]
                st.markdown(f"**{sup}** — {len(df_s)} pedido(s)")
                st.dataframe(
                    df_s[["Nome", "Pedido", "Valor pedido", "Acerto"]].style
                        .format({"Valor pedido": _R}),
                    use_container_width=True, hide_index=True,
                )

    # Alerta 2: Abaixo do mínimo
    with col_b:
        df_abaixo = df_res[(df_res["Total"] > 0) & (df_res["Total"] < MINIMO_REV)].copy() if not df_res.empty else pd.DataFrame()
        st.markdown(f"#### 🟡 Abaixo do mínimo (< {_R(MINIMO_REV)}) — {len(df_abaixo)}")
        st.caption("Têm alguma venda, mas abaixo do mínimo de permanência na equipe.")
        if df_abaixo.empty:
            st.success("Nenhuma revendedora abaixo do mínimo neste mês.")
        else:
            exib = df_abaixo[["Nome", "Supervisor", "Total", "Pré-baixa", "Baixado"]].copy()
            exib.columns = ["Nome", "Supervisor", "Total (R$)", "Pré-baixa (R$)", "Baixado (R$)"]
            exib = exib.sort_values("Total (R$)")
            st.dataframe(
                exib.style
                    .map(_estilo_total, subset=["Total (R$)"])
                    .format({"Total (R$)": _R, "Pré-baixa (R$)": _R, "Baixado (R$)": _R}),
                use_container_width=True, hide_index=True,
            )



# ── Tab 3: Acompanhamento Semanal ─────────────────────────────────────────────

@st.dialog("Acompanhamento de Revendedora", width="large")
def _dialog_acompanhamento():
    import html as _html
    from src.logic.acompanhamentos import save_acompanhamento, get_ultimos_valores, get_historico, delete_acompanhamento

    # Tradução PT-BR do calendário (observer no DOM pai via srcdoc iframe)
    _js = (
        "var M={'January':'Janeiro','February':'Fevereiro','March':'Março',"
        "'April':'Abril','May':'Maio','June':'Junho','July':'Julho','August':'Agosto',"
        "'September':'Setembro','October':'Outubro','November':'Novembro','December':'Dezembro'};"
        "var D={'Su':'Dom','Mo':'Seg','Tu':'Ter','We':'Qua','Th':'Qui','Fr':'Sex','Sa':'Sáb'};"
        "function tr(r){"
        "r.querySelectorAll('select option').forEach(function(o){"
        "var t=o.textContent.trim();if(M[t])o.textContent=M[t];});"
        "r.querySelectorAll('[role=columnheader]').forEach(function(e){"
        "var t=e.textContent.trim();if(D[t])e.textContent=D[t];});"
        "}"
        "if(!window.parent._ptCal){"
        "window.parent._ptCal=1;"
        "var doc=window.parent.document;"
        "new MutationObserver(function(){"
        "doc.querySelectorAll('[data-baseweb=calendar]').forEach(tr);"
        "}).observe(doc.body,{childList:true,subtree:true});"
        "doc.querySelectorAll('[data-baseweb=calendar]').forEach(tr);}"
    )
    _src = _html.escape(f"<script>{_js}</script>")
    st.markdown(f'<iframe style="display:none" srcdoc="{_src}"></iframe>', unsafe_allow_html=True)

    nome     = st.session_state.get("_acomp_nome", "")
    pedido   = st.session_state.get("_acomp_pedido", "")
    valor    = st.session_state.get("_acomp_valor", 0.0)
    prebaixa = st.session_state.get("_acomp_prebaixa", {})

    if not nome:
        st.error("Revendedora não identificada.")
        return

    _sep = '&nbsp;&nbsp;<span style="color:#cbd5e1">·</span>&nbsp;&nbsp;'
    _info = f'<strong>Revendedora:</strong> {nome}'
    if pedido:
        _info += f'{_sep}Pedido:&nbsp;<strong>{pedido}</strong>'
    if valor:
        _info += f'{_sep}Valor:&nbsp;<strong>{_R(valor)}</strong>'
    st.markdown(
        f'<p style="margin-bottom:0;font-size:1.05em">{_info}</p>',
        unsafe_allow_html=True,
    )
    st.divider()

    data_sel  = st.date_input("Data do acompanhamento", value=date.today(), key="dlg_acomp_data", format="DD/MM/YYYY")
    descricao = st.text_area(
        "Como foi feito o acompanhamento *",
        placeholder="Ex: Ligação realizada, acordo de entrega até dia X...",
        key="dlg_acomp_desc",
    )

    # Pré-baixa por período — dados automáticos do Jueri
    ultimos  = get_ultimos_valores(nome)
    chaves   = ["0-7",      "8-15",      "16-20",      "21-30"]
    labels   = ["0–7 dias", "8–15 dias", "16–20 dias", "21–30 dias"]

    rows_pb = []
    for lbl, key in zip(labels, chaves):
        atual   = float(prebaixa.get(key, 0.0))
        efetivo = atual if atual > 0 else float(ultimos.get(key, 0.0))
        rows_pb.append({"Período": lbl, "Pré-baixa (R$)": efetivo})

    col_pb, col_hist = st.columns([2, 3])

    with col_pb:
        st.caption("📊 Pré-baixa por período — dados automáticos do Jueri.")
        st.dataframe(
            pd.DataFrame(rows_pb).style.format({"Pré-baixa (R$)": _R}),
            use_container_width=True,
            hide_index=True,
        )

    with col_hist:
        historico = get_historico(nome)
        st.markdown("**📋 Histórico de acompanhamentos**")
        if not historico:
            st.caption("Nenhum acompanhamento registrado ainda.")
        else:
            from datetime import datetime as _dt
            scroll = st.container(height=280)
            for i, reg in enumerate(reversed(historico)):
                try:
                    data_fmt = _dt.strptime(reg["data"], "%Y-%m-%d").strftime("%d/%m/%Y")
                except Exception:
                    data_fmt = reg.get("data", "?")
                uid = reg.get("_id") or reg.get("_local_idx", i)
                with scroll.container(border=True):
                    c_txt, c_del = st.columns([7, 1])
                    with c_txt:
                        st.caption(f"🗓️ {data_fmt}")
                        st.write(reg.get("descricao", ""))
                    with c_del:
                        if st.button("🗑️", key=f"del_acomp_{uid}", help="Remover este acompanhamento"):
                            delete_acompanhamento(
                                nome=nome,
                                record_id=reg.get("_id"),
                                local_idx=reg.get("_local_idx"),
                            )

    st.divider()
    c1, c2 = st.columns(2)
    if c1.button("💾 Salvar", type="primary", use_container_width=True, key="dlg_acomp_save"):
        if not descricao.strip():
            st.error("⚠️ Informe como foi feito o acompanhamento.")
        else:
            semanas = {key: r["Pré-baixa (R$)"] for key, r in zip(chaves, rows_pb)}
            save_acompanhamento(nome, str(data_sel), descricao.strip(), semanas)
            st.toast("✅ Acompanhamento registrado!")
            for _k in ("_acomp_nome", "_acomp_pedido", "_acomp_valor", "_acomp_prebaixa"):
                st.session_state.pop(_k, None)
            st.rerun(scope="app")
    if c2.button("Cancelar", use_container_width=True, key="dlg_acomp_cancel"):
        for _k in ("_acomp_nome", "_acomp_pedido", "_acomp_valor", "_acomp_prebaixa"):
            st.session_state.pop(_k, None)
        st.rerun(scope="app")


def _build_info_maps(todos_pedidos: list, mes: int, ano: int) -> tuple:
    """Retorna (subida_map, rebaixa_map, premio_map) {nome → texto tooltip}."""
    from src.logic.niveis import alertas_subida, alertas_rebaixamento
    from src.logic.premiacoes import load_premiacoes, calcular_ranking

    subida_map, rebaixa_map, premio_map = {}, {}, {}

    try:
        df_sub = alertas_subida(todos_pedidos, mes, ano)
        if not df_sub.empty:
            for _, r in df_sub.iterrows():
                if "Já" in str(r["Situação"]):
                    txt = f"🔼 Nível: já atingiu a meta para subir para {r['Próx. nível']}"
                else:
                    falta = r.get("Falta", "")
                    txt = f"🔼 Nível: próxima de subir para {r['Próx. nível']}"
                    if falta:
                        txt += f"\n     Falta R$ {falta:,.2f} para atingir"
                subida_map[r["Nome"]] = txt
    except Exception:
        pass

    try:
        df_reb = alertas_rebaixamento(todos_pedidos, mes, ano)
        if not df_reb.empty:
            proj_col = next((c for c in df_reb.columns if "Projeção" in c), None)
            if proj_col:
                for _, r in df_reb.iterrows():
                    rebaixa = r.get("Rebaixa para", "—")
                    rebaixa_map[r["Nome"]] = (
                        f"🔽 {r[proj_col]}\n"
                        f"     Nível atual: {r['Nível atual']} → risco: {rebaixa}"
                    )
    except Exception:
        pass

    try:
        cfg   = load_premiacoes().get(f"{mes:02d}/{ano}", {})
        meta  = float(cfg.get("meta", 0.0))
        if meta > 0:
            prem_nome = cfg.get("premio", "Prêmio do mês")
            for r in calcular_ranking(todos_pedidos, mes, ano, meta):
                if r["Categoria"] == "ganhadora":
                    premio_map[r["Nome"]] = (
                        f"🏆 Premiação: GANHADORA\n"
                        f"     Prêmio: {prem_nome}\n"
                        f"     Total baixado: R$ {r['Baixado']:,.2f}"
                    )
                elif r["Categoria"] == "potencial":
                    premio_map[r["Nome"]] = (
                        f"🎯 Premiação: potencial ganhadora\n"
                        f"     Prêmio: {prem_nome}\n"
                        f"     Falta baixar: R$ {r['Falta']:,.2f}"
                    )
    except Exception:
        pass

    return subida_map, rebaixa_map, premio_map


def _tab_periodo(todos_pedidos: list, hoje: date, is_admin: bool = True):
    st.subheader("Pré-baixa por idade do pedido")
    st.caption(
        "Para cada janela de tempo, mostra os pedidos **abertos** criados naquele período "
        "e o valor já vendido (pré-baixa). "
        "🔵 Linhas em azul: revendedoras com o **primeiro pedido na história**."
    )

    # Info maps para tooltips
    _sub_map, _reb_map, _prm_map = _build_info_maps(todos_pedidos, hoje.month, hoje.year)

    # Pré-computar todos os períodos (intervalos exclusivos)
    _PERIODOS = [(7, 0), (15, 7), (20, 15), (30, 20)]
    _CHAVES   = ["0-7", "8-15", "16-20", "21-30"]
    _LABELS   = ["⏱ 0–7 dias", "⏱ 8–15 dias", "⏱ 16–20 dias", "⏱ 21–30 dias"]
    _dfs      = [analise_periodo(todos_pedidos, dias, hoje, dias_min=dmin)
                 for (dias, dmin) in _PERIODOS]

    # Pré-baixa atual por revendedora × período (alimenta o dialog)
    prebaixa_por_periodo: dict = {}
    for chave, df_p in zip(_CHAVES, _dfs):
        if not df_p.empty:
            for _, row in df_p.iterrows():
                nome = row["Nome"]
                if nome not in prebaixa_por_periodo:
                    prebaixa_por_periodo[nome] = {k: 0.0 for k in _CHAVES}
                prebaixa_por_periodo[nome][chave] = float(row["Pré-baixa"])

    # Detectar novas revendedoras (apenas 1 pedido em toda a história)
    pedidos_count: dict = {}
    for p in todos_pedidos:
        rid = p.get("fk_revendedor_id")
        if rid:
            pedidos_count[rid] = pedidos_count.get(rid, 0) + 1
    novas: set = set()
    for p in todos_pedidos:
        rid = p.get("fk_revendedor_id")
        if pedidos_count.get(rid, 0) == 1:
            comprador = p.get("comprador") or {}
            novas.add(comprador.get("nome") or f"Rev {rid}")

    # Acompanhamentos registrados (para métrica e destaque)
    from src.logic.acompanhamentos import load_acompanhamentos as _load_acomp
    _acomp_todos = _load_acomp()

    subtabs = st.tabs(_LABELS)

    for subtab, (dias, dias_min), chave, df in zip(subtabs, _PERIODOS, _CHAVES, _dfs):
        with subtab:
            if df.empty:
                st.info("Nenhum pedido aberto criado neste intervalo.")
                continue

            # Métricas
            n_total  = len(df)
            n_ok     = (df["Risco"] == "🟢 No ritmo").sum()
            n_risco  = (df["Risco"].isin(["🔴 Sem vendas", "🟠 Abaixo do mínimo"])).sum()
            total_pb = df["Pré-baixa"].sum()

            n_sem_acomp = sum(1 for n in df["Nome"] if n not in _acomp_todos)

            c1, c2, c3, c4, c5 = st.columns(5)
            c1.metric("Pedidos no período", n_total)
            c2.metric("🟢 No ritmo", n_ok,
                      help="Ritmo de referência (3M): média mensal das vendas baixadas nos 3 meses anteriores. "
                           "Representa o que a revendedora costuma vender por mês. "
                           "Para novas revendedoras sem histórico, usa R$ 300 como referência mínima.")
            c3.metric("🔴🟠 Em risco", n_risco)
            c4.metric("Total pré-baixa", _R(total_pb))
            c5.metric("📋 Sem acompanhamento", n_sem_acomp,
                      help="Revendedoras sem nenhum acompanhamento registrado no sistema")

            # ── Tabela detalhada ──────────────────────────────────────────────
            df_show = df.copy()

            # Novas revendedoras vêm primeiro
            df_show["_nova"] = df_show["Nome"].isin(novas).astype(int)
            df_show = (
                df_show.sort_values(["_nova", "Risco"], ascending=[False, True])
                .drop(columns="_nova").reset_index(drop=True)
            )

            # Coluna 🔔 — ícones de alerta com tooltip ao passar o mouse
            def _alerta_icons(nome):
                icons = []
                tem_pos = nome in _sub_map or nome in _prm_map
                if nome in _sub_map:
                    icons.append("🔼")
                if nome in _reb_map and not tem_pos:
                    icons.append("🔽")
                if nome in _prm_map:
                    icons.append("🏆" if "Ganhadora" in _prm_map[nome] else "🎯")
                return "".join(icons)

            def _alerta_html(nome):
                parts = []
                tem_pos = nome in _sub_map or nome in _prm_map
                if nome in _sub_map:
                    _tip = _sub_map[nome].replace('"', "&quot;").replace("\n", "&#10;")
                    parts.append(f'<span title="{_tip}" style="cursor:help">🔼</span>')
                if nome in _reb_map and not tem_pos:
                    _tip = _reb_map[nome].replace('"', "&quot;").replace("\n", "&#10;")
                    parts.append(f'<span title="{_tip}" style="cursor:help">🔽</span>')
                if nome in _prm_map:
                    _icon = "🏆" if "Ganhadora" in _prm_map[nome] else "🎯"
                    _tip  = _prm_map[nome].replace('"', "&quot;").replace("\n", "&#10;")
                    parts.append(f'<span title="{_tip}" style="cursor:help">{_icon}</span>')
                return "".join(parts) or ""

            df_show["🔔"] = df_show["Nome"].apply(_alerta_icons)

            # ✅/❌ — acompanhamento nos últimos 7 dias
            from datetime import datetime as _dt_ac
            _corte_ac = date.today() - timedelta(days=7)

            def _tem_acomp_semana(nome_rev: str) -> bool:
                for reg in _acomp_todos.get(nome_rev, []):
                    try:
                        if _dt_ac.strptime(reg["data"], "%Y-%m-%d").date() >= _corte_ac:
                            return True
                    except Exception:
                        pass
                return False

            # ── Cabeçalho ────────────────────────────────────────────────────
            _sup_off = 1 if is_admin else 0
            _PC = ([1.9, 0.55, 1.9, 3.3]
                   + ([2.8] if is_admin else [])
                   + [1.0, 1.0, 0.8, 1.55, 1.9])
            _PH = (["Ação", "🔔", "Risco", "Nome"]
                   + (["Supervisor"] if is_admin else [])
                   + ["Criado", "Acerto", "Dias", "Pré-baixa", "Ritmo (3M)"])
            _HS = ("font-size:0.73em;font-weight:700;color:#64748b;"
                   "text-transform:uppercase;letter-spacing:0.4px")

            hcols = st.columns(_PC)
            for _hc, _lbl in zip(hcols, _PH):
                _hc.markdown(f'<span style="{_HS}">{_lbl}</span>', unsafe_allow_html=True)

            st.markdown(
                '<hr style="margin:4px 0 6px 0;border:none;border-top:2px solid #e2e8f0">',
                unsafe_allow_html=True,
            )

            # ── Linhas de dados ───────────────────────────────────────────────
            for _i, (_, _row) in enumerate(df_show.iterrows()):
                _nome  = _row.get("Nome", "")
                _risco = _row.get("Risco", "")
                _tem   = _tem_acomp_semana(_nome)
                _nova  = _nome in novas

                dcols = st.columns(_PC)

                with dcols[0]:
                    _btn_lbl = "✅ Registrado" if _tem else "💬 Acompanhar"
                    _btn_tp  = "secondary"     if _tem else "primary"
                    if st.button(_btn_lbl, key=f"acomp_{chave}_{_i}",
                                 use_container_width=True, type=_btn_tp):
                        st.session_state["_acomp_nome"] = _nome
                        _ped = _row.get("Pedido", "")
                        st.session_state["_acomp_pedido"] = (
                            str(_ped) if _ped and str(_ped) not in ("nan", "None", "") else ""
                        )
                        st.session_state["_acomp_valor"]   = float(_row.get("Valor pedido", 0) or 0)
                        st.session_state["_acomp_prebaixa"] = prebaixa_por_periodo.get(_nome, {})
                        _dialog_acompanhamento()

                dcols[1].markdown(_alerta_html(_nome), unsafe_allow_html=True)

                _cor_r = _CORES_RISCO.get(_risco, "#64748b")
                dcols[2].markdown(
                    f'<b style="color:{_cor_r};font-size:0.87em">{_risco}</b>',
                    unsafe_allow_html=True,
                )

                _nome_html = (
                    f'<b style="color:#1d4ed8">{_nome}</b>' if _nova else
                    f'<span>{_nome}</span>'
                )
                dcols[3].markdown(_nome_html, unsafe_allow_html=True)

                if is_admin:
                    dcols[4].markdown(
                        f'<span style="font-size:0.87em;color:#475569">'
                        f'{_row.get("Supervisor","")}</span>',
                        unsafe_allow_html=True,
                    )

                dcols[4 + _sup_off].markdown(_row.get("Criado", ""))
                dcols[5 + _sup_off].markdown(_row.get("Acerto", ""))
                dcols[6 + _sup_off].markdown(f'**{_row.get("Dias do pedido", "")}**')
                dcols[7 + _sup_off].markdown(
                    f'<span style="font-size:0.87em">{_R(_row.get("Pré-baixa", 0))}</span>',
                    unsafe_allow_html=True,
                )
                dcols[8 + _sup_off].markdown(
                    f'<span style="font-size:0.87em">{_R(_row.get("Ritmo ref. (3M)", 0))}</span>',
                    unsafe_allow_html=True,
                )

                st.markdown(
                    '<hr style="margin:2px 0;border:none;border-top:1px solid #f1f5f9">',
                    unsafe_allow_html=True,
                )

            # Gráfico (abaixo da tabela)
            df_graf = df.sort_values("Pré-baixa", ascending=False).head(40).copy()
            fig = go.Figure()
            for risco, cor in [
                ("🟢 No ritmo",         "#2ecc71"),
                ("🟡 Abaixo do ritmo",  "#f1c40f"),
                ("🟠 Abaixo do mínimo", "#e67e22"),
                ("🔴 Sem vendas",        "#e74c3c"),
            ]:
                df_r = df_graf[df_graf["Risco"] == risco]
                if df_r.empty:
                    continue
                fig.add_bar(
                    x=df_r["Nome"], y=df_r["Pré-baixa"], name=risco, marker_color=cor,
                    customdata=df_r[["Ritmo ref. (3M)", "% do ritmo", "Dias do pedido"]].values,
                    hovertemplate=(
                        "<b>%{x}</b><br>Pré-baixa: R$ %{y:,.0f}<br>"
                        "Ritmo ref. (média 3M): R$ %{customdata[0]:,.0f}<br>"
                        "% do ritmo: %{customdata[1]:.1f}%<br>"
                        "Dias do pedido: %{customdata[2]}<br><extra></extra>"
                    ),
                )
            fig.add_hline(y=MINIMO_REV, line_dash="dash", line_color="#e74c3c",
                          annotation_text=f"Mínimo R${MINIMO_REV:.0f}")
            lbl_intervalo = f"{dias_min+1}–{dias} dias" if dias_min else f"0–{dias} dias"
            fig.update_layout(
                barmode="group", title=f"Pré-baixa — pedidos abertos ({lbl_intervalo})",
                xaxis_tickangle=-45, height=400, margin=dict(b=120),
                legend=dict(orientation="h", yanchor="bottom", y=1.02),
            )
            st.plotly_chart(fig, use_container_width=True)


# ── Tab 4: Visão gerencial ────────────────────────────────────────────────────

def _tab_gerencial(df_res: pd.DataFrame, todos_pedidos: list, hoje: date):
    """
    Visualizações gerenciais baseadas em boas práticas de gestão de equipes de vendas:
    - Leaderboard com ranking e metas (identifica top e bottom performers)
    - Distribuição por faixa de receita (entende a saúde da equipe)
    - Comparativo por supervisora (benchmarking de times)
    - Funil de atividade (pedido → pré-baixa → acima do mínimo)
    """
    df_res = df_res.copy()  # evita mutação do DataFrame original
    if df_res.empty:
        st.info("Sem dados disponíveis para o mês selecionado.")
        return

    st.subheader("Visão gerencial")
    st.caption(
        "Painéis de controle baseados em metodologias de gestão de equipes de vendas "
        "por consignação (Sales Performance Management — KPI tracking, risk segmentation, "
        "team benchmarking)."
    )

    # ── Leaderboard ─────────────────────────────────────────────────────────
    st.markdown("#### 🏆 Leaderboard — ranking de revendedoras")
    st.caption(
        "As barras mostram o total vendido (baixado + pré-baixa). "
        "A linha vermelha é o mínimo de permanência (R$300). "
        "Use este gráfico para identificar as top performers e aquelas que precisam de atenção."
    )

    df_rank = df_res.sort_values("Total", ascending=True).copy()
    df_rank["Cor"] = df_rank["Risco"].map(_CORES_RISCO).fillna("#95a5a6")

    fig_rank = go.Figure()
    fig_rank.add_bar(
        x=df_rank["Total"],
        y=df_rank["Nome"],
        orientation="h",
        marker_color=df_rank["Cor"],
        text=df_rank["Total"].apply(lambda v: _R(v)),
        textposition="outside",
        customdata=df_rank[["Supervisor", "Risco"]].values,
        hovertemplate=(
            "<b>%{y}</b><br>"
            "Total: %{text}<br>"
            "Supervisora: %{customdata[0]}<br>"
            "Situação: %{customdata[1]}<br>"
            "<extra></extra>"
        ),
    )
    fig_rank.add_vline(x=MINIMO_REV, line_dash="dash", line_color="#e74c3c",
                       annotation_text=f"Mínimo R${MINIMO_REV:.0f}", annotation_position="top right")
    fig_rank.update_layout(
        height=max(400, len(df_rank) * 22),
        xaxis_title="Total vendido",
        xaxis=dict(tickformat=",.0f", tickprefix="R$ "),
        yaxis_title="",
        showlegend=False,
        margin=dict(l=220, r=100),
    )
    st.plotly_chart(fig_rank, use_container_width=True)

    st.divider()

    # ── Distribuição por faixa de receita ────────────────────────────────────
    col_l, col_r = st.columns(2)

    with col_l:
        st.markdown("#### 📊 Distribuição por faixa de receita")
        st.caption(
            "Histograma que mostra quantas revendedoras estão em cada faixa de receita. "
            "Uma equipe saudável tem a maior concentração acima do mínimo."
        )
        faixas = [0, 300, 600, 1000, 2000, 5000, float("inf")]
        rotulos = ["R$0–300", "R$301–600", "R$601–1K", "R$1K–2K", "R$2K–5K", "> R$5K"]
        cores_faixa = ["#e74c3c", "#f39c12", "#f1c40f", "#2ecc71", "#27ae60", "#1a7a4a"]

        df_res["Faixa"] = pd.cut(
            df_res["Total"],
            bins=faixas,
            labels=rotulos,
            right=True,
            include_lowest=True,
        )
        dist = df_res.groupby("Faixa", observed=True).size().reset_index(name="Qtd")

        fig_dist = px.bar(
            dist, x="Faixa", y="Qtd",
            color="Faixa",
            color_discrete_sequence=cores_faixa,
            text="Qtd",
            title="Revendedoras por faixa de receita",
        )
        fig_dist.update_traces(textposition="outside")
        fig_dist.update_layout(showlegend=False, height=350)
        st.plotly_chart(fig_dist, use_container_width=True)

    # ── Comparativo por supervisora ───────────────────────────────────────────
    with col_r:
        st.markdown("#### 👥 Desempenho por supervisora")
        st.caption(
            "Compara a soma e a média de vendas por equipe. "
            "Permite identificar supervisoras com equipes acima ou abaixo da média geral."
        )
        df_sup_agg = (
            df_res.groupby("Supervisor", as_index=False)
            .agg(
                Total=("Total", "sum"),
                Media=("Total", "mean"),
                Revendedoras=("Nome", "count"),
                OK=("Risco", lambda x: (x == "🟢 OK").sum()),
            )
            .sort_values("Total", ascending=False)
        )
        df_sup_agg["Média por rev."] = df_sup_agg["Media"].round(2)

        fig_sup = go.Figure()
        fig_sup.add_bar(
            x=df_sup_agg["Supervisor"], y=df_sup_agg["Total"],
            name="Total equipe", marker_color="#6B2737",
            text=df_sup_agg["Total"].apply(_R),
            textposition="outside",
        )
        fig_sup.add_scatter(
            x=df_sup_agg["Supervisor"], y=df_sup_agg["Media"],
            mode="markers+text", name="Média por rev.",
            marker=dict(size=12, color="#AB6776", symbol="diamond"),
            text=df_sup_agg["Media"].apply(_R),
            textposition="top center",
        )
        fig_sup.add_hline(y=MINIMO_REV, line_dash="dot", line_color="#e74c3c",
                          annotation_text="Mínimo/rev", annotation_position="top right")
        fig_sup.update_layout(
            title="Total e média por supervisora",
            xaxis_tickangle=-20, height=380,
            legend=dict(orientation="h"),
            yaxis=dict(tickformat=",.0f", tickprefix="R$ "),
        )
        st.plotly_chart(fig_sup, use_container_width=True)

    st.divider()

    # ── Funil de atividade ────────────────────────────────────────────────────
    st.markdown("#### 🔽 Funil de atividade — pedidos abertos (últimos 30 dias)")
    st.caption(
        "Mostra a conversão dos pedidos abertos recentes: do total de pedidos, "
        "quantos já têm alguma venda, e quantos estão acima do mínimo de R$300. "
        "Referência: modelo de funil de vendas por consignação (Sales Funnel Analysis)."
    )
    df30 = analise_periodo(todos_pedidos, 30, hoje)
    if not df30.empty:
        n_total30 = len(df30)
        n_com_venda = (df30["Pré-baixa"] > 0).sum()
        n_acima_min = (df30["Pré-baixa"] >= MINIMO_REV).sum()
        n_no_ritmo  = (df30["Risco"] == "🟢 No ritmo").sum()

        fig_funil = go.Figure(go.Funnel(
            y=["Pedidos abertos (30 dias)", "Com alguma venda", f"Acima do mínimo (≥ R${MINIMO_REV:.0f})", "No ritmo de vendas"],
            x=[n_total30, n_com_venda, n_acima_min, n_no_ritmo],
            textinfo="value+percent initial",
            marker_color=["#6B2737", "#AB6776", "#f39c12", "#2ecc71"],
        ))
        fig_funil.update_layout(title="Funil de atividade das revendedoras", height=320)
        st.plotly_chart(fig_funil, use_container_width=True)
    else:
        st.info("Sem pedidos abertos nos últimos 30 dias para o funil.")



# ── Tab 5: Níveis ─────────────────────────────────────────────────────────────

def _tab_niveis(todos_pedidos: list, mes: int, ano: int):
    st.subheader(f"Classificação por nível — {mes:02d}/{ano}")
    st.caption(
        "**Pérola**: 40–54 peças · **Ouro**: 55–75 peças · **Diamante**: 76–500 peças. "
        "Pedidos **fechados** têm resultado definitivo; pedidos **em aberto** mostram o parcial (pré-baixa)."
    )

    df_cls = classificar_revendedoras(todos_pedidos, mes, ano)

    # ── Cards de resumo ───────────────────────────────────────────────────────
    niveis_ordem = ["Diamante", "Ouro", "Pérola", "Sem nível"]
    cols_nv = st.columns(4)
    for col, nv in zip(cols_nv, niveis_ordem):
        qtd = int((df_cls["Nível"] == nv).sum()) if not df_cls.empty else 0
        col.metric(f"{ICONE_NIVEL.get(nv, '')} {nv}", qtd)

    st.divider()

    if df_cls.empty:
        st.info("Nenhuma revendedora com pedido no mês selecionado.")
        return

    def _estilo_status(val):
        cores = {
            "✅ Atingiu o mínimo":  "color: #27ae60; font-weight: bold",
            "⚠️ Abaixo do mínimo": "color: #e67e22; font-weight: bold",
            "🔴 Sem vendas":        "color: #e74c3c; font-weight: bold",
        }
        return cores.get(str(val), "")

    # ── Seção 1: Pedidos baixados (resultado definitivo) ──────────────────────
    df_bx = df_cls[df_cls["Tipo"] == "🔒 Baixado (fechado)"].copy()
    if not df_bx.empty:
        st.markdown("#### 🔒 Pedidos fechados no mês — resultado definitivo")
        st.caption(
            "Pedidos já encerrados. Nível pelo campo **quantidade_antes_baixa** (total original da maleta). "
            "Valor = **valor_total** vendido."
        )
        for nv in ["Diamante", "Ouro", "Pérola", "Sem nível"]:
            df_nv = df_bx[df_bx["Nível"] == nv]
            if df_nv.empty:
                continue
            with st.expander(
                f"{ICONE_NIVEL.get(nv, '')} **{nv}** — {len(df_nv)} pedido(s) fechado(s)",
                expanded=False,
            ):
                exib = df_nv[["Nome", "Supervisor", "Peças pedido", "Vendas mês", "Mínimo nível", "Status"]].copy()
                exib.columns = ["Nome", "Supervisor", "Peças (maleta)", "Vendas (R$)", "Mínimo (R$)", "Status"]
                st.dataframe(
                    exib.style
                        .map(_estilo_status, subset=["Status"])
                        .format({"Vendas (R$)": _R, "Mínimo (R$)": _R}),
                    use_container_width=True, hide_index=True,
                )

    # ── Seção 2: Pedidos em aberto (parcial — pré-baixa) ─────────────────────
    df_ab = df_cls[df_cls["Tipo"] == "🔓 Em aberto"].copy()
    if not df_ab.empty:
        st.markdown("#### 🔓 Pedidos em aberto — parcial (pré-baixa)")
        st.caption("Pedidos ainda não encerrados. O valor mostrado é o **parcial vendido** até agora (pré-baixa). Ainda podem melhorar.")
        for nv in ["Diamante", "Ouro", "Pérola", "Sem nível"]:
            df_nv = df_ab[df_ab["Nível"] == nv]
            if df_nv.empty:
                continue
            with st.expander(
                f"{ICONE_NIVEL.get(nv, '')} **{nv}** — {len(df_nv)} pedido(s) em aberto",
                expanded=False,
            ):
                exib = df_nv[["Nome", "Supervisor", "Peças pedido", "Vendas mês", "Mínimo nível", "Status"]].copy()
                exib.columns = ["Nome", "Supervisor", "Peças", "Pré-baixa (R$)", "Mínimo (R$)", "Status"]
                st.dataframe(
                    exib.style
                        .map(_estilo_status, subset=["Status"])
                        .format({"Pré-baixa (R$)": _R, "Mínimo (R$)": _R}),
                    use_container_width=True, hide_index=True,
                )

    st.divider()

    # ── Alerta: risco de rebaixamento ─────────────────────────────────────────
    st.markdown("#### ⬇️ Risco de rebaixamento")
    st.caption(
        "Análise dos **3 meses** (M-2, M-1 e mês atual). "
        "Projeção para o próximo mês com base no desempenho recente. "
        "Regra: 2 meses consecutivos abaixo do mínimo → rebaixamento."
    )
    df_reb = alertas_rebaixamento(todos_pedidos, mes, ano)

    def _estilo_proj(val):
        if "🔴" in str(val): return "color: #e74c3c; font-weight: bold"
        if "🟠" in str(val): return "color: #e67e22; font-weight: bold"
        if "🟡" in str(val): return "color: #f1c40f; font-weight: bold"
        return ""

    if df_reb.empty:
        st.success("Nenhuma revendedora com sinal de risco nos últimos 3 meses.")
    else:
        n_alto   = df_reb.apply(lambda r: any("🔴" in str(v) for v in r), axis=1).sum()
        n_atencao = df_reb.apply(lambda r: any("🟠" in str(v) for v in r), axis=1).sum()
        if n_alto:
            st.error(f"🔴 {n_alto} revendedora(s) com risco confirmado de rebaixamento no próximo mês!")
        if n_atencao:
            st.warning(f"🟠 {n_atencao} revendedora(s) com tendência negativa — monitorar.")

        cols_vendas = [c for c in df_reb.columns if c.startswith("Vendas ")]
        proj_col    = [c for c in df_reb.columns if c.startswith("Projeção")]
        fmt_cols    = {"Mínimo do nível": _R}
        for c in cols_vendas:
            fmt_cols[c] = lambda v: _R(v) if isinstance(v, (int, float)) else str(v)

        styled = df_reb.style.format(fmt_cols)
        if proj_col:
            styled = styled.map(_estilo_proj, subset=proj_col)

        st.dataframe(styled, use_container_width=True, hide_index=True)

    st.divider()

    # ── Alerta: potencial de subida ───────────────────────────────────────────
    st.markdown("#### ⬆️ Potencial de subida de nível")
    st.caption(
        "Revendedoras com vendas ≥ 75% da meta do próximo nível. "
        "Inclui as que **já atingiram** a meta — priorize o contato para oferecer o pedido maior."
    )
    df_sub = alertas_subida(todos_pedidos, mes, ano)
    if df_sub.empty:
        st.info("Nenhuma revendedora próxima de subir de nível neste mês.")
    else:
        ja_atingiu = (df_sub["Situação"] == "✅ Já atingiu a meta").sum()
        proxima    = (df_sub["Situação"] == "🔜 Próxima de subir").sum()
        st.success(
            f"🚀 {len(df_sub)} revendedora(s) com potencial — "
            f"{ja_atingiu} já atingiram a meta · {proxima} próximas"
        )

        def _estilo_sit(val):
            if "Já atingiu" in str(val): return "color: #27ae60; font-weight: bold"
            if "Próxima"    in str(val): return "color: #e67e22; font-weight: bold"
            return ""

        st.dataframe(
            df_sub.style
                .map(_estilo_sit, subset=["Situação"])
                .format({"Vendas mês": _R, "Meta subida": _R, "Falta": _R}),
            use_container_width=True, hide_index=True,
        )


# ── Tab 6: Premiações ─────────────────────────────────────────────────────────

def _tab_premiacoes(todos_pedidos: list, mes: int, ano: int, mes_label: str):
    from src.logic.premiacoes import (
        load_premiacoes, save_premiacao, calcular_ranking, verificar_colar,
    )

    st.subheader(f"🏆 Premiações — {mes_label}")

    prem    = load_premiacoes()
    mes_key = f"{mes:02d}/{ano}"
    cfg     = prem.get(mes_key, {})
    meta_atual   = float(cfg.get("meta", 0.0))
    premio_atual = cfg.get("premio", "")

    # ── Configuração do mês ───────────────────────────────────────────────────
    with st.expander("⚙️ Configurar premiação do mês", expanded=(meta_atual == 0)):
        c1, c2 = st.columns(2)
        with c1:
            meta_input = st.number_input(
                "Meta de vendas (R$)", min_value=0.0, value=meta_atual,
                step=100.0, format="%.2f", key=f"meta_{mes_key}",
            )
        with c2:
            premio_input = st.text_input(
                "Prêmio do mês", value=premio_atual,
                placeholder="Ex: Kit beleza, Viagem...", key=f"premio_{mes_key}",
            )
        if st.button("💾 Salvar configuração", type="primary", key=f"salvar_{mes_key}"):
            save_premiacao(mes_key, meta_input, premio_input)
            st.success("Configuração salva!")
            st.rerun()

    if not meta_atual:
        st.info("Configure a meta de vendas do mês acima para ver o ranking de premiações.")
        return

    # ── Banner do prêmio ──────────────────────────────────────────────────────
    st.markdown(
        f'<div style="background:linear-gradient(135deg,#6B2737 0%,#AB6776 100%);'
        f'color:white;padding:16px 24px;border-radius:12px;margin-bottom:4px">'
        f'<span style="font-size:1.6em">🏆</span> '
        f'<span style="font-size:1.15em;font-weight:700">'
        f'{premio_atual or "Prêmio do mês"}</span>'
        f'<br><span style="opacity:0.85;font-size:0.9em">'
        f'Meta: {_R(meta_atual)} &nbsp;·&nbsp; {mes_label}</span>'
        f'</div>',
        unsafe_allow_html=True,
    )

    # ── Calcular ranking ──────────────────────────────────────────────────────
    ranking    = calcular_ranking(todos_pedidos, mes, ano, meta_atual)
    ganhadoras = [r for r in ranking if r["Categoria"] == "ganhadora"]
    potenciais = [r for r in ranking if r["Categoria"] == "potencial"]
    proximas   = [r for r in ranking if r["Categoria"] == "proxima"]
    colar      = verificar_colar(todos_pedidos, mes, ano)

    # Métricas resumo
    st.markdown("<br>", unsafe_allow_html=True)
    mc1, mc2, mc3, mc4 = st.columns(4)
    mc1.metric("🏆 Ganhadoras confirmadas", len(ganhadoras))
    mc2.metric("🎯 Potenciais ganhadoras",  len(potenciais))
    mc3.metric("📈 Próximas (≥ 70%)",       len(proximas))
    mc4.metric("💎 Colar personalizado",    len(colar))

    st.divider()

    # ── Seção 1: Ganhadoras confirmadas ───────────────────────────────────────
    st.markdown("### 🏆 Ganhadoras confirmadas")
    st.caption("Atingiram a meta com pedidos já **baixados** — resultado definitivo.")
    if ganhadoras:
        cols = st.columns(min(len(ganhadoras), 4))
        for i, r in enumerate(ganhadoras):
            with cols[i % 4]:
                st.markdown(
                    f'<div style="background:#fff8e1;border:2px solid #f9a825;'
                    f'border-radius:10px;padding:10px 12px;margin-bottom:8px">'
                    f'<div style="font-weight:700;font-size:0.95em">🥇 {r["Nome"]}</div>'
                    f'<div style="color:#888;font-size:0.78em;margin-bottom:4px">{r["Supervisor"]}</div>'
                    f'<div style="font-size:1em;font-weight:700">{_R(r["Total"])}</div>'
                    f'<div style="color:#27ae60;font-size:0.82em;font-weight:700">'
                    f'✅ {r["% da meta"]:.1f}% da meta</div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
    else:
        st.info("Nenhuma revendedora atingiu a meta com pedidos já baixados neste mês.")

    st.divider()

    # ── Seção 2: Potenciais ganhadoras ────────────────────────────────────────
    st.markdown("### 🎯 Potenciais ganhadoras")
    st.caption(
        "Total (baixado + pré-baixa) já atingiu a meta, mas ainda há pedidos em aberto. "
        "Ganharão se a pré-baixa converter."
    )
    if potenciais:
        cols = st.columns(min(len(potenciais), 4))
        for i, r in enumerate(potenciais):
            with cols[i % 4]:
                st.markdown(
                    f'<div style="background:#e8f5e9;border:2px solid #66bb6a;'
                    f'border-radius:10px;padding:10px 12px;margin-bottom:8px">'
                    f'<div style="font-weight:700;font-size:0.95em">🎯 {r["Nome"]}</div>'
                    f'<div style="color:#888;font-size:0.78em;margin-bottom:4px">{r["Supervisor"]}</div>'
                    f'<div style="font-size:1em;font-weight:700">{_R(r["Pré-baixa"])}</div>'
                    f'<div style="color:#1976d2;font-size:0.82em;font-weight:700">'
                    f'📊 {r["% da meta"]:.1f}% da meta</div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
    else:
        st.info("Nenhuma revendedora com total (baixado + pré-baixa) acima da meta neste mês.")

    st.divider()

    # ── Seção 3: Próximas da meta ─────────────────────────────────────────────
    st.markdown("### 📈 Próximas da meta")
    st.caption("Pedidos em aberto com pré-baixa entre 70% e 99% da meta (sem pedido baixado no mês).")
    if proximas:
        cols = st.columns(min(len(proximas), 4))
        for i, r in enumerate(proximas):
            with cols[i % 4]:
                st.markdown(
                    f'<div style="background:#e3f2fd;border:2px solid #90caf9;'
                    f'border-radius:10px;padding:10px 12px;margin-bottom:8px">'
                    f'<div style="font-weight:700;font-size:0.95em">📈 {r["Nome"]}</div>'
                    f'<div style="color:#888;font-size:0.78em;margin-bottom:4px">{r["Supervisor"]}</div>'
                    f'<div style="font-size:1em;font-weight:700">{_R(r["Pré-baixa"])}</div>'
                    f'<div style="color:#1565c0;font-size:0.82em;font-weight:700">'
                    f'{r["% pré-baixa"]:.1f}% — faltam {_R(r["Falta"])}</div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
    else:
        st.info("Nenhuma revendedora entre 70% e 99% da meta neste mês.")

    st.divider()

    # ── Seção 4: Colar personalizado ──────────────────────────────────────────
    st.markdown("### 💎 Colar personalizado — nova revendedora")
    st.caption(
        "Regra fixa: primeiro pedido de nova revendedora com valor > R$ 1.000,00. "
        "✅ Pedido finalizado = ganhou. 📊 Em aberto = contando pré-baixa (ainda pode mudar)."
    )
    if colar:
        cols = st.columns(min(len(colar), 4))
        for i, r in enumerate(colar):
            with cols[i % 4]:
                confirmado = r["status_pedido"] == "Baixado"
                status_txt = "✅ Pedido finalizado — ganhou!" if confirmado else "📊 Pedido em aberto (pré-baixa)"
                status_cor = "#7b1fa2" if confirmado else "#1976d2"
                borda      = "#9c27b0" if confirmado else "#90caf9"
                fundo      = "linear-gradient(135deg,#f3e5f5,#e1bee7)" if confirmado else "#e3f2fd"
                st.markdown(
                    f'<div style="background:{fundo};border:2px solid {borda};'
                    f'border-radius:10px;padding:10px 12px;margin-bottom:8px">'
                    f'<div style="font-weight:700;font-size:0.95em">💎 {r["Nome"]}</div>'
                    f'<div style="color:#888;font-size:0.78em;margin-bottom:4px">{r["Supervisor"]}</div>'
                    f'<div style="font-size:1em;font-weight:700">{_R(r["Valor 1º pedido"])}</div>'
                    f'<div style="color:{status_cor};font-size:0.82em;font-weight:700">'
                    f'{status_txt}</div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
    else:
        st.info("Nenhuma nova revendedora qualificou para o colar personalizado neste mês.")


# ── Render principal ──────────────────────────────────────────────────────────

def _calcular_desempenho_mes(todos_pedidos: list, mes: int, ano: int) -> list:
    """Retorna lista de dicts com desempenho por pedido para o mês/ano."""
    from src.logic.niveis import nivel_por_pecas, _qtd_original
    rows = []
    for p in todos_pedidos:
        status = p.get("status", "")
        comprador = p.get("comprador") or {}
        nome = comprador.get("nome") or f"Rev {p.get('fk_revendedor_id','?')}"
        supervisor = p.get("supervisor_nome") or "Sem supervisora"
        qtd_orig = _qtd_original(p)
        nivel = nivel_por_pecas(qtd_orig)

        if status == "Baixado":
            d = parse_date(p.get("data_baixa"))
            if not (d and d.month == mes and d.year == ano):
                continue
            valor_baixa = float(p.get("valor_total") or 0)
            qtd_vend = int(float(p.get("quantidade") or 0))
            # estima valor original da maleta pela proporção de peças
            if qtd_vend > 0 and qtd_orig > qtd_vend:
                valor_maleta = valor_baixa * qtd_orig / qtd_vend
            else:
                valor_maleta = valor_baixa

        elif status == "Aberto":
            d = parse_date(p.get("data_acerto"))
            if not (d and d.month == mes and d.year == ano):
                continue
            valor_baixa  = float(p.get("valor_pre_baixa") or 0)
            valor_maleta = float(p.get("valor_total") or 0)

        else:
            continue

        pct = valor_baixa / valor_maleta * 100 if valor_maleta > 0 else 0.0
        rows.append({
            "Nome":         nome,
            "Supervisor":   supervisor,
            "Nível":        nivel,
            "Valor Maleta": round(valor_maleta, 2),
            "Valor Baixa":  round(valor_baixa, 2),
            "Desempenho":   round(pct, 1),
            "Status":       status,
        })
    return rows


def _tab_desempenho(todos_pedidos: list, hoje: date):
    from src.logic.niveis import ICONE_NIVEL

    st.subheader("📊 Desempenho das Revendedoras")
    st.caption(
        "Desempenho (%) = Valor baixado no mês ÷ Valor total da maleta. "
        "Para pedidos **Abertos**: maleta = valor do pedido, baixa = pré-baixa acumulada. "
        "Para pedidos **Baixados**: maleta estimada proporcionalmente pela quantidade de peças."
    )

    MESES_PT  = ["Jan","Fev","Mar","Abr","Mai","Jun","Jul","Ago","Set","Out","Nov","Dez"]
    NIVEIS_ORD = ["Diamante", "Ouro", "Pérola", "Sem nível"]
    ano = hoje.year
    meses_range = list(range(1, hoje.month + 1))

    # ── Pré-calcular todos os meses de uma vez ────────────────────────────
    dados_por_mes: dict = {}
    for m in meses_range:
        dados_por_mes[m] = _calcular_desempenho_mes(todos_pedidos, m, ano)

    # ── Tabela anual: Nível × Mês ─────────────────────────────────────────
    st.markdown("### 📅 Visão anual por nível")

    def _celula(rows):
        if not rows:
            return "—"
        vm = sum(r["Valor Maleta"] for r in rows)
        vb = sum(r["Valor Baixa"]  for r in rows)
        pct = vb / vm * 100 if vm > 0 else 0.0
        return f"{pct:.1f}% ({len(rows)})"

    tbl = []
    for nivel in NIVEIS_ORD:
        row = {"Nível": f"{ICONE_NIVEL.get(nivel,'')} {nivel}"}
        for m in meses_range:
            sub = [r for r in dados_por_mes[m] if r["Nível"] == nivel]
            row[MESES_PT[m-1]] = _celula(sub)
        tbl.append(row)

    # Linha total
    row_total = {"Nível": "🔢 Total"}
    for m in meses_range:
        row_total[MESES_PT[m-1]] = _celula(dados_por_mes[m])
    tbl.append(row_total)

    st.dataframe(
        pd.DataFrame(tbl).set_index("Nível"),
        use_container_width=True,
    )

    # ── Detalhamento por mês ───────────────────────────────────────────────
    st.markdown("### 🔍 Detalhamento por mês")

    opcoes = [(m, f"{MESES_PT[m-1]}/{ano}") for m in reversed(meses_range)]
    mes_lbl = st.selectbox("Mês", [lb for _, lb in opcoes], key="desemp_mes_sel")
    mes_sel = next(m for m, lb in opcoes if lb == mes_lbl)

    rows_mes = dados_por_mes.get(mes_sel, [])
    if not rows_mes:
        st.info("Sem dados para este mês.")
        return

    vm_total = sum(r["Valor Maleta"] for r in rows_mes)
    vb_total = sum(r["Valor Baixa"]  for r in rows_mes)
    pct_geral = vb_total / vm_total * 100 if vm_total > 0 else 0.0

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Pedidos", len(rows_mes))
    c2.metric("Total da maleta", _R(vm_total))
    c3.metric("Total baixado",   _R(vb_total))
    c4.metric("Desempenho geral", f"{pct_geral:.1f}%")

    st.divider()

    # Tabela por revendedora ordenada por desempenho
    df_det = pd.DataFrame(rows_mes).sort_values("Desempenho", ascending=False)
    df_det["Nível"] = df_det["Nível"].apply(lambda n: f"{ICONE_NIVEL.get(n,'')} {n}")
    df_show = df_det[["Nome", "Nível", "Supervisor", "Status",
                       "Valor Maleta", "Valor Baixa", "Desempenho"]].copy()
    st.dataframe(
        df_show.style
            .format({
                "Valor Maleta": _R,
                "Valor Baixa":  _R,
                "Desempenho":   lambda v: f"{v:.1f}%",
            }),
        use_container_width=True,
        hide_index=True,
    )


def render(filtro_supervisor: str = ""):
    """
    filtro_supervisor: se preenchido, restringe todos os dados à equipe desta supervisora.
    Passado automaticamente pelo app.py quando o usuário logado tem role='supervisora'.
    """
    _is_admin = not bool(filtro_supervisor)
    if filtro_supervisor:
        st.header(f"👥 Minha Equipe — {filtro_supervisor}")
    else:
        st.header("👥 Acompanhamento de Revendedoras")

    with st.spinner("Carregando pedidos..."):
        try:
            todos_pedidos_bruto = _get_lista_pedidos()
        except Exception as e:
            st.error(f"Erro ao carregar dados: {e}")
            return

    if not todos_pedidos_bruto:
        st.warning("Nenhum pedido encontrado.")
        return

    # Aplica filtro de supervisora: se definido, mantém apenas pedidos da sua equipe
    if filtro_supervisor:
        todos_pedidos = [
            p for p in todos_pedidos_bruto
            if (p.get("supervisor_nome") or "") == filtro_supervisor
        ]
        if not todos_pedidos:
            st.warning("Nenhum pedido encontrado para sua equipe.")
            return
    else:
        todos_pedidos = todos_pedidos_bruto

    hoje = date.today()

    # ── Filtro de mês ─────────────────────────────────────────────────────────
    meses = meses_disponiveis(7, futuros=1)
    opcoes = [f"{m:02d}/{y}" for y, m in meses]

    mes_atual = f"{hoje.month:02d}/{hoje.year}"
    idx_default = opcoes.index(mes_atual) if mes_atual in opcoes else 0

    col_f, col_info = st.columns([2, 5])
    with col_f:
        mes_sel = st.selectbox("Mês de competência", opcoes, index=idx_default)
    mes_num = int(mes_sel[:2])
    ano_num = int(mes_sel[3:])

    with col_info:
        st.caption(
            f"**Regra:** pedidos **Baixados** com data_baixa em {mes_sel} + "
            f"pedidos **Abertos** com previsão de acerto em {mes_sel} (soma da pré-baixa)."
        )

    # ── Calcular dados ────────────────────────────────────────────────────────
    df_res, df_det = calcular_competencia(todos_pedidos, mes_num, ano_num)
    df_zero = pedidos_abertos_sem_prebaixa(todos_pedidos, mes_num, ano_num)

    # ── Métricas globais ──────────────────────────────────────────────────────
    total_mes   = df_res["Total"].sum()    if not df_res.empty else 0
    total_pb    = df_res["Pré-baixa"].sum() if not df_res.empty else 0
    total_bx    = df_res["Baixado"].sum()   if not df_res.empty else 0
    n_rev       = len(df_res)
    n_zero      = len(df_zero)
    n_abaixo    = int(((df_res["Total"] > 0) & (df_res["Total"] < MINIMO_REV)).sum()) if not df_res.empty else 0
    n_sem_res   = int((df_res["Total"] == 0).sum()) if not df_res.empty else 0

    ticket_medio = total_mes / n_rev if n_rev > 0 else 0

    # Linha 1 — valores financeiros (colunas largas para não truncar)
    c1, c2, c3, c4, c5 = st.columns([1, 2, 2, 2, 2])
    c1.metric("Revendedoras", n_rev)
    c2.metric("Total vendido", _R(total_mes))
    c3.metric("↳ Baixados", _R(total_bx))
    c4.metric("↳ Pré-baixa", _R(total_pb))
    c5.metric("🎯 Ticket médio", _R(ticket_medio))

    # Linha 2 — alertas de risco
    c6, c7, _esp = st.columns([2, 2, 5])
    c6.metric("🟡 Abaixo do mínimo", n_abaixo)
    c7.metric("🔴 Sem vendas", n_zero + n_sem_res,
              help="Pedidos abertos com R$0 + revendedoras com total = R$0")

    # ── Tabs ──────────────────────────────────────────────────────────────────
    _tab_labels = [
        "📅 Competência",
        "⚠️ Alertas",
        "⏱️ Acompanhamento Semanal",
        "📈 Visão gerencial",
        "🏅 Níveis",
        "🏆 Premiações",
    ]
    if _is_admin:
        _tab_labels.append("📊 Desempenho")

    _tabs = st.tabs(_tab_labels)
    tab1, tab2, tab3, tab4, tab5, tab6 = _tabs[:6]

    with tab1:
        _tab_competencia(df_res, mes_sel)

    with tab2:
        _tab_alertas(df_zero, df_res)

    with tab3:
        _tab_periodo(todos_pedidos, hoje, is_admin=_is_admin)

    with tab4:
        _tab_gerencial(df_res, todos_pedidos, hoje)

    with tab5:
        _tab_niveis(todos_pedidos, mes_num, ano_num)

    with tab6:
        _tab_premiacoes(todos_pedidos, mes_num, ano_num, mes_sel)

    if _is_admin:
        with _tabs[6]:
            _tab_desempenho(todos_pedidos, hoje)
