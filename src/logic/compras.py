import pandas as pd
from src.logic.estoque import nome_categoria

# ── Palavras removidas do estilo (tamanhos, materiais, preposições) ──────────
# Cores NÃO são removidas — fazem parte do estilo de compra
_IGNORAR = {
    "pequeno", "pequena", "pequenos", "pequenas",
    "grande", "grandes",
    "médio", "média", "médios", "médias",
    "micro", "mini", "maxi", "longo", "longa", "curto", "curta",
    "fino", "fina", "grosso", "grossa", "finos", "finas",
    "aço", "inox", "folheado", "folheada", "banho", "ródio",
    "cristal", "strass", "zircônia", "zirconia", "zircão",
    "piercing", "par",
    "com", "de", "da", "do", "e", "em", "na", "no", "para",
    "a", "o", "ou", "por", "dos", "das",
}

_CORES = {
    "prata": "Prata", "prateado": "Prata", "prateada": "Prata", "silver": "Prata",
    "dourado": "Dourado", "dourada": "Dourado", "gold": "Dourado", "ouro": "Dourado",
    "rosê": "Rosê", "rose": "Rosê", "rosado": "Rosê", "rosada": "Rosê",
    "preto": "Preto", "preta": "Preto",
    "branco": "Branco", "branca": "Branco",
    "colorido": "Colorido", "colorida": "Colorido",
}

# Quantidade máxima de unidades por item de pedido (evita valores absurdos da API)
_MAX_QTD_POR_ITEM = 200


def extrair_modelo(descricao: str) -> str:
    """
    Extrai estilo + cor da descrição. Remove tamanho/material, mantém cor.
    'Brinco Argola Pequena Prata' → 'Brinco Argola Prata'
    'Brinco Argola Grande Dourada' → 'Brinco Argola Dourado'
    """
    words = (descricao or "").strip().split()
    cor = None
    estilo = []
    for w in words:
        wl = w.lower()
        if wl in _CORES:
            if cor is None:
                cor = _CORES[wl]
            continue
        if wl in _IGNORAR:
            continue
        if w.replace(".", "").replace(",", "").replace("/", "").isdigit():
            continue
        if len(w) <= 1:
            continue
        estilo.append(w)
    base = " ".join(estilo[:3])
    return f"{base} {cor}" if cor else (base or (words[0] if words else "Outros"))


def classificar_abc(df: pd.DataFrame) -> pd.DataFrame:
    """
    Classifica estilos em A / B / C por volume de vendas dentro de cada categoria.
    A = top 80% do volume acumulado  |  B = 80–95%  |  C = acima de 95%
    """
    resultado = []
    for _, grupo in df.groupby("Categoria"):
        grupo = grupo.sort_values("Vendas (período)", ascending=False).copy()
        total = grupo["Vendas (período)"].sum()
        if total == 0:
            grupo["Curva"] = "C"
        else:
            grupo["_cum"] = grupo["Vendas (período)"].cumsum() / total
            grupo["Curva"] = grupo["_cum"].apply(
                lambda x: "A" if x <= 0.80 else ("B" if x <= 0.95 else "C")
            )
            grupo = grupo.drop(columns="_cum")
        resultado.append(grupo)
    return pd.concat(resultado).reset_index(drop=True) if resultado else df


def contar_novas_revendedoras(pedidos_abertos: list, pedidos_baixados: list) -> int:
    """
    Conta revendedoras com pedido aberto mas sem nenhum pedido baixado anterior.
    Essas são as revendedoras novas (primeiro pedido ainda em aberto).
    """
    ids_com_historico = {
        p.get("fk_revendedor_id")
        for p in pedidos_baixados
        if p.get("fk_revendedor_id")
    }
    novas = {
        p.get("fk_revendedor_id")
        for p in pedidos_abertos
        if p.get("fk_revendedor_id") and p.get("fk_revendedor_id") not in ids_com_historico
    }
    return len(novas)


