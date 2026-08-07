import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
import requests
import streamlit as st
from dotenv import load_dotenv

load_dotenv()


def _ttl_dinamico() -> float:
    """
    Retorna o TTL de cache em horas baseado no horário atual (Brasília).

    Seg–Sex  08h–18h  →  1 hora  (horário comercial: dados frescos)
    Seg–Sex  fora      →  4 horas (madrugada / manhã cedo)
    Sab–Dom  qualquer  →  6 horas (fim de semana: dados mudam pouco)
    """
    try:
        from zoneinfo import ZoneInfo
        agora = datetime.now(ZoneInfo("America/Sao_Paulo"))
    except Exception:
        from datetime import timezone
        agora = datetime.now(timezone(timedelta(hours=-3)))

    dia_semana = agora.weekday()   # 0=seg … 4=sex, 5=sab, 6=dom
    hora       = agora.hour

    if dia_semana >= 5:            # fim de semana
        return 6.0
    if 8 <= hora < 18:             # dia útil, horário comercial
        return 1.0
    return 4.0                     # dia útil, fora do horário


def _get_secret(key: str, default: str = "") -> str:
    try:
        return st.secrets[key]
    except Exception:
        return os.getenv(key, default)


BASE_URL = _get_secret("JUERI_BASE_URL", "https://aureumjoias.jueri.com.br/sis/api/v1/4216")
TOKEN = _get_secret("JUERI_TOKEN", "")


@st.cache_resource
def _get_session() -> requests.Session:
    """Sessão HTTP reutilizada entre requisições (evita custo de handshake a cada chamada)."""
    s = requests.Session()
    s.headers.update({"Authorization": f"Bearer {TOKEN}", "Accept": "application/json"})
    return s


def _headers():
    return {"Authorization": f"Bearer {TOKEN}", "Accept": "application/json"}


def _req(endpoint_ou_url: str, params: dict = None) -> dict:
    url = endpoint_ou_url if endpoint_ou_url.startswith("http") else f"{BASE_URL}/{endpoint_ou_url}"
    session = _get_session()
    for tentativa in range(4):
        resp = session.get(url, params=params or {}, timeout=30)
        if resp.status_code == 429:
            time.sleep(10 * (tentativa + 1))
            continue
        resp.raise_for_status()
        return resp.json()
    raise requests.exceptions.HTTPError(
        "Limite de requisições atingido. Aguarde alguns minutos e atualize a página."
    )


def _get_all_pages(endpoint: str, params: dict = None, _status_placeholder=None) -> list:
    """Percorre todas as páginas usando next_page_url."""
    params = dict(params or {})
    params["page"] = 1
    results = []
    while True:
        data = _req(endpoint, params)
        results.extend(data.get("data", []))
        total_pages = data.get("last_page", 1)
        current_page = params["page"]
        if _status_placeholder and total_pages > 1:
            _status_placeholder.caption(
                f"Carregando dados... página {current_page} de {total_pages}"
            )
        if not data.get("next_page_url"):
            break
        params["page"] += 1
    return results


def _fetch_pedido_raw(pedido_id: int) -> dict:
    """Busca pedido individual direto na API Jueri (sem cache — para uso em threads)."""
    try:
        data = _req(f"pedido/{pedido_id}")
        registro = data.get("data", data)
        if isinstance(registro, list):
            return registro[0] if registro else {}
        return registro if isinstance(registro, dict) else {}
    except Exception:
        return {}


