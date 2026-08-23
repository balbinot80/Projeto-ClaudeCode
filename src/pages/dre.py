"""
Tela DRE — Demonstração do Resultado do Exercício.
Visual tipo planilha: Planejado | % | Realizado | % | Var%
Editor de categoria inline na tabela de despesas.
"""

from __future__ import annotations
from datetime import date

import streamlit as st
import pandas as pd

from src.logic.dre import (
    calcular_dre_completo, ORDEM_DRE, TOTAIS, CUSTOS_VAR,
    mes_esta_fechado, nome_aba_financeiro,
    carregar_mapeamento_custom, salvar_mapeamento_custom,
    categorizar_despesa, CATEGORIAS_DISPONIVEIS,
)
from src.api.google_sheets import (
    ler_despesas_mes, credentials_configuradas,
    cmv_pct_historico, ler_cmv_historico,
    ler_taxa_cartao_mes,
)


# ── Helpers numéricos ─────────────────────────────────────────────────────────

def _br(v: float, dash_zero: bool = False) -> str:
    if dash_zero and v == 0:
        return "—"
    sinal = "-" if v < 0 else ""
    return f"{sinal}R$ {abs(v):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _pct(valor: float, base: float) -> str:
    if not base:
        return "—"
    return f"{valor / base * 100:.1f}%"


def _var(real: float, plan: float) -> str:
    if not plan:
        return "—"
    v = (real - plan) / plan * 100
    sinal = "▲" if v >= 0 else "▼"
    return f"{sinal} {abs(v):.1f}%"


def _var_class(real: float, plan: float, inverted: bool = False) -> str:
    """CSS class para variação (verde=bom, vermelho=ruim)."""
    if not plan:
        return ""
    positivo = real >= plan
    if inverted:
        positivo = not positivo
    return "var-pos" if positivo else "var-neg"


# ── Receita do Jueri ──────────────────────────────────────────────────────────

def _receita_mes(pedidos: list, mes: int, ano: int) -> tuple[float, float]:
    try:
        from src.logic.revendedoras import parse_date
    except ImportError:
        from datetime import datetime
        def parse_date(s):
            for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
                try:
                    return datetime.strptime(str(s), fmt).date()
                except Exception:
                    pass
            return None

    fechado = mes_esta_fechado(mes, ano)
    receita = comissoes = 0.0
    for p in pedidos:
        status = p.get("status", "")
        if status == "Baixado":
            d = parse_date(p.get("data_baixa"))
            if d and d.month == mes and d.year == ano:
                receita   += float(p.get("valor_total") or 0)
                comissoes += float(p.get("valor_comissao") or p.get("comissao_revendedor") or p.get("comissao") or 0)
        elif not fechado and status == "Aberto":
            d = parse_date(p.get("data_acerto"))
            if d and d.month == mes and d.year == ano:
                receita += float(p.get("valor_pre_baixa") or p.get("valor_total") or 0)
    return receita, comissoes


# ── Tabela DRE visual ─────────────────────────────────────────────────────────

_CSS = """
<style>
.dre-wrap { overflow-x: auto; margin-top: 8px; }
.dre { width: 100%; border-collapse: collapse; font-size: 0.88em; }
.dre th {
  background: #2A1A1F; color: #FAF7F4;
  padding: 7px 10px; text-align: right; font-weight: 600; white-space: nowrap;
}
.dre th:first-child { text-align: left; }
.dre td { padding: 6px 10px; border-bottom: 1px solid #EDE8E3;
          white-space: nowrap; text-align: right; }
.dre td:first-child { text-align: left; }

/* Seções (tipo item 1, 2, 3…) */
.sec td { background: #C4985A; color: #fff; font-weight: 700; }

/* Subtotais (Margem, Lucro Op.) */
.sub td { background: #F5EBEC; color: #2A1A1F; font-weight: 700; }

/* Resultado final */
.fin-pos td { background: #1a6b3a; color: #fff; font-weight: 700; }
.fin-neg td { background: #8b2020; color: #fff; font-weight: 700; }

/* Linhas normais alternadas */
.dre tr.row:nth-child(even) td { background: #FAFAFA; }
.dre tr.row:nth-child(odd) td { background: #fff; }

/* Variação colorida */
.var-pos { color: #1a6b3a; }
.var-neg { color: #8b2020; }
.dash { color: #aaa; }
</style>
"""