def sugerir_compras_por_modelo(
    produtos: list,
    itens_vendidos: list,
    na_rua_map: dict,
    categorias_map: dict,
    novas_revendedoras: int = 0,
    pecas_por_nova: int = 40,
    dias_cobertura: int = 60,
    dias_historico: int = 90,
    lead_time: int = 14,
) -> pd.DataFrame:
    """
    Sugestões de compra por estilo (categoria + modelo + cor).

    Fórmula de mínimo: média_diária × lead_time × 1,5 (buffer de 50%).
    Cobertura ajustada pela curva ABC: A=100%, B=75%, C=50% dos dias de cobertura.
    Novas revendedoras: distribuídas pelas categorias proporcionalmente às vendas,
    concentradas nos itens A e B.
    """
    produtos_map = {p["id"]: p for p in produtos}

    # Vendas por produto por dia (com cap por item para evitar valores absurdos)
    venda_pid: dict = {}
    for item in itens_vendidos:
        pid = item.get("produto_id")
        data = item.get("data")
        ds = data.strftime("%Y-%m-%d") if data else "sem-data"
        qtd = min(float(item.get("quantidade") or 0), _MAX_QTD_POR_ITEM)
        venda_pid.setdefault(pid, {})
        venda_pid[pid][ds] = venda_pid[pid].get(ds, 0) + qtd

    # Agrupa produtos por (categoria, modelo)
    modelo_pids: dict = {}
    for p in produtos:
        pid = p.get("id")
        desc = p.get("descricao", "")
        cat_id = p.get("fk_categoria_id")
        cat = nome_categoria(cat_id, categorias_map, desc)
        modelo = extrair_modelo(desc)
        modelo_pids.setdefault((cat, modelo), []).append(pid)

    rows = []
    for (categoria, modelo), pids in modelo_pids.items():
        em_estoque = sum(
            min(float(produtos_map.get(pid, {}).get("quantidade") or 0), 99_999)
            for pid in pids
        )
        na_rua = sum(na_rua_map.get(pid, 0) for pid in pids)

        vendas_dia: dict = {}
        for pid in pids:
            for ds, qty in venda_pid.get(pid, {}).items():
                vendas_dia[ds] = vendas_dia.get(ds, 0) + qty

        total_vendido = sum(vendas_dia.values())
        media_diaria = total_vendido / max(dias_historico, 1)

        # Ignora estilos sem vendas e sem estoque
        if media_diaria == 0 and em_estoque == 0 and na_rua == 0:
            continue

        rows.append({
            "Categoria": categoria,
            "Estilo": modelo,
            "Variantes": len(pids),
            "Vendas (período)": int(round(total_vendido)),
            "Vendas/dia": round(media_diaria, 3),
            "Em estoque": int(em_estoque),
            "Na rua": int(na_rua),
            "_media_diaria": media_diaria,
        })

    df = pd.DataFrame(rows)
    if df.empty:
        return df

    # Curva ABC dentro de cada categoria
    df = classificar_abc(df)

    # Cobertura ajustada pela curva
    cobertura_map = {"A": dias_cobertura, "B": int(dias_cobertura * 0.75), "C": int(dias_cobertura * 0.5)}
    df["Mínimo recomendado"] = (df["_media_diaria"] * lead_time * 1.5).apply(lambda x: int(round(x)))

    def _a_comprar(row):
        dias = cobertura_map.get(row["Curva"], dias_cobertura)
        disponivel = row["Em estoque"] + row["Na rua"]
        valor = row["_media_diaria"] * dias - disponivel + row["Mínimo recomendado"]
        valor = max(0, valor)
        # Cap: nunca sugerir mais de 12 meses de demanda ou 1.000 unidades
        cap = max(int(row["_media_diaria"] * 365), 1_000) if row["_media_diaria"] > 0 else 1_000
        return int(min(valor, cap))

    df["A comprar"] = df.apply(_a_comprar, axis=1)

    # Demanda extra de novas revendedoras — distribuída por categoria, proporc. às vendas
    df["Novas Rev."] = 0
    if novas_revendedoras > 0:
        total_extra = novas_revendedoras * pecas_por_nova
        vendas_por_cat = df.groupby("Categoria")["Vendas (período)"].sum()
        total_vendas_geral = vendas_por_cat.sum()

        for cat, cat_df_idx in df.groupby("Categoria").groups.items():
            cat_extra = (
                round(vendas_por_cat.get(cat, 0) / total_vendas_geral * total_extra)
                if total_vendas_geral > 0
                else round(total_extra / len(vendas_por_cat))
            )
            # Distribui entre estilos A e B proporcional às vendas
            mask_ab = df.index.isin(cat_df_idx) & df["Curva"].isin(["A", "B"])
            total_vendas_ab = df.loc[mask_ab, "Vendas (período)"].sum()
            if total_vendas_ab > 0:
                df.loc[mask_ab, "Novas Rev."] = (
                    df.loc[mask_ab, "Vendas (período)"] / total_vendas_ab * cat_extra
                ).round().astype(int)
            elif mask_ab.any():
                n = mask_ab.sum()
                df.loc[mask_ab, "Novas Rev."] = round(cat_extra / n)

    df["A comprar total"] = df["A comprar"] + df["Novas Rev."]

    # Status
    def _status(r):
        disponivel = r["Em estoque"] + r["Na rua"]
        if disponivel < r["Mínimo recomendado"] and r["A comprar total"] > 0:
            return "🔴 Crítico"
        if r["Curva"] == "A" and r["A comprar total"] > 0:
            return "🟡 Comprar A"
        if r["A comprar total"] > 0:
            return "🟢 Planejar"
        return "✅ OK"

    df["Status"] = df.apply(_status, axis=1)

    ordem = {"🔴 Crítico": 0, "🟡 Comprar A": 1, "🟢 Planejar": 2, "✅ OK": 3}
    df["_ord"] = df["Status"].map(ordem).fillna(4)
    df = (
        df.sort_values(["Categoria", "_ord", "Vendas (período)"], ascending=[True, True, False])
        .drop(columns=["_ord", "_media_diaria"])
        .reset_index(drop=True)
    )
    return df


