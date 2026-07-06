from datetime import date, timedelta

import pandas as pd
import streamlit as st

from src.api.jueri_client import _get_lista_pedidos
from src.logic.acertos import montar_acertos
from src.logic.premiacoes import calcular_ranking, load_premiacoes
from src.logic.revendedoras import MINIMO_REV, calcular_competencia, parse_date

# Importa o sistema de dialogs do módulo de acertos
from src.pages.acertos import (
    _dialog_agendar,
    _dialog_agendar_envio_maleta,
    _dialog_gcal_confirm,
    _dialog_gcal_duplo,
    _dialog_troca_mesmo_dia,
)

_DIAS_PT = ["Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo"]
_MESES_PT = ["janeiro", "fevereiro", "março", "abril", "maio", "junho",
             "julho", "agosto", "setembro", "outubro", "novembro", "dezembro"]

_R = lambda v: f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


# ── CSS ────────────────────────────────────────────────────────────────────────

def _css():
    st.markdown("""
<style>
.hj-card{border-radius:14px;padding:1.1rem 1.4rem 1.2rem;margin-bottom:.65rem}
.hj-urgente{background:#FEF2F2;border:1.5px solid rgba(220,38,38,.25)}
.hj-hoje{background:#FFFBEB;border:1.5px solid rgba(202,138,4,.28)}
.hj-semana{background:#F0F9FF;border:1.5px solid rgba(14,165,233,.22)}
.hj-ok{background:#F0FDF4;border:1.5px solid rgba(22,163,74,.22)}
.hj-neutro{background:#F8FAFC;border:1.5px solid rgba(100,116,139,.2)}
.hj-gold{background:#FFFBEB;border:1.5px solid rgba(196,152,90,.3)}
.hj-titulo{font-size:.62rem;font-weight:700;text-transform:uppercase;letter-spacing:.12em;margin-bottom:.7rem}
.hj-titulo-urg{color:#dc2626}
.hj-titulo-hj{color:#b45309}
.hj-titulo-sem{color:#0284c7}
.hj-titulo-ok{color:#15803d}
.hj-titulo-neutro{color:#475569}
.hj-titulo-gold{color:#C4985A}
.hj-item{display:flex;justify-content:space-between;align-items:center;
          padding:6px 0;border-bottom:1px solid rgba(0,0,0,.06)}
.hj-item:last-child{border-bottom:none}
.hj-nome{font-weight:600;color:#1e293b;font-size:.9em}
.hj-detalhe{color:#64748b;font-size:.78em}
.hj-badge{display:inline-block;border-radius:6px;padding:2px 9px;font-size:.72em;font-weight:600;white-space:nowrap}
.hj-badge-red{background:#fee2e2;color:#dc2626}
.hj-badge-yellow{background:#fef9c3;color:#854d0e}
.hj-badge-blue{background:#dbeafe;color:#1d4ed8}
.hj-badge-green{background:#dcfce7;color:#15803d}
.hj-badge-gray{background:#f1f5f9;color:#475569}
.hj-badge-gold{background:#fef3c7;color:#92400e}
.hj-badge-purple{background:#f3e8ff;color:#6b21a8}
.hj-stat{text-align:center;padding:.5rem .8rem}
.hj-stat-num{font-size:2rem;font-weight:700;line-height:1}
.hj-stat-lbl{font-size:.72rem;color:#7A6068;margin-top:.2rem}
.hj-num-red{color:#dc2626}
.hj-num-yellow{color:#b45309}
.hj-num-green{color:#15803d}
.hj-num-blue{color:#0284c7}
.hj-num-neutral{color:#2A1A1F}
.hj-prog-bg{background:#e5e7eb;border-radius:99px;height:6px;margin-top:4px}
.hj-prog-fill{height:6px;border-radius:99px;background:#C4985A}
</style>
""", unsafe_allow_html=True)


def _card(titulo, cls_titulo, cls_card, corpo_html, rodape=""):
    rod = f'<div style="font-size:.73rem;color:#94a3b8;margin-top:.6rem">{rodape}</div>' if rodape else ""
    st.markdown(
        f'<div class="hj-card {cls_card}">'
        f'<div class="hj-titulo {cls_titulo}">{titulo}</div>'
        f'{corpo_html}{rod}</div>',
        unsafe_allow_html=True,
    )


def _item_html(nome, detalhe, badge, badge_cls):
    return (
        f'<div class="hj-item">'
        f'<div><div class="hj-nome">{nome}</div>'
        f'<div class="hj-detalhe">{detalhe}</div></div>'
        f'<span class="hj-badge {badge_cls}">{badge}</span>'
        f'</div>'
    )