# Grupos e suas classes visuais
_SECOES = {
    "receita_bruta",
    "margem_contribuicao",
    "lucro_operacional",
    "lucro_liquido",
}
_LABELS_SECAO = {
    "receita_bruta":        "1. VENDAS TOTAIS",
    "margem_contribuicao":  "3. MARGEM DE CONTRIBUIÇÃO  (1 − 2)",
    "lucro_operacional":    "5. LUCRO OPERACIONAL  (3 − 4)",
    "lucro_liquido":        "10. LUCRO LÍQUIDO",
}
# Cabecalhos de grupo (sem valor próprio — só estilo)
_GRUPO_ANTES = {
    "2.1 CMV":   "2. CUSTOS VARIÁVEIS",
    "4.1 Pró-labore": "4. CUSTOS FIXOS",
    "6. Receitas Não Operacionais": "6–9. NÃO OPERACIONAIS / INVESTIMENTOS",
}


def _html_dre(real: dict, plan: dict) -> str:
    rb_r = real.get("receita_bruta", 0) or 1   # base %
    rb_p = plan.get("receita_bruta", 0) or 1

    rows = ['<div class="dre-wrap"><table class="dre">']
    rows.append(
        "<thead><tr>"
        "<th style='width:38%'>Discriminação</th>"
        "<th>Planejado</th><th>%</th>"
        "<th>Realizado</th><th>%</th>"
        "<th>Var%</th>"
        "</tr></thead><tbody>"
    )

    for codigo, rotulo in ORDEM_DRE:
        vr = real.get(codigo, 0.0)
        vp = plan.get(codigo, 0.0)

        # Sem dados? pula linhas de detalhe (não pula totais)
        if vr == 0 and vp == 0 and codigo not in TOTAIS:
            continue

        # Cabeçalho de grupo (inserido antes de certos itens)
        if codigo in _GRUPO_ANTES:
            rows.append(
                f'<tr class="sec">'
                f'<td colspan="6">{_GRUPO_ANTES[codigo]}</td>'
                f'</tr>'
            )

        # Decide classe da linha
        if codigo == "lucro_liquido":
            cls = "fin-pos" if vr >= 0 else "fin-neg"
            label = _LABELS_SECAO[codigo]
        elif codigo in _LABELS_SECAO:
            cls = "sub"
            label = _LABELS_SECAO[codigo]
        else:
            cls = "row"
            label = rotulo.strip()

        # Inversão de "bom": despesas, quanto menor melhor
        inverted = codigo not in TOTAIS and codigo != "receita_bruta"
        vc = _var_class(vr, vp, inverted=inverted)
        v_str = _var(vr, vp)
        v_td = f'<span class="{vc}">{v_str}</span>' if vc else f'<span class="dash">{v_str}</span>'

        rows.append(
            f'<tr class="{cls}">'
            f'<td>{label}</td>'
            f'<td>{_br(vp, dash_zero=(cls=="row"))}</td>'
            f'<td>{_pct(vp, rb_p) if vp else "—"}</td>'
            f'<td>{_br(vr, dash_zero=(cls=="row"))}</td>'
            f'<td>{_pct(vr, rb_r) if vr else "—"}</td>'
            f'<td>{v_td}</td>'
            f'</tr>'
        )

    rows.append("</tbody></table></div>")
    return _CSS + "".join(rows)


# ── Render principal ──────────────────────────────────────────────────────────

