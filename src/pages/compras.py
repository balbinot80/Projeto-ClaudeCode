import streamlit as st
import plotly.express as px
from datetime import datetime
from src.api.jueri_client import (
    get_produtos, get_categorias, get_itens_pedidos_abertos, get_itens_pedidos_baixados
)
from src.logic.compras import (
    sugerir_compras_por_modelo, resumo_por_categoria, top_vendidos_por_categoria
)

_MAX_BAIXADOS = 120  # pedidos baixados mais recentes usados no cálculo de velocidade


def _calcular_e_salvar(dias_cobertura, dias_historico, lead_time, chave):
    """Executa o cálculo pesado e salva resultados no session_state."""
    placeholder = st.empty()

    with placeholder.container():
        st.info("Passo 1/4 — Carregando produtos e categorias...")
    produtos = get_produtos(status="1")
    categorias_map = get_categorias()

    with placeholder.container():
        st.info("Passo 2/4 — Buscando pedidos abertos (itens na rua)...")
    na_rua_map = get_itens_pedidos_abertos()

    with placeholder.container():
        st.info(
            f"Passo 3/4 — Buscando histórico de vendas ({dias_historico} dias, "
            f"máx. {_MAX_BAIXADOS} pedidos)..."
        )
    itens_vendidos = get_itens_pedidos_baixados(dias=dias_historico, max_pedidos=_MAX_BAIXADOS)

    with placeholder.container():
        st.info("Passo 4/4 — Calculando sugestões de compra...")
    df = sugerir_compras_por_modelo(
        produtos, itens_vendidos, na_rua_map, categorias_map,
        dias_cobertura=dias_cobertura, dias_historico=dias_historico, lead_time=lead_time,
    )

    st.session_state["compras_df"] = df
    st.session_state["compras_itens"] = itens_vendidos
    st.session_state["compras_produtos"] = produtos
    st.session_state["compras_categorias"] = categorias_map
    st.session_state["compras_chave"] = chave
    placeholder.empty()


