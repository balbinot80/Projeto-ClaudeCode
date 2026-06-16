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

    # ── Estrutura de produto ───────────────────────────────────────────────
    st.divider()
    st.subheader("2. Estrutura de um produto `/produto` — todos os campos disponíveis")

    code_p, r_p = _get("produto", {"page": 1})
    if code_p == 200 and isinstance(r_p, dict):
        prods = r_p.get("data", [])
        if prods:
            st.write(f"**Campos do produto** (`{len(prods)} na página 1`):")
            st.write(list(prods[0].keys()))
            st.write("**Exemplo de produto completo:**")
            st.json(prods[0])
        else:
            st.warning("Nenhum produto retornado.")
    else:
        st.error(f"HTTP {code_p}: {str(r_p)[:200]}")

    # ── Pedido individual (qualquer) ───────────────────────────────────────
    st.divider()
    st.subheader("3. Pedido individual `/pedido/{id}` — campos completos")

    if dados_p1:
        pid = dados_p1[0].get("id")
        code_id, r_id = _get(f"pedido/{pid}")
        st.write(f"GET `/pedido/{pid}` → HTTP {code_id}")
        if code_id == 200 and isinstance(r_id, dict):
            registro = r_id.get("data", r_id)
            if isinstance(registro, list) and registro:
                registro = registro[0]
            if isinstance(registro, dict):
                st.write("**Todos os campos:**", list(registro.keys()))
                st.json(registro)
            else:
                st.code(str(r_id)[:500])
        elif code_id == 429:
            st.error("⛔ HTTP 429 — limite atingido.")
        else:
            st.warning(f"HTTP {code_id}: {str(r_id)[:200]}")

    # ── Pedido BAIXADO individual — campos de quantidade original ─────────
    st.divider()
    st.subheader("4. Pedido BAIXADO — campos de quantidade (diagnóstico de nível)")
    st.caption("Usa a lista completa de pedidos (cacheada) para encontrar o primeiro Baixado e inspecionar seus campos.")

    try:
        from src.api.jueri_client import _get_lista_pedidos
        todos = _get_lista_pedidos()
        # Pega o baixado MAIS RECENTE (maior data_baixa) para ter campos mais atuais
        baixados = [p for p in todos if p.get("status") == "Baixado"]
        pedido_baixado = max(
            baixados,
            key=lambda p: p.get("data_baixa") or "",
            default=None,
        )
    except Exception as e:
        pedido_baixado = None
        st.error(f"Erro ao carregar lista: {e}")

    if not pedido_baixado:
        st.warning("Nenhum pedido com status 'Baixado' encontrado na lista completa.")
    else:
        pid_bx = pedido_baixado.get("id")
        st.write(f"Pedido baixado encontrado: **ID {pid_bx}**")

        # Todos os campos do resumo (lista)
        st.write("**Todos os campos do pedido baixado (resumo da lista):**")
        st.json(pedido_baixado)

        # Destaca campos de quantidade (inclui "inicial" na busca)
        termos = ["qtd", "quant", "pec", "item", "total", "inicial", "origin", "consign", "maleta"]
        campos_qtd = {k: v for k, v in pedido_baixado.items()
                      if any(x in k.lower() for x in termos)}
        st.write("**Campos relacionados a quantidade/total/inicial:**")
        st.json(campos_qtd if campos_qtd else {"(nenhum encontrado com esse padrão)": None})

        # Campos completos no endpoint individual
        st.write("---")
        st.write(f"**Campos do endpoint individual `/pedido/{pid_bx}`:**")
        code_bx, r_bx = _get(f"pedido/{pid_bx}")
        if code_bx == 200 and isinstance(r_bx, dict):
            reg = r_bx.get("data", r_bx)
            if isinstance(reg, list) and reg:
                reg = reg[0]
            if isinstance(reg, dict):
                campos_qtd_ind = {k: v for k, v in reg.items()
                                  if any(x in k.lower() for x in ["qtd", "quant", "pec", "item", "total"])}
                st.write("**Campos de quantidade/total (endpoint individual):**")
                st.json(campos_qtd_ind)
                st.write("**Registro completo:**")
                st.json(reg)
        elif code_bx == 429:
            st.error("⛔ HTTP 429 — limite atingido.")

    # ── Pedido ABERTO individual — procura campos de pré-baixa ────────────
    st.divider()
    st.subheader("5. Pedido ABERTO individual — campos de pré-baixa")
    st.caption("Busca o primeiro pedido com status 'Aberto' e exibe todos os seus campos.")

    # Varre páginas até achar um pedido Aberto
    pedido_aberto = None
    for pagina in range(1, 6):
        code_pg, r_pg = _get("pedido", {"page": pagina})
        if code_pg != 200 or not isinstance(r_pg, dict):
            break
        for p in r_pg.get("data", []):
            if p.get("status") == "Aberto":
                pedido_aberto = p
                break
        if pedido_aberto:
            break

    if not pedido_aberto:
        st.warning("Nenhum pedido com status 'Aberto' encontrado nas primeiras 5 páginas.")
    else:
        pid_aberto = pedido_aberto.get("id")
        st.write(f"Pedido aberto encontrado: **ID {pid_aberto}**")
        st.write("**Campos do resumo (lista):**", list(pedido_aberto.keys()))

        code_ab, r_ab = _get(f"pedido/{pid_aberto}")
        if code_ab == 200 and isinstance(r_ab, dict):
            reg = r_ab.get("data", r_ab)
            if isinstance(reg, list) and reg:
                reg = reg[0]
            if isinstance(reg, dict):
                st.write("**Campos completos do pedido aberto:**", list(reg.keys()))

                # Destaca campos relacionados a valores / pré-baixa
                campos_valor = {k: v for k, v in reg.items()
                                if any(x in k.lower() for x in
                                       ["valor", "pre", "baixa", "vend", "pago", "descont", "total"])}
                if campos_valor:
                    st.write("**Campos relacionados a valores / pré-baixa:**")
                    st.json(campos_valor)

                st.write("**Registro completo:**")
                st.json(reg)
        elif code_ab == 429:
            st.error("⛔ HTTP 429 — limite atingido.")
        else:
            st.warning(f"HTTP {code_ab}: {str(r_ab)[:200]}")
