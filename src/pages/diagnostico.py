import streamlit as st
import json
import requests
import os
from src.api.jueri_client import BASE_URL, _headers


def _testar_endpoint(endpoint: str, params: dict = None) -> tuple:
    """Retorna (status_code, dados_json_ou_texto)."""
    try:
        url = f"{BASE_URL}/{endpoint}"
        resp = requests.get(url, headers=_headers(), params=params or {}, timeout=15)
        try:
            return resp.status_code, resp.json()
        except Exception:
            return resp.status_code, resp.text[:500]
    except Exception as e:
        return 0, str(e)


def render():
    st.header("🔍 Diagnóstico da API")
    st.caption("Testa endpoints da API Jueri para descobrir nomes e estrutura corretos.")

    # Endpoints candidatos para pedidos
    candidatos = [
        ("pedido", {}),
        ("pedido", {"status": "Aberto"}),
        ("pedido", {"status": "Baixado"}),
        ("pedido", {"status": "Fechado"}),
        ("pedidos", {}),
        ("ordem", {}),
        ("ordens", {}),
        ("remessa", {}),
        ("remessas", {}),
        ("venda", {}),
        ("vendas", {}),
    ]

    st.subheader("Testando endpoints de pedidos")

    for endpoint, params in candidatos:
        label = f"`{endpoint}`" + (f" com `{params}`" if params else "")
        code, dados = _testar_endpoint(endpoint, params)

        if code == 200 and isinstance(dados, dict):
            total = len(dados.get("data", []))
            if total > 0:
                st.success(f"✅ {label} → HTTP {code} · {total} registros")
                with st.expander(f"Ver primeiro registro de `{endpoint}` {params}"):
                    primeiro = dados["data"][0]
                    st.write("**Chaves disponíveis:**", list(primeiro.keys()))
                    st.json(primeiro)
            else:
                st.info(f"🟡 {label} → HTTP {code} · 0 registros (endpoint existe mas está vazio)")
        elif code == 200:
            st.info(f"🟡 {label} → HTTP {code} · resposta inesperada")
            st.code(str(dados)[:300])
        elif code == 404:
            st.warning(f"❌ {label} → HTTP {code} · endpoint não existe")
        elif code == 429:
            st.error(f"⛔ {label} → HTTP 429 · limite de requisições atingido")
            break
        else:
            st.warning(f"⚠️ {label} → HTTP {code}")
            st.code(str(dados)[:200])
