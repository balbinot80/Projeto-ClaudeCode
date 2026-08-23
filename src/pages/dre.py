"""
Tela DRE — Demonstração do Resultado do Exercício.
Cruza receita do Jueri com despesas do Google Sheets.
"""

from __future__ import annotations
from datetime import date

import streamlit as st
import pandas as pd

from src.logic.dre import (
    calcular_dre, ORDEM_DRE, TOTAIS,
    mes_esta_fechado, nome_aba_financeiro,
    carregar_mapeamento_custom, salvar_mapeamento_custom,
    categorizar_despesa, CATEGORIAS_DISPONIVEIS,
)
from src.api.google_sheets import ler_despesas_mes, credentials_configuradas


# ── Helpers ───────────────────────────────────────────────────────────────────

def _fmt(v: float) -> str:
    """Formata valor em R$ com separadores brasileiros."""
    sinal = "-" if v < 0 else ""
    return f"{sinal}R$ {abs(v):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _receita_mes(pedidos: list, mes: int, ano: int) -> tuple[float, float]:
    """
    Retorna (receita_bruta, comissoes) para o mês.
    - Meses fechados: só baixados
    - Mês atual/futuro: baixados + pré-baixa
    """
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
    receita = 0.0
    comissoes = 0.0

    for p in pedidos:
        status = p.get("status", "")

        # Baixados: data_baixa no mês
        if status == "Baixado":
            d = parse_date(p.get("data_baixa"))
            if d and d.month == mes and d.year == ano:
                receita   += float(p.get("valor_total") or 0)
                comissoes += float(p.get("comissao_revendedor") or
                                   p.get("comissao") or 0)

        # Abertos com acerto no mês (pré-baixa) — só para meses não fechados
        elif not fechado and status == "Aberto":
            d = parse_date(p.get("data_acerto"))
            if d and d.month == mes and d.year == ano:
                receita += float(p.get("valor_pre_baixa") or
                                 p.get("valor_total") or 0)

    return receita, comissoes


# ── Render ────────────────────────────────────────────────────────────────────

