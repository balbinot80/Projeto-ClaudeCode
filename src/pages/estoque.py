import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import date

from src.api.jueri_client import (
    get_produtos, get_categorias, get_itens_pedidos_abertos, get_itens_pedidos_baixados
)
from src.logic.estoque import montar_df_estoque
from src.logic.compras import top_vendidos_por_categoria

_DIAS_HIST = 90     # janela de vendas para calcular velocidade
_CRITICO_D = 7      # cobertura < 7 dias → ruptura iminente
_ATENCAO_D = 30     # cobertura < 30 dias → atenção
_CAP_QTD   = 200    # cap de unidades por item de pedido (evita lixo da API)


# ── Enriquecimento com velocidade de vendas ────────────────────────────────

def _enriquecer(df: pd.DataFrame, itens_vendidos: list) -> pd.DataFrame:
    """Adiciona Vendas(90d), Vendas/dia, Cobertura, Giro e Status enriquecido."""
    vendas_pid: dict = {}
    for item in itens_vendidos:
        pid = item.get("produto_id")
        qtd = min(float(item.get("quantidade") or 0), _CAP_QTD)
        vendas_pid[pid] = vendas_pid.get(pid, 0) + qtd

    df = df.copy()
    df["Vendas (90d)"]  = df["ID"].map(lambda p: int(round(vendas_pid.get(p, 0))))
    df["Vendas/dia"]    = (df["Vendas (90d)"] / _DIAS_HIST).round(3)

    def _cob(row):
        if row["Vendas/dia"] == 0:
            return None
        return int(round(row["Em estoque"] / row["Vendas/dia"]))

    def _giro(row):
        vendas_ano = row["Vendas (90d)"] * (365 / _DIAS_HIST)
        return round(vendas_ano / max(row["Total"], 1), 1)

    df["Cobertura (dias)"] = df.apply(_cob, axis=1)
    df["Giro anual"]       = df.apply(_giro, axis=1)

    def _status(r):
        if r["Em estoque"] == 0 and r["Na rua"] == 0:
            return "⚫ Zerado"
        if r["Em estoque"] == 0:
            return "🟡 Só na rua"
        if r["Vendas/dia"] == 0:
            return "🔵 Parado"
        cob = r["Cobertura (dias)"]
        if cob is not None and cob < _CRITICO_D:
            return "🔴 Ruptura iminente"
        if cob is not None and cob < _ATENCAO_D:
            return "🟡 Atenção"
        return "🟢 OK"

    df["Status"] = df.apply(_status, axis=1)
    return df


# ── Helpers de estilo ──────────────────────────────────────────────────────

def _cor_status(val):
    s = str(val)
    if "Ruptura"  in s: return "background-color:#ffd6d6;color:#c00"
    if "Parado"   in s: return "background-color:#e3f2fd"
    if "Só na rua" in s or "Atenção" in s: return "background-color:#fff9c4"
    if "Zerado"   in s: return "background-color:#eeeeee"
    return ""


# ── Sub-telas ──────────────────────────────────────────────────────────────

def _painel_alertas(df):
    """Cards de resumo de situação no topo da página."""
    n_rupt  = (df["Status"] == "🔴 Ruptura iminente").sum()
    n_aten  = (df["Status"] == "🟡 Atenção").sum()
    n_par   = (df["Status"] == "🔵 Parado").sum()
    n_rua   = (df["Status"] == "🟡 Só na rua").sum()
    n_zer   = (df["Status"] == "⚫ Zerado").sum()

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("🔴 Ruptura iminente", n_rupt,  help=f"Cobertura < {_CRITICO_D} dias — compre urgente")
    c2.metric("🟡 Atenção",          n_aten,  help=f"Cobertura entre {_CRITICO_D} e {_ATENCAO_D} dias")
    c3.metric("🔵 Parados (90d)",    n_par,   help="Estoque > 0 mas sem nenhuma venda nos últimos 90 dias")
    c4.metric("🟡 Só na rua",        n_rua,   help="0 unidades em depósito — risco se revendedora não devolver")
    c5.metric("⚫ Zerados",          n_zer,   help="Sem estoque em nenhum lugar")
    return n_rupt, n_aten, n_par, n_rua, n_zer


