from datetime import datetime, timedelta
import pandas as pd
from src.logic.estoque import nome_categoria


def top_vendidos_por_categoria(itens: list, produtos_map: dict,
                                categorias_map: dict, top_n: int = 10) -> dict:
    """
    itens: lista de dicts {produto_id, quantidade, ...} vindos de get_itens_pedidos_baixados()
    Retorna {categoria: DataFrame com top N mais vendidos}.
    """
    if not itens:
        return {}

    rows = []
    for item in itens:
        pid = item.get("produto_id")
        produto_info = produtos_map.get(pid, {})
        descricao = produto_info.get("descricao", f"Produto {pid}")
        cat_id = produto_info.get("fk_categoria_id")
        categoria = nome_categoria(cat_id, categorias_map, descricao)
        rows.append({
            "produto_id": pid,
            "descricao": descricao,
            "categoria": categoria,
            "quantidade": float(item.get("quantidade") or 0),
        })

    df = pd.DataFrame(rows)
    resultado = {}
    for cat, grupo in df.groupby("categoria"):
        ranking = (
            grupo.groupby(["produto_id", "descricao"], as_index=False)
            .agg(total_vendido=("quantidade", "sum"))
            .sort_values("total_vendido", ascending=False)
            .head(top_n)
        )
        resultado[cat] = ranking

    return resultado


def sugerir_compras(produtos: list, itens_vendidos: list,
                    na_rua_map: dict, categorias_map: dict,
                    dias_cobertura: int = 60, dias_historico: int = 180) -> pd.DataFrame:
    """
    itens_vendidos: lista de dicts vindos de get_itens_pedidos_baixados()
    na_rua_map: {produto_id: qtd} vindo de get_itens_pedidos_abertos()
    """
    produtos_map = {p["id"]: p for p in produtos}

    # Velocidade de vendas por produto
    vel_map: dict = {}
    for item in itens_vendidos:
        pid = item.get("produto_id")
        if pid:
            vel_map[pid] = vel_map.get(pid, 0) + float(item.get("quantidade") or 0)
    for pid in vel_map:
        vel_map[pid] = vel_map[pid] / dias_historico

    rows = []
    for p in produtos:
        pid = p.get("id")
        cat_id = p.get("fk_categoria_id")
        categoria = nome_categoria(cat_id, categorias_map, p.get("descricao", ""))
        descricao = p.get("descricao", "")
        em_estoque = float(p.get("quantidade") or 0)
        na_rua = na_rua_map.get(pid, 0)
        estoque_min = float(p.get("estoque_minimo") or 0)
        estoque_max = float(p.get("estoque_maximo") or 0)
        media_diaria = vel_map.get(pid, 0)

        dias_restantes = (em_estoque / media_diaria) if media_diaria > 0 else 999
        estoque_alvo = media_diaria * dias_cobertura
        qtd_sugerida = max(0, estoque_alvo - em_estoque - na_rua)
        if estoque_max > 0:
            qtd_sugerida = min(qtd_sugerida, max(0, estoque_max - em_estoque - na_rua))

        if media_diaria == 0 and em_estoque >= estoque_min:
            continue

        if em_estoque <= estoque_min and estoque_min > 0:
            status = "🔴 Crítico"
        elif dias_restantes < 30:
            status = "🟡 Atenção"
        elif qtd_sugerida > 0:
            status = "🟢 Planejar"
        else:
            status = "✅ OK"

        rows.append({
            "Categoria": categoria,
            "Produto": descricao,
            "Em estoque": int(em_estoque),
            "Na rua": int(na_rua),
            "Vendas/dia": round(media_diaria, 2),
            "Dias restantes": round(dias_restantes, 0) if dias_restantes < 999 else "∞",
            "Sugestão de compra": int(qtd_sugerida),
            "Status": status,
        })

    df = pd.DataFrame(rows)
    if df.empty:
        return df

    ordem = {"🔴 Crítico": 0, "🟡 Atenção": 1, "🟢 Planejar": 2, "✅ OK": 3}
    df["_ord"] = df["Status"].map(ordem)
    return df.sort_values(["Categoria", "_ord"]).drop(columns="_ord").reset_index(drop=True)
