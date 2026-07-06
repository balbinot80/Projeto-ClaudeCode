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
    st.session_state["_ag_id"]    = pedido_id
    st.session_state["_nav_page"] = "📅 Controle de Acertos"
    st.rerun()


def _css():
    st.markdown("""
<style>
/* Coloração dos containers via :has() — suportado em todos os browsers modernos */
div[data-testid="stVerticalBlockBorderWrapper"]:has(.hj-mk-urgente){
    background:#FEF2F2 !important;border-color:rgba(220,38,38,.28)!important}
div[data-testid="stVerticalBlockBorderWrapper"]:has(.hj-mk-hoje){
    background:#FFFBEB !important;border-color:rgba(202,138,4,.32)!important}
div[data-testid="stVerticalBlockBorderWrapper"]:has(.hj-mk-semana){
    background:#F0F9FF !important;border-color:rgba(14,165,233,.28)!important}
div[data-testid="stVerticalBlockBorderWrapper"]:has(.hj-mk-ok){
    background:#F0FDF4 !important;border-color:rgba(22,163,74,.28)!important}
div[data-testid="stVerticalBlockBorderWrapper"]:has(.hj-mk-gold){
    background:#FFFBEB !important;border-color:rgba(196,152,90,.32)!important}
div[data-testid="stVerticalBlockBorderWrapper"]:has(.hj-mk-neutro){
    background:#F8FAFC !important;border-color:rgba(100,116,139,.22)!important}

.hj-titulo{font-size:.62rem;font-weight:700;text-transform:uppercase;letter-spacing:.13em}
.hj-titulo-urg   {color:#dc2626}
.hj-titulo-hj    {color:#b45309}
.hj-titulo-sem   {color:#0284c7}
.hj-titulo-ok    {color:#15803d}
.hj-titulo-gold  {color:#C4985A}
.hj-titulo-neutro{color:#475569}

.hj-nome   {font-weight:600;color:#1e293b;font-size:.92em}
.hj-sub    {color:#64748b;font-size:.78em}
.hj-badge  {display:inline-block;border-radius:6px;padding:1px 8px;font-size:.72em;font-weight:600;white-space:nowrap;margin-left:.4rem}
.hj-red    {background:#fee2e2;color:#dc2626}
.hj-yellow {background:#fef9c3;color:#854d0e}
.hj-blue   {background:#dbeafe;color:#1d4ed8}
.hj-green  {background:#dcfce7;color:#15803d}
.hj-gray   {background:#f1f5f9;color:#475569}
.hj-gold   {background:#fef3c7;color:#92400e}

.hj-stat{text-align:center;padding:.5rem .8rem}
.hj-stat-num{font-size:2rem;font-weight:700;line-height:1}
.hj-stat-lbl{font-size:.72rem;color:#7A6068;margin-top:.2rem}
.hj-num-red    {color:#dc2626}
.hj-num-yellow {color:#b45309}
.hj-num-blue   {color:#0284c7}
.hj-num-neutral{color:#2A1A1F}

.hj-prog-bg  {background:#e5e7eb;border-radius:99px;height:5px;margin-top:3px}
.hj-prog-fill{height:5px;border-radius:99px;background:#C4985A}

/* Remove margem extra dos containers coloridos */
div[data-testid="stVerticalBlockBorderWrapper"] > div{padding:.75rem 1rem}
</style>
""", unsafe_allow_html=True)


def _titulo(texto, cls):
    st.markdown(f'<p class="hj-titulo {cls}" style="margin:0 0 .6rem">{texto}</p>',
                unsafe_allow_html=True)


def _pessoa_row(nome, detalhe, badge_txt, badge_cls, key, btn_label, btn_type="secondary"):
    c_info, c_btn = st.columns([4, 2])
    with c_info:
        st.markdown(
            f'<div style="padding:2px 0 4px">'
            f'<span class="hj-nome">{nome}</span>'
            f'<span class="hj-badge {badge_cls}">{badge_txt}</span>'
            f'<br><span class="hj-sub">{detalhe}</span>'
            f'</div>',
            unsafe_allow_html=True,
        )
    with c_btn:
        if st.button(btn_label, key=key, use_container_width=True,
                     type="primary" if btn_type == "primary" else "secondary"):
            return True
    return False


