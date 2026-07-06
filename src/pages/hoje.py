from datetime import date, timedelta

import streamlit as st

from src.api.jueri_client import _get_lista_pedidos
from src.logic.acertos import montar_acertos
from src.logic.revendedoras import parse_date

_DIAS_PT = ["Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo"]
_MESES_PT = ["janeiro","fevereiro","março","abril","maio","junho",
             "julho","agosto","setembro","outubro","novembro","dezembro"]

_R = lambda v: f"R$ {v:,.2f}".replace(",","X").replace(".",",").replace("X",".")


# ── helpers visuais ────────────────────────────────────────────────────────────

def _css():
    st.markdown("""
<style>
.hj-card{border-radius:14px;padding:1.1rem 1.4rem 1.2rem;margin-bottom:.65rem}
.hj-urgente{background:#FEF2F2;border:1.5px solid rgba(220,38,38,.25)}
.hj-hoje{background:#FFFBEB;border:1.5px solid rgba(202,138,4,.28)}
.hj-semana{background:#F0F9FF;border:1.5px solid rgba(14,165,233,.22)}
.hj-ok{background:#F0FDF4;border:1.5px solid rgba(22,163,74,.22)}
.hj-titulo{font-size:.62rem;font-weight:700;text-transform:uppercase;letter-spacing:.12em;margin-bottom:.7rem}
.hj-titulo-urg{color:#dc2626}
.hj-titulo-hj{color:#b45309}
.hj-titulo-sem{color:#0284c7}
.hj-titulo-ok{color:#15803d}
.hj-item{display:flex;justify-content:space-between;align-items:center;
          padding:5px 0;border-bottom:1px solid rgba(0,0,0,.06);font-size:.88em}
.hj-item:last-child{border-bottom:none}
.hj-nome{font-weight:600;color:#1e293b}
.hj-detalhe{color:#64748b;font-size:.8em}
.hj-badge{display:inline-block;border-radius:6px;padding:1px 8px;font-size:.75em;font-weight:600;white-space:nowrap}
.hj-badge-red{background:#fee2e2;color:#dc2626}
.hj-badge-yellow{background:#fef9c3;color:#854d0e}
.hj-badge-blue{background:#dbeafe;color:#1d4ed8}
.hj-badge-green{background:#dcfce7;color:#15803d}
.hj-badge-gray{background:#f1f5f9;color:#475569}
.hj-stat{text-align:center;padding:.5rem .8rem}
.hj-stat-num{font-size:2rem;font-weight:700;line-height:1}
.hj-stat-lbl{font-size:.72rem;color:#7A6068;margin-top:.2rem}
.hj-num-red{color:#dc2626}
.hj-num-yellow{color:#b45309}
.hj-num-green{color:#15803d}
.hj-num-blue{color:#0284c7}
.hj-num-neutral{color:#2A1A1F}
</style>
""", unsafe_allow_html=True)


def _item(nome: str, detalhe: str, badge: str, badge_cls: str) -> str:
    return (
        f'<div class="hj-item">'
        f'<div><div class="hj-nome">{nome}</div>'
        f'<div class="hj-detalhe">{detalhe}</div></div>'
        f'<span class="hj-badge {badge_cls}">{badge}</span>'
        f'</div>'
    )


def _card(titulo: str, cls_titulo: str, cls_card: str, itens_html: str, rodape: str = ""):
    rod = f'<div style="font-size:.75rem;color:#94a3b8;margin-top:.6rem">{rodape}</div>' if rodape else ""
    st.markdown(
        f'<div class="hj-card {cls_card}">'
        f'<div class="hj-titulo {cls_titulo}">{titulo}</div>'
        f'{itens_html}{rod}</div>',
        unsafe_allow_html=True,
    )


# ── render ─────────────────────────────────────────────────────────────────────

