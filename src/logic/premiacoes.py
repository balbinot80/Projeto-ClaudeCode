import json
import os
from collections import defaultdict
from datetime import date
from src.logic.revendedoras import parse_date

_FILE = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "..", "data", "premiacoes.json")
)


def load_premiacoes() -> dict:
    try:
        if os.path.exists(_FILE):
            with open(_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return {}


def save_premiacao(mes_key: str, meta: float, premio: str):
    p = load_premiacoes()
    p[mes_key] = {"meta": meta, "premio": premio}
    os.makedirs(os.path.dirname(_FILE), exist_ok=True)
    with open(_FILE, "w", encoding="utf-8") as f:
        json.dump(p, f, ensure_ascii=False, indent=2)


def calcular_ranking(todos_pedidos: list, mes: int, ano: int, meta: float) -> list:
    """
    Calcula ranking de revendedoras para o mês selecionado.
    Categorias:
      ganhadora  — baixado >= meta (definitivo)
      potencial  — baixado < meta mas baixado + pré-baixa >= meta
      proxima    — total >= 70% da meta mas < meta
      outras     — abaixo de 70%
    """
    baixado_map: dict = defaultdict(float)
    prebaixa_map: dict = defaultdict(float)
    nome_map: dict = {}
    sup_map: dict = {}

    for p in todos_pedidos:
        rid = p.get("fk_revendedor_id")
        if not rid:
            continue
        status = p.get("status", "")
        comprador = p.get("comprador") or {}
        nome_map[rid] = comprador.get("nome") or f"Rev {rid}"
        sup_map[rid] = p.get("supervisor_nome") or "Sem supervisora"

        if status == "Baixado":
            d = parse_date(p.get("data_baixa"))
            if d and d.month == mes and d.year == ano:
                baixado_map[rid] += float(p.get("valor_total") or 0)
        elif status == "Aberto":
            d = parse_date(p.get("data_acerto"))
            if d and d.month == mes and d.year == ano:
                prebaixa_map[rid] += float(p.get("valor_pre_baixa") or 0)

    all_ids = set(baixado_map) | set(prebaixa_map)
    rows = []
    for rid in all_ids:
        baixado = baixado_map[rid]
        pre     = prebaixa_map[rid]
        total   = baixado + pre
        pct     = round(total / meta * 100, 1) if meta > 0 else 0.0

        if baixado >= meta:
            cat = "ganhadora"
        elif total >= meta:
            cat = "potencial"
        elif total >= meta * 0.70:
            cat = "proxima"
        else:
            cat = "outras"

        rows.append({
            "id":        rid,
            "Nome":      nome_map.get(rid, f"Rev {rid}"),
            "Supervisor": sup_map.get(rid, ""),
            "Baixado":   round(baixado, 2),
            "Pré-baixa": round(pre, 2),
            "Total":     round(total, 2),
            "% da meta": pct,
            "Falta":     round(max(meta - total, 0), 2),
            "Categoria": cat,
        })

    return sorted(rows, key=lambda x: x["Total"], reverse=True)


def _criacao_key(p):
    d = parse_date(p.get("data_criacao"))
    return d if d else date(2099, 1, 1)


def verificar_colar(todos_pedidos: list, mes: int, ano: int) -> list:
    """
    Regra fixa: nova revendedora cujo PRIMEIRO pedido (mais antigo por data_criacao)
    está relacionado a este mês e tem valor > R$ 1.000,00.
    - Baixado no mês com valor_total > 1000 → ganhou (confirmado)
    - Aberto com data_acerto no mês e valor_pre_baixa > 1000 → potencial (em aberto)
    Retorna campo "status_pedido": "Baixado" ou "Aberto".
    """
    pedidos_por_rev: dict = defaultdict(list)
    for p in todos_pedidos:
        rid = p.get("fk_revendedor_id")
        if rid:
            pedidos_por_rev[rid].append(p)

    winners = []
    for rid, pedidos in pedidos_por_rev.items():
        primeiro = sorted(pedidos, key=_criacao_key)[0]
        status   = primeiro.get("status", "")
        comprador = primeiro.get("comprador") or {}
        nome      = comprador.get("nome") or f"Rev {rid}"
        supervisor = primeiro.get("supervisor_nome") or "Sem supervisora"

        if status == "Baixado":
            d_baixa = parse_date(primeiro.get("data_baixa"))
            if not (d_baixa and d_baixa.month == mes and d_baixa.year == ano):
                continue
            valor = float(primeiro.get("valor_total") or 0)
            if valor <= 1000:
                continue
            winners.append({
                "Nome":            nome,
                "Supervisor":      supervisor,
                "Valor 1º pedido": round(valor, 2),
                "status_pedido":   "Baixado",
            })

        elif status == "Aberto":
            d_acerto = parse_date(primeiro.get("data_acerto"))
            if not (d_acerto and d_acerto.month == mes and d_acerto.year == ano):
                continue
            valor = float(primeiro.get("valor_pre_baixa") or 0)
            if valor <= 1000:
                continue
            winners.append({
                "Nome":            nome,
                "Supervisor":      supervisor,
                "Valor 1º pedido": round(valor, 2),
                "status_pedido":   "Aberto",
            })

    return sorted(winners, key=lambda x: x["Nome"])
