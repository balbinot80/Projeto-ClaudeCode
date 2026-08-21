"""
Sync runner sem dependência do Streamlit.
Executa em background thread via FastAPI — sobrevive ao tab fechar.

Modos:
  'fast'  — só listas (pedidos, produtos, revendedoras, categorias)
             Suficiente para o dashboard. ~2-5 min.
  'full'  — listas + detalhes de pedidos abertos + baixados recentes
             Necessário para telas de Estoque e Compras. ~10-30 min.
             Inteligente: só busca os IDs ainda não no cache.
"""
import os
import sys
import time
import threading
from pathlib import Path
from datetime import datetime, timedelta, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

import requests

# Supabase — _get_client() tenta st.secrets e cai em os.getenv se não encontrar
from src.api.cache_supabase import (
    escrever_cache,
    escrever_cache_pedidos,
    ler_cache_pedidos_batch,
)

# ── Config Jueri ──────────────────────────────────────────────────────────────

BASE_URL = os.getenv("JUERI_BASE_URL", "https://aureumjoias.jueri.com.br/sis/api/v1/4216")
TOKEN    = os.getenv("JUERI_TOKEN", "")


def _nova_sessao() -> requests.Session:
    s = requests.Session()
    s.headers.update({"Authorization": f"Bearer {TOKEN}", "Accept": "application/json"})
    return s


def _req(sess: requests.Session, endpoint_ou_url: str, params: dict = None) -> dict:
    url = endpoint_ou_url if endpoint_ou_url.startswith("http") else f"{BASE_URL}/{endpoint_ou_url}"
    for tentativa in range(4):
        try:
            resp = sess.get(url, params=params or {}, timeout=30)
            if resp.status_code == 429:
                espera = 8 * (tentativa + 1)  # 8s, 16s, 24s, 32s
                time.sleep(espera)
                continue
            resp.raise_for_status()
            return resp.json()
        except requests.exceptions.Timeout:
            if tentativa == 3:
                raise
            time.sleep(3)
        except requests.exceptions.RequestException:
            if tentativa == 3:
                raise
            time.sleep(3 * (tentativa + 1))
    raise RuntimeError("Falha após 4 tentativas")


def _paginar(sess: requests.Session, endpoint: str, params: dict = None, on_page=None) -> list:
    """Percorre todas as páginas do endpoint paginado."""
    p = dict(params or {})
    p["page"] = 1
    results = []
    while True:
        data = _req(sess, endpoint, p)
        results.extend(data.get("data", []))
        total = data.get("last_page", 1)
        if on_page:
            on_page(p["page"], total)
        if not data.get("next_page_url"):
            break
        p["page"] += 1
    return results


def _detalhe_pedido(sess: requests.Session, pedido_id: int) -> dict:
    """Busca detalhes de um pedido (thread-safe — usa sessão já criada)."""
    try:
        data = _req(sess, f"pedido/{pedido_id}")
        reg = data.get("data", data)
        if isinstance(reg, list):
            return reg[0] if reg else {}
        return reg if isinstance(reg, dict) else {}
    except Exception:
        return {}


def _buscar_detalhes_em_paralelo(
    sess: requests.Session,
    ids: list,
    on_progress=None,
    max_workers: int = 5,
) -> dict:
    """
    Busca detalhes de uma lista de IDs de pedidos.
    Verifica cache Supabase primeiro — só chama a API para os que faltam.
    """
    if not ids:
        return {}

    # Verifica quais já estão no Supabase (em lotes)
    cached = ler_cache_pedidos_batch(ids)
    ids_faltando = [pid for pid in ids if pid not in cached]

    resultado = dict(cached)
    total_faltando = len(ids_faltando)

    if not ids_faltando:
        if on_progress:
            on_progress(0, 0)
        return resultado

    novos: dict = {}
    done = 0

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futuros = {pool.submit(_detalhe_pedido, sess, pid): pid for pid in ids_faltando}
        for fut in as_completed(futuros):
            pid = futuros[fut]
            try:
                r = fut.result()
                if r:
                    novos[pid] = r
            except Exception:
                novos[pid] = {}
            done += 1
            if on_progress:
                on_progress(done, total_faltando)

    if novos:
        escrever_cache_pedidos(novos)
    resultado.update(novos)
    return resultado


# ── Estado global ─────────────────────────────────────────────────────────────

_state: dict = {
    "status":       "idle",     # idle | running | success | error
    "mode":         None,
    "progress":     0,          # 0-100
    "step":         "",
    "detail":       "",         # info extra (ex: "123/456 pedidos")
    "started_at":   None,
    "finished_at":  None,
    "counts":       {},
    "error":        None,
}
_lock = threading.Lock()
_thread: threading.Thread | None = None


def get_state() -> dict:
    with _lock:
        return dict(_state)


def _upd(**kw):
    with _lock:
        _state.update(kw)


def is_running() -> bool:
    with _lock:
        return _state["status"] == "running"


# ── Entry point ───────────────────────────────────────────────────────────────