def _tab_alertas(df):
    urgentes = df[df["Status"].isin(
        ["🔴 Ruptura iminente", "🟡 Atenção", "🟡 Só na rua"]
    )].sort_values("Cobertura (dias)", na_position="last").copy()

    if urgentes.empty:
        st.success("Nenhum produto em situação crítica no momento.")
        return

    st.caption(
        f"**{len(urgentes)} produtos** precisam de atenção. "
        "Ordene por 'Cobertura (dias)' para ver os mais urgentes primeiro."
    )

    cols = ["Produto", "Categoria", "Em estoque", "Na rua",
            "Vendas/dia", "Cobertura (dias)", "Status"]
    st.dataframe(
        urgentes[cols].style.map(_cor_status, subset=["Status"]),
        use_container_width=True, hide_index=True,
    )

    csv = urgentes[cols].to_csv(index=False).encode("utf-8")
    st.download_button("⬇️ Exportar alertas (CSV)", csv, "alertas_estoque.csv", "text/csv")


def _tab_categorias(df):
    resumo = df.groupby("Categoria", as_index=False).agg(
        Produtos        = ("Produto",          "count"),
        Em_estoque      = ("Em estoque",        "sum"),
        Na_rua          = ("Na rua",            "sum"),
        Total           = ("Total",             "sum"),
        Cob_mediana     = ("Cobertura (dias)",  "median"),
        Criticos        = ("Status", lambda x: (x == "🔴 Ruptura iminente").sum()),
        Atencao         = ("Status", lambda x: (x == "🟡 Atenção").sum()),
        Parados         = ("Status", lambda x: (x == "🔵 Parado").sum()),
    )
    resumo["% na rua"] = (resumo["Na_rua"] / resumo["Total"].clip(lower=1) * 100).round(1)
    resumo = resumo.rename(columns={
        "Em_estoque": "Em estoque", "Na_rua": "Na rua",
        "Cob_mediana": "Cobertura mediana (dias)",
        "Criticos": "🔴", "Atencao": "🟡", "Parados": "🔵",
    })

    # Gráfico de cobertura por categoria — o mais útil para o dono
    fig = px.bar(
        resumo.sort_values("Cobertura mediana (dias)"),
        x="Cobertura mediana (dias)", y="Categoria", orientation="h",
        color="Cobertura mediana (dias)",
        color_continuous_scale=[[0, "#c00"], [0.12, "#ffb300"], [0.5, "#2e7d32"], [1, "#2e7d32"]],
        range_color=[0, 60],
        title="Cobertura mediana de estoque por categoria (dias até ruptura)",
        labels={"Cobertura mediana (dias)": "Dias de cobertura"},
    )
    fig.add_vline(x=_CRITICO_D, line_dash="dash", line_color="red",
                  annotation_text=f"Crítico ({_CRITICO_D}d)", annotation_position="top right")
    fig.add_vline(x=_ATENCAO_D, line_dash="dash", line_color="orange",
                  annotation_text=f"Atenção ({_ATENCAO_D}d)", annotation_position="top right")
    fig.update_layout(coloraxis_showscale=False)
    st.plotly_chart(fig, use_container_width=True)

    st.dataframe(
        resumo[["Categoria", "Produtos", "Em estoque", "Na rua", "% na rua",
                "Cobertura mediana (dias)", "🔴", "🟡", "🔵"]],
        use_container_width=True, hide_index=True,
    )

    st.divider()
    st.subheader("Detalhamento por categoria")

    for cat in sorted(df["Categoria"].unique()):
        df_c = df[df["Categoria"] == cat].copy()
        n_crit = (df_c["Status"] == "🔴 Ruptura iminente").sum()
        n_par  = (df_c["Status"] == "🔵 Parado").sum()
        badge  = (f" — 🔴 {n_crit} ruptura" if n_crit else "") + \
                 (f" — 🔵 {n_par} parado(s)" if n_par else "")

        with st.expander(
            f"**{cat}** — {len(df_c)} produtos{badge}",
            expanded=(n_crit > 0),
        ):
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Em estoque", int(df_c["Em estoque"].sum()))
            m2.metric("Na rua",     int(df_c["Na rua"].sum()))
            m3.metric("🔴 Rupturas", int(n_crit))
            m4.metric("🔵 Parados",  int(n_par))

            cols = ["Produto", "Em estoque", "Na rua",
                    "Vendas (90d)", "Cobertura (dias)", "Giro anual", "Status"]
            st.dataframe(
                df_c[cols].sort_values("Cobertura (dias)", na_position="last")
                .style.map(_cor_status, subset=["Status"]),
                use_container_width=True, hide_index=True,
            )


