import streamlit as st
import json
import requests
from collections import Counter
from src.api.jueri_client import BASE_URL, _headers


def _get(endpoint: str, params: dict = None) -> tuple:
    try:
        resp = requests.get(
            f"{BASE_URL}/{endpoint}",
            headers=_headers(),
            params=params or {},
            timeout=15,
        )
        try:
            return resp.status_code, resp.json()
        except Exception:
            return resp.status_code, resp.text[:500]
    except Exception as e:
        return 0, str(e)


def render():
    st.header("🔍 Diagnóstico da API")

    # ── Paginação ──────────────────────────────────────────────────────────
    st.subheader("1. Estrutura de paginação do endpoint `pedido`")

    code1, r1 = _get("pedido", {"per_page": 15, "page": 1})
    if code1 != 200 or not isinstance(r1, dict):
        st.error(f"Falha na página 1: HTTP {code1} — {str(r1)[:200]}")
        return

    meta = {k: v for k, v in r1.items() if k != "data"}
    st.write("**Campos de paginação (página 1):**")
    st.json(meta)

    dados_p1 = r1.get("data", [])
    st.metric("Registros na página 1", len(dados_p1))
    if dados_p1:
        st.write("**Status nesta página:**", dict(Counter(r.get("status") for r in dados_p1)))

    st.write("---")
    code2, r2 = _get("pedido", {"per_page": 15, "page": 2})
    if code2 == 200 and isinstance(r2, dict):
        dados_p2 = r2.get("data", [])
        st.metric("Registros na página 2", len(dados_p2))
        if dados_p2:
            st.write("**Status página 2:**", dict(Counter(r.get("status") for r in dados_p2)))
        meta2 = {k: v for k, v in r2.items() if k != "data"}
        st.write("**Paginação página 2:**")
        st.json(meta2)
    elif code2 == 429:
        st.error("⛔ HTTP 429 — limite de requisições. Aguarde e tente novamente.")
        return
    else:
        st.warning(f"Página 2: HTTP {code2}")

    # ── Pedido individual ──────────────────────────────────────────────────
    st.divider()
    st.subheader("2. Pedido individual `/pedido/{id}` — tem itens?")

    if dados_p1:
        pid = dados_p1[0].get("id")
        code_id, r_id = _get(f"pedido/{pid}")
        st.write(f"GET `/pedido/{pid}` → HTTP {code_id}")
        if code_id == 200 and isinstance(r_id, dict):
            registro = r_id.get("data", r_id)
            if isinstance(registro, list) and registro:
                registro = registro[0]
            if isinstance(registro, dict):
                st.write("**Campos disponíveis:**", list(registro.keys()))
                st.json(registro)
            else:
                st.code(str(r_id)[:500])
        elif code_id == 429:
            st.error("⛔ HTTP 429 — limite atingido.")
        else:
            st.warning(f"HTTP {code_id}: {str(r_id)[:200]}")