def start_sync(mode: str = "fast") -> bool:
    """
    Inicia o sync em background thread.
    Retorna False se já estiver rodando.
    """
    global _thread
    with _lock:
        if _state["status"] == "running":
            return False
        _state.update({
            "status": "running", "mode": mode, "progress": 0,
            "step": "Iniciando…", "detail": "",
            "started_at": datetime.now(timezone.utc).isoformat(),
            "finished_at": None, "counts": {}, "error": None,
        })

    _thread = threading.Thread(target=_executar, args=(mode,), daemon=True)
    _thread.start()
    return True


# ── Sync principal ────────────────────────────────────────────────────────────

def _executar(mode: str):
    sess = _nova_sessao()
    counts: dict = {}

    try:
        # ── 1. Pedidos (lista) ────────────────────────────────────────────────
        _upd(progress=3, step="Buscando pedidos…", detail="")
        pedidos = _paginar(
            sess, "pedido", params={},
            on_page=lambda pg, tot: _upd(
                step=f"Pedidos — pág. {pg}/{tot}",
                progress=3 + int(pg / max(tot, 1) * 28),
            ),
        )
        escrever_cache("pedidos", pedidos)
        counts["pedidos"] = len(pedidos)
        _upd(progress=32, step=f"{len(pedidos)} pedidos salvos")

        # ── 2. Revendedoras ───────────────────────────────────────────────────
        _upd(progress=40, step="Buscando revendedoras…")
        revs = _paginar(
            sess, "revendedor", params={},
            on_page=lambda pg, tot: _upd(step=f"Revendedoras — pág. {pg}/{tot}"),
        )
        escrever_cache("revendedores_todos", revs)
        counts["revendedores"] = len(revs)
        _upd(progress=65, step=f"{len(revs)} revendedoras salvas")

        if mode == "fast":
            # Sync rápida encerra aqui
            _upd(
                status="success", progress=100,
                step=f"Sync rápida concluída! {len(pedidos)} pedidos · {len(revs)} revendedoras",
                counts=counts,
            )
            return

        # ── 5. Detalhes: pedidos abertos ──────────────────────────────────────
        abertos = [p for p in pedidos if p.get("status") == "Aberto" and p.get("id")]
        ids_abertos = [p["id"] for p in abertos]
        n_abertos = len(ids_abertos)

        _upd(progress=72, step=f"Detalhes de {n_abertos} pedidos abertos…",
             detail="Verificando cache…")

        def _prog_ab(done, total):
            if total:
                _upd(
                    progress=72 + int(done / total * 12),
                    detail=f"{done + (n_abertos - total)}/{n_abertos}",
                )

        _buscar_detalhes_em_paralelo(sess, ids_abertos, on_progress=_prog_ab, max_workers=5)
        counts["detalhes_abertos"] = n_abertos
        _upd(progress=84, step=f"Detalhes abertos ✓")

        # ── 6. Detalhes: baixados (últimos 90 dias — reduzido de 180) ─────────
        corte = datetime.today() - timedelta(days=90)
        baixados_recentes = []
        for p in pedidos:
            if p.get("status") != "Baixado":
                continue
            data_str = (p.get("data_baixa") or p.get("data_criacao") or "")[:10]
            try:
                if datetime.fromisoformat(data_str) >= corte:
                    baixados_recentes.append(p)
            except (ValueError, TypeError):
                pass

        ids_baixados = [p["id"] for p in baixados_recentes if p.get("id")]
        n_baixados = len(ids_baixados)
        _upd(progress=85, step=f"Detalhes de {n_baixados} pedidos baixados (90d)…",
             detail="Verificando cache…")

        def _prog_bx(done, total):
            if total:
                _upd(
                    progress=85 + int(done / total * 12),
                    detail=f"{done + (n_baixados - total)}/{n_baixados}",
                )

        _buscar_detalhes_em_paralelo(sess, ids_baixados, on_progress=_prog_bx, max_workers=5)
        counts["detalhes_baixados"] = n_baixados

        _upd(
            status="success", progress=100,
            step=(
                f"Sync completa! {len(pedidos)} pedidos · "
                f"{n_abertos} abertos · {n_baixados} baixados (90d)"
            ),
            counts=counts,
        )

    except Exception as e:
        _upd(status="error", step="Erro durante sincronização", error=str(e))

    finally:
        with _lock:
            _state["finished_at"] = datetime.now(timezone.utc).isoformat()


# ── Modo script ───────────────────────────────────────────────────────────────
# python web/sync_runner.py [fast|full]

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Aureum sync runner")
    parser.add_argument("mode", nargs="?", default="fast", choices=["fast", "full"])
    args = parser.parse_args()

    print(f"Iniciando sync {args.mode}…")
    start_sync(args.mode)

    while True:
        state = get_state()
        print(f"  [{state['progress']:3d}%] {state['step']}", end="")
        if state["detail"]:
            print(f"  ({state['detail']})", end="")
        print()
        if state["status"] in ("success", "error"):
            if state["error"]:
                print(f"\nERRO: {state['error']}")
            break
        time.sleep(2)
