import streamlit as st
import requests
import pandas as pd
from collections import Counter
from datetime import date
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


def _parse_date(s: str):
    if not s:
        return None
    try:
        return date.fromisoformat(str(s)[:10])
    except Exception:
        return None


def _tab_relatorio_contatos():
    from src.api.jueri_client import _get_lista_pedidos, get_revendedores

    st.subheader("📞 Revendedoras com maleta aberta — Contato")
    st.caption(
        "Revendedoras com **primeiro pedido anterior a junho de 2026** que possuem maleta em aberto. "
        "Ordenado da mais antiga para a mais nova na equipe."
    )

    corte = date(2026, 6, 1)
    hoje  = date.today()

    with st.spinner("Carregando pedidos e revendedoras..."):
        try:
            todos_pedidos = _get_lista_pedidos()
            revs          = get_revendedores()
        except Exception as e:
            st.error(f"Erro ao carregar dados: {e}")
            return

    rev_map = {str(r["id"]): r for r in revs}

    # Para cada revendedora: data do primeiro pedido e lista de pedidos abertos
    primeiro_pedido: dict[str, date] = {}
    abertos_por_rev: dict[str, list] = {}

    for p in todos_pedidos:
        rid = str(p.get("fk_revendedor_id") or "")
        if not rid:
            continue
        dc = _parse_date(p.get("data_criacao"))
        if dc:
            if rid not in primeiro_pedido or dc < primeiro_pedido[rid]:
                primeiro_pedido[rid] = dc
        if p.get("status") == "Aberto":
            abertos_por_rev.setdefault(rid, []).append(p)

    # Elegíveis: primeiro pedido antes de 06/2026 E tem pedido aberto agora
    rev_pedidos = {
        rid: abertos_por_rev[rid]
        for rid in abertos_por_rev
        if primeiro_pedido.get(rid, date(9999, 1, 1)) < corte
    }

    if not rev_pedidos:
        st.success("Nenhuma revendedora com primeiro pedido anterior a 06/2026 possui maleta em aberto.")
        return

    rows = []
    for rid, pedidos in rev_pedidos.items():
        rev = rev_map[rid]
        nome = (rev.get("nome") or "").strip() or f"Rev {rid}"

        # Telefone — tenta variações do campo "Telefone 1"
        fone = (
            rev.get("telefone_1") or
            rev.get("telefone1") or
            rev.get("Telefone 1") or
            rev.get("telefone 1") or
            rev.get("celular") or
            rev.get("telefone") or
            rev.get("fone") or
            "—"
        )

        # Meses na empresa = desde o primeiro pedido registrado
        data_entrada = primeiro_pedido.get(rid)
        if data_entrada:
            meses = (hoje.year - data_entrada.year) * 12 + (hoje.month - data_entrada.month)
        else:
            meses = None

        rows.append({
            "Nome completo":      nome,
            "Telefone":           str(fone).strip() if fone and fone != "—" else "—",
            "Meses na empresa":   meses,
            "Maletas abertas":    len(pedidos),
            "_data_entrada":      primeiro_pedido.get(rid, date(9999, 1, 1)),
        })

    df = (
        pd.DataFrame(rows)
        .sort_values("_data_entrada", ascending=True)
        .drop(columns=["_data_entrada"])
        .reset_index(drop=True)
    )

    col1, col2 = st.columns(2)
    col1.metric("Revendedoras encontradas", len(df))
    col2.metric("Total de maletas abertas", df["Maletas abertas"].sum())

    st.dataframe(
        df,
        hide_index=True,
        use_container_width=True,
        column_config={
            "Nome completo":    st.column_config.TextColumn("Nome completo",   width="large"),
            "Telefone":         st.column_config.TextColumn("Telefone",        width="medium"),
            "Meses na empresa": st.column_config.NumberColumn("Meses na equipe", width="small", format="%d meses"),
            "Maletas abertas":  st.column_config.NumberColumn("Maletas abertas",  width="small", format="%d"),
        },
    )

    # Aviso se alguma linha ficou sem telefone
    sem_fone = df[df["Telefone"] == "—"]
    if not sem_fone.empty:
        st.warning(
            f"⚠️ {len(sem_fone)} revendedora(s) sem telefone cadastrado: "
            + ", ".join(sem_fone["Nome completo"].tolist())
        )


