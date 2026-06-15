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
    # Primeiro: busca todos os pedidos sem filtro para ver a estrutura
    st.subheader("Estrutura do endpoint `pedido` (sem filtro)")
    code, dados = _testar_endpoint("pedido", {})
    if code == 200 and isinstance(dados, dict) and dados.get("data"):
        registros = dados["data"]
        st.success(f"{len(registros)} registros retornados")
        primeiro = registros[0]
        st.write("**Campos do primeiro pedido:**")
        st.code(json.dumps(list(primeiro.keys()), ensure_ascii=False, indent=2))
        st.write("**Primeiro pedido completo:**")
        st.json(primeiro)

        # Mostra todos os valores únicos do campo que pareça ser status
        for campo in ["status", "situacao", "fk_status_id", "status_pedido", "situacao_pedido"]:
            valores = list({str(r.get(campo, "")) for r in registros if r.get(campo) is not None})
            if valores:
                st.write(f"**Valores únicos de `{campo}`:** {valores}")
    else:
        st.error(f"Falha: HTTP {code}")
        st.code(str(dados)[:300])

    st.divider()

    # Segundo: testa variações de parâmetro de filtro
    st.subheader("Testando parâmetros de filtro de status")
    filtros_candidatos = [
        {"situacao": "Aberto"},
        {"situacao": "Baixado"},
        {"fk_status_id": "1"},
        {"fk_status_id": "2"},
        {"fk_status_id": "3"},
        {"fk_status_id": "4"},
        {"status_pedido": "Aberto"},
        {"status_pedido": "Baixado"},
    ]

    for params in filtros_candidatos:
        code2, dados2 = _testar_endpoint("pedido", params)
        if code2 == 429:
            st.error(f"⛔ HTTP 429 — limite atingido, pare e aguarde")
            break
        if code2 == 200 and isinstance(dados2, dict):
            total2 = len(dados2.get("data", []))
            if total2 > 0:
                st.success(f"✅ `{params}` → {total2} registros encontrados!")
            else:
                st.info(f"🟡 `{params}` → 0 registros")
        else:
            st.warning(f"⚠️ `{params}` → HTTP {code2}")