def _fetch_em_paralelo(pedido_ids: list, max_workers: int = 6) -> dict:
    """
    Busca detalhes de múltiplos pedidos.
    Estratégia em 3 camadas:
      1. st.cache_data (in-memory, por pedido individual — já via get_pedido_detalhado)
      2. Supabase cache (persistente entre restarts)
      3. Jueri API (para os que faltam — em paralelo com max_workers threads)
    """
    from src.api.cache_supabase import ler_cache_pedidos_batch, escrever_cache_pedidos

    # Camada 2: batch read do Supabase
    cached = ler_cache_pedidos_batch(pedido_ids)

    # IDs que não vieram do cache
    ids_faltando = [pid for pid in pedido_ids if pid not in cached]

    if ids_faltando:
        # Camada 3: Jueri API em paralelo para os que faltam
        novos: dict = {}
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futuros = {executor.submit(_fetch_pedido_raw, pid): pid for pid in ids_faltando}
            for futuro in as_completed(futuros):
                pid = futuros[futuro]
                try:
                    novos[pid] = futuro.result()
                except Exception:
                    novos[pid] = {}

        # Persiste no Supabase para as próximas requisições
        escrever_cache_pedidos(novos)
        cached.update(novos)

    return cached


# ── Produtos e categorias ──────────────────────────────────────────────────

@st.cache_data(ttl=3600)
def get_produtos(status: str = "1") -> list:
    from src.api.cache_supabase import ler_cache, escrever_cache
    chave = f"produtos_{status or 'todos'}"
    # Produtos mudam menos — usa o dobro do TTL dinâmico (mín 2h)
    ttl = max(_ttl_dinamico() * 2, 2.0)
    dados, _ = ler_cache(chave, max_idade_horas=ttl)
    if dados is not None:
        return dados
    resultado = _get_all_pages("produto", {"status": status} if status else {})
    escrever_cache(chave, resultado)
    return resultado


@st.cache_data(ttl=86400)
def get_categorias() -> dict:
    from src.api.cache_supabase import ler_cache, escrever_cache
    dados, _ = ler_cache("categorias", max_idade_horas=24.0)
    if dados is not None:
        # dados é lista; reconverte para dict
        if isinstance(dados, list):
            return {str(c.get("id")): c.get("descricao", f"Cat {c.get('id')}") for c in dados}
        return dados
    try:
        items = _get_all_pages("categoria_produto")
        escrever_cache("categorias", items)
        return {str(c.get("id")): c.get("descricao", f"Cat {c.get('id')}") for c in items}
    except Exception:
        return {}


# ── Pedidos ────────────────────────────────────────────────────────────────

@st.cache_data(ttl=3600)
def _get_ultima_atualizacao_pedidos() -> str:
    """Retorna o horário em que os pedidos foram buscados na API (horário de Brasília). Cache de 1h."""
    try:
        from zoneinfo import ZoneInfo
        from datetime import datetime
        return datetime.now(ZoneInfo("America/Sao_Paulo")).strftime("%d/%m/%Y às %H:%M")
    except Exception:
        from datetime import datetime, timezone, timedelta
        brt = timezone(timedelta(hours=-3))
        return datetime.now(brt).strftime("%d/%m/%Y às %H:%M")


@st.cache_data(ttl=3600, show_spinner=False)
def _get_lista_pedidos() -> list:
    """
    Todos os pedidos (resumo, sem itens por produto).
    Camadas de cache:
      1. st.cache_data (in-memory, TTL 1h)
      2. Supabase cache_jueri (persistente, TTL dinâmico por horário)
      3. Jueri API (fallback — lento, acionado só quando TTL expirar)
    TTL Supabase: 1h (seg–sex 8h–18h) · 4h (dias úteis fora do horário) · 6h (fim de semana)
    """
    from src.api.cache_supabase import ler_cache, escrever_cache
    dados, _ = ler_cache("pedidos", max_idade_horas=_ttl_dinamico())
    if dados is not None:
        return dados
    resultado = _get_all_pages("pedido")
    escrever_cache("pedidos", resultado)
    return resultado


def get_pedidos_abertos() -> list:
    return [p for p in _get_lista_pedidos() if p.get("status") == "Aberto"]


def get_pedidos_baixados() -> list:
    return [p for p in _get_lista_pedidos() if p.get("status") == "Baixado"]