# ── render ─────────────────────────────────────────────────────────────────────

def render(filtro_supervisor: str = "", nome_usuario: str = ""):
    _css()

    hoje    = date.today()
    mes_num = hoje.month
    ano_num = hoje.year
    mes_key = f"{mes_num:02d}/{ano_num}"
    sem_fim = hoje + timedelta(days=6)

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

    # ── Classifica acertos ─────────────────────────────────────────────────────
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

    # ── Competência do mês ─────────────────────────────────────────────────────
    try:
        df_res, _ = calcular_competencia(pedidos, mes_num, ano_num)
    except Exception:
        df_res = pd.DataFrame()

    abaixo_min, sem_vendas_list = [], []
    if not df_res.empty:
        for _, r in df_res[(df_res["Total"] > 0) & (df_res["Total"] < MINIMO_REV)].iterrows():
            abaixo_min.append({"nome": r["Nome"], "total": r["Total"],
                               "falta": MINIMO_REV - r["Total"]})
        for _, r in df_res[df_res["Total"] == 0].iterrows():
            sem_vendas_list.append({"nome": r["Nome"]})

    # ── Premiações ─────────────────────────────────────────────────────────────
    try:
        prem_cfg = load_premiacoes().get(mes_key, {})
        meta_mes = float(prem_cfg.get("meta", 0))
        premio   = prem_cfg.get("premio", "")
        ranking  = calcular_ranking(pedidos, mes_num, ano_num, meta_mes) if meta_mes > 0 else []
        if filtro_supervisor:
            ranking = [r for r in ranking if r.get("Supervisor") == filtro_supervisor]
    except Exception:
        meta_mes, premio, ranking = 0.0, "", []

    ganhadoras = [r for r in ranking if r["Categoria"] == "ganhadora"]
    quase_meta = [r for r in ranking if r["Categoria"] in ("proxima", "potencial")]

    # ── Números ────────────────────────────────────────────────────────────────
    c1, c2, c3, c4, c5 = st.columns(5)
    for col, num, lbl, cor in [
        (c1, len(vencidos),        "Vencidos",            "hj-num-red"),
        (c2, len(agendados_hj),    "Agendados hoje",      "hj-num-yellow"),
        (c3, len(a_agendar_sem),   "A agendar esta sem.", "hj-num-blue"),
        (c4, len(abaixo_min),      "Abaixo do mínimo",    "hj-num-neutral"),
        (c5, len(sem_vendas_list), "Sem vendas no mês",   "hj-num-neutral"),
    ]:
        col.markdown(
            f'<div class="hj-stat"><div class="hj-stat-num {cor}">{num}</div>'
            f'<div class="hj-stat-lbl">{lbl}</div></div>',
            unsafe_allow_html=True,
        )

    st.divider()

    # ── Linha 1: Vencidos | A agendar semana ──────────────────────────────────
    col_esq, col_dir = st.columns([3, 2])

    with col_esq:
        # Vencidos
        if vencidos:
            with st.container(border=True):
                st.markdown('<span class="hj-mk-urgente" style="display:none"></span>',
                            unsafe_allow_html=True)
                _titulo("🚨 Acertos vencidos — ação imediata", "hj-titulo-urg")
                for row in sorted(vencidos, key=lambda r: r["Data acerto"] or hoje):
                    dag    = row.get("Data agendada")
                    has_ag = pd.notna(dag) and bool(dag)
                    badge  = f"📅 {dag.strftime('%d/%m')}" if has_ag else "⚠️ Sem agenda"
                    b_cls  = "hj-yellow" if has_ag else "hj-red"
                    dac    = row.get("Data acerto")
                    det    = f'Previsto {dac.strftime("%d/%m/%Y") if dac else "—"}'
                    if has_ag:
                        det += f' · {row.get("Forma") or ""}'
                    if _pessoa_row(row["Nome"], det, badge, b_cls,
                                   f"hj_v_{row['id']}",
                                   "🔄 Reagendar" if has_ag else "📅 Agendar agora"):
                        _ir_agendar(row["id"])
        else:
            with st.container(border=True):
                st.markdown('<span class="hj-mk-ok" style="display:none"></span>',
                            unsafe_allow_html=True)
                _titulo("✅ Nenhum acerto vencido", "hj-titulo-ok")
                st.markdown('<span class="hj-sub">Tudo em dia!</span>',
                            unsafe_allow_html=True)

        # Agendados hoje
        if agendados_hj:
            with st.container(border=True):
                st.markdown('<span class="hj-mk-hoje" style="display:none"></span>',
                            unsafe_allow_html=True)
                _titulo("📅 Agendados para hoje", "hj-titulo-hj")
                for row in agendados_hj:
                    hora  = row.get("Hora agendada") or ""
                    badge = hora if hora else "Sem hora"
                    det   = f'{row.get("Forma") or "—"} · {_R(row.get("Valor", 0))}'
                    if _pessoa_row(row["Nome"], det, badge, "hj-yellow",
                                   f"hj_h_{row['id']}", "🔄 Reagendar"):
                        _ir_agendar(row["id"])
        else:
            with st.container(border=True):
                st.markdown('<span class="hj-mk-hoje" style="display:none"></span>',
                            unsafe_allow_html=True)
                _titulo("📅 Nenhum acerto agendado para hoje", "hj-titulo-hj")
                st.markdown('<span class="hj-sub">Veja os pendentes da semana ao lado.</span>',
                            unsafe_allow_html=True)

    with col_dir:
        # A agendar esta semana
        if a_agendar_sem:
            with st.container(border=True):
                st.markdown('<span class="hj-mk-semana" style="display:none"></span>',
                            unsafe_allow_html=True)
                _titulo(f"⬜ A agendar esta semana ({len(a_agendar_sem)})", "hj-titulo-sem")
                for row in sorted(a_agendar_sem, key=lambda r: r["Data acerto"] or hoje):
                    dac  = row.get("Data acerto")
                    dias = (dac - hoje).days if dac else 0
                    urg  = "Hoje!" if dias == 0 else f"em {dias}d"
                    det  = f'Acerto em {dac.strftime("%d/%m") if dac else "—"} ({urg})'
                    if _pessoa_row(row["Nome"], det, "⬜ Pendente", "hj-blue",
                                   f"hj_s_{row['id']}", "📅 Agendar", "primary"):
                        _ir_agendar(row["id"])
        else:
            with st.container(border=True):
                st.markdown('<span class="hj-mk-ok" style="display:none"></span>',
                            unsafe_allow_html=True)
                _titulo("✅ Agenda da semana completa", "hj-titulo-ok")
                st.markdown('<span class="hj-sub">Todos os acertos desta semana estão agendados.</span>',
                            unsafe_allow_html=True)

        # Sem vendas
        if sem_vendas_list:
            with st.container(border=True):
                st.markdown('<span class="hj-mk-urgente" style="display:none"></span>',
                            unsafe_allow_html=True)
                rod = f" (+{len(sem_vendas_list) - 7} mais)" if len(sem_vendas_list) > 7 else ""
                _titulo(f"⚠️ Sem vendas este mês ({len(sem_vendas_list)}){rod}", "hj-titulo-urg")
                for r in sem_vendas_list[:7]:
                    st.markdown(
                        f'<div style="padding:4px 0;border-bottom:1px solid rgba(0,0,0,.06)">'
                        f'<span class="hj-nome">{r["nome"]}</span>'
                        f'<span class="hj-badge hj-gray">⚠️ R$ 0,00</span></div>',
                        unsafe_allow_html=True,
                    )

    # ── Linha 2: Abaixo do mínimo | Premiações ────────────────────────────────
    st.divider()
    col_ab, col_pr = st.columns(2)

    with col_ab:
        if abaixo_min:
            with st.container(border=True):
                st.markdown('<span class="hj-mk-hoje" style="display:none"></span>',
                            unsafe_allow_html=True)
                _titulo(f"🟡 Abaixo do mínimo ({len(abaixo_min)})", "hj-titulo-hj")
                for r in sorted(abaixo_min, key=lambda x: x["total"]):
                    pct = int(r["total"] / MINIMO_REV * 100)
                    st.markdown(
                        f'<div style="padding:4px 0 6px;border-bottom:1px solid rgba(0,0,0,.06)">'
                        f'<span class="hj-nome">{r["nome"]}</span>'
                        f'<span class="hj-badge hj-yellow">{pct}%</span>'
                        f'<br><span class="hj-sub">'
                        f'{_R(r["total"])} de {_R(MINIMO_REV)} · falta {_R(r["falta"])}'
                        f'</span>'
                        f'<div class="hj-prog-bg">'
                        f'<div class="hj-prog-fill" style="width:{min(pct,100)}%"></div></div>'
                        f'</div>',
                        unsafe_allow_html=True,
                    )
                st.caption(f"Mínimo de permanência: {_R(MINIMO_REV)}/mês.")
        else:
            with st.container(border=True):
                st.markdown('<span class="hj-mk-ok" style="display:none"></span>',
                            unsafe_allow_html=True)
                _titulo("✅ Todas acima do mínimo", "hj-titulo-ok")
                st.markdown('<span class="hj-sub">Todas as revendedoras estão acima do mínimo este mês.</span>',
                            unsafe_allow_html=True)

    with col_pr:
        with st.container(border=True):
            st.markdown('<span class="hj-mk-gold" style="display:none"></span>',
                        unsafe_allow_html=True)
            if meta_mes <= 0:
                _titulo("🏆 Premiação", "hj-titulo-gold")
                st.markdown('<span class="hj-sub">Meta do mês não configurada.<br>'
                            'Acesse Revendedoras → Premiações para definir.</span>',
                            unsafe_allow_html=True)
            else:
                rod = f'Meta: {_R(meta_mes)}' + (f' · Prêmio: {premio}' if premio else "")
                if ganhadoras:
                    _titulo(f"🏆 {len(ganhadoras)} ganhadora(s) este mês", "hj-titulo-gold")
                    for r in ganhadoras[:4]:
                        st.markdown(
                            f'<div style="padding:4px 0;border-bottom:1px solid rgba(0,0,0,.06)">'
                            f'<span class="hj-nome">{r["Nome"]}</span>'
                            f'<span class="hj-badge hj-green">🏆 Ganhou!</span>'
                            f'<br><span class="hj-sub">{_R(r["Baixado"])} baixado</span>'
                            f'</div>', unsafe_allow_html=True)
                    for r in quase_meta[:3]:
                        pct = r["% da meta"]
                        st.markdown(
                            f'<div style="padding:4px 0;border-bottom:1px solid rgba(0,0,0,.06)">'
                            f'<span class="hj-nome">{r["Nome"]}</span>'
                            f'<span class="hj-badge hj-gold">🔥 Quase</span>'
                            f'<br><span class="hj-sub">{_R(r["Total"])} · falta {_R(r["Falta"])} ({pct:.0f}%)</span>'
                            f'<div class="hj-prog-bg"><div class="hj-prog-fill" style="width:{min(int(pct),100)}%"></div></div>'
                            f'</div>', unsafe_allow_html=True)
                elif quase_meta:
                    _titulo(f"🏆 {len(quase_meta)} perto da meta", "hj-titulo-gold")
                    for r in quase_meta[:5]:
                        pct   = r["% da meta"]
                        badge = "🔥 Quase!" if pct >= 85 else f"{pct:.0f}%"
                        b_cls = "hj-gold" if pct >= 85 else "hj-gray"
                        st.markdown(
                            f'<div style="padding:4px 0;border-bottom:1px solid rgba(0,0,0,.06)">'
                            f'<span class="hj-nome">{r["Nome"]}</span>'
                            f'<span class="hj-badge {b_cls}">{badge}</span>'
                            f'<br><span class="hj-sub">{_R(r["Total"])} · falta {_R(r["Falta"])}</span>'
                            f'<div class="hj-prog-bg"><div class="hj-prog-fill" style="width:{min(int(pct),100)}%"></div></div>'
                            f'</div>', unsafe_allow_html=True)
                else:
                    _titulo("🏆 Premiação", "hj-titulo-gold")
                    st.markdown('<span class="hj-sub">Nenhuma revendedora chegou a 70% da meta ainda.</span>',
                                unsafe_allow_html=True)
                st.caption(rod)

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
