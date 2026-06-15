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

    # Distribuição de status
    if code == 200 and isinstance(dados, dict) and dados.get("data"):
        registros = dados["data"]
        from collections import Counter
        dist_status = Counter(r.get("status", "?") for r in registros)
        st.write("**Distribuição de status nos pedidos:**", dict(dist_status))

    st.divider()

    # Busca pedido individual por ID para ver se tem itens
    st.subheader("Pedido individual: `/pedido/{id}`")
    code0, dados0 = _testar_endpoint("pedido", {})
    if code0 == 200 and isinstance(dados0, dict) and dados0.get("data"):
        primeiro_id = dados0["data"][0].get("id")
        if primeiro_id:
            code_id, dados_id = _testar_endpoint(f"pedido/{primeiro_id}")
            st.write(f"Buscando `/pedido/{primeiro_id}` → HTTP {code_id}")
            if code_id == 200:
                if isinstance(dados_id, dict):
                    # Pode vir direto ou dentro de 'data'
                    registro = dados_id.get("data", dados_id)
                    if isinstance(registro, list) and registro:
                        registro = registro[0]
                    st.write("**Campos disponíveis:**", list(registro.keys()) if isinstance(registro, dict) else "formato inesperado")
                    st.json(registro)
                else:
                    st.code(str(dados_id)[:500])
            else:
                st.warning(f"HTTP {code_id}: {str(dados_id)[:200]}")