@st.cache_data(ttl=3600)
def get_pedido_detalhado(pedido_id: int) -> dict:
    """Busca um pedido individual com seus itens (cache por ID)."""
    from src.api.cache_supabase import ler_cache_pedidos_batch, escrever_cache_pedidos
    cached = ler_cache_pedidos_batch([pedido_id])
    if pedido_id in cached:
        return cached[pedido_id]
    resultado = _fetch_pedido_raw(pedido_id)
    escrever_cache_pedidos({pedido_id: resultado})
    return resultado


@st.cache_data(ttl=1800)
def get_itens_pedidos_abertos() -> dict:
    """
    Retorna {produto_id: quantidade_na_rua}.
    Usa _fetch_em_paralelo que verifica Supabase antes de chamar a API.
    """
    abertos = get_pedidos_abertos()
    ids = [p["id"] for p in abertos if p.get("id")]
    if not ids:
        return {}

    detalhes_map = _fetch_em_paralelo(ids, max_workers=6)

    na_rua: dict = {}
    for pedido in abertos:
        detalhes = detalhes_map.get(pedido.get("id"), {})
        for item in detalhes.get("itens", []):
            prod_id = (item.get("produto") or {}).get("id")
            if prod_id:
                na_rua[prod_id] = na_rua.get(prod_id, 0) + float(item.get("quantidade") or 0)
    return na_rua


@st.cache_data(ttl=1800)
def get_itens_pedidos_baixados(dias: int = 180) -> list:
    """
    Lista de itens vendidos (pedidos baixados) nos últimos N dias.
    Usa _fetch_em_paralelo que verifica Supabase antes de chamar a API.
    """
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

    recentes.sort(
        key=lambda p: (p.get("data_baixa") or p.get("data_criacao") or ""),
        reverse=True,
    )

    ids = [p["id"] for p in recentes if p.get("id")]
    if not ids:
        return []

    detalhes_map = _fetch_em_paralelo(ids, max_workers=6)

    rows = []
    for pedido in recentes:
        pid = pedido.get("id")
        data_str = (pedido.get("data_baixa") or pedido.get("data_criacao") or "")[:10]
        try:
            data_pedido = datetime.fromisoformat(data_str)
        except (ValueError, TypeError):
            data_pedido = None

        detalhes = detalhes_map.get(pid, {})
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

@st.cache_data(ttl=3600)
def get_revendedores(status: str = None) -> list:
    from src.api.cache_supabase import ler_cache, escrever_cache
    chave = f"revendedores_{status or 'todos'}"
    # Cadastros de revendedoras mudam menos — usa TTL dinâmico * 2 (mín 2h)
    ttl = max(_ttl_dinamico() * 2, 2.0)
    dados, _ = ler_cache(chave, max_idade_horas=ttl)
    if dados is not None:
        return dados
    params = {}
    if status:
        params["status"] = status
    resultado = _get_all_pages("revendedor", params)
    escrever_cache(chave, resultado)
    return resultado


# ── Sincronização completa ─────────────────────────────────────────────────

