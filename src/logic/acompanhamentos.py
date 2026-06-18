import json
import os

_FILE = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "..", "data", "acompanhamentos.json")
)

_SEMANAS = ["0-7", "8-15", "16-20", "21-30"]


def load_acompanhamentos() -> dict:
    try:
        if os.path.exists(_FILE):
            with open(_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return {}


def save_acompanhamento(nome: str, data_str: str, descricao: str, prebaixa_semanas: dict):
    dados = load_acompanhamentos()
    if nome not in dados:
        dados[nome] = []
    dados[nome].append({
        "data": data_str,
        "descricao": descricao,
        "prebaixa_semanas": {k: prebaixa_semanas.get(k, 0.0) for k in _SEMANAS},
    })
    os.makedirs(os.path.dirname(_FILE), exist_ok=True)
    with open(_FILE, "w", encoding="utf-8") as f:
        json.dump(dados, f, ensure_ascii=False, indent=2)


def get_ultimos_valores(nome: str) -> dict:
    """Últimos valores de pré-baixa registrados por semana para uma revendedora."""
    dados = load_acompanhamentos()
    registros = dados.get(nome, [])
    if not registros:
        return {k: 0.0 for k in _SEMANAS}
    return {k: registros[-1].get("prebaixa_semanas", {}).get(k, 0.0) for k in _SEMANAS}


def get_historico(nome: str) -> list:
    """Todos os registros de acompanhamento de uma revendedora."""
    return load_acompanhamentos().get(nome, [])