def _tab_parados(df):
    parados = df[df["Status"] == "🔵 Parado"].sort_values("Em estoque", ascending=False)

    if parados.empty:
        st.success("Todos os produtos com estoque tiveram pelo menos uma venda nos últimos 90 dias.")
        return

    total_unidades = int(parados["Em estoque"].sum())
    st.warning(
        f"**{len(parados)} produtos** têm estoque mas **zero vendas nos últimos 90 dias**. "
        f"Total de **{total_unidades} unidades** imobilizadas sem giro."
    )

    fig = px.bar(
        parados.head(20),
        x="Em estoque", y="Produto", orientation="h",
        color="Categoria",
        title="Top 20 produtos parados (por quantidade em estoque)",
    )
    fig.update_layout(yaxis={"categoryorder": "total ascending"}, margin={"l": 260})
    st.plotly_chart(fig, use_container_width=True)

    # Parados por categoria
    cat_parados = parados.groupby("Categoria").agg(
        Produtos=("Produto", "count"),
        Unidades=("Em estoque", "sum"),
    ).sort_values("Unidades", ascending=False)
    st.dataframe(cat_parados, use_container_width=True)

    st.divider()
    cols = ["Produto", "Categoria", "Em estoque", "Na rua", "Total"]
    st.dataframe(parados[cols], use_container_width=True, hide_index=True)

    csv = parados[cols].to_csv(index=False).encode("utf-8")
    st.download_button("⬇️ Exportar parados (CSV)", csv, "estoque_parado.csv", "text/csv")


def _tab_velocidade(df, itens_vendidos, produtos_map, categorias_map):
    com_vendas = df[df["Vendas/dia"] > 0].copy()

    if com_vendas.empty:
        st.info("Sem dados de vendas para calcular velocidade.")
        return

    # Distribuição de giro
    bins   = [0, 1, 4, 12, float("inf")]
    labels = ["< 1 (muito lento)", "1–4 (lento)", "4–12 (normal)", "> 12 (rápido)"]
    com_vendas["Faixa de giro"] = pd.cut(com_vendas["Giro anual"], bins=bins, labels=labels)

    fig_pizza = px.pie(
        com_vendas.groupby("Faixa de giro", as_index=False).size(),
        names="Faixa de giro", values="size",
        title="Distribuição de giro anual dos produtos",
        color_discrete_sequence=["#c00", "#ffb300", "#66bb6a", "#1565c0"],
    )
    st.plotly_chart(fig_pizza, use_container_width=True)

    col_r, col_l = st.columns(2)
    cols_vel = ["Produto", "Categoria", "Vendas/dia", "Giro anual", "Cobertura (dias)"]

    with col_r:
        st.markdown("**⚡ 20 maiores velocidades de venda**")
        st.dataframe(
            com_vendas.nlargest(20, "Vendas/dia")[cols_vel],
            use_container_width=True, hide_index=True,
        )

    with col_l:
        st.markdown("**🐢 20 menores velocidades (com vendas)**")
        st.dataframe(
            com_vendas.nsmallest(20, "Vendas/dia")[cols_vel],
            use_container_width=True, hide_index=True,
        )

    st.divider()
    st.subheader("Top 10 estilos mais vendidos por categoria — últimos 90 dias")
    top_cat = top_vendidos_por_categoria(itens_vendidos, produtos_map, categorias_map, top_n=10)
    if top_cat:
        tabs = st.tabs(sorted(top_cat.keys())[:12])
        for tab, cat in zip(tabs, sorted(top_cat.keys())[:12]):
            with tab:
                top_df = top_cat[cat][["modelo", "total_vendido"]].copy()
                top_df.columns = ["Estilo", "Unidades vendidas"]
                fig = px.bar(
                    top_df, x="Unidades vendidas", y="Estilo", orientation="h",
                    color_discrete_sequence=["#AB6776"],
                )
                fig.update_layout(yaxis={"categoryorder": "total ascending"}, margin={"l": 220})
                st.plotly_chart(fig, use_container_width=True)