def render():
    st.title("💰 DRE — Demonstração do Resultado")

    # ── Seletor de mês ────────────────────────────────────────────────────────
    hoje = date.today()
    opcoes = []
    for delta in range(0, 12):
        m = hoje.month - delta
        a = hoje.year
        while m <= 0:
            m += 12
            a -= 1
        opcoes.append((m, a))

    MESES_PT = ["Jan","Fev","Mar","Abr","Mai","Jun","Jul","Ago","Set","Out","Nov","Dez"]
    labels = [f"{MESES_PT[m-1]}/{a}" for m, a in opcoes]

    col_sel, col_info, _ = st.columns([2, 3, 5])
    with col_sel:
        idx = st.selectbox("Mês de referência", range(len(opcoes)),
                           format_func=lambda i: labels[i], key="dre_mes")
    mes, ano = opcoes[idx]
    fechado = mes_esta_fechado(mes, ano)

    with col_info:
        st.markdown("<div style='margin-top:28px'></div>", unsafe_allow_html=True)
        if fechado:
            st.caption("📅 Mês fechado — usando apenas pedidos baixados")
        else:
            st.caption("📊 Mês em aberto — baixados + pré-baixa acumulada")

    st.divider()

    # ── Verifica credenciais Google ───────────────────────────────────────────
    if not credentials_configuradas():
        st.warning(
            "⚠️ Credenciais do Google não configuradas. "
            "Adicione o arquivo `.streamlit/google_credentials.json` "
            "para carregar as despesas automaticamente.",
            icon="🔑",
        )
        st.info("As receitas do Jueri continuam disponíveis abaixo.")

    # ── Carrega dados ─────────────────────────────────────────────────────────
    with st.spinner("Carregando dados..."):
        try:
            from src.api.jueri_client import _get_lista_pedidos
            pedidos = _get_lista_pedidos()
        except Exception:
            pedidos = []

        receita, comissoes = _receita_mes(pedidos, mes, ano)
        despesas = ler_despesas_mes(mes, ano)
        custom = carregar_mapeamento_custom()

    # ── KPIs rápidos ─────────────────────────────────────────────────────────
    dre = calcular_dre(receita, comissoes, despesas, custom)

    lucro_liq    = dre.get("lucro_liquido", 0.0)
    lucro_op     = dre.get("lucro_operacional", 0.0)
    margem_contr = dre.get("margem_contribuicao", 0.0)
    total_desp   = sum(v for k, v in dre.items()
                       if k not in TOTAIS and k != "receita_bruta" and v > 0)
    margem_pct   = (lucro_liq / receita * 100) if receita else 0.0

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("💰 Receita Bruta",    _fmt(receita))
    c2.metric("📊 Margem Contrib.",  _fmt(margem_contr),
              f"{(margem_contr/receita*100):.1f}%" if receita else "—")
    c3.metric("⚙️ Lucro Operacional", _fmt(lucro_op),
              f"{(lucro_op/receita*100):.1f}%" if receita else "—",
              delta_color="normal" if lucro_op >= 0 else "inverse")
    c4.metric("💸 Total Despesas",   _fmt(total_desp))
    c5.metric("✅ Lucro Líquido",    _fmt(lucro_liq),
              f"{margem_pct:.1f}% da receita",
              delta_color="normal" if lucro_liq >= 0 else "inverse")

    st.divider()

    # ── Tabela DRE ────────────────────────────────────────────────────────────
    st.subheader(f"DRE — {MESES_PT[mes-1]}/{ano}")

    if not despesas and credentials_configuradas():
        st.info(f"Nenhuma despesa encontrada para {nome_aba_financeiro(mes, ano)}. "
                "Verifique se a aba existe na planilha financeira.")

    linhas = []
    for codigo, rotulo in ORDEM_DRE:
        valor = dre.get(codigo, 0.0)
        if valor == 0.0 and codigo not in TOTAIS:
            continue   # oculta linhas zeradas

        eh_total = codigo in TOTAIS
        linhas.append({
            "Descrição": rotulo,
            "Realizado": _fmt(valor),
            "_valor":    valor,
            "_total":    eh_total,
        })

    if linhas:
        df = pd.DataFrame(linhas)[["Descrição", "Realizado"]]
        st.dataframe(
            df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Descrição": st.column_config.TextColumn(width="large"),
                "Realizado": st.column_config.TextColumn(width="medium"),
            },
        )

    st.divider()

    # ── Editor de categorias (correção rápida inline) ─────────────────────────
    with st.expander("✏️ Corrigir categoria de uma despesa", expanded=False):
        st.caption(
            "Se uma despesa está na categoria errada, selecione-a abaixo e "
            "defina a categoria correta. O ajuste é salvo permanentemente."
        )

        if not despesas:
            st.info("Nenhuma despesa carregada para o mês selecionado.")
        else:
            # Monta lista de despesas com categoria atual
            nomes = sorted(set(d["nome"] for d in despesas))
            nome_sel = st.selectbox("Despesa", nomes, key="dre_edit_nome")

            cat_atual = custom.get(nome_sel) or categorizar_despesa(nome_sel, custom)
            cat_nova = st.selectbox(
                "Nova categoria",
                CATEGORIAS_DISPONIVEIS,
                index=CATEGORIAS_DISPONIVEIS.index(cat_atual)
                      if cat_atual in CATEGORIAS_DISPONIVEIS else 0,
                key="dre_edit_cat",
            )

            col_btn, col_rem, _ = st.columns([2, 2, 6])
            with col_btn:
                if st.button("💾 Salvar ajuste", type="primary", use_container_width=True):
                    custom[nome_sel] = cat_nova
                    salvar_mapeamento_custom(custom)
                    st.success(f"✅ '{nome_sel}' → {cat_nova}")
                    st.cache_data.clear()
                    st.rerun()

            with col_rem:
                if nome_sel in custom:
                    if st.button("🔄 Remover ajuste manual", use_container_width=True):
                        del custom[nome_sel]
                        salvar_mapeamento_custom(custom)
                        st.info(f"'{nome_sel}' voltou à categoria automática.")
                        st.cache_data.clear()
                        st.rerun()

    # ── Detalhamento de despesas ──────────────────────────────────────────────
    if despesas:
        with st.expander("📋 Ver todas as despesas da planilha"):
            linhas_desp = []
            for d in despesas:
                cat = categorizar_despesa(d["nome"], custom)
                eh_manual = d["nome"] in custom
                linhas_desp.append({
                    "Despesa":      d["nome"],
                    "Categoria DRE": ("🔧 " if eh_manual else "") + cat,
                    "Previsto":     _fmt(d["previsto"]) if d["previsto"] else "—",
                    "Realizado":    _fmt(d["realizado"]) if d["realizado"] else "—",
                    "Tipo":         d.get("tipo", ""),
                    "Forma Pgto":   d.get("forma_pgto", ""),
                })

            df_desp = pd.DataFrame(linhas_desp)
            st.dataframe(
                df_desp,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Despesa":       st.column_config.TextColumn(width="large"),
                    "Categoria DRE": st.column_config.TextColumn(width="medium"),
                    "Previsto":      st.column_config.TextColumn(width="small"),
                    "Realizado":     st.column_config.TextColumn(width="small"),
                },
            )

            # Alerta: despesas sem categoria definida
            sem_cat = [d["Despesa"] for d in linhas_desp
                       if "4.99 Outros" in d["Categoria DRE"]]
            if sem_cat:
                st.warning(
                    f"⚠️ {len(sem_cat)} despesa(s) em **Outros** (sem mapeamento): "
                    + ", ".join(sem_cat[:8])
                    + ("…" if len(sem_cat) > 8 else "")
                )