def render():
    st.title("💰 DRE — Demonstração do Resultado")

    # ── Seletor de mês (pills horizontais) ────────────────────────────────────
    hoje = date.today()
    MESES_PT = ["Jan","Fev","Mar","Abr","Mai","Jun",
                "Jul","Ago","Set","Out","Nov","Dez"]

    # Mostra Jan/2026 até mês atual
    opcoes: list[tuple[int,int]] = []
    for m in range(1, hoje.month + 1):
        opcoes.append((m, hoje.year))

    labels = [f"{MESES_PT[m-1]}/{str(a)[2:]}" for m, a in opcoes]

    col_sel, col_tip, _ = st.columns([2, 4, 4])
    with col_sel:
        idx = st.selectbox("Mês", range(len(opcoes)),
                           index=len(opcoes) - 1,
                           format_func=lambda i: labels[i],
                           key="dre_mes")
    mes, ano = opcoes[idx]
    fechado = mes_esta_fechado(mes, ano)

    with col_tip:
        st.markdown("<div style='margin-top:28px'></div>", unsafe_allow_html=True)
        if fechado:
            st.caption("📅 Mês fechado — dados consolidados")
        else:
            st.caption("📊 Mês em aberto — baixados + pré-baixa acumulada")

    st.divider()

    # ── Aviso sem Google Sheets ───────────────────────────────────────────────
    sem_sheets = not credentials_configuradas()
    if sem_sheets:
        st.warning(
            "⚠️ Credenciais do Google não configuradas — despesas indisponíveis.",
            icon="🔑",
        )

    # ── Carrega dados ─────────────────────────────────────────────────────────
    with st.spinner("Carregando dados..."):
        try:
            from src.api.jueri_client import _get_lista_pedidos
            pedidos = _get_lista_pedidos()
        except Exception:
            pedidos = []

        receita, comissoes = _receita_mes(pedidos, mes, ano)
        despesas   = ler_despesas_mes(mes, ano)
        custom     = carregar_mapeamento_custom()
        pct_cmv    = cmv_pct_historico()        # % médio total histórico
        dados_cmv  = ler_cmv_historico()        # para exibir detalhes

        # Taxa de cartão: lida da coluna N a partir de Jul/2026
        taxa_cartao = None
        if (ano, mes) >= (2026, 7):
            taxa_cartao = ler_taxa_cartao_mes(mes, ano) or None

    real, plan = calcular_dre_completo(
        receita, comissoes, despesas, custom,
        cmv_pct=pct_cmv,
        taxa_cartao=taxa_cartao,
    )

    # ── KPIs rápidos ─────────────────────────────────────────────────────────
    ll = real.get("lucro_liquido", 0)
    lo = real.get("lucro_operacional", 0)
    mc = real.get("margem_contribuicao", 0)
    td = sum(v for k, v in real.items() if k not in TOTAIS and k != "receita_bruta" and v > 0)
    rb = real.get("receita_bruta", 0)

    comissao = real.get("2.4 Comissões", 0.0)

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("💰 Receita Bruta",     _br(rb))
    c2.metric("💸 Total Despesas",     _br(td))
    c3.metric("🤝 Comissões",          _br(comissao),
              _pct(comissao, rb) if rb else "—")
    c4.metric("⚙️ Lucro Operacional",  _br(lo),
              _pct(lo, rb) if rb else "—",
              delta_color="normal" if lo >= 0 else "inverse")
    c5.metric("✅ Lucro Líquido",      _br(ll),
              f"{ll/rb*100:.1f}% da receita" if rb else "—",
              delta_color="normal" if ll >= 0 else "inverse")

    st.divider()

    # ── Tabela DRE visual ─────────────────────────────────────────────────────
    st.subheader(f"DRE — {MESES_PT[mes-1]}/{ano}")

    if pct_cmv is not None:
        n = dados_cmv.get("n_meses", "?")
        tc = dados_cmv.get("total_compra", 0)
        tv = dados_cmv.get("total_venda", 0)
        st.caption(
            f"📦 **CMV pelo histórico total ({n} meses):** "
            f"{_br(tc)} compras ÷ {_br(tv)} vendas = **{pct_cmv*100:.2f}%** → "
            f"{_br(receita * pct_cmv)} neste mês. "
            f"Atualiza automaticamente conforme novos meses são lançados."
        )
    elif credentials_configuradas():
        st.caption("📦 CMV calculado pelas compras reais do mês (planilha de histórico não acessível)")
    st.markdown(_html_dre(real, plan), unsafe_allow_html=True)

    # ── Tabela de despesas com editor inline ──────────────────────────────────
    if despesas:
        st.divider()
        st.subheader("📋 Despesas do mês")
        st.caption(
            "Altere a **Categoria DRE** diretamente na tabela e clique em "
            "**Salvar alterações** para atualizar o DRE acima."
        )

        # Monta dataframe editável
        linhas = []
        for d in despesas:
            cat = categorizar_despesa(d["nome"], custom)
            linhas.append({
                "Despesa":       d["nome"],
                "Categoria DRE": cat,
                "Previsto":      round(float(d.get("previsto") or 0), 2),
                "Realizado":     round(float(d.get("realizado") or 0), 2),
                "Tipo":          d.get("tipo", ""),
                "Forma Pgto":    d.get("forma_pgto", ""),
                "_manual":       d["nome"] in custom,
            })

        df_orig = pd.DataFrame(linhas)

        edited = st.data_editor(
            df_orig.drop(columns=["_manual"]),
            column_config={
                "Despesa":       st.column_config.TextColumn("Despesa", disabled=True, width="large"),
                "Categoria DRE": st.column_config.SelectboxColumn(
                    "Categoria DRE",
                    options=CATEGORIAS_DISPONIVEIS,
                    required=True,
                    width="medium",
                ),
                "Previsto":  st.column_config.NumberColumn("Previsto (R$)",  format="R$ %.2f", disabled=True),
                "Realizado": st.column_config.NumberColumn("Realizado (R$)", format="R$ %.2f", disabled=True),
                "Tipo":      st.column_config.TextColumn("Tipo",      disabled=True, width="small"),
                "Forma Pgto":st.column_config.TextColumn("Forma Pgto",disabled=True, width="small"),
            },
            use_container_width=True,
            hide_index=True,
            key=f"dre_editor_{mes}_{ano}",
        )

        # Detecta mudanças
        alteracoes = {}
        for _, row_orig, row_edit in zip(
            range(len(df_orig)),
            df_orig.itertuples(index=False),
            edited.itertuples(index=False),
        ):
            if row_orig._1 != row_edit._1:   # _1 = "Categoria DRE" (2ª col)
                alteracoes[row_orig.Despesa] = row_edit._1

        if alteracoes:
            st.info(f"✏️ {len(alteracoes)} alteração(ões) pendente(s). Clique abaixo para salvar.")

        col_save, col_reset, _ = st.columns([2, 2, 6])
        with col_save:
            if st.button("💾 Salvar alterações", type="primary",
                         use_container_width=True, disabled=not alteracoes):
                custom.update(alteracoes)
                salvar_mapeamento_custom(custom)
                st.cache_data.clear()
                st.success(f"✅ {len(alteracoes)} categoria(s) salva(s).")
                st.rerun()

        with col_reset:
            manuais = [n for n in (d["nome"] for d in despesas) if n in custom]
            if manuais and st.button("🔄 Limpar todos os ajustes manuais",
                                     use_container_width=True):
                for n in manuais:
                    del custom[n]
                salvar_mapeamento_custom(custom)
                st.cache_data.clear()
                st.rerun()

        # Aviso de despesas em "Outros"
        sem_cat = edited[edited["Categoria DRE"] == "4.99 Sem Classificação"]["Despesa"].tolist()
        if sem_cat:
            st.warning(
                f"⚠️ {len(sem_cat)} despesa(s) em **4.99 Outros** (sem mapeamento): "
                + ", ".join(sem_cat[:6]) + ("…" if len(sem_cat) > 6 else "")
            )