def _tab_diagnostico_api():
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

    st.divider()
    st.subheader("4. Pedido BAIXADO — campos de quantidade (diagnóstico de nível)")
    st.caption("Usa a lista completa de pedidos (cacheada) para encontrar o primeiro Baixado e inspecionar seus campos.")

    try:
        from src.api.jueri_client import _get_lista_pedidos
        todos = _get_lista_pedidos()
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
        st.write("**Todos os campos do pedido baixado (resumo da lista):**")
        st.json(pedido_baixado)

        termos_qtd = ["qtd", "quant", "pec", "item", "inicial", "origin", "consign", "maleta"]
        campos_qtd = {k: v for k, v in pedido_baixado.items()
                      if any(x in k.lower() for x in termos_qtd)}
        st.write("**Campos relacionados a quantidade:**")
        st.json(campos_qtd if campos_qtd else {"(nenhum encontrado)": None})

        termos_val = ["valor", "preco", "total", "baixa", "pago", "cobrado", "acerto"]
        campos_val = {k: v for k, v in pedido_baixado.items()
                      if any(x in k.lower() for x in termos_val)}
        st.write("**Campos relacionados a valor monetário:**")
        st.json(campos_val if campos_val else {"(nenhum encontrado)": None})

        st.write("---")
        st.write(f"**Campos do endpoint individual `/pedido/{pid_bx}`:**")
        code_bx, r_bx = _get(f"pedido/{pid_bx}")
        if code_bx == 200 and isinstance(r_bx, dict):
            reg = r_bx.get("data", r_bx)
            if isinstance(reg, list) and reg:
                reg = reg[0]
            if isinstance(reg, dict):
                campos_qtd_ind = {k: v for k, v in reg.items()
                                  if any(x in k.lower() for x in ["qtd", "quant", "pec", "item"])}
                st.write("**Campos de quantidade (endpoint individual):**")
                st.json(campos_qtd_ind)
                campos_val_ind = {k: v for k, v in reg.items()
                                  if any(x in k.lower() for x in ["valor", "preco", "total", "baixa", "pago", "cobrado", "acerto"])}
                st.write("**Campos de valor monetário (endpoint individual):**")
                st.json(campos_val_ind)
                st.write("**Registro completo:**")
                st.json(reg)
        elif code_bx == 429:
            st.error("⛔ HTTP 429 — limite atingido.")

    st.divider()
    st.subheader("5. Pedido ABERTO individual — campos de pré-baixa")
    st.caption("Busca o primeiro pedido com status 'Aberto' e exibe todos os seus campos.")

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

    st.divider()
    st.subheader("6. Revendedor — todos os campos disponíveis")
    st.caption("Inspeciona o primeiro registro do endpoint `/revendedor` para verificar nomes de campos (telefone, data de entrada, etc.).")

    code_rev, r_rev = _get("revendedor", {"page": 1})
    if code_rev == 200 and isinstance(r_rev, dict):
        revs_data = r_rev.get("data", [])
        if revs_data:
            st.write("**Todos os campos do primeiro revendedor:**", list(revs_data[0].keys()))
            st.json(revs_data[0])
        else:
            st.warning("Nenhum revendedor retornado.")
    else:
        st.error(f"HTTP {code_rev}: {str(r_rev)[:200]}")

    st.divider()
    st.subheader("7. Teste de imagens de produtos")
    st.caption("Busca as fotos das peças BR2615, BR2614 e AN1640 diretamente do Jueri via parâmetro `search`.")

    refs_teste = ["BR2615", "BR2614", "AN1640"]
    cols = st.columns(len(refs_teste))

    for col, ref in zip(cols, refs_teste):
        code_img, r_img = _get("produto", {"search": ref})
        with col:
            st.markdown(f"**{ref}**")
            if code_img != 200 or not isinstance(r_img, dict):
                st.error(f"HTTP {code_img}")
                continue
            items = r_img.get("data", [])
            match = next(
                (p for p in items if (p.get("referencia") or "").upper() == ref),
                None,
            )
            if not match:
                st.warning("Não encontrado")
                continue
            st.caption(match.get("descricao") or "")
            img_url = match.get("imagem")
            if img_url:
                st.image(img_url, use_container_width=True)
                fotos_adicionais = match.get("fotos_adicionais") or []
                if fotos_adicionais:
                    st.caption(f"{len(fotos_adicionais)} foto(s) adicional(is)")
            else:
                st.info("Sem imagem cadastrada")


def render():
    st.header("🔍 Diagnóstico")

    tab_rel, tab_api = st.tabs(["📋 Relatório de Contatos", "🔧 Diagnóstico da API"])

    with tab_rel:
        _tab_relatorio_contatos()

    with tab_api:
        _tab_diagnostico_api()
