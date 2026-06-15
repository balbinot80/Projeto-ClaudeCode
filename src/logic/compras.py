import math
import pandas as pd
from src.logic.estoque import nome_categoria

# Palavras removidas do estilo: tamanhos, materiais, preposições
# Cores NÃO são removidas — fazem parte do estilo de compra
_IGNORAR = {
    # tamanhos
    "pequeno", "pequena", "pequenos", "pequenas",
    "grande", "grandes",
    "médio", "média", "médios", "médias",
    "micro", "mini", "maxi", "longo", "longa", "curto", "curta",
    "fino", "fina", "grosso", "grossa", "finos", "finas",
    # materiais/acabamento (não são cor)
    "aço", "inox", "folheado", "folheada", "banho", "ródio",
    "cristal", "strass", "zircônia", "zirconia", "zircão",
    "piercing", "Par",
    # preposições e artigos
    "com", "de", "da", "do", "e", "em", "na", "no", "para",
    "a", "o", "ou", "por", "dos", "das",
}

# Normalização de cores para nome canônico
_CORES = {
    "prata": "Prata", "prateado": "Prata", "prateada": "Prata", "silver": "Prata",
    "dourado": "Dourado", "dourada": "Dourado", "gold": "Dourado", "ouro": "Dourado",
    "rosê": "Rosê", "rose": "Rosê", "rosado": "Rosê", "rosada": "Rosê",
    "preto": "Preto", "preta": "Preto",
    "branco": "Branco", "branca": "Branco",
    "colorido": "Colorido", "colorida": "Colorido",
}


def extrair_modelo(descricao: str) -> str:
    """
    Extrai estilo + cor da descrição do produto.
    Remove tamanho, material e preposições; mantém a cor (Prata/Dourado/Rosê).

    Exemplos:
      'Brinco Argola Pequena Prata'   → 'Brinco Argola Prata'
      'Brinco Argola Grande Prata'    → 'Brinco Argola Prata'   (mesmo estilo)
      'Brinco Argola Pequena Dourada' → 'Brinco Argola Dourado' (estilo diferente)
      'Colar Ponto de Luz Dourado'    → 'Colar Ponto Luz Dourado'
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


def calcular_safety_stock(qtds_diarias: list, lead_time: int = 14,
                           z: float = 1.65) -> float:
    """
    Safety Stock estatístico = Z × desvio_padrão × √(lead_time)
    Z = 1,65 → nível de serviço de 95% (raramente ficar sem estoque).
    """
    if len(qtds_diarias) < 2:
        return 0.0
    media = sum(qtds_diarias) / len(qtds_diarias)
    variancia = sum((x - media) ** 2 for x in qtds_diarias) / (len(qtds_diarias) - 1)
    return z * math.sqrt(variancia) * math.sqrt(lead_time)


def sugerir_compras_por_modelo(produtos: list, itens_vendidos: list,
                                na_rua_map: dict, categorias_map: dict,
                                dias_cobertura: int = 60,
                                dias_historico: int = 180,
                                lead_time: int = 14) -> pd.DataFrame:
    """
    Sugestões de compra agrupadas por estilo (categoria + modelo + cor).
    O mínimo é calculado estatisticamente via safety stock.
    """
    produtos_map = {p["id"]: p for p in produtos}

    # Vendas por produto por dia
    venda_pid: dict = {}
    for item in itens_vendidos:
        pid = item.get("produto_id")
        data = item.get("data")
        ds = data.strftime("%Y-%m-%d") if data else "sem-data"
        qtd = float(item.get("quantidade") or 0)
        venda_pid.setdefault(pid, {})
        venda_pid[pid][ds] = venda_pid[pid].get(ds, 0) + qtd

    # Agrupa produtos por (categoria, estilo)
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
        em_estoque = sum(float(produtos_map.get(pid, {}).get("quantidade") or 0) for pid in pids)
        na_rua = sum(na_rua_map.get(pid, 0) for pid in pids)
        min_config = sum(float(produtos_map.get(pid, {}).get("estoque_minimo") or 0) for pid in pids)

        # Vendas agregadas por dia para o estilo inteiro
        vendas_dia: dict = {}
        for pid in pids:
            for ds, qty in venda_pid.get(pid, {}).items():
                vendas_dia[ds] = vendas_dia.get(ds, 0) + qty

        total_vendido = sum(vendas_dia.values())
        media_diaria = total_vendido / dias_historico if dias_historico > 0 else 0

        # Safety stock
        if len(vendas_dia) >= 2:
            ss = calcular_safety_stock(list(vendas_dia.values()), lead_time)
        elif media_diaria > 0:
            ss = media_diaria * lead_time * 0.5
        else:
            ss = 0.0

        minimo = max(ss + media_diaria * lead_time, min_config)
        disponivel = em_estoque + na_rua
        a_comprar = max(0, (media_diaria * dias_cobertura) + minimo - disponivel)

        if media_diaria == 0 and min_config == 0:
            continue
        if media_diaria == 0 and disponivel >= min_config:
            continue

        if disponivel < minimo:
            status = "🔴 Crítico"
        elif media_diaria > 0 and em_estoque / media_diaria < 30:
            status = "🟡 Atenção"
        elif a_comprar > 0:
            status = "🟢 Planejar"
        else:
            status = "✅ OK"

        rows.append({
            "Categoria": categoria,
            "Estilo": modelo,
            "Variantes": len(pids),
            "Vendas (período)": int(total_vendido),
            "Vendas/dia": round(media_diaria, 2),
            "Em estoque": int(em_estoque),
            "Na rua": int(na_rua),
            "Mínimo recomendado": int(round(minimo)),
            "A comprar": int(round(a_comprar)),
            "Status": status,
        })

    df = pd.DataFrame(rows)
    if df.empty:
        return df

    ordem = {"🔴 Crítico": 0, "🟡 Atenção": 1, "🟢 Planejar": 2, "✅ OK": 3}
    df["_ord"] = df["Status"].map(ordem)
    return (
        df.sort_values(["Categoria", "_ord", "Vendas (período)"], ascending=[True, True, False])
        .drop(columns="_ord")
        .reset_index(drop=True)
    )


def resumo_por_categoria(df_modelos: pd.DataFrame) -> pd.DataFrame:
    """Agrega por categoria: totais de estoque, mínimo e quantidade a comprar."""
    if df_modelos.empty:
        return pd.DataFrame()

    agg = df_modelos.groupby("Categoria", as_index=False).agg(
        Estilos=("Estilo", "count"),
        Vendas_periodo=("Vendas (período)", "sum"),
        Em_estoque=("Em estoque", "sum"),
        Na_rua=("Na rua", "sum"),
        Minimo=("Mínimo recomendado", "sum"),
        A_comprar=("A comprar", "sum"),
    )
    agg["Total disponível"] = agg["Em_estoque"] + agg["Na_rua"]
    agg = agg.rename(columns={
        "Em_estoque": "Em estoque",
        "Na_rua": "Na rua",
        "Minimo": "Mínimo (total)",
        "A_comprar": "A comprar",
        "Vendas_periodo": "Vendas (período)",
    })

    def _status(row):
        if row["Em estoque"] < row["Mínimo (total)"] and row["A comprar"] > 0:
            return "🔴 Crítico"
        if row["A comprar"] > 0:
            return "🟡 Comprar"
        return "✅ OK"

    agg["Status"] = agg.apply(_status, axis=1)
    return agg.sort_values("A comprar", ascending=False).reset_index(drop=True)


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
        rows.append({"modelo": modelo, "categoria": cat,
                     "quantidade": float(item.get("quantidade") or 0)})

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
