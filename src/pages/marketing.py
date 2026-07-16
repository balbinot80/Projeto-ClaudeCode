import io
import streamlit as st
import requests
from src.marketing.ocasioes import OCASIOES
from src.marketing.template_engine import gerar_artes, imagem_para_bytes
from src.api.jueri_client import BASE_URL, _headers


# ── Busca produtos no Jueri ────────────────────────────────────────────────────
@st.cache_data(ttl=3600, show_spinner=False)
def _buscar_produtos(termo: str) -> list[dict]:
    if not termo or len(termo) < 2:
        return []
    try:
        resp = requests.get(
            f"{BASE_URL}/produto",
            headers=_headers(),
            params={"search": termo, "status": "1"},
            timeout=12,
        )
        resp.raise_for_status()
        return resp.json().get("data", [])[:20]
    except Exception:
        return []


def _preco_varejo(produto: dict) -> float | None:
    for tp in (produto.get("tipo_preco") or []):
        if "varejo" in (tp.get("nome") or "").lower():
            v = tp.get("preco")
            return float(v) if v else None
    tipos = produto.get("tipo_preco") or []
    if tipos:
        v = tipos[0].get("preco")
        return float(v) if v else None
    return None


def _preco_fmt(preco: float | None) -> str:
    if preco is None:
        return "—"
    return f"R$ {preco:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