def resumo_por_categoria(df: pd.DataFrame) -> pd.DataFrame:
    """Agrega por categoria: totais de estoque, mínimo, a comprar e curva ABC."""
    if df.empty:
        return pd.DataFrame()

    agg = df.groupby("Categoria", as_index=False).agg(
        Estilos=("Estilo", "count"),
        Itens_A=("Curva", lambda x: (x == "A").sum()),
        Itens_B=("Curva", lambda x: (x == "B").sum()),
        Itens_C=("Curva", lambda x: (x == "C").sum()),
        Vendas_periodo=("Vendas (período)", "sum"),
        Em_estoque=("Em estoque", "sum"),
        Na_rua=("Na rua", "sum"),
        Minimo=("Mínimo recomendado", "sum"),
        A_comprar=("A comprar", "sum"),
        Novas_rev=("Novas Rev.", "sum"),
        A_comprar_total=("A comprar total", "sum"),
    )
    agg["Total disponível"] = agg["Em_estoque"] + agg["Na_rua"]
    agg = agg.rename(columns={
        "Em_estoque": "Em estoque",
        "Na_rua": "Na rua",
        "Minimo": "Mínimo (total)",
        "Vendas_periodo": "Vendas (período)",
        "A_comprar": "A comprar (estoque)",
        "Novas_rev": "Novas revendedoras",
        "A_comprar_total": "A comprar total",
        "Itens_A": "Curva A",
        "Itens_B": "Curva B",
        "Itens_C": "Curva C",
    })

    def _status(row):
        if row["Em estoque"] < row["Mínimo (total)"] and row["A comprar total"] > 0:
            return "🔴 Crítico"
        if row["A comprar total"] > 0:
            return "🟡 Comprar"
        return "✅ OK"

    agg["Status"] = agg.apply(_status, axis=1)
    return agg.sort_values("A comprar total", ascending=False).reset_index(drop=True)


def top_vendidos_por_categoria(itens: list, produtos_map: dict,
                                categorias_map: dict, top_n: int = 10) -> dict:
    """Retorna {categoria: DataFrame top N estilos mais vendidos}."""
    if not itens:
        return {}
    rows = []
    for item in itens:
        pid = item.get("produto_id")
        info = produtos_map.get(pid, {})
        desc = info.get("descricao", f"Produto {pid}")
        cat_id = info.get("fk_categoria_id")
        cat = nome_categoria(cat_id, categorias_map, desc)
        modelo = extrair_modelo(desc)
        qtd = min(float(item.get("quantidade") or 0), _MAX_QTD_POR_ITEM)
        rows.append({"modelo": modelo, "categoria": cat, "quantidade": qtd})

    df = pd.DataFrame(rows)
    resultado = {}
    for cat, grupo in df.groupby("categoria"):
        ranking = (
            grupo.groupby("modelo", as_index=False)
            .agg(total_vendido=("quantidade", "sum"))
            .sort_values("total_vendido", ascending=False)
            .head(top_n)
        )
        resultado[cat] = ranking
    return resultado