def _tab_busca(df):
    busca  = st.text_input("Nome do produto", placeholder="Ex: Argola Prata, Gota Dourado...")
    col_f1, col_f2 = st.columns(2)
    with col_f1:
        cat_f = st.multiselect("Categoria", sorted(df["Categoria"].unique()))
    with col_f2:
        status_f = st.multiselect("Status", sorted(df["Status"].unique()))

    df_f = df.copy()
    if busca:
        df_f = df_f[df_f["Produto"].str.contains(busca, case=False, na=False)]
    if cat_f:
        df_f = df_f[df_f["Categoria"].isin(cat_f)]
    if status_f:
        df_f = df_f[df_f["Status"].isin(status_f)]

    st.caption(f"{len(df_f)} produto(s) encontrado(s)")

    if df_f.empty:
        return

    cols = ["Produto", "Categoria", "Em estoque", "Na rua",
            "Vendas (90d)", "Cobertura (dias)", "Giro anual", "Status"]
    st.dataframe(
        df_f[cols].style.map(_cor_status, subset=["Status"]),
        use_container_width=True, hide_index=True,
    )

    csv = df_f[cols].to_csv(index=False).encode("utf-8")
    st.download_button("⬇️ Exportar busca (CSV)", csv, "busca_estoque.csv", "text/csv")


# ── Produtos antigos no estoque (15+ meses) ───────────────────────────────

_MESES_PARADO  = 15
_MESES_RECENTE = 6   # referência com entrada mais nova que N meses → excluída dos antigos


def _meses_produto(p: dict) -> int:
    """Meses desde data_criacao do produto até hoje."""
    hoje = date.today()
    dc_str = (p.get("data_criacao") or "")[:10]
    try:
        dc = date.fromisoformat(dc_str)
        return (hoje.year - dc.year) * 12 + (hoje.month - dc.month)
    except (ValueError, TypeError):
        return 0