def render(filtro_supervisor: str = "", nome_usuario: str = ""):
    _css()

    hoje = date.today()
    dia_semana = _DIAS_PT[hoje.weekday()]
    data_fmt = f"{hoje.day} de {_MESES_PT[hoje.month - 1]} de {hoje.year}"

    st.markdown(
        f'<h2 style="margin-bottom:2px">👋 Olá, {nome_usuario or "Supervisora"}!</h2>'
        f'<p style="color:#7A6068;margin-top:0">{dia_semana}, {data_fmt}</p>',
        unsafe_allow_html=True,
    )

    # ── Carrega dados ──────────────────────────────────────────────────────────
    with st.spinner("Carregando sua agenda..."):
        try:
            todos_pedidos_bruto = _get_lista_pedidos()
        except Exception as e:
            st.error(f"Erro ao carregar dados: {e}")
            return

    if filtro_supervisor:
        pedidos = [p for p in todos_pedidos_bruto
                   if (p.get("supervisor_nome") or "") == filtro_supervisor]
    else:
        pedidos = todos_pedidos_bruto

    df = montar_acertos(pedidos)

    # ── Calcula urgências ──────────────────────────────────────────────────────
    sem_ini, sem_fim = hoje, hoje + timedelta(days=6)

    vencidos      = []
    agendados_hj  = []
    a_agendar_sem = []

    if not df.empty:
        for _, row in df.iterrows():
            sit = row.get("Situação", "")
            dag = row.get("Data agendada")
            dac = row.get("Data acerto")
            nom = row.get("Nome", "—")
            val = row.get("Valor", 0)
            forma = row.get("Forma", "")

            if sit == "🔴 Vencido":
                vencidos.append({"nome": nom, "acerto": dac, "valor": val})
            elif sit == "📅 Agendado" and dag == hoje:
                agendados_hj.append({"nome": nom, "acerto": dac, "forma": forma, "valor": val})
            elif sit == "⬜ A agendar" and dac and sem_ini <= dac <= sem_fim:
                a_agendar_sem.append({"nome": nom, "acerto": dac, "valor": val})

    # Sem vendas no mês atual
    mes_num, ano_num = hoje.month, hoje.year
    sem_vendas = set()
    for p in pedidos:
        if p.get("status") not in ("Aberto", "Baixado"):
            continue
        d = parse_date(p.get("data_acerto"))
        if d and d.month == mes_num and d.year == ano_num:
            val = float(p.get("valor_total") or p.get("valor_pre_baixa") or 0)
            if val == 0:
                comp = p.get("comprador") or {}
                sem_vendas.add(comp.get("nome") or f"Rev {p.get('fk_revendedor_id')}")

    # ── Painel de números ──────────────────────────────────────────────────────
    n_venc = len(vencidos)
    n_hj   = len(agendados_hj)
    n_sem  = len(a_agendar_sem)
    n_sv   = len(sem_vendas)

    c1, c2, c3, c4 = st.columns(4)
    for col, num, lbl, cor in [
        (c1, n_venc, "Vencidos", "hj-num-red"),
        (c2, n_hj,   "Agendados hoje", "hj-num-yellow"),
        (c3, n_sem,  "A agendar esta semana", "hj-num-blue"),
        (c4, n_sv,   "Sem vendas no mês", "hj-num-neutral"),
    ]:
        col.markdown(
            f'<div class="hj-stat">'
            f'<div class="hj-stat-num {cor}">{num}</div>'
            f'<div class="hj-stat-lbl">{lbl}</div></div>',
            unsafe_allow_html=True,
        )

    st.divider()

    col_esq, col_dir = st.columns([3, 2])

    with col_esq:
        # Vencidos
        if vencidos:
            itens = "".join(
                _item(v["nome"],
                      f'Acerto em {v["acerto"].strftime("%d/%m") if v["acerto"] else "—"}',
                      "🚨 Vencido", "hj-badge-red")
                for v in sorted(vencidos, key=lambda x: x["acerto"] or hoje)
            )
            _card("🚨 Acertos vencidos — ação imediata",
                  "hj-titulo-urg", "hj-urgente", itens,
                  "Ligue agora e reagende no Controle de Acertos.")
        else:
            _card("✅ Nenhum acerto vencido",
                  "hj-titulo-ok", "hj-ok",
                  '<div style="color:#15803d;font-size:.9em;padding:4px 0">Tudo em dia! Continue assim.</div>')

        # Agendados hoje
        if agendados_hj:
            itens = "".join(
                _item(a["nome"],
                      a.get("forma") or "Forma não definida",
                      _R(a["valor"]) if a["valor"] else "—", "hj-badge-yellow")
                for a in agendados_hj
            )
            _card("📅 Agendados para hoje",
                  "hj-titulo-hj", "hj-hoje", itens,
                  "Confirme os detalhes no Controle de Acertos.")
        else:
            _card("📅 Nenhum acerto agendado para hoje",
                  "hj-titulo-hj", "hj-hoje",
                  '<div style="color:#92400e;font-size:.9em;padding:4px 0">Verifique se há pendentes a agendar esta semana.</div>')

    with col_dir:
        # A agendar esta semana
        if a_agendar_sem:
            itens = "".join(
                _item(a["nome"],
                      f'Acerto previsto {a["acerto"].strftime("%d/%m") if a["acerto"] else "—"}',
                      "⬜ Sem agenda", "hj-badge-blue")
                for a in sorted(a_agendar_sem, key=lambda x: x["acerto"] or hoje)
            )
            _card(f"⬜ A agendar esta semana ({n_sem})",
                  "hj-titulo-sem", "hj-semana", itens,
                  "Acesse Controle de Acertos para agendar.")
        else:
            _card("✅ Agenda da semana completa",
                  "hj-titulo-ok", "hj-ok",
                  '<div style="color:#15803d;font-size:.9em;padding:4px 0">Todos os acertos desta semana estão agendados.</div>')

        # Sem vendas
        if sem_vendas:
            nomes_sv = sorted(sem_vendas)[:8]
            itens = "".join(
                _item(n, "R$ 0,00 no mês", "⚠️ Sem venda", "hj-badge-gray")
                for n in nomes_sv
            )
            rodape = f"+ {len(sem_vendas) - 8} revendedoras" if len(sem_vendas) > 8 else ""
            _card(f"⚠️ Sem vendas este mês ({n_sv})",
                  "hj-titulo-urg", "hj-urgente", itens, rodape)

    # ── Dica de navegação ──────────────────────────────────────────────────────
    st.divider()
    st.caption("💡 Use o menu lateral para acessar **Revendedoras** e **Controle de Acertos**.")
