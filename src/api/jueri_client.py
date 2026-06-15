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


def _get_all_pages(endpoint: str, params: dict = None) -> list:
    params = params or {}
    params["per_page"] = 100
    params["page"] = 1
    results = []

    while True:
        for tentativa in range(3):
            resp = requests.get(f"{BASE_URL}/{endpoint}", headers=_headers(), params=params, timeout=30)
            if resp.status_code == 429:
                if tentativa < 2:
                    time.sleep(6 * (tentativa + 1))
                    continue
                raise requests.exceptions.HTTPError(
                    "A API Jueri está com limite de requisições (429). Aguarde alguns minutos e atualize a página.",
                    response=resp,
                )
            resp.raise_for_status()
            break

        data = resp.json()
        results.extend(data.get("data", []))

        if not data.get("next_page_url"):
            break
        params["page"] += 1

    return results


@st.cache_data(ttl=7200)
def get_produtos(status: str = "1") -> list:
    params = {"status": status} if status else {}
    return _get_all_pages("produto", params)


@st.cache_data(ttl=86400)  # categorias raramente mudam — cache 24h
def get_categorias() -> dict:
    """Retorna dict {id: nome} das categorias. Fallback via keywords se API indisponível."""
    try:
        items = _get_all_pages("categoria_produto")
        return {str(c.get("id")): c.get("descricao", f"Cat {c.get('id')}") for c in items}
    except Exception:
        return {}


@st.cache_data(ttl=7200)
def _get_todos_pedidos() -> list:
    """Busca todos os pedidos sem filtro (API ignora parâmetros de status)."""
    return _get_all_pages("pedido")


def get_pedidos_abertos() -> list:
    """Pedidos com status 'Aberto' = peças na rua com revendedoras."""
    return [p for p in _get_todos_pedidos() if p.get("status") == "Aberto"]


def get_pedidos_baixados() -> list:
    """Pedidos com status 'Baixado' = vendas realizadas."""
    return [p for p in _get_todos_pedidos() if p.get("status") == "Baixado"]


@st.cache_data(ttl=7200)
def get_vendas(data_inicial: str = None, data_final: str = None) -> list:
    params = {}
    if data_inicial:
        params["data_inicial"] = data_inicial
    if data_final:
        params["data_final"] = data_final
    return _get_all_pages("venda", params)


@st.cache_data(ttl=7200)
def get_revendedores(status: str = None) -> list:
    params = {}
    if status:
        params["status"] = status
    return _get_all_pages("revendedor", params)


def limpar_cache():
    st.cache_data.clear()
