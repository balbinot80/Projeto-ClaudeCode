import os
import time
import requests
import streamlit as st
from dotenv import load_dotenv

load_dotenv()


def _get_secret(key: str, default: str = "") -> str:
    try:
        return st.secrets[key]
    except Exception:
        return os.getenv(key, default)


BASE_URL = _get_secret("JUERI_BASE_URL", "https://aureumjoias.jueri.com.br/sis/api/v1/4216")
TOKEN = _get_secret("JUERI_TOKEN", "")


def _headers():
    return {"Authorization": f"Bearer {TOKEN}", "Accept": "application/json"}


def _req(endpoint_ou_url: str, params: dict = None) -> dict:
    """GET com retry automático em 429."""
    url = endpoint_ou_url if endpoint_ou_url.startswith("http") else f"{BASE_URL}/{endpoint_ou_url}"
    for tentativa in range(4):
        resp = requests.get(url, headers=_headers(), params=params or {}, timeout=30)
        if resp.status_code == 429:
            time.sleep(10 * (tentativa + 1))
            continue
        resp.raise_for_status()
        return resp.json()
    raise requests.exceptions.HTTPError(
        "Limite de requisições atingido. Aguarde alguns minutos e atualize a página."
    )


def _get_all_pages(endpoint: str, params: dict = None) -> list:
    """Percorre todas as páginas usando next_page_url."""
    params = dict(params or {})
    params["page"] = 1
    results = []
    while True:
        data = _req(endpoint, params)
        results.extend(data.get("data", []))
        if not data.get("next_page_url"):
            break
        params["page"] += 1
    return results


# ── Produtos e categorias ──────────────────────────────────────────────────

@st.cache_data(ttl=7200)
def get_produtos(status: str = "1") -> list:
    params = {"status": status} if status else {}
    return _get_all_pages("produto", params)


@st.cache_data(ttl=86400)
def get_categorias() -> dict:
    try:
        items = _get_all_pages("categoria_produto")
        return {str(c.get("id")): c.get("descricao", f"Cat {c.get('id')}") for c in items}
    except Exception:
        return {}


# ── Pedidos ────────────────────────────────────────────────────────────────

@st.cache_data(ttl=3600)
def _get_lista_pedidos() -> list:
    """
    Busca a lista completa de pedidos (resumo, SEM itens).
    A API retorna 15 por página — ~168 páginas para 2509 pedidos.
    Resultado fica em cache por 1 hora.
    """
    return _get_all_pages("pedido")


def get_pedidos_abertos() -> list:
    """Pedidos com status 'Aberto' (filtrado em Python após buscar lista completa)."""
    return [p for p in _get_lista_pedidos() if p.get("status") == "Aberto"]


def get_pedidos_baixados() -> list:
    """Pedidos com status 'Baixado' (filtrado em Python após buscar lista completa)."""
    return [p for p in _get_lista_pedidos() if p.get("status") == "Baixado"]


@st.cache_data(ttl=3600)
def get_pedido_detalhado(pedido_id: int) -> dict:
    """Busca um pedido individual com seus itens. Resultado cacheado por pedido."""
    try:
        data = _req(f"pedido/{pedido_id}")
        registro = data.get("data", data)
        if isinstance(registro, list):
            return registro[0] if registro else {}
        return registro if isinstance(registro, dict) else {}
    except Exception:
        return {}


@st.cache_data(ttl=3600)
def get_itens_pedidos_abertos() -> dict:
    """
    Retorna {produto_id: quantidade_na_rua} buscando cada pedido aberto
    individualmente para obter os itens.
    """
    abertos = get_pedidos_abertos()
    na_rua: dict = {}
    for pedido in abertos:
        pid = pedido.get("id")
        if not pid:
            continue
        detalhes = get_pedido_detalhado(pid)
        for item in detalhes.get("itens", []):
            prod_id = (item.get("produto") or {}).get("id")
            if prod_id:
                na_rua[prod_id] = na_rua.get(prod_id, 0) + float(item.get("quantidade") or 0)
    return na_rua


@st.cache_data(ttl=3600)
def get_itens_pedidos_baixados(dias: int = 180) -> list:
    """
    Retorna lista de itens vendidos (de pedidos baixados) nos últimos `dias` dias.
    Busca cada pedido baixado individualmente para obter itens.
    Cada item: {pedido_id, produto_id, quantidade, data, fk_revendedor_id}
    """
    from datetime import datetime, timedelta
    corte = datetime.today() - timedelta(days=dias)

    baixados = get_pedidos_baixados()
    recentes = []
    for p in baixados:
        data_str = (p.get("data_baixa") or p.get("data_criacao") or "")[:10]
        try:
            if datetime.fromisoformat(data_str) >= corte:
                recentes.append(p)
        except (ValueError, TypeError):
            pass

    rows = []
    for pedido in recentes:
        pid = pedido.get("id")
        data_str = (pedido.get("data_baixa") or pedido.get("data_criacao") or "")[:10]
        try:
            data_pedido = __import__("datetime").datetime.fromisoformat(data_str)
        except Exception:
            data_pedido = None

        detalhes = get_pedido_detalhado(pid)
        for item in detalhes.get("itens", []):
            prod_id = (item.get("produto") or {}).get("id")
            if prod_id:
                rows.append({
                    "pedido_id": pid,
                    "produto_id": prod_id,
                    "quantidade": float(item.get("quantidade") or 0),
                    "data": data_pedido,
                    "fk_revendedor_id": pedido.get("fk_revendedor_id"),
                })
    return rows


# ── Revendedores ───────────────────────────────────────────────────────────

@st.cache_data(ttl=7200)
def get_revendedores(status: str = None) -> list:
    params = {}
    if status:
        params["status"] = status
    return _get_all_pages("revendedor", params)


def limpar_cache():
    st.cache_data.clear()