def render():
    st.header("Programação de Compras")

    # ── Parâmetros ────────────────────────────────────────────────────────
    col1, col2, col3 = st.columns(3)
    with col1:
        dias_cobertura = st.slider("Dias de cobertura desejados", 30, 180, 60)
    with col2:
        dias_historico = st.slider("Histórico de vendas (dias)", 30, 365, 90)
    with col3:
        lead_time = st.slider("Prazo de entrega (dias)", 7, 30, 14)

    st.caption(
        f"Safety Stock = 1,65 × σ × √({lead_time} dias) → 95% de nível de serviço. "
        f"Usa os {_MAX_BAIXADOS} pedidos baixados mais recentes no período selecionado."
    )

    chave = f"compras_{dias_cobertura}_{dias_historico}_{lead_time}"
    ja_calculado = st.session_state.get("compras_chave") == chave

    col_btn1, col_btn2 = st.columns([2, 1])
    with col_btn1:
        calcular = st.button("🔄 Calcular sugestões de compra", type="primary")
    with col_btn2:
        if ja_calculado:
            st.success("Dados calculados ✓")

    if calcular:
        try:
            _calcular_e_salvar(dias_cobertura, dias_historico, lead_time, chave)
            st.rerun()
        except Exception as e:
            st.error(f"Erro ao calcular: {e}")
            return

    if not ja_calculado:
        st.info(
            "Configure os parâmetros acima e clique em **Calcular sugestões de compra**. "
            "Na primeira execução pode demorar alguns minutos."
        )
        return

    df = st.session_state.get("compras_df")
    if df is None or df.empty:
        st.warning("Nenhum dado de compra identificado. Verifique o histórico de vendas.")
        return

    # ── Resumo global ─────────────────────────────────────────────────────
    df_cat = resumo_por_categoria(df)

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total em estoque", int(df_cat["Em estoque"].sum()))
    col2.metric("Total na rua", int(df_cat["Na rua"].sum()))
    col3.metric("Mínimo recomendado", int(df_cat["Mínimo (total)"].sum()))
    col4.metric("Total a comprar", int(df_cat["A comprar"].sum()),
                delta=f"{len(df[df['A comprar'] > 0])} estilos", delta_color="off")

    # ── Resumo por categoria ───────────────────────────────────────────────
    st.divider()
    st.subheader("Resumo por categoria")

    def _cor_status(val):
        if "Crítico" in str(val):
            return "background-color: #ffd6d6; color: #c00"
        if "Comprar" in str(val):
            return "background-color: #fff3cd"
        return ""

    st.dataframe(
        df_cat[["Categoria", "Estilos", "Vendas (período)", "Em estoque",
                "Na rua", "Total disponível", "Mínimo (total)", "A comprar", "Status"]]
        .style.map(_cor_status, subset=["Status"]),
        use_container_width=True, hide_index=True,
    )

    fig_cat = px.bar(
        df_cat.sort_values("A comprar", ascending=False),
        x="Categoria",
        y=["Em estoque", "Na rua", "A comprar"],
        barmode="group",
        color_discrete_sequence=["#AB6776", "#D4A0AA", "#6B2737"],
        title="Estoque atual vs. quantidade a comprar por categoria",
        labels={"value": "Unidades", "variable": ""},
    )
    st.plotly_chart(fig_cat, use_container_width=True)

    # ── Detalhamento por estilo ────────────────────────────────────────────
    st.divider()
    st.subheader("Detalhamento por estilo e cor")

    col_f1, col_f2, col_f3 = st.columns(3)
    with col_f1:
        cat_sel = st.multiselect("Categoria", sorted(df["Categoria"].unique()))
    with col_f2:
        apenas_comprar = st.checkbox("Só estilos que precisam de compra", value=True)
    with col_f3:
        busca = st.text_input("Buscar estilo", placeholder="Ex: Argola Prata...")

    df_exibir = df.copy()
    if cat_sel:
        df_exibir = df_exibir[df_exibir["Categoria"].isin(cat_sel)]
    if apenas_comprar:
        df_exibir = df_exibir[df_exibir["A comprar"] > 0]
    if busca:
        df_exibir = df_exibir[df_exibir["Estilo"].str.contains(busca, case=False, na=False)]

    st.caption(f"{len(df_exibir)} estilos exibidos")

    for cat in sorted(df_exibir["Categoria"].unique()):
        df_c = df_exibir[df_exibir["Categoria"] == cat].drop(columns="Categoria").copy()
        criticos = (df_c["Status"] == "🔴 Crítico").sum()
        total_comprar = int(df_c["A comprar"].sum())
        badge = f" — {criticos} crítico(s) 🔴" if criticos else ""

        with st.expander(
            f"**{cat}** — {len(df_c)} estilos · comprar **{total_comprar} unidades**{badge}",
            expanded=(criticos > 0),
        ):
            rc1, rc2, rc3, rc4 = st.columns(4)
            rc1.metric("Em estoque", int(df_c["Em estoque"].sum()))
            rc2.metric("Na rua", int(df_c["Na rua"].sum()))
            rc3.metric("Mínimo recomendado", int(df_c["Mínimo recomendado"].sum()))
            rc4.metric("A comprar", total_comprar)

            def _cor(val):
                if "Crítico" in str(val):
                    return "background-color: #ffd6d6; color: #c00"
                if "Atenção" in str(val):
                    return "background-color: #fff3cd"
                return ""

            cores_presentes = []
            for cor_label in ["Prata", "Dourado", "Rosê", "Preto", "Branco", "Colorido"]:
                df_cor = df_c[df_c["Estilo"].str.contains(cor_label, case=False, na=False)]
                if not df_cor.empty:
                    cores_presentes.append((cor_label, df_cor))

            df_sem_cor = df_c[~df_c["Estilo"].str.contains(
                "Prata|Dourado|Rosê|Preto|Branco|Colorido", case=False, na=False
            )]
            if not df_sem_cor.empty:
                cores_presentes.append(("Outros", df_sem_cor))

            if len(cores_presentes) > 1:
                for cor_label, df_cor in cores_presentes:
                    st.write(f"**{cor_label}** — {int(df_cor['A comprar'].sum())} unidades a comprar")
                    st.dataframe(
                        df_cor.style.map(_cor, subset=["Status"]),
                        use_container_width=True, hide_index=True,
                    )
            else:
                st.dataframe(
                    df_c.style.map(_cor, subset=["Status"]),
                    use_container_width=True, hide_index=True,
                )

    if not df_exibir.empty:
        csv = df_exibir.to_csv(index=False).encode("utf-8")
        st.download_button(
            "Exportar lista de compras (CSV)",
            csv,
            f"compras_{datetime.now().strftime('%Y%m%d')}.csv",
            "text/csv",
        )

    # ── Top estilos mais vendidos ──────────────────────────────────────────
    itens_vendidos = st.session_state.get("compras_itens", [])
    if itens_vendidos:
        st.divider()
        st.subheader(f"Estilos mais vendidos — últimos {dias_historico} dias")
        produtos_list = st.session_state.get("compras_produtos", [])
        categorias_map = st.session_state.get("compras_categorias", {})
        produtos_map = {p["id"]: p for p in produtos_list}
        top_por_cat = top_vendidos_por_categoria(itens_vendidos, produtos_map, categorias_map, top_n=10)
        if top_por_cat:
            tabs = st.tabs(sorted(top_por_cat.keys())[:12])
            for tab, cat in zip(tabs, sorted(top_por_cat.keys())[:12]):
                with tab:
                    top_df = top_por_cat[cat][["modelo", "total_vendido"]].copy()
                    top_df.columns = ["Estilo", "Unidades vendidas"]
                    fig = px.bar(
                        top_df, x="Unidades vendidas", y="Estilo", orientation="h",
                        color_discrete_sequence=["#AB6776"],
                    )
                    fig.update_layout(yaxis={"categoryorder": "total ascending"}, margin={"l": 220})
                    st.plotly_chart(fig, use_container_width=True)
