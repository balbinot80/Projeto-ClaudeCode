from datetime import date, timedelta

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

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


def _inject_colors():
    """JS via iframe: usa window.parent.document para acessar o DOM do Streamlit."""
    components.html("""
<script>
(function() {
  const d = window.parent.document;
  const MAP = {
    'hj-red':    {bg:'#FEF2F2', bd:'rgba(220,38,38,.4)'},
    'hj-green':  {bg:'#F0FDF4', bd:'rgba(22,163,74,.4)'},
    'hj-yellow': {bg:'#FFFDE7', bd:'rgba(202,138,4,.4)'},
    'hj-gold':   {bg:'#FFFDE7', bd:'rgba(196,152,90,.4)'},
  };
  const apply = () => {
    for (const [cls, c] of Object.entries(MAP)) {
      d.querySelectorAll('.hj-card-' + cls).forEach(el => {
        const w = el.closest('[data-testid="stVerticalBlockBorderWrapper"]');
        if (w) {
          w.style.setProperty('background', c.bg, 'important');
          w.style.setProperty('border-color', c.bd, 'important');
        }
      });
    }
  };
  apply();
  new MutationObserver(apply).observe(d.body, {childList:true, subtree:true});
})();
</script>
""", height=0)


def _css():
    st.markdown("""
<style>
.hj-titulo{font-size:.62rem;font-weight:700;text-transform:uppercase;letter-spacing:.13em;margin:0 0 .6rem}
.hj-titulo-red   {color:#dc2626}
.hj-titulo-green {color:#15803d}
.hj-titulo-yellow{color:#b45309}
.hj-titulo-gold  {color:#C4985A}
.hj-titulo-neutro{color:#475569}

.hj-nome{font-weight:600;color:#1e293b;font-size:.92em}
.hj-sub {color:#64748b;font-size:.78em}
.hj-badge{display:inline-block;border-radius:6px;padding:1px 8px;font-size:.72em;
          font-weight:600;white-space:nowrap;margin-left:.4rem}
.hj-b-red   {background:#fee2e2;color:#dc2626}
.hj-b-yellow{background:#fef9c3;color:#854d0e}
.hj-b-blue  {background:#dbeafe;color:#1d4ed8}
.hj-b-green {background:#dcfce7;color:#15803d}
.hj-b-gray  {background:#f1f5f9;color:#475569}
.hj-b-gold  {background:#fef3c7;color:#92400e}

.hj-stat{text-align:center;padding:.5rem .8rem}
.hj-stat-num{font-size:2rem;font-weight:700;line-height:1}
.hj-stat-lbl{font-size:.72rem;color:#7A6068;margin-top:.2rem}
.hj-num-red    {color:#dc2626}
.hj-num-yellow {color:#b45309}
.hj-num-blue   {color:#0284c7}
.hj-num-neutral{color:#2A1A1F}

.hj-sep{padding:4px 0;border-bottom:1px solid rgba(0,0,0,.07)}
.hj-prog-bg  {background:#e5e7eb;border-radius:99px;height:5px;margin-top:3px}
.hj-prog-fill{height:5px;border-radius:99px;background:#C4985A}
</style>
""", unsafe_allow_html=True)


def _marker(cor):
    """Span invisível usado pelo JS para identificar o card."""
    st.markdown(f'<span class="hj-card-{cor}" style="display:none"></span>',
                unsafe_allow_html=True)


def _titulo(txt, cor):
    st.markdown(f'<p class="hj-titulo hj-titulo-{cor}">{txt}</p>', unsafe_allow_html=True)


def _pessoa(nome, detalhe, badge, b_cls, key, btn_lbl, primario=False):
    c_info, c_btn = st.columns([4, 2])
    with c_info:
        st.markdown(
            f'<div class="hj-sep">'
            f'<span class="hj-nome">{nome}</span>'
            f'<span class="hj-badge {b_cls}">{badge}</span>'
            f'<br><span class="hj-sub">{detalhe}</span></div>',
            unsafe_allow_html=True,
        )
    with c_btn:
        if st.button(btn_lbl, key=key, use_container_width=True,
                     type="primary" if primario else "secondary"):
            return True
    return False


# ── render ─────────────────────────────────────────────────────────────────────