def _tab_antigos(df: pd.DataFrame, produtos: list):
    """Produtos com total > 0 cadastrados há mais de 15 meses."""
    hoje = date.today()

    def _preco_varejo(p: dict) -> float:
        for tp in (p.get("tipo_preco") or []):
            if "varejo" in (tp.get("nome") or "").lower():
                try: return float(tp.get("preco") or 0)
                except (TypeError, ValueError): pass
        tipos = p.get("tipo_preco") or []
        if tipos:
            try: return float(tipos[0].get("preco") or 0)
            except (TypeError, ValueError): pass
        return 0.0

    # Mapeia id → data_criacao, referencia e preco
    # Também detecta referências com entrada recente (estoque reposto nos últimos _MESES_RECENTE meses)
    dc_map:             dict = {}
    ref_map:            dict = {}
    preco_map:          dict = {}
    referencias_recentes: set = set()
    for p in produtos:
        pid    = p.get("id")
        ref    = p.get("referencia") or ""
        ref_map[pid]   = ref
        preco_map[pid] = _preco_varejo(p)
        dc_str = (p.get("data_criacao") or "")[:10]
        try:
            dc = date.fromisoformat(dc_str)
            dc_map[pid] = dc
            meses_dc = (hoje.year - dc.year) * 12 + (hoje.month - dc.month)
            if ref and meses_dc < _MESES_RECENTE:
                referencias_recentes.add(ref)
        except (ValueError, TypeError):
            pass

    def _meses(d: date) -> int:
        return (hoje.year - d.year) * 12 + (hoje.month - d.month)

    df_an = df[df["Total"] > 0].copy()
    df_an["_dc"]             = df_an["ID"].map(dc_map)
    df_an                    = df_an.dropna(subset=["_dc"])
    df_an["Meses"]           = df_an["_dc"].apply(_meses)
    df_an                    = df_an[df_an["Meses"] >= _MESES_PARADO].copy()
    df_an["Desde"]           = df_an["_dc"].apply(lambda d: d.strftime("%m/%Y"))
    df_an["Referência"]      = df_an["ID"].map(ref_map)
    df_an["Preço (R$)"]      = df_an["ID"].map(preco_map)
    df_an["Valor total (R$)"] = (df_an["Total"] * df_an["Preço (R$)"]).round(2)
    df_an                    = df_an.drop(columns=["_dc"])

    # Exclui referências que tiveram estoque adicionado recentemente
    mask_recente = df_an["Referência"].isin(referencias_recentes) & (df_an["Referência"] != "")
    n_excluidos  = int(mask_recente.sum())
    df_an        = df_an[~mask_recente].copy()

    df_an = df_an.sort_values("Meses", ascending=False)

    if n_excluidos > 0:
        st.info(
            f"ℹ️ **{n_excluidos} produto(s) excluído(s)** da análise: referência com "
            f"entrada de estoque nos últimos {_MESES_RECENTE} meses. "
            "Referências com reposição recente não são contabilizadas como paradas."
        )

    if df_an.empty:
        st.success(
            f"Nenhum produto com estoque cadastrado há mais de {_MESES_PARADO} meses."
        )
        return

    total_unid = int(df_an["Total"].sum())
    total_prod = len(df_an)

    valor_total = df_an["Valor total (R$)"].sum()
    valor_fmt   = f"R$ {valor_total:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

    st.warning(
        f"**{total_prod} produtos** no portfólio há mais de **{_MESES_PARADO} meses** "
        f"ainda com estoque (interno + na rua). "
        f"Total de **{total_unid} unidades** · **{valor_fmt}** imobilizados."
    )

    # ── Lista para impressão ──────────────────────────────────────────────
    def _html_impressao(df: pd.DataFrame) -> str:
        hoje_str = date.today().strftime("%d/%m/%Y")
        linhas_cat = []
        for cat in sorted(df["Categoria"].unique()):
            df_c = df[df["Categoria"] == cat].sort_values("Meses", ascending=False)
            linhas = ""
            for _, r in df_c.iterrows():
                val_fmt = f"R$ {r['Valor total (R$)']:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
                linhas += (
                    f"<tr>"
                    f"<td class='ref'>{r['Referência'] or '—'}</td>"
                    f"<td>{r['Produto']}</td>"
                    f"<td class='num'>{int(r['Em estoque'])}</td>"
                    f"<td class='num'>{int(r['Na rua'])}</td>"
                    f"<td class='num'><b>{int(r['Total'])}</b></td>"
                    f"<td class='num'>{r['Desde']}</td>"
                    f"<td class='num'>{int(r['Meses'])}m</td>"
                    f"<td class='num'>{val_fmt}</td>"
                    f"<td class='cb'><input type='checkbox'></td>"
                    f"</tr>"
                )
            n_c   = len(df_c)
            tot_c = int(df_c["Total"].sum())
            linhas_cat.append(
                f"<tr class='cat-header'><td colspan='9'>{cat} — {n_c} produto(s) · {tot_c} peças</td></tr>"
                + linhas
            )

        corpo = "\n".join(linhas_cat)
        return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<title>Estoque parado — {hoje_str}</title>
