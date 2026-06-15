import os
import requests
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

# Streamlit Cloud usa st.secrets; localmente usa .env
def _get_secret(key: str, default: str = "") -> str:
    try:
        return st.secrets[key]
    except Exception:
        return os.getenv(key, default)

BASE_URL = _get_secret("JUERI_BASE_URL", "https://aureumjoias.jueri.com.br/sis/api/v1/aureumjoias")
TOKEN = _get_secret("JUERI_TOKEN", "")


def _headers():
    return {"Authorization": f"Bearer {TOKEN}", "Accept": "application/json"}


def _get_all_pages(endpoint: str, params: dict = None) -> list:
    """Busca todas as páginas de um endpoint paginado."""
    import time
    params = params or {}
    params["per_page"] = 100
    params["page"] = 1
    results = []

    while True:
        for tentativa in range(3):
            resp = requests.get(f"{BASE_URL}/{endpoint}", headers=_headers(), params=params, timeout=30)
            if resp.status_code == 429:
                if tentativa < 2:
                    time.sleep(5 * (tentativa + 1))
                    continue
                raise requests.exceptions.HTTPError(
                    "A API Jueri está com limite de requisições (429). Aguarde alguns minutos e atualize a página.",
                    response=resp,
                )
            resp.raise_for_status()
            break

        data = resp.json()
        items = data.get("data", [])
        results.extend(items)

        # Usa next_page_url pois alguns endpoints não retornam last_page
        if not data.get("next_page_url"):
            break
        params["page"] += 1

    return results


@st.cache_data(ttl=7200)  # cache de 2 horas
def get_produtos(status: str = "1") -> list:
    # status=1 traz apenas produtos ativos (evita carregar 10k+ inativos)
    params = {"status": status} if status else {}
    return _get_all_pages("produto", params)


@st.cache_data(ttl=1800)
def get_produto(produto_id: int) -> dict:
    resp = requests.get(f"{BASE_URL}/produto/{produto_id}", headers=_headers(), timeout=30)
    resp.raise_for_status()
    return resp.json()


@st.cache_data(ttl=1800)
def get_pedidos(data_inicial: str = None, data_final: str = None) -> list:
    params = {}
    if data_inicial:
        params["data_inicial"] = data_inicial
    if data_final:
        params["data_final"] = data_final
    return _get_all_pages("pedido", params)


@st.cache_data(ttl=1800)
def get_vendas(data_inicial: str = None, data_final: str = None) -> list:
    params = {}
    if data_inicial:
        params["data_inicial"] = data_inicial
    if data_final:
        params["data_final"] = data_final
    return _get_all_pages("venda", params)


@st.cache_data(ttl=1800)
def get_revendedores(status: str = None) -> list:
    params = {}
    if status:
        params["status"] = status
    return _get_all_pages("revendedor", params)


def limpar_cache():
    st.cache_data.clear()