def render(filtro_supervisor: str = "", nome_usuario: str = ""):
    _css()
    _inject_colors()

    hoje    = date.today()
    mes_num = hoje.month
    ano_num = hoje.year
    mes_key = f"{mes_num:02d}/{ano_num}"
    sem_fim = hoje + timedelta(days=6)

    # ── Cabeçalho ─────────────────────────────────────────────────────────────
    st.markdown(
        f'<h2 style="margin-bottom:2px">👋 Olá, {nome_usuario or "Supervisora"}!</h2>'
        f'<p style="color:#7A6068;margin-top:0">'
        f'{_DIAS_PT[hoje.weekday()]}, {hoje.day} de {_MESES_PT[hoje.month-1]} de {hoje.year}</p>',
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

    # ── Linha 1: Vencidos + Agendados hoje | A agendar esta semana ────────────
    col_esq, col_dir = st.columns([3, 2])

    with col_esq:
        # Vencidos — vermelho
        if vencidos:
            with st.container(border=True):
                _marker("hj-red")
                _titulo("🚨 Acertos vencidos — ação imediata", "red")
                for row in sorted(vencidos, key=lambda r: r["Data acerto"] or hoje):
                    dag    = row.get("Data agendada")
                    has_ag = pd.notna(dag) and bool(dag)
                    badge  = f"📅 {dag.strftime('%d/%m')}" if has_ag else "⚠️ Sem agenda"
                    b_cls  = "hj-b-yellow" if has_ag else "hj-b-red"
                    dac    = row.get("Data acerto")
                    det    = f'Previsto {dac.strftime("%d/%m/%Y") if dac else "—"}'
                    if has_ag:
                        det += f' · {row.get("Forma") or ""}'
                    if _pessoa(row["Nome"], det, badge, b_cls,
                               f"hj_v_{row['id']}",
                               "🔄 Reagendar" if has_ag else "📅 Agendar agora"):
                        _ir_agendar(row["id"])
        else:
            with st.container(border=True):
                _marker("hj-green")
                _titulo("✅ Nenhum acerto vencido", "green")
                st.markdown('<span class="hj-sub">Tudo em dia!</span>', unsafe_allow_html=True)

        # Agendados hoje — verde
        if agendados_hj:
            with st.container(border=True):
                _marker("hj-green")
                _titulo("📅 Agendados para hoje", "green")
                for row in agendados_hj:
                    hora  = row.get("Hora agendada") or ""
                    badge = hora if hora else "Sem hora"
                    det   = f'{row.get("Forma") or "—"} · {_R(row.get("Valor", 0))}'
                    if _pessoa(row["Nome"], det, badge, "hj-b-green",
                               f"hj_h_{row['id']}", "🔄 Reagendar"):
                        _ir_agendar(row["id"])
        else:
            with st.container(border=True):
                _marker("hj-green")
                _titulo("📅 Nenhum acerto agendado para hoje", "green")
                st.markdown('<span class="hj-sub">Veja os pendentes da semana ao lado.</span>',
                            unsafe_allow_html=True)

    with col_dir:
        # A agendar esta semana — amarelo
        if a_agendar_sem:
            with st.container(border=True):
                _marker("hj-yellow")
                _titulo(f"⬜ A agendar esta semana ({len(a_agendar_sem)})", "yellow")
                for row in sorted(a_agendar_sem, key=lambda r: r["Data acerto"] or hoje):
                    dac  = row.get("Data acerto")
                    dias = (dac - hoje).days if dac else 0
                    urg  = "Hoje!" if dias == 0 else f"em {dias}d"
                    det  = f'Acerto em {dac.strftime("%d/%m") if dac else "—"} ({urg})'
                    if _pessoa(row["Nome"], det, "⬜ Pendente", "hj-b-blue",
                               f"hj_s_{row['id']}", "📅 Agendar", primario=True):
                        _ir_agendar(row["id"])
        else:
            with st.container(border=True):
                _marker("hj-green")
                _titulo("✅ Agenda da semana completa", "green")
                st.markdown('<span class="hj-sub">Todos os acertos desta semana estão agendados.</span>',
                            unsafe_allow_html=True)

    # ── Linha 2: Abaixo do mínimo | Sem vendas | Premiações ──────────────────
    st.divider()
    col_ab, col_sv, col_pr = st.columns(3)

    with col_ab:
        # Abaixo do mínimo — amarelo
        if abaixo_min:
            with st.container(border=True):
                _marker("hj-yellow")
                _titulo(f"🟡 Abaixo do mínimo ({len(abaixo_min)})", "yellow")
                for r in sorted(abaixo_min, key=lambda x: x["total"]):
                    pct = int(r["total"] / MINIMO_REV * 100)
                    st.markdown(
                        f'<div class="hj-sep">'
                        f'<span class="hj-nome">{r["nome"]}</span>'
                        f'<span class="hj-badge hj-b-yellow">{pct}%</span>'
                        f'<br><span class="hj-sub">'
                        f'{_R(r["total"])} de {_R(MINIMO_REV)} · falta {_R(r["falta"])}</span>'
                        f'<div class="hj-prog-bg">'
                        f'<div class="hj-prog-fill" style="width:{min(pct,100)}%"></div></div>'
                        f'</div>',
                        unsafe_allow_html=True,
                    )
                st.caption(f"Mínimo: {_R(MINIMO_REV)}/mês.")
        else:
            with st.container(border=True):
                _marker("hj-green")
                _titulo("✅ Todas acima do mínimo", "green")
                st.markdown('<span class="hj-sub">Todas acima do mínimo este mês.</span>',
                            unsafe_allow_html=True)

    with col_sv:
        # Sem vendas — amarelo
        if sem_vendas_list:
            with st.container(border=True):
                _marker("hj-yellow")
                rod = f" (+{len(sem_vendas_list)-7} mais)" if len(sem_vendas_list) > 7 else ""
                _titulo(f"⚠️ Sem vendas ({len(sem_vendas_list)}){rod}", "yellow")
                for r in sem_vendas_list[:7]:
                    st.markdown(
                        f'<div class="hj-sep">'
                        f'<span class="hj-nome">{r["nome"]}</span>'
                        f'<span class="hj-badge hj-b-gray">R$ 0,00</span></div>',
                        unsafe_allow_html=True,
                    )
        else:
            with st.container(border=True):
                _marker("hj-green")
                _titulo("✅ Todas com vendas no mês", "green")
                st.markdown('<span class="hj-sub">Nenhuma revendedora com zero vendas.</span>',
                            unsafe_allow_html=True)

    with col_pr:
        # Premiações
        with st.container(border=True):
            if meta_mes <= 0:
                _marker("hj-gold")
                _titulo("🏆 Premiação", "gold")
                st.markdown('<span class="hj-sub">Meta não configurada. Acesse Revendedoras → Premiações.</span>',
                            unsafe_allow_html=True)
            elif ganhadoras:
                _marker("hj-green")
                _titulo(f"🏆 {len(ganhadoras)} ganhadora(s) este mês", "green")
                for r in ganhadoras[:4]:
                    st.markdown(
                        f'<div class="hj-sep">'
                        f'<span class="hj-nome">{r["Nome"]}</span>'
                        f'<span class="hj-badge hj-b-green">🏆 Ganhou!</span>'
                        f'<br><span class="hj-sub">{_R(r["Baixado"])} baixado</span>'
                        f'</div>', unsafe_allow_html=True)
                for r in quase_meta[:2]:
                    pct = r["% da meta"]
                    st.markdown(
                        f'<div class="hj-sep">'
                        f'<span class="hj-nome">{r["Nome"]}</span>'
                        f'<span class="hj-badge hj-b-gold">🔥 {pct:.0f}%</span>'
                        f'<br><span class="hj-sub">falta {_R(r["Falta"])}</span>'
                        f'<div class="hj-prog-bg"><div class="hj-prog-fill" '
                        f'style="width:{min(int(pct),100)}%"></div></div>'
                        f'</div>', unsafe_allow_html=True)
            elif quase_meta:
                _marker("hj-gold")
                _titulo(f"🏆 {len(quase_meta)} perto da meta", "gold")
                for r in quase_meta[:5]:
                    pct   = r["% da meta"]
                    badge = "🔥 Quase!" if pct >= 85 else f"{pct:.0f}%"
                    b_cls = "hj-b-gold" if pct >= 85 else "hj-b-gray"
                    st.markdown(
                        f'<div class="hj-sep">'
                        f'<span class="hj-nome">{r["Nome"]}</span>'
                        f'<span class="hj-badge {b_cls}">{badge}</span>'
                        f'<br><span class="hj-sub">{_R(r["Total"])} · falta {_R(r["Falta"])}</span>'
                        f'<div class="hj-prog-bg"><div class="hj-prog-fill" '
                        f'style="width:{min(int(pct),100)}%"></div></div>'
                        f'</div>', unsafe_allow_html=True)
            else:
                _marker("hj-gold")
                _titulo("🏆 Premiação", "gold")
                st.markdown('<span class="hj-sub">Nenhuma chegou a 70% da meta ainda.</span>',
                            unsafe_allow_html=True)
            if meta_mes > 0:
                st.caption(f'Meta: {_R(meta_mes)}' + (f' · {premio}' if premio else ""))

    # ── Guia de rotina ─────────────────────────────────────────────────────────
    st.divider()
    with st.expander("🗓️ Guia de rotina — por onde começar?", expanded=False):
        st.markdown("""
#### ☀️ Check diário — 5 minutos, toda manhã

| Passo | Onde | O que fazer |
|---|---|---|
| 1 | **🏠 Hoje** | Acertos vencidos → clicar em Reagendar |
| 2 | **🏠 Hoje** | Agendados para hoje → confirmar com a revendedora |
| 3 | **🏠 Hoje** | A agendar esta semana → clicar em Agendar |

---

#### 📅 Revisão semanal — Segunda-feira, 15 minutos

| Passo | Onde | O que fazer |
|---|---|---|
| 1 | **📅 Controle de Acertos** | Aba **📋 Agendar esta semana** → agendar pendentes |
| 2 | **👥 Revendedoras** | Expander **⏰ Postergados** → contatar atrasadas |
| 3 | **👥 Revendedoras** | Expander **📅 Acertos no mês** → planejar a semana |

---

#### 📊 Revisão semanal — Sexta-feira, 10 minutos

| Passo | Onde | O que fazer |
|---|---|---|
| 1 | **👥 Revendedoras** | Bloco **💰 Financeiro** → total vendido acumulado |
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