# ── Render principal ───────────────────────────────────────────────────────────
def render():
    st.markdown(
        """
        <style>
        .mkt-header {
            background: linear-gradient(135deg, #AB6774 0%, #C4985A 100%);
            padding: 28px 32px; border-radius: 16px; margin-bottom: 24px; color: white;
        }
        .mkt-header h1 { color: white; margin: 0; font-size: 1.8em; }
        .mkt-header p  { color: rgba(255,255,255,.85); margin: 6px 0 0; font-size: 1em; }
        .prod-card {
            border: 2px solid #f0e8ea; border-radius: 12px; padding: 12px;
            text-align: center; cursor: pointer; transition: border-color .2s;
            background: #FAF7F4;
        }
        .prod-card:hover { border-color: #AB6774; }
        .prod-card.selected { border-color: #AB6774; background: #f5ebec; }
        </style>
        <div class="mkt-header">
            <h1>🎨 Marketing — Criação de Artes</h1>
            <p>Crie posts para Stories e WhatsApp com as peças da Aureum</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ── Passo 1: Ocasião ──────────────────────────────────────────────────────
    st.markdown("### 1️⃣ Escolha a ocasião")

    opcoes_label = {k: f"{v['emoji']} {v['label']}" for k, v in OCASIOES.items()}
    ocasiao_key  = st.selectbox(
        "Ocasião",
        options=list(opcoes_label.keys()),
        format_func=lambda k: opcoes_label[k],
        index=0,
        label_visibility="collapsed",
    )
    ocasiao = OCASIOES[ocasiao_key]

    if ocasiao.get("data"):
        st.caption(f"📅 {ocasiao['data']}")

    st.divider()

    # ── Passo 2: Buscar produto ───────────────────────────────────────────────
    st.markdown("### 2️⃣ Busque e selecione a peça")

    col_busca, col_limpar = st.columns([4, 1])
    with col_busca:
        termo = st.text_input(
            "Buscar peça",
            placeholder="Digite a referência ou nome (ex: AN1640, anel, bracelete...)",
            label_visibility="collapsed",
            key="mkt_busca",
        )
    with col_limpar:
        if st.button("Limpar", use_container_width=True, key="mkt_limpar"):
            for k in ["mkt_busca", "mkt_produto_sel"]:
                st.session_state.pop(k, None)
            st.rerun()

    produtos = []
    if termo and len(termo.strip()) >= 2:
        with st.spinner("Buscando peças..."):
            produtos = _buscar_produtos(termo.strip())

    produto_sel = st.session_state.get("mkt_produto_sel")

    if produtos:
        st.caption(f"{len(produtos)} peça(s) encontrada(s). Clique para selecionar.")
        cols = st.columns(min(len(produtos), 4))
        for i, p in enumerate(produtos):
            with cols[i % 4]:
                ref   = p.get("referencia") or p.get("id", "")
                nome  = p.get("descricao") or ref
                preco = _preco_varejo(p)
                img   = p.get("imagem") or ""
                selecionado = produto_sel and produto_sel.get("id") == p.get("id")

                borda = "2px solid #AB6774" if selecionado else "2px solid #f0e8ea"
                fundo = "#f5ebec" if selecionado else "#FAF7F4"

                if img:
                    st.markdown(
                        f'<div style="border:{borda};border-radius:12px;padding:8px;'
                        f'background:{fundo};text-align:center">',
                        unsafe_allow_html=True,
                    )
                    st.image(img, use_container_width=True)
                    st.markdown(
                        f'<p style="font-size:.82em;font-weight:600;margin:4px 0 2px;color:#2A1A1F">'
                        f'{ref}</p>'
                        f'<p style="font-size:.78em;color:#7A6068;margin:0">{nome[:40]}</p>'
                        f'<p style="font-size:.85em;color:#AB6774;font-weight:700;margin:4px 0">'
                        f'{_preco_fmt(preco)}</p>',
                        unsafe_allow_html=True,
                    )
                    st.markdown("</div>", unsafe_allow_html=True)

                lbl_btn = "✅ Selecionado" if selecionado else "Selecionar"
                if st.button(lbl_btn, key=f"sel_{p.get('id')}_{i}", use_container_width=True):
                    st.session_state["mkt_produto_sel"] = p
                    st.rerun()
    elif termo and len(termo.strip()) >= 2:
        st.info("Nenhuma peça encontrada. Tente outro termo.")

    # Mostra produto selecionado
    if produto_sel:
        ref   = produto_sel.get("referencia") or str(produto_sel.get("id", ""))
        nome  = produto_sel.get("descricao") or ref
        preco = _preco_varejo(produto_sel)
        img   = produto_sel.get("imagem") or ""

        st.success(f"✅ **{ref}** — {nome} — {_preco_fmt(preco)}")

    st.divider()

    # ── Passo 3: Gerar artes ─────────────────────────────────────────────────
    st.markdown("### 3️⃣ Gerar as 3 artes")

    pode_gerar = produto_sel is not None
    if not pode_gerar:
        st.info("Selecione uma peça acima para liberar a geração de artes.")

    if pode_gerar:
        if st.button(
            "✨ Gerar 3 artes agora",
            type="primary",
            use_container_width=True,
            key="mkt_gerar",
        ):
            ref   = produto_sel.get("referencia") or str(produto_sel.get("id", ""))
            nome  = produto_sel.get("descricao") or ref
            preco = _preco_varejo(produto_sel)
            img   = produto_sel.get("imagem") or ""

            if not img:
                st.error("Esta peça não tem foto cadastrada no Jueri.")
            else:
                with st.spinner("Gerando artes... pode levar alguns segundos ⏳"):
                    try:
                        artes = gerar_artes(img, nome, preco, ocasiao)
                        st.session_state["mkt_artes"] = [
                            (titulo, imagem_para_bytes(art, "PNG"))
                            for titulo, art in artes
                        ]
                        st.session_state["mkt_nome_arquivo"] = (
                            f"{ocasiao['label'].replace(' ', '_')}_{ref}"
                        )
                    except Exception as e:
                        st.error(f"Erro ao gerar artes: {e}")
            st.rerun()

    # ── Resultado: prévia + download ─────────────────────────────────────────
    artes_geradas = st.session_state.get("mkt_artes")
    if artes_geradas:
        st.divider()
        st.markdown("### 🖼️ Artes geradas — baixe cada uma")
        st.caption("Formato Stories / WhatsApp (1080 × 1920 px) · PNG")

        cols = st.columns(len(artes_geradas))
        nome_base = st.session_state.get("mkt_nome_arquivo", "arte_aureum")

        for col, (titulo, png_bytes) in zip(cols, artes_geradas):
            with col:
                st.markdown(f"**{titulo}**")
                st.image(png_bytes, use_container_width=True)
                nome_arquivo = f"{nome_base}_{titulo.replace(' ', '_').replace('&', 'e')}.png"
                st.download_button(
                    "⬇️ Baixar",
                    data=png_bytes,
                    file_name=nome_arquivo,
                    mime="image/png",
                    use_container_width=True,
                    key=f"dl_{titulo}",
                )

        st.caption(
            f"💡 **Hashtags sugeridas para {ocasiao['label']}:** {ocasiao['hashtags']}"
        )