# ── render ─────────────────────────────────────────────────────────────────────

def render(filtro_supervisor: str = "", nome_usuario: str = ""):
    _css()

    hoje = date.today()
    mes_num, ano_num = hoje.month, hoje.year
    mes_key = f"{mes_num:02d}/{ano_num}"
    dia_semana = _DIAS_PT[hoje.weekday()]
    data_fmt = f"{hoje.day} de {_MESES_PT[hoje.month - 1]} de {hoje.year}"

    # ── Dialogs (devem ser chamados antes de qualquer widget) ──────────────────
    if "_troca_check" in st.session_state:
        _dialog_troca_mesmo_dia()
    elif "_envio_maleta" in st.session_state:
        _dialog_agendar_envio_maleta()
    elif "_gcal_duplo" in st.session_state or "_gcal_duplo_active" in st.session_state:
        duplo = st.session_state.pop("_gcal_duplo", None)
        if duplo:
            st.session_state["_gcal_duplo_active"] = duplo
        _dialog_gcal_duplo()
    else:
        gcal = st.session_state.pop("_gcal_dict", None)
        if gcal:
            st.session_state["_gcal_active"] = gcal
            _dialog_gcal_confirm()

    # ── Carrega dados ──────────────────────────────────────────────────────────
    with st.spinner("Carregando sua agenda..."):
        try:
            todos_bruto = _get_lista_pedidos()
        except Exception as e:
            st.error(f"Erro ao carregar dados: {e}")
            return

    pedidos = (
        [p for p in todos_bruto if (p.get("supervisor_nome") or "") == filtro_supervisor]
        if filtro_supervisor else todos_bruto
    )

    df = montar_acertos(pedidos)

    # Dialog de agendamento (precisa do df já carregado)
    ag_id = st.session_state.get("_ag_id")
    if ag_id is not None:
        if st.session_state.get("_ag_id_prev") != ag_id:
            st.session_state.pop(f"dlg_data_{ag_id}", None)
            st.session_state["_ag_id_prev"] = ag_id
        rows = df[df["id"] == ag_id] if not df.empty else pd.DataFrame()
        if not rows.empty:
            _dialog_agendar(rows.iloc[0])
        else:
            st.session_state.pop("_ag_id", None)
            st.session_state.pop("_ag_id_prev", None)

    # ── Cabeçalho ─────────────────────────────────────────────────────────────
    st.markdown(
        f'<h2 style="margin-bottom:2px">👋 Olá, {nome_usuario or "Supervisora"}!</h2>'
        f'<p style="color:#7A6068;margin-top:0">{dia_semana}, {data_fmt}</p>',
        unsafe_allow_html=True,
    )

    # ── Métricas dos acertos ───────────────────────────────────────────────────
    sem_fim = hoje + timedelta(days=6)

    vencidos, agendados_hj, a_agendar_sem = [], [], []

    if not df.empty:
        for _, row in df.iterrows():
            sit = row.get("Situação", "")
            dag = row.get("Data agendada")
            dac = row.get("Data acerto")
            if sit == "🔴 Vencido":
                vencidos.append(row)
            elif sit == "📅 Agendado" and dag == hoje:
                agendados_hj.append(row)
            elif sit == "⬜ A agendar" and dac and hoje <= dac <= sem_fim:
                a_agendar_sem.append(row)

    # ── Métricas competência (abaixo mínimo + sem vendas) ─────────────────────
    try:
        df_res, _ = calcular_competencia(pedidos, mes_num, ano_num)
    except Exception:
        df_res = pd.DataFrame()

    abaixo_min = []
    sem_vendas_list = []
    if not df_res.empty:
        _df_ab = df_res[(df_res["Total"] > 0) & (df_res["Total"] < MINIMO_REV)].copy()
        for _, r in _df_ab.iterrows():
            abaixo_min.append({"nome": r["Nome"], "total": r["Total"],
                               "falta": MINIMO_REV - r["Total"]})
        _df_sv = df_res[df_res["Total"] == 0].copy()
        for _, r in _df_sv.iterrows():
            sem_vendas_list.append({"nome": r["Nome"]})

    # ── Premiações ─────────────────────────────────────────────────────────────
    try:
        prem_cfg = load_premiacoes().get(mes_key, {})
        meta_mes = float(prem_cfg.get("meta", 0))
        premio_mes = prem_cfg.get("premio", "")
        ranking = calcular_ranking(pedidos, mes_num, ano_num, meta_mes) if meta_mes > 0 else []
    except Exception:
        meta_mes, premio_mes, ranking = 0.0, "", []

    # Filtra apenas pela supervisora
    if filtro_supervisor:
        ranking = [r for r in ranking if r.get("Supervisor") == filtro_supervisor]

    quase_meta = [r for r in ranking if r["Categoria"] in ("proxima", "potencial")]
    ganhadoras = [r for r in ranking if r["Categoria"] == "ganhadora"]

    # ── Painel de números ──────────────────────────────────────────────────────
    c1, c2, c3, c4, c5 = st.columns(5)
    for col, num, lbl, cor in [
        (c1, len(vencidos),      "Vencidos",            "hj-num-red"),
        (c2, len(agendados_hj),  "Agendados hoje",      "hj-num-yellow"),
        (c3, len(a_agendar_sem), "A agendar esta sem.", "hj-num-blue"),
        (c4, len(abaixo_min),    "Abaixo do mínimo",    "hj-num-neutral"),
        (c5, len(sem_vendas_list),"Sem vendas no mês",  "hj-num-neutral"),
    ]:
        col.markdown(
            f'<div class="hj-stat">'
            f'<div class="hj-stat-num {cor}">{num}</div>'
            f'<div class="hj-stat-lbl">{lbl}</div></div>',
            unsafe_allow_html=True,
        )

    st.divider()

    # ── Linha 1: Vencidos | A agendar semana ──────────────────────────────────
    col_esq, col_dir = st.columns([3, 2])

    with col_esq:
        # Vencidos
        if vencidos:
            itens_html = ""
            for row in sorted(vencidos, key=lambda r: r["Data acerto"] or hoje):
                dag = row.get("Data agendada")
                has_ag = pd.notna(dag) and bool(dag)
                badge = f"📅 Reagend. {dag.strftime('%d/%m')}" if has_ag else "⚠️ Sem agenda"
                badge_cls = "hj-badge-yellow" if has_ag else "hj-badge-red"
                dac = row.get("Data acerto")
                detalhe = f'Previsto: {dac.strftime("%d/%m/%Y") if dac else "—"}'
                if has_ag:
                    forma = row.get("Forma") or ""
                    detalhe += f' · {forma}' if forma else ""
                itens_html += _item_html(row["Nome"], detalhe, badge, badge_cls)
            _card("🚨 Acertos vencidos — ação imediata", "hj-titulo-urg", "hj-urgente",
                  itens_html, "Ligue agora e reagende abaixo.")

            for row in sorted(vencidos, key=lambda r: r["Data acerto"] or hoje):
                dag = row.get("Data agendada")
                has_ag = pd.notna(dag) and bool(dag)
                lbl_btn = "🔄 Reagendar" if has_ag else "📅 Agendar agora"
                col_n, col_b = st.columns([3, 2])
                col_n.markdown(
                    f'<div style="padding:4px 0;font-size:.88em;font-weight:600">'
                    f'{row["Nome"]}</div>',
                    unsafe_allow_html=True,
                )
                if col_b.button(lbl_btn, key=f"hj_venc_{row['id']}", use_container_width=True):
                    st.session_state["_ag_id"] = row["id"]
                    st.rerun()
        else:
            _card("✅ Nenhum acerto vencido", "hj-titulo-ok", "hj-ok",
                  '<div style="color:#15803d;font-size:.9em;padding:4px 0">Tudo em dia! Continue assim.</div>')

        # Agendados hoje
        if agendados_hj:
            itens_html = ""
            for row in agendados_hj:
                dag = row.get("Data agendada")
                hora = row.get("Hora agendada") or ""
                badge = hora if hora else _R(row.get("Valor", 0))
                detalhe = f'{row.get("Forma") or "—"} · {_R(row.get("Valor", 0))}'
                itens_html += _item_html(row["Nome"], detalhe, badge, "hj-badge-yellow")
            _card("📅 Agendados para hoje", "hj-titulo-hj", "hj-hoje",
                  itens_html, "Confirme os detalhes abaixo ou reagende se necessário.")
            for row in agendados_hj:
                col_n, col_b = st.columns([3, 2])
                col_n.markdown(
                    f'<div style="padding:4px 0;font-size:.88em;font-weight:600">'
                    f'{row["Nome"]}</div>',
                    unsafe_allow_html=True,
                )
                if col_b.button("🔄 Reagendar", key=f"hj_hj_{row['id']}", use_container_width=True):
                    st.session_state["_ag_id"] = row["id"]
                    st.rerun()
        else:
            _card("📅 Nenhum acerto agendado para hoje", "hj-titulo-hj", "hj-hoje",
                  '<div style="color:#92400e;font-size:.9em;padding:4px 0">Verifique os pendentes desta semana ao lado.</div>')

    with col_dir:
        # A agendar esta semana
        if a_agendar_sem:
            itens_html = ""
            for row in sorted(a_agendar_sem, key=lambda r: r["Data acerto"] or hoje):
                dac = row.get("Data acerto")
                dias = (dac - hoje).days if dac else 0
                urg = "Hoje!" if dias == 0 else f"em {dias}d"
                itens_html += _item_html(
                    row["Nome"],
                    f'Acerto em {dac.strftime("%d/%m") if dac else "—"} ({urg})',
                    "⬜ Pendente", "hj-badge-blue",
                )
            _card(f"⬜ A agendar esta semana ({len(a_agendar_sem)})",
                  "hj-titulo-sem", "hj-semana", itens_html,
                  "Clique para agendar direto aqui:")
            for row in sorted(a_agendar_sem, key=lambda r: r["Data acerto"] or hoje):
                col_n, col_b = st.columns([3, 2])
                col_n.markdown(
                    f'<div style="padding:4px 0;font-size:.88em;font-weight:600">'
                    f'{row["Nome"]}</div>',
                    unsafe_allow_html=True,
                )
                if col_b.button("📅 Agendar", key=f"hj_sem_{row['id']}", use_container_width=True):
                    st.session_state["_ag_id"] = row["id"]
                    st.rerun()
        else:
            _card("✅ Agenda da semana completa", "hj-titulo-ok", "hj-ok",
                  '<div style="color:#15803d;font-size:.9em;padding:4px 0">Todos os acertos desta semana estão agendados.</div>')

        # Sem vendas
        if sem_vendas_list:
            nomes = sem_vendas_list[:7]
            itens_html = "".join(
                _item_html(r["nome"], "R$ 0,00 registrado no mês", "⚠️ Sem venda", "hj-badge-gray")
                for r in nomes
            )
            rodape = f"+ {len(sem_vendas_list) - 7} revendedoras" if len(sem_vendas_list) > 7 else ""
            _card(f"⚠️ Sem vendas este mês ({len(sem_vendas_list)})",
                  "hj-titulo-urg", "hj-urgente", itens_html, rodape)

    # ── Linha 2: Abaixo do mínimo | Premiações ────────────────────────────────
    st.divider()
    col_ab, col_prem = st.columns(2)

    with col_ab:
        if abaixo_min:
            itens_html = ""
            for r in sorted(abaixo_min, key=lambda x: x["total"]):
                pct = int(r["total"] / MINIMO_REV * 100)
                prog = f'<div class="hj-prog-bg"><div class="hj-prog-fill" style="width:{min(pct,100)}%"></div></div>'
                itens_html += (
                    f'<div class="hj-item"><div style="flex:1">'
                    f'<div class="hj-nome">{r["nome"]}</div>'
                    f'<div class="hj-detalhe">{_R(r["total"])} de {_R(MINIMO_REV)} · falta {_R(r["falta"])}</div>'
                    f'{prog}</div>'
                    f'<span class="hj-badge hj-badge-yellow" style="margin-left:.5rem">{pct}%</span></div>'
                )
            _card(f"🟡 Abaixo do mínimo ({len(abaixo_min)})",
                  "hj-titulo-hj", "hj-hoje", itens_html,
                  f"Mínimo de permanência: {_R(MINIMO_REV)}/mês.")
        else:
            _card("✅ Todas acima do mínimo", "hj-titulo-ok", "hj-ok",
                  '<div style="color:#15803d;font-size:.9em;padding:4px 0">Todas as revendedoras estão acima do mínimo este mês.</div>')

    with col_prem:
        if meta_mes <= 0:
            _card("🏆 Premiação", "hj-titulo-gold", "hj-gold",
                  '<div style="color:#92400e;font-size:.9em;padding:4px 0">Meta do mês não configurada. Acesse Revendedoras → Premiações para definir.</div>')
        elif ganhadoras:
            itens_html = "".join(
                _item_html(r["Nome"], f'{_R(r["Baixado"])} baixado',
                           "🏆 Ganhou!", "hj-badge-green")
                for r in ganhadoras[:5]
            )
            if quase_meta:
                for r in quase_meta[:3]:
                    pct = r["% da meta"]
                    itens_html += _item_html(
                        r["Nome"],
                        f'{_R(r["Total"])} · falta {_R(r["Falta"])} ({pct:.0f}%)',
                        "🔥 Quase lá", "hj-badge-gold",
                    )
            rod = f'Meta: {_R(meta_mes)} · Prêmio: {premio_mes}' if premio_mes else f'Meta: {_R(meta_mes)}'
            _card(f"🏆 Premiação — {len(ganhadoras)} ganhadora(s)",
                  "hj-titulo-gold", "hj-gold", itens_html, rod)
        elif quase_meta:
            itens_html = ""
            for r in quase_meta[:5]:
                pct = r["% da meta"]
                falta = r["Falta"]
                badge = "🔥 Quase!" if pct >= 85 else f"{pct:.0f}%"
                badge_cls = "hj-badge-gold" if pct >= 85 else "hj-badge-gray"
                prog_fill = min(int(pct), 100)
                itens_html += (
                    f'<div class="hj-item"><div style="flex:1">'
                    f'<div class="hj-nome">{r["Nome"]}</div>'
                    f'<div class="hj-detalhe">{_R(r["Total"])} · falta {_R(falta)}</div>'
                    f'<div class="hj-prog-bg"><div class="hj-prog-fill" style="width:{prog_fill}%"></div></div>'
                    f'</div><span class="hj-badge {badge_cls}" style="margin-left:.5rem">{badge}</span></div>'
                )
            rod = f'Meta: {_R(meta_mes)} · Prêmio: {premio_mes}' if premio_mes else f'Meta: {_R(meta_mes)}'
            _card(f"🏆 Premiação — {len(quase_meta)} perto da meta",
                  "hj-titulo-gold", "hj-gold", itens_html, rod)
        else:
            itens_html = '<div style="color:#92400e;font-size:.9em;padding:4px 0">Nenhuma revendedora chegou a 70% da meta ainda.</div>'
            rod = f'Meta: {_R(meta_mes)} · Prêmio: {premio_mes}' if premio_mes else f'Meta: {_R(meta_mes)}'
            _card("🏆 Premiação", "hj-titulo-gold", "hj-gold", itens_html, rod)

    # ── Guia de rotina ─────────────────────────────────────────────────────────
    st.divider()
    with st.expander("🗓️ Guia de rotina — por onde começar?", expanded=False):
        st.markdown("""
#### ☀️ Check diário — 5 minutos, toda manhã

| Passo | Onde | O que fazer |
|---|---|---|
| 1 | **🏠 Hoje** | Ver acertos vencidos → ligar agora e reagendar aqui mesmo |
| 2 | **🏠 Hoje** | Ver agendados para hoje → confirmar com a revendedora |
| 3 | **🏠 Hoje** | Ver "A agendar esta semana" → agendar pendentes aqui mesmo |

---

#### 📅 Revisão semanal — Segunda-feira, 15 minutos

| Passo | Onde | O que fazer |
|---|---|---|
| 1 | **📅 Controle de Acertos** | Aba **📋 Agendar esta semana** → agendar todos os pendentes |
| 2 | **👥 Revendedoras** | Expander **⏰ Postergados** → contatar quem está atrasando |
| 3 | **👥 Revendedoras** | Expander **📅 Acertos no mês** → planejar a semana |

---

#### 📊 Revisão semanal — Sexta-feira, 10 minutos

| Passo | Onde | O que fazer |
|---|---|---|
| 1 | **👥 Revendedoras** | Ver bloco **💰 Financeiro** → total vendido acumulado |
| 2 | **🏠 Hoje** | Seção **🏆 Premiação** → quem está perto de bater meta? |
| 3 | **👥 Revendedoras** | Aba **🏅 Níveis** → quem está perto de subir? |

---

#### 🏁 Balanço mensal — Início do mês, 30 minutos

| Passo | Onde | O que fazer |
|---|---|---|
| 1 | **👥 Revendedoras** | Mudar mês para o anterior → ver resultado final |
| 2 | **👥 Revendedoras** | Expander **📈 Potencial s/ postergação** → o que ficou para trás |
| 3 | **👥 Revendedoras** | Aba **🏆 Premiações** → confirmar prêmios do mês |
| 4 | **👥 Revendedoras** | Aba **📅 Competência** → análise completa do fechamento |
""")

    st.caption("💡 Use o menu lateral para acessar **Revendedoras** e **Controle de Acertos**.")
