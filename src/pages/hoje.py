from datetime import date, timedelta

import pandas as pd
import streamlit as st

from src.api.jueri_client import _get_lista_pedidos
from src.logic.acertos import montar_acertos
from src.logic.premiacoes import calcular_ranking, load_premiacoes
from src.logic.revendedoras import MINIMO_REV, calcular_competencia, parse_date

_DIAS_PT  = ["Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo"]
_MESES_PT = ["janeiro", "fevereiro", "março", "abril", "maio", "junho",
             "julho", "agosto", "setembro", "outubro", "novembro", "dezembro"]

_R = lambda v: f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _ir_agendar(pedido_id):
    """Navega para Acertos com o pedido pré-selecionado para agendamento."""
    st.session_state["_ag_id"]   = pedido_id
    st.session_state["_nav_page"] = "📅 Controle de Acertos"
    st.rerun()


# ── CSS ────────────────────────────────────────────────────────────────────────

def _css():
    st.markdown("""
<style>
.hj-card{border-radius:14px;padding:1.1rem 1.4rem 1.2rem;margin-bottom:.65rem}
.hj-urgente{background:#FEF2F2;border:1.5px solid rgba(220,38,38,.25)}
.hj-hoje{background:#FFFBEB;border:1.5px solid rgba(202,138,4,.28)}
.hj-semana{background:#F0F9FF;border:1.5px solid rgba(14,165,233,.22)}
.hj-ok{background:#F0FDF4;border:1.5px solid rgba(22,163,74,.22)}
.hj-gold{background:#FFFBEB;border:1.5px solid rgba(196,152,90,.3)}
.hj-neutro{background:#F8FAFC;border:1.5px solid rgba(100,116,139,.2)}
.hj-titulo{font-size:.62rem;font-weight:700;text-transform:uppercase;letter-spacing:.12em;margin-bottom:.7rem}
.hj-titulo-urg{color:#dc2626}
.hj-titulo-hj{color:#b45309}
.hj-titulo-sem{color:#0284c7}
.hj-titulo-ok{color:#15803d}
.hj-titulo-gold{color:#C4985A}
.hj-titulo-neutro{color:#475569}
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
.hj-stat{text-align:center;padding:.5rem .8rem}
.hj-stat-num{font-size:2rem;font-weight:700;line-height:1}
.hj-stat-lbl{font-size:.72rem;color:#7A6068;margin-top:.2rem}
.hj-num-red{color:#dc2626}
.hj-num-yellow{color:#b45309}
.hj-num-blue{color:#0284c7}
.hj-num-neutral{color:#2A1A1F}
.hj-prog-bg{background:#e5e7eb;border-radius:99px;height:6px;margin-top:4px}
.hj-prog-fill{height:6px;border-radius:99px;background:#C4985A}
</style>
""", unsafe_allow_html=True)


def _card_html(titulo, cls_titulo, cls_card, corpo, rodape=""):
    rod = f'<div style="font-size:.73rem;color:#94a3b8;margin-top:.6rem">{rodape}</div>' if rodape else ""
    st.markdown(
        f'<div class="hj-card {cls_card}">'
        f'<div class="hj-titulo {cls_titulo}">{titulo}</div>'
        f'{corpo}{rod}</div>',
        unsafe_allow_html=True,
    )