<style>
  body {{ font-family: Arial, sans-serif; font-size: 11px; margin: 20px; color: #111; }}
  h1   {{ font-size: 15px; margin-bottom: 4px; }}
  p.sub{{ font-size: 11px; color: #555; margin-top: 0; margin-bottom: 12px; }}
  table{{ border-collapse: collapse; width: 100%; }}
  th   {{ background: #3a3a3a; color: #fff; padding: 5px 7px; text-align: left; font-size: 10px; }}
  td   {{ padding: 4px 7px; border-bottom: 1px solid #ddd; vertical-align: middle; }}
  tr:nth-child(even) td {{ background: #f7f7f7; }}
  tr.cat-header td {{
    background: #AB6774; color: #fff; font-weight: bold;
    padding: 5px 7px; font-size: 11px; border-bottom: none;
  }}
  .ref {{ font-weight: bold; white-space: nowrap; }}
  .num {{ text-align: right; white-space: nowrap; }}
  .cb  {{ text-align: center; width: 28px; }}
  input[type=checkbox] {{ width: 14px; height: 14px; }}
  @media print {{
    body {{ margin: 10px; }}
    input[type=checkbox] {{ -webkit-print-color-adjust: exact; print-color-adjust: exact; }}
  }}
</style>
</head>
<body>
<h1>Estoque parado há +{_MESES_PARADO} meses — {hoje_str}</h1>
<p class="sub">{total_prod} produto(s) · {total_unid} peças · {valor_fmt} imobilizados</p>
<table>
  <thead>
    <tr>
      <th>Referência</th><th>Produto</th>
      <th>Estoque</th><th>Na rua</th><th>Total</th>
      <th>Desde</th><th>Tempo</th><th>Valor total</th><th>✓</th>
    </tr>
  </thead>
  <tbody>
{corpo}
  </tbody>
</table>
</body>
</html>"""

    html_bytes = _html_impressao(df_an).encode("utf-8")
    st.download_button(
        label="🖨️ Gerar lista para impressão",
        data=html_bytes,
        file_name=f"estoque_parado_{date.today().strftime('%Y%m%d')}.html",
        mime="text/html",
        help="Baixe o arquivo, abra no navegador e use Ctrl+P para imprimir.",
    )

    # ── Resumo por categoria ──────────────────────────────────────────────
    resumo = (
        df_an.groupby("Categoria", as_index=False)
        .agg(
            Produtos    = ("Produto",          "count"),
            Em_estoque  = ("Em estoque",       "sum"),
            Na_rua      = ("Na rua",           "sum"),
            Total       = ("Total",            "sum"),
            Valor_total = ("Valor total (R$)", "sum"),
            Mais_antigo = ("Meses",            "max"),
        )
        .sort_values("Valor_total", ascending=False)
    )
    resumo.rename(columns={
        "Em_estoque":  "Em estoque",
        "Na_rua":      "Na rua",
        "Valor_total": "Valor total (R$)",
        "Mais_antigo": "Mais antigo (meses)",
    }, inplace=True)
    resumo["Valor total (R$)"] = resumo["Valor total (R$)"].round(2)

    fig = px.bar(
        resumo.sort_values("Total"),
        x="Total", y="Categoria", orientation="h",
        color="Mais antigo (meses)",
        color_continuous_scale=[[0, "#fbbf24"], [0.5, "#f97316"], [1, "#dc2626"]],
        title=f"Unidades imobilizadas há +{_MESES_PARADO} meses — por categoria",
        labels={"Total": "Unidades (estoque + na rua)", "Mais antigo (meses)": "Mais antigo (meses)"},
        text="Total",
    )
    fig.update_traces(textposition="outside")
    fig.update_layout(coloraxis_colorbar_title="Meses", margin={"l": 160})
    st.plotly_chart(fig, use_container_width=True)

    st.dataframe(
        resumo[["Categoria", "Produtos", "Em estoque", "Na rua", "Total",
                "Valor total (R$)", "Mais antigo (meses)"]],
        use_container_width=True, hide_index=True,
        column_config={
            "Valor total (R$)": st.column_config.NumberColumn("Valor total (R$)", format="R$ %.2f"),
        },
    )

    st.divider()
    st.markdown("#### Detalhamento por categoria")

    valor_fmt_det = f"R$ {valor_total:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    mc1, mc2, mc3 = st.columns(3)
    mc1.metric("Produtos",       total_prod)
    mc2.metric("Total de peças", total_unid)
    mc3.metric("Valor imobilizado", valor_fmt_det)

    cols_det = ["Referência", "Produto", "Em estoque", "Na rua", "Total",
                "Preço (R$)", "Valor total (R$)", "Desde", "Meses"]

    def _cor_meses(val):
        try:
            v = int(val)
            if v >= 30:  return "background-color:#ffd6d6;color:#9b1c1c"
            if v >= 20:  return "background-color:#fed7aa;color:#7c2d12"
            return "background-color:#fef9c3;color:#713f12"
        except (TypeError, ValueError):
            return ""

    for cat in resumo["Categoria"].tolist():
        df_c = df_an[df_an["Categoria"] == cat].copy()
        mais_antigo = int(df_c["Meses"].max())
        with st.expander(
            f"**{cat}** — {len(df_c)} produto(s) · {int(df_c['Total'].sum())} un. "
            f"· mais antigo: {mais_antigo} meses",
            expanded=False,
        ):
            st.dataframe(
                df_c[cols_det]
                .sort_values("Meses", ascending=False)
                .rename(columns={"Meses": "Meses no estoque"}),
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Preço (R$)":      st.column_config.NumberColumn("Preço (R$)",      format="R$ %.2f"),
                    "Valor total (R$)": st.column_config.NumberColumn("Valor total (R$)", format="R$ %.2f"),
                    "Meses no estoque": st.column_config.NumberColumn("Meses no estoque"),
                },
            )

    csv = df_an[cols_det].rename(columns={"Meses": "Meses no estoque"}).to_csv(
        index=False
    ).encode("utf-8")
    st.download_button(
        "⬇️ Exportar lista completa (CSV)",
        csv,
        f"estoque_antigos_{_MESES_PARADO}meses.csv",
        "text/csv",
    )


# ── Visão básica (sem velocidade carregada) ────────────────────────────────

def _visao_basica(df_base):
    n_crit = (df_base["Situação"] == "🔴 Crítico").sum()
    n_zer  = (df_base["Situação"] == "⚫ Zerado").sum()
    if n_crit: st.error(f"🔴 {n_crit} produto(s) abaixo do estoque mínimo cadastrado.")
    if n_zer:  st.warning(f"⚫ {n_zer} produto(s) com estoque zerado.")

    resumo = df_base.groupby("Categoria", as_index=False).agg(
        Em_estoque=("Em estoque", "sum"), Na_rua=("Na rua", "sum"),
    ).sort_values("Em_estoque", ascending=False)

    fig = px.bar(
        resumo, x="Categoria", y=["Em_estoque", "Na_rua"],
        barmode="stack",
        color_discrete_map={"Em_estoque": "#AB6776", "Na_rua": "#D4A0AA"},
        labels={"value": "Quantidade", "variable": ""},
        title="Estoque em depósito vs. com revendedoras",
    )
    fig.for_each_trace(lambda t: t.update(
        name={"Em_estoque": "Em estoque", "Na_rua": "Na rua"}.get(t.name, t.name)
    ))
    st.plotly_chart(fig, use_container_width=True)

    busca = st.text_input("Buscar produto", placeholder="Nome do produto...")
    df_f = df_base if not busca else df_base[
        df_base["Produto"].str.contains(busca, case=False, na=False)
    ]

    for cat in sorted(df_f["Categoria"].unique()):
        df_c = df_f[df_f["Categoria"] == cat].copy()
        n_c = (df_c["Situação"] == "🔴 Crítico").sum()
        n_z = (df_c["Situação"] == "⚫ Zerado").sum()
        badge = (f" 🔴 {n_c}" if n_c else "") + (f" ⚫ {n_z}" if n_z else "")
        with st.expander(f"**{cat}** ({len(df_c)} produtos){badge}", expanded=(n_c > 0)):
            m1, m2, m3 = st.columns(3)
            m1.metric("Em estoque", int(df_c["Em estoque"].sum()))
            m2.metric("Na rua", int(df_c["Na rua"].sum()))
            m3.metric("Total", int(df_c["Total"].sum()))
            cols = ["Produto", "Em estoque", "Na rua", "Total", "Mínimo", "Situação"]

            def _cor(val):
                if "Crítico" in str(val): return "background-color:#ffd6d6;color:#c00"
                if "Zerado"  in str(val): return "background-color:#eeeeee"
                if "Só na rua" in str(val): return "background-color:#fff9c4"
                return ""

            st.dataframe(
                df_c[cols].style.map(_cor, subset=["Situação"]),
                use_container_width=True, hide_index=True,
            )


# ── Ponto de entrada ───────────────────────────────────────────────────────

def render():
    st.header("Estoque")

    # Carrega dados básicos (rápido — usa cache)
    with st.spinner("Carregando estoque..."):
        try:
            produtos      = get_produtos(status="1")
            categorias_map = get_categorias()
            na_rua_map    = get_itens_pedidos_abertos()
        except Exception as e:
            st.error(f"Erro ao carregar dados: {e}")
            return

    if not produtos:
        st.warning("Nenhum produto ativo encontrado.")
        return

    df_base = montar_df_estoque(produtos, na_rua_map, categorias_map)

    # ── Métricas globais ──────────────────────────────────────────────────
    total_unid = int(df_base["Total"].sum())
    pct_rua    = int(df_base["Na rua"].sum() / max(total_unid, 1) * 100)

    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Produtos ativos",  len(df_base))
    m2.metric("Em depósito",      int(df_base["Em estoque"].sum()))
    m3.metric("Na rua",           int(df_base["Na rua"].sum()))
    m4.metric("Total geral",      total_unid)
    m5.metric("% na rua",         f"{pct_rua}%",
              help="Percentual do estoque total que está com revendedoras")

    st.divider()

    # ── Carregamento da análise de velocidade ─────────────────────────────
    tem_vel = "estoque_enriched" in st.session_state

    col_b1, col_b2, col_b3 = st.columns([2, 1, 2])
    with col_b1:
        if not tem_vel:
            if st.button("📊 Carregar análise completa de vendas", type="primary",
                         help="Busca histórico de 90 dias para calcular cobertura, giro e produtos parados"):
                with st.spinner("Buscando histórico de vendas (aguarde)..."):
                    try:
                        itens = get_itens_pedidos_baixados(dias=_DIAS_HIST)
                        st.session_state["estoque_enriched"] = _enriquecer(df_base, itens)
                        st.session_state["estoque_itens"]    = itens
                        st.rerun()
                    except Exception as e:
                        st.error(f"Erro: {e}")
        else:
            if st.button("🔄 Atualizar análise"):
                del st.session_state["estoque_enriched"]
                del st.session_state["estoque_itens"]
                st.rerun()

    if not tem_vel:
        st.info(
            "Clique em **Carregar análise completa** para ver: "
            "cobertura em dias, produtos parados, giro de estoque e alertas de ruptura."
        )
        _visao_basica(df_base)
        st.divider()
        st.subheader(f"⏳ Produtos no estoque há mais de {_MESES_PARADO} meses")
        _tab_antigos(df_base, produtos)
        return

    df = st.session_state["estoque_enriched"]

    # ── Painel de alertas ─────────────────────────────────────────────────
    st.subheader("Situação atual do estoque")
    n_rupt, n_aten, n_par, n_rua, n_zer = _painel_alertas(df)

    if n_rupt > 0:
        st.error(
            f"⚠️ {n_rupt} produto(s) com **ruptura iminente** (menos de {_CRITICO_D} dias de estoque). "
            "Acesse a aba **⚠️ Alertas** para ver a lista."
        )

    # ── Abas principais ───────────────────────────────────────────────────
    st.divider()
    n_antigos = len([
        p for p in produtos
        if _meses_produto(p) >= _MESES_PARADO and (
            float(p.get("quantidade") or 0) + na_rua_map.get(p.get("id"), 0) > 0
        )
    ])

    tab_al, tab_cat, tab_par, tab_ant, tab_vel, tab_bus = st.tabs([
        f"⚠️ Alertas  ({n_rupt + n_aten})",
        "📦 Por categoria",
        f"🐌 Parados  ({n_par})",
        f"⏳ Antigos  ({n_antigos})",
        "⚡ Velocidade de venda",
        "🔍 Busca",
    ])

    with tab_al:
        _tab_alertas(df)

    with tab_cat:
        _tab_categorias(df)

    with tab_par:
        _tab_parados(df)

    with tab_ant:
        _tab_antigos(df, produtos)

    with tab_vel:
        produtos_map = {p["id"]: p for p in produtos}
        _tab_velocidade(df, st.session_state["estoque_itens"], produtos_map, categorias_map)

    with tab_bus:
        _tab_busca(df)