def sincronizar_cache(status_fn=None) -> dict:
    """
    Busca dados frescos da API Jueri e atualiza todo o cache Supabase.
    Retorna dict com contagens do que foi sincronizado.

    status_fn: callable(str) opcional — recebe mensagens de progresso para exibir na UI.

    Depois de chamar esta função, execute st.cache_data.clear() para que a próxima
    leitura em memória use os dados frescos do Supabase.
    """
    from src.api.cache_supabase import escrever_cache, escrever_cache_pedidos

    def _log(msg: str):
        if status_fn:
            try:
                status_fn(msg)
            except Exception:
                pass

    resultado = {}

    # ── 1. Pedidos (lista completa) ───────────────────────────────────────
    _log("📦 Buscando todos os pedidos da API Jueri...")
    pedidos = _get_all_pages("pedido")
    escrever_cache("pedidos", pedidos)
    resultado["pedidos"] = len(pedidos)
    _log(f"✅ {len(pedidos)} pedidos salvos no Supabase.")

    # ── 2. Produtos ───────────────────────────────────────────────────────
    _log("🛍️ Buscando produtos ativos...")
    produtos = _get_all_pages("produto", {"status": "1"})
    escrever_cache("produtos_1", produtos)
    resultado["produtos"] = len(produtos)
    _log(f"✅ {len(produtos)} produtos salvos.")

    # ── 3. Revendedores ───────────────────────────────────────────────────
    _log("👥 Buscando revendedoras...")
    revs = _get_all_pages("revendedor")
    escrever_cache("revendedores_todos", revs)
    resultado["revendedores"] = len(revs)
    _log(f"✅ {len(revs)} revendedoras salvas.")

    # ── 4. Categorias ─────────────────────────────────────────────────────
    _log("🏷️ Buscando categorias de produtos...")
    try:
        cats = _get_all_pages("categoria_produto")
        escrever_cache("categorias", cats)
        resultado["categorias"] = len(cats)
        _log(f"✅ {len(cats)} categorias salvas.")
    except Exception:
        resultado["categorias"] = 0
        _log("⚠️ Categorias: erro ao buscar — mantendo cache anterior.")

    # ── 5. Detalhes dos pedidos abertos (itens na rua) ────────────────────
    pedidos_abertos = [p for p in pedidos if p.get("status") == "Aberto"]
    ids_abertos = [p["id"] for p in pedidos_abertos if p.get("id")]
    if ids_abertos:
        _log(f"🔍 Buscando detalhes de {len(ids_abertos)} pedidos abertos (itens na rua)...")
        novos: dict = {}
        BATCH_THREADS = 8
        with ThreadPoolExecutor(max_workers=BATCH_THREADS) as executor:
            futuros = {executor.submit(_fetch_pedido_raw, pid): pid for pid in ids_abertos}
            ok = 0
            for futuro in as_completed(futuros):
                pid = futuros[futuro]
                try:
                    novos[pid] = futuro.result()
                    ok += 1
                except Exception:
                    novos[pid] = {}
                if ok % 20 == 0 and ok > 0:
                    _log(f"   …{ok}/{len(ids_abertos)} pedidos abertos buscados")
        escrever_cache_pedidos(novos)
        resultado["detalhes_abertos"] = len(novos)
        _log(f"✅ Detalhes de {len(novos)} pedidos abertos salvos.")

    # ── 6. Detalhes dos pedidos baixados recentes (últimos 180 dias) ──────
    corte = datetime.today() - timedelta(days=180)
    pedidos_recentes = []
    for p in pedidos:
        if p.get("status") != "Baixado":
            continue
        data_str = (p.get("data_baixa") or p.get("data_criacao") or "")[:10]
        try:
            if datetime.fromisoformat(data_str) >= corte:
                pedidos_recentes.append(p)
        except (ValueError, TypeError):
            pass

    ids_recentes = [p["id"] for p in pedidos_recentes if p.get("id")]
    if ids_recentes:
        _log(f"📊 Buscando detalhes de {len(ids_recentes)} pedidos baixados (últimos 180 dias)...")
        novos_b: dict = {}
        with ThreadPoolExecutor(max_workers=BATCH_THREADS) as executor:
            futuros = {executor.submit(_fetch_pedido_raw, pid): pid for pid in ids_recentes}
            ok = 0
            for futuro in as_completed(futuros):
                pid = futuros[futuro]
                try:
                    novos_b[pid] = futuro.result()
                    ok += 1
                except Exception:
                    novos_b[pid] = {}
                if ok % 50 == 0 and ok > 0:
                    _log(f"   …{ok}/{len(ids_recentes)} pedidos baixados buscados")
        escrever_cache_pedidos(novos_b)
        resultado["detalhes_baixados"] = len(novos_b)
        _log(f"✅ Detalhes de {len(novos_b)} pedidos baixados recentes salvos.")

    _log("🎉 Sincronização concluída!")
    return resultado


# ── Cache management ───────────────────────────────────────────────────────

def limpar_cache():
    """Limpa apenas o cache in-memory (st.cache_data). O Supabase não é afetado."""
    st.cache_data.clear()