def _item(nome, detalhe, badge, badge_cls):
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

    hoje      = date.today()
    mes_num   = hoje.month
    ano_num   = hoje.year
    mes_key   = f"{mes_num:02d}/{ano_num}"
    sem_fim   = hoje + timedelta(days=6)

    # ── Cabeçalho ─────────────────────────────────────────────────────────────
    dia_semana = _DIAS_PT[hoje.weekday()]
    data_fmt   = f"{hoje.day} de {_MESES_PT[hoje.month - 1]} de {hoje.year}"
    st.markdown(
        f'<h2 style="margin-bottom:2px">👋 Olá, {nome_usuario or "Supervisora"}!</h2>'
        f'<p style="color:#7A6068;margin-top:0">{dia_semana}, {data_fmt}</p>',
        unsafe_allow_html=True,
    )

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

    # ── Separa situações ───────────────────────────────────────────────────────
    vencidos, agendados_hj, a_agendar_sem = [], [], []
    if not df.empty:
        for _, row in df.iterrows():
            sit = row.get("Situação", "")
            dag = row.get("Data agendada")
            dac = row.get("Data acerto")
            if sit == "🔴 Vencido":
                vencidos.append(row)
            elif sit == "📅 Agendado" and pd.notna(dag) and dag == hoje:
                agendados_hj.append(row)
            elif sit == "⬜ A agendar" and dac and hoje <= dac <= sem_fim:
                a_agendar_sem.append(row)

    # ── Competência do mês ────────────────────────────────────────────────────
    try:
        df_res, _ = calcular_competencia(pedidos, mes_num, ano_num)
    except Exception:
        df_res = pd.DataFrame()

    abaixo_min     = []
    sem_vendas_list = []
    if not df_res.empty:
        for _, r in df_res[(df_res["Total"] > 0) & (df_res["Total"] < MINIMO_REV)].iterrows():
            abaixo_min.append({"nome": r["Nome"], "total": r["Total"],
                               "falta": MINIMO_REV - r["Total"]})
        for _, r in df_res[df_res["Total"] == 0].iterrows():
            sem_vendas_list.append({"nome": r["Nome"]})

    # ── Premiações ─────────────────────────────────────────────────────────────
    try:
        prem_cfg  = load_premiacoes().get(mes_key, {})
        meta_mes  = float(prem_cfg.get("meta", 0))
        premio    = prem_cfg.get("premio", "")
        ranking   = calcular_ranking(pedidos, mes_num, ano_num, meta_mes) if meta_mes > 0 else []
        if filtro_supervisor:
            ranking = [r for r in ranking if r.get("Supervisor") == filtro_supervisor]
    except Exception:
        meta_mes, premio, ranking = 0.0, "", []

    ganhadoras  = [r for r in ranking if r["Categoria"] == "ganhadora"]
    quase_meta  = [r for r in ranking if r["Categoria"] in ("proxima", "potencial")]

    # ── Painel de números ──────────────────────────────────────────────────────
    c1, c2, c3, c4, c5 = st.columns(5)
    for col, num, lbl, cor in [
        (c1, len(vencidos),       "Vencidos",            "hj-num-red"),
        (c2, len(agendados_hj),   "Agendados hoje",      "hj-num-yellow"),
        (c3, len(a_agendar_sem),  "A agendar esta sem.", "hj-num-blue"),
        (c4, len(abaixo_min),     "Abaixo do mínimo",    "hj-num-neutral"),
        (c5, len(sem_vendas_list),"Sem vendas no mês",   "hj-num-neutral"),
    ]:
        col.markdown(
            f'<div class="hj-stat">'
            f'<div class="hj-stat-num {cor}">{num}</div>'
            f'<div class="hj-stat-lbl">{lbl}</div></div>',
            unsafe_allow_html=True,
        )

    st.divider()

    # ── Linha 1: Vencidos (esq) | A agendar semana (dir) ──────────────────────
    col_esq, col_dir = st.columns([3, 2])

    with col_esq:
        if vencidos:
            corpo = ""
            for row in sorted(vencidos, key=lambda r: r["Data acerto"] or hoje):
                dag = row.get("Data agendada")
                has_ag  = pd.notna(dag) and bool(dag)
                badge   = f"📅 {dag.strftime('%d/%m')}" if has_ag else "⚠️ Sem agenda"
                b_cls   = "hj-badge-yellow" if has_ag else "hj-badge-red"
                dac     = row.get("Data acerto")
                detalhe = f'Previsto {dac.strftime("%d/%m/%Y") if dac else "—"}'
                if has_ag:
                    detalhe += f' · {row.get("Forma") or ""}'
                corpo += _item(row["Nome"], detalhe, badge, b_cls)
            _card_html("🚨 Acertos vencidos — ação imediata", "hj-titulo-urg",
                       "hj-urgente", corpo, "Clique para agendar/reagendar direto:")
            for row in sorted(vencidos, key=lambda r: r["Data acerto"] or hoje):
                dag    = row.get("Data agendada")
                has_ag = pd.notna(dag) and bool(dag)
                c_n, c_b = st.columns([3, 2])
                c_n.markdown(
                    f'<div style="padding:3px 0;font-size:.88em;font-weight:600">'
                    f'{row["Nome"]}</div>', unsafe_allow_html=True)
                if c_b.button(
                    "🔄 Reagendar" if has_ag else "📅 Agendar agora",
                    key=f"hj_v_{row['id']}", use_container_width=True
                ):
                    _ir_agendar(row["id"])
        else:
            _card_html("✅ Nenhum acerto vencido", "hj-titulo-ok", "hj-ok",
                       '<div style="color:#15803d;font-size:.9em;padding:4px 0">Tudo em dia!</div>')

        # Agendados hoje
        if agendados_hj:
            corpo = ""
            for row in agendados_hj:
                hora    = row.get("Hora agendada") or ""
                badge   = hora if hora else _R(row.get("Valor", 0))
                detalhe = f'{row.get("Forma") or "—"} · {_R(row.get("Valor", 0))}'
                corpo  += _item(row["Nome"], detalhe, badge, "hj-badge-yellow")
            _card_html("📅 Agendados para hoje", "hj-titulo-hj", "hj-hoje",
                       corpo, "Clique para ajustar se necessário:")
            for row in agendados_hj:
                c_n, c_b = st.columns([3, 2])
                c_n.markdown(
                    f'<div style="padding:3px 0;font-size:.88em;font-weight:600">'
                    f'{row["Nome"]}</div>', unsafe_allow_html=True)
                if c_b.button("🔄 Reagendar", key=f"hj_h_{row['id']}", use_container_width=True):
                    _ir_agendar(row["id"])
        else:
            _card_html("📅 Nenhum acerto agendado para hoje", "hj-titulo-hj", "hj-hoje",
                       '<div style="color:#92400e;font-size:.9em;padding:4px 0">Veja os pendentes da semana ao lado.</div>')

    with col_dir:
        if a_agendar_sem:
            corpo = ""
            for row in sorted(a_agendar_sem, key=lambda r: r["Data acerto"] or hoje):
                dac  = row.get("Data acerto")
                dias = (dac - hoje).days if dac else 0
                urg  = "Hoje!" if dias == 0 else f"em {dias}d"
                corpo += _item(
                    row["Nome"],
                    f'Acerto em {dac.strftime("%d/%m") if dac else "—"} ({urg})',
                    "⬜ Pendente", "hj-badge-blue",
                )
            _card_html(f"⬜ A agendar esta semana ({len(a_agendar_sem)})",
                       "hj-titulo-sem", "hj-semana", corpo,
                       "Clique para agendar direto:")
            for row in sorted(a_agendar_sem, key=lambda r: r["Data acerto"] or hoje):
                c_n, c_b = st.columns([3, 2])
                c_n.markdown(
                    f'<div style="padding:3px 0;font-size:.88em;font-weight:600">'
                    f'{row["Nome"]}</div>', unsafe_allow_html=True)
                if c_b.button("📅 Agendar", key=f"hj_s_{row['id']}", use_container_width=True):
                    _ir_agendar(row["id"])
        else:
            _card_html("✅ Agenda da semana completa", "hj-titulo-ok", "hj-ok",
                       '<div style="color:#15803d;font-size:.9em;padding:4px 0">Todos os acertos desta semana estão agendados.</div>')

        if sem_vendas_list:
            corpo = "".join(
                _item(r["nome"], "R$ 0,00 registrado no mês", "⚠️ Sem venda", "hj-badge-gray")
                for r in sem_vendas_list[:7]
            )
            rodape = f"+ {len(sem_vendas_list) - 7} revendedoras" if len(sem_vendas_list) > 7 else ""
            _card_html(f"⚠️ Sem vendas este mês ({len(sem_vendas_list)})",
                       "hj-titulo-urg", "hj-urgente", corpo, rodape)

    # ── Linha 2: Abaixo do mínimo | Premiações ────────────────────────────────
    st.divider()
    col_ab, col_pr = st.columns(2)

    with col_ab:
        if abaixo_min:
            corpo = ""
            for r in sorted(abaixo_min, key=lambda x: x["total"]):
                pct  = int(r["total"] / MINIMO_REV * 100)
                prog = (f'<div class="hj-prog-bg">'
                        f'<div class="hj-prog-fill" style="width:{min(pct,100)}%"></div></div>')
                corpo += (
                    f'<div class="hj-item"><div style="flex:1">'
                    f'<div class="hj-nome">{r["nome"]}</div>'
                    f'<div class="hj-detalhe">{_R(r["total"])} de {_R(MINIMO_REV)} · falta {_R(r["falta"])}</div>'
                    f'{prog}</div>'
                    f'<span class="hj-badge hj-badge-yellow" style="margin-left:.5rem">{pct}%</span></div>'
                )
            _card_html(f"🟡 Abaixo do mínimo ({len(abaixo_min)})", "hj-titulo-hj",
                       "hj-hoje", corpo, f"Mínimo de permanência: {_R(MINIMO_REV)}/mês.")
        else:
            _card_html("✅ Todas acima do mínimo", "hj-titulo-ok", "hj-ok",
                       '<div style="color:#15803d;font-size:.9em;padding:4px 0">Todas as revendedoras estão acima do mínimo este mês.</div>')

    with col_pr:
        if meta_mes <= 0:
            _card_html("🏆 Premiação", "hj-titulo-gold", "hj-gold",
                       '<div style="color:#92400e;font-size:.9em;padding:4px 0">'
                       'Meta do mês não configurada. Acesse Revendedoras → Premiações.</div>')
        else:
            rod = f'Meta: {_R(meta_mes)}' + (f' · Prêmio: {premio}' if premio else "")
            if ganhadoras:
                corpo = "".join(
                    _item(r["Nome"], f'{_R(r["Baixado"])} baixado', "🏆 Ganhou!", "hj-badge-green")
                    for r in ganhadoras[:4]
                )
                for r in quase_meta[:3]:
                    pct = r["% da meta"]
                    prog_w = min(int(pct), 100)
                    corpo += (
                        f'<div class="hj-item"><div style="flex:1">'
                        f'<div class="hj-nome">{r["Nome"]}</div>'
                        f'<div class="hj-detalhe">{_R(r["Total"])} · falta {_R(r["Falta"])} ({pct:.0f}%)</div>'
                        f'<div class="hj-prog-bg"><div class="hj-prog-fill" style="width:{prog_w}%"></div></div>'
                        f'</div><span class="hj-badge hj-badge-gold" style="margin-left:.5rem">🔥 Quase</span></div>'
                    )
                _card_html(f"🏆 {len(ganhadoras)} ganhadora(s) este mês",
                           "hj-titulo-gold", "hj-gold", corpo, rod)
            elif quase_meta:
                corpo = ""
                for r in quase_meta[:5]:
                    pct    = r["% da meta"]
                    prog_w = min(int(pct), 100)
                    badge  = "🔥 Quase!" if pct >= 85 else f"{pct:.0f}%"
                    b_cls  = "hj-badge-gold" if pct >= 85 else "hj-badge-gray"
                    corpo += (
                        f'<div class="hj-item"><div style="flex:1">'
                        f'<div class="hj-nome">{r["Nome"]}</div>'
                        f'<div class="hj-detalhe">{_R(r["Total"])} · falta {_R(r["Falta"])}</div>'
                        f'<div class="hj-prog-bg"><div class="hj-prog-fill" style="width:{prog_w}%"></div></div>'
                        f'</div><span class="hj-badge {b_cls}" style="margin-left:.5rem">{badge}</span></div>'
                    )
                _card_html(f"🏆 {len(quase_meta)} perto da meta",
                           "hj-titulo-gold", "hj-gold", corpo, rod)
            else:
                _card_html("🏆 Premiação", "hj-titulo-gold", "hj-gold",
                           '<div style="color:#92400e;font-size:.9em;padding:4px 0">'
                           'Nenhuma revendedora chegou a 70% da meta ainda.</div>', rod)

    # ── Guia de rotina ─────────────────────────────────────────────────────────
    st.divider()
    with st.expander("🗓️ Guia de rotina — por onde começar?", expanded=False):
        st.markdown("""
#### ☀️ Check diário — 5 minutos, toda manhã

| Passo | Onde | O que fazer |
|---|---|---|
| 1 | **🏠 Hoje** | Ver acertos vencidos → clicar em Reagendar |
| 2 | **🏠 Hoje** | Ver agendados para hoje → confirmar com a revendedora |
| 3 | **🏠 Hoje** | Ver "A agendar esta semana" → clicar em Agendar |

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
| 1 | **👥 Revendedoras** | Mudar mês → ver resultado final |
| 2 | **👥 Revendedoras** | Expander **📈 Potencial s/ postergação** |
| 3 | **👥 Revendedoras** | Aba **🏆 Premiações** → confirmar prêmios |
| 4 | **👥 Revendedoras** | Aba **📅 Competência** → análise completa |
""")

    st.caption("💡 Use o menu lateral para navegar entre as telas.")
