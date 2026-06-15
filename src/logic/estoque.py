import pandas as pd
import re

# Palavras-chave para inferir categoria quando API não retorna nome
_KEYWORDS = [
    ("Brinco", ["brinco", "ear"]),
    ("Colar", ["colar", "gargantilha", "corrente"]),
    ("Choker", ["choker"]),
    ("Pulseira", ["pulseira", "bracelete"]),
    ("Tornozeleira", ["tornozeleira"]),
    ("Anel", ["anel", "aliança"]),
    ("Pingente", ["pingente"]),
    ("Conjunto", ["conjunto", "kit"]),
    ("Ponto de Luz", ["ponto de luz"]),
    ("Berloques", ["berloque"]),
]


def inferir_categoria(descricao: str) -> str:
    desc = (descricao or "").lower()
    for nome, keys in _KEYWORDS:
        if any(k in desc for k in keys):
            return nome
    return "Outros"


def nome_categoria(cat_id, categorias_map: dict, descricao: str = "") -> str:
    """Resolve nome da categoria: usa mapa da API ou infere por keyword."""
    nome = categorias_map.get(str(cat_id), "")
    if nome:
        return nome
    if descricao:
        return inferir_categoria(descricao)
    return f"Categoria {cat_id}" if cat_id else "Sem categoria"


def calcular_na_rua(pedidos_abertos: list) -> dict:
    """Retorna {produto_id: quantidade_na_rua} com base nos pedidos em aberto."""
    na_rua = {}
    for pedido in pedidos_abertos:
        for item in pedido.get("itens", []):
            pid = item.get("produto", {}).get("id") if isinstance(item.get("produto"), dict) else item.get("fk_produto_id")
            if pid:
                qtd = float(item.get("quantidade") or 0)
                na_rua[pid] = na_rua.get(pid, 0) + qtd
    return na_rua


def montar_df_estoque(produtos: list, pedidos_abertos: list, categorias_map: dict) -> pd.DataFrame:
    na_rua_map = calcular_na_rua(pedidos_abertos)

    rows = []
    for p in produtos:
        pid = p.get("id")
        descricao = p.get("descricao", "")
        cat_id = p.get("fk_categoria_id")
        categoria = nome_categoria(cat_id, categorias_map, descricao)
        em_estoque = float(p.get("quantidade") or 0)
        na_rua = na_rua_map.get(pid, 0)
        total = em_estoque + na_rua
        estoque_min = float(p.get("estoque_minimo") or 0)
        estoque_max = float(p.get("estoque_maximo") or 0)

        if em_estoque < estoque_min and estoque_min > 0:
            alerta = "🔴 Crítico"
        elif em_estoque == 0 and na_rua > 0:
            alerta = "🟡 Só na rua"
        elif em_estoque > 0 and na_rua > 0:
            alerta = "✅ OK"
        elif em_estoque > 0:
            alerta = "✅ Em estoque"
        else:
            alerta = "⚫ Zerado"

        rows.append({
            "ID": pid,
            "Produto": descricao,
            "Categoria": categoria,
            "Em estoque": int(em_estoque),
            "Na rua": int(na_rua),
            "Total": int(total),
            "Mínimo": int(estoque_min),
            "Máximo": int(estoque_max),
            "Situação": alerta,
        })

    return pd.DataFrame(rows)
