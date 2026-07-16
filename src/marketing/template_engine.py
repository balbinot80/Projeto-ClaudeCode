"""
Motor de geração de artes para Stories (1080×1920) usando Pillow.
Três templates: Creme Dourado, Escuro Luxo, Rosa Vibrante.
"""

from __future__ import annotations

import io
import os
from pathlib import Path
from typing import Optional

import requests
from PIL import Image, ImageDraw, ImageFilter, ImageFont

# ── Paths ─────────────────────────────────────────────────────────────────────
_ASSETS = Path(__file__).parent.parent.parent / "assets"
_FONTS  = _ASSETS / "fonts"
_LOGO_ROSA    = _ASSETS / "Logo rosa.png"
_LOGO_BRANCO  = _ASSETS / "Logo branco.png"
_PATTERN_ROSA = _ASSETS / "Pattern rosa.png"
_SUBMARCA_BRANCA = _ASSETS / "Submarca branca.png"

# ── Cores da marca ─────────────────────────────────────────────────────────────
ROSA    = (171, 103, 116)       # #AB6774
DOURADO = (196, 152, 90)        # #C4985A
CREME   = (250, 247, 244)       # #FAF7F4
ESCURO  = (26, 10, 16)          # #1A0A10
BRANCO  = (255, 255, 255)

# ── Tamanho do canvas ─────────────────────────────────────────────────────────
W, H = 1080, 1920


# ── Helpers de fonte ──────────────────────────────────────────────────────────
def _font(name: str, size: int) -> ImageFont.FreeTypeFont:
    candidates = [
        str(_FONTS / name),
        # fallbacks Linux (Streamlit Cloud)
        f"/usr/share/fonts/truetype/liberation/Liberation{name.split('-')[0]}-{name.split('-')[1].replace('.ttf','')+'.ttf' if '-' in name else 'Regular.ttf'}",
        f"/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for path in candidates:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue
    return ImageFont.load_default()


def _font_titulo(size: int = 90):
    return _font("Georgia-Bold.ttf", size)


def _font_subtitulo(size: int = 46):
    return _font("Georgia-Regular.ttf", size)


def _font_body(size: int = 44):
    return _font("Calibri-Regular.ttf", size)


def _font_body_bold(size: int = 50):
    return _font("Calibri-Bold.ttf", size)


# ── Helpers visuais ───────────────────────────────────────────────────────────
def _baixar_imagem(url: str) -> Optional[Image.Image]:
    try:
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        img = Image.open(io.BytesIO(r.content)).convert("RGBA")
        return img
    except Exception:
        return None


def _redimensionar_produto(img: Image.Image, size: int) -> Image.Image:
    """Recorta e redimensiona a foto do produto para um quadrado."""
    img = img.convert("RGBA")
    lado = min(img.size)
    esq = (img.width  - lado) // 2
    top = (img.height - lado) // 2
    img = img.crop((esq, top, esq + lado, top + lado))
    return img.resize((size, size), Image.LANCZOS)


def _cantos_arredondados(img: Image.Image, raio: int = 40) -> Image.Image:
    mask = Image.new("L", img.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, *img.size], radius=raio, fill=255)
    resultado = img.copy().convert("RGBA")
    resultado.putalpha(mask)
    return resultado


def _sombra(img: Image.Image, offset: int = 18, blur: int = 20, alpha: int = 80) -> Image.Image:
    """Adiciona sombra sob a imagem."""
    shadow = Image.new("RGBA", (img.width + blur * 2, img.height + blur * 2), (0, 0, 0, 0))
    mask = Image.new("L", img.size, alpha)
    shadow.paste(Image.new("RGBA", img.size, (0, 0, 0, alpha)), (blur, blur), mask)
    shadow = shadow.filter(ImageFilter.GaussianBlur(radius=blur // 2))
    result = Image.new("RGBA", shadow.size, (0, 0, 0, 0))
    result.paste(shadow, (0, 0))
    result.paste(img, (blur - offset // 2, blur - offset // 2), img)
    return result


def _logo(nome_arquivo: str, largura: int) -> Optional[Image.Image]:
    path = _ASSETS / nome_arquivo
    if not path.exists():
        return None
    img = Image.open(path).convert("RGBA")
    ratio = largura / img.width
    nova_altura = int(img.height * ratio)
    return img.resize((largura, nova_altura), Image.LANCZOS)


def _colar_centralizado(canvas: Image.Image, elemento: Image.Image, y: int):
    x = (canvas.width - elemento.width) // 2
    canvas.paste(elemento, (x, y), elemento)


def _texto_centralizado(
    draw: ImageDraw.ImageDraw,
    texto: str,
    y: int,
    font: ImageFont.FreeTypeFont,
    cor: tuple,
    largura_max: int = W - 80,
):
    """Quebra o texto se necessário e centraliza horizontalmente."""
    palavras = texto.split()
    linhas, linha_atual = [], ""
    for palavra in palavras:
        teste = f"{linha_atual} {palavra}".strip()
        bbox = draw.textbbox((0, 0), teste, font=font)
        if bbox[2] - bbox[0] <= largura_max:
            linha_atual = teste
        else:
            if linha_atual:
                linhas.append(linha_atual)
            linha_atual = palavra
    if linha_atual:
        linhas.append(linha_atual)

    for linha in linhas:
        bbox = draw.textbbox((0, 0), linha, font=font)
        x = (W - (bbox[2] - bbox[0])) // 2
        draw.text((x, y), linha, font=font, fill=cor)
        y += bbox[3] - bbox[1] + 10
    return y


def _gradiente_vertical(w: int, h: int, cor1: tuple, cor2: tuple, alpha1: int = 255, alpha2: int = 255) -> Image.Image:
    img = Image.new("RGBA", (w, h))
    for i in range(h):
        t = i / h
        r = int(cor1[0] * (1 - t) + cor2[0] * t)
        g = int(cor1[1] * (1 - t) + cor2[1] * t)
        b = int(cor1[2] * (1 - t) + cor2[2] * t)
        a = int(alpha1 * (1 - t) + alpha2 * t)
        for j in range(w):
            img.putpixel((j, i), (r, g, b, a))
    return img


def _preco_str(preco: float | None) -> str:
    if preco is None:
        return ""
    return f"R$ {preco:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


# ── Template 1 — Creme & Dourado ─────────────────────────────────────────────
def template_creme(produto_img_url: str, nome_produto: str, preco: float | None, ocasiao: dict) -> Image.Image:
    canvas = Image.new("RGB", (W, H), CREME)
    draw   = ImageDraw.Draw(canvas)

    # Faixa superior rosa
    draw.rectangle([0, 0, W, 320], fill=ROSA)

    # Título da ocasião
    ft_titulo = _font_titulo(100)
    ft_sub    = _font_subtitulo(46)
    y = 60
    y = _texto_centralizado(draw, ocasiao["titulo_principal"].upper(), y, ft_titulo, BRANCO)
    y = _texto_centralizado(draw, ocasiao["subtitulo"], y + 10, ft_sub, (255, 235, 235))

    # Linha dourada separadora
    draw.rectangle([60, 310, W - 60, 318], fill=DOURADO)

    # Foto do produto
    prod_img = _baixar_imagem(produto_img_url)
    if prod_img:
        tamanho = 860
        prod = _redimensionar_produto(prod_img, tamanho)
        prod = _cantos_arredondados(prod, raio=32)
        prod_shadow = _sombra(prod, offset=12, blur=24, alpha=60)
        x_prod = (W - prod_shadow.width) // 2
        y_prod = 360
        canvas.paste(prod_shadow, (x_prod, y_prod), prod_shadow)
    else:
        y_prod = 360
        tamanho = 860
        draw.rounded_rectangle([60, y_prod, W - 60, y_prod + tamanho], radius=32, fill=(230, 225, 220))

    # Linha dourada inferior
    y_info = y_prod + tamanho + 60 + (48 if not prod_img else 0)
    draw.rectangle([60, y_info, W - 60, y_info + 3], fill=DOURADO)
    y_info += 30

    # Nome do produto
    ft_nome  = _font_body_bold(54)
    ft_preco = _font_titulo(70)
    y_info = _texto_centralizado(draw, nome_produto.upper(), y_info, ft_nome, ESCURO)
    y_info += 16

    # Preço
    if preco:
        y_info = _texto_centralizado(draw, _preco_str(preco), y_info, ft_preco, ROSA)

    # Faixa inferior rosa
    draw.rectangle([0, H - 180, W, H], fill=ROSA)

    # Logo branco no rodapé
    logo = _logo("Logo branco.png", 220)
    if logo:
        _colar_centralizado(canvas.convert("RGBA"), logo, H - 155)
        canvas = canvas.convert("RGBA")
        canvas.paste(logo, ((W - logo.width) // 2, H - 155), logo)
        canvas = canvas.convert("RGB")

    return canvas


# ── Template 2 — Escuro & Luxo ───────────────────────────────────────────────
def template_escuro(produto_img_url: str, nome_produto: str, preco: float | None, ocasiao: dict) -> Image.Image:
    canvas = Image.new("RGB", (W, H), ESCURO)
    draw   = ImageDraw.Draw(canvas)

    # Gradiente sutil de rosa escuro para escuro
    grad = _gradiente_vertical(W, H // 2, (60, 20, 30), ESCURO, 200, 255)
    canvas.paste(grad.convert("RGB"), (0, 0))

    # Linha dourada decorativa no topo
    draw.rectangle([0, 0, W, 6], fill=DOURADO)

    # Título
    ft_titulo = _font_titulo(95)
    ft_sub    = _font_subtitulo(44)
    y = 60
    y = _texto_centralizado(draw, ocasiao["titulo_principal"].upper(), y, ft_titulo, (*DOURADO, 255))
    y = _texto_centralizado(draw, ocasiao["subtitulo"], y + 12, ft_sub, (200, 170, 140))

    # Linha dourada separadora
    draw.rectangle([120, y + 20, W - 120, y + 23], fill=DOURADO)

    # Foto do produto — com brilho
    prod_img = _baixar_imagem(produto_img_url)
    if prod_img:
        tamanho = 880
        prod = _redimensionar_produto(prod_img, tamanho)
        prod = _cantos_arredondados(prod, raio=24)
        # Overlay de brilho (levemente mais brilhante)
        brilho = Image.new("RGBA", prod.size, (255, 240, 200, 20))
        prod_rgba = prod.convert("RGBA")
        prod_rgba.alpha_composite(brilho)
        x_prod = (W - prod_rgba.width) // 2
        y_prod = y + 60
        canvas_rgba = canvas.convert("RGBA")
        canvas_rgba.paste(prod_rgba, (x_prod, y_prod), prod_rgba)
        canvas = canvas_rgba.convert("RGB")
        draw   = ImageDraw.Draw(canvas)
    else:
        y_prod = y + 60
        tamanho = 880
        draw.rounded_rectangle([60, y_prod, W - 60, y_prod + tamanho], radius=24, fill=(50, 30, 35))

    # Gradiente inferior (escuro para muito escuro)
    grad_bot = _gradiente_vertical(W, 400, ESCURO, (10, 3, 6), 200, 255)
    canvas.paste(grad_bot.convert("RGB"), (0, H - 400))
    draw = ImageDraw.Draw(canvas)

    # Linha dourada
    draw.rectangle([60, H - 400, W - 60, H - 397], fill=DOURADO)

    # Nome e preço
    ft_nome  = _font_body_bold(52)
    ft_preco = _font_titulo(75)
    y_info   = H - 380
    y_info   = _texto_centralizado(draw, nome_produto.upper(), y_info, ft_nome, BRANCO)
    y_info   += 14
    if preco:
        y_info = _texto_centralizado(draw, _preco_str(preco), y_info, ft_preco, DOURADO)

    # Logo branco
    draw.rectangle([0, H - 6, W, H], fill=DOURADO)
    logo = _logo("Logo branco.png", 200)
    if logo:
        canvas_rgba = canvas.convert("RGBA")
        canvas_rgba.paste(logo, ((W - logo.width) // 2, H - logo.height - 24), logo)
        canvas = canvas_rgba.convert("RGB")

    return canvas


# ── Template 3 — Rosa Vibrante ────────────────────────────────────────────────
def template_rosa(produto_img_url: str, nome_produto: str, preco: float | None, ocasiao: dict) -> Image.Image:
    canvas = Image.new("RGB", (W, H), ROSA)
    draw   = ImageDraw.Draw(canvas)

    # Gradiente de variação de rosa
    grad = _gradiente_vertical(W, H, (200, 130, 140), (140, 70, 85), 255, 255)
    canvas.paste(grad.convert("RGB"), (0, 0))
    draw = ImageDraw.Draw(canvas)

    # Pattern como overlay (se disponível)
    if _PATTERN_ROSA.exists():
        pat = Image.open(_PATTERN_ROSA).convert("RGBA")
        pat = pat.resize((W, H), Image.LANCZOS)
        pat_dim = pat.copy()
        # Reduz opacidade para 12%
        r, g, b, a = pat_dim.split()
        a = a.point(lambda x: int(x * 0.12))
        pat_dim.putalpha(a)
        canvas_rgba = canvas.convert("RGBA")
        canvas_rgba.alpha_composite(pat_dim)
        canvas = canvas_rgba.convert("RGB")
        draw = ImageDraw.Draw(canvas)

    # Título em branco
    ft_titulo = _font_titulo(95)
    ft_sub    = _font_subtitulo(46)
    y = 70
    y = _texto_centralizado(draw, ocasiao["titulo_principal"].upper(), y, ft_titulo, BRANCO)
    y = _texto_centralizado(draw, ocasiao["subtitulo"], y + 12, ft_sub, (255, 235, 235))

    # Foto com borda branca e sombra
    prod_img = _baixar_imagem(produto_img_url)
    if prod_img:
        tamanho = 840
        prod = _redimensionar_produto(prod_img, tamanho)
        # Borda branca
        borda = 14
        prod_borda = Image.new("RGBA", (tamanho + borda * 2, tamanho + borda * 2), (255, 255, 255, 255))
        prod_rgba  = _cantos_arredondados(prod.convert("RGBA"), raio=28)
        prod_borda_r = _cantos_arredondados(prod_borda, raio=36)
        prod_borda_r.paste(prod_rgba, (borda, borda), prod_rgba)
        prod_shadow = _sombra(prod_borda_r, offset=14, blur=22, alpha=100)
        x_prod = (W - prod_shadow.width) // 2
        y_prod = y + 55
        canvas_rgba = canvas.convert("RGBA")
        canvas_rgba.paste(prod_shadow, (x_prod, y_prod), prod_shadow)
        canvas = canvas_rgba.convert("RGB")
        draw   = ImageDraw.Draw(canvas)
        altura_total_prod = prod_shadow.height
    else:
        y_prod = y + 55
        tamanho = 840
        borda   = 14
        altura_total_prod = tamanho + borda * 2 + 48
        draw.rounded_rectangle(
            [60 - borda, y_prod, W - 60 + borda, y_prod + tamanho + borda * 2],
            radius=36, fill=(255, 255, 255, 200),
        )

    # Linha branca decorativa
    y_info = y_prod + altura_total_prod + 35
    draw.rectangle([80, y_info, W - 80, y_info + 2], fill=(255, 255, 255, 180))
    y_info += 28

    # Nome e preço em branco
    ft_nome  = _font_body_bold(52)
    ft_preco = _font_titulo(75)
    y_info   = _texto_centralizado(draw, nome_produto.upper(), y_info, ft_nome, BRANCO)
    y_info   += 14
    if preco:
        y_info = _texto_centralizado(draw, _preco_str(preco), y_info, ft_preco, (255, 240, 190))

    # Logo branco
    logo = _logo("Logo branco.png", 210)
    if logo:
        canvas_rgba = canvas.convert("RGBA")
        logo_y = max(y_info + 30, H - logo.height - 50)
        canvas_rgba.paste(logo, ((W - logo.width) // 2, logo_y), logo)
        canvas = canvas_rgba.convert("RGB")

    return canvas


# ── Função principal ──────────────────────────────────────────────────────────
def gerar_artes(
    produto_img_url: str,
    nome_produto: str,
    preco: float | None,
    ocasiao: dict,
) -> list[tuple[str, Image.Image]]:
    """
    Retorna lista de (nome_template, imagem_PIL) com os 3 templates gerados.
    """
    return [
        ("Creme & Dourado",  template_creme(produto_img_url, nome_produto, preco, ocasiao)),
        ("Escuro & Luxo",    template_escuro(produto_img_url, nome_produto, preco, ocasiao)),
        ("Rosa Vibrante",    template_rosa(produto_img_url, nome_produto, preco, ocasiao)),
    ]


def imagem_para_bytes(img: Image.Image, formato: str = "PNG") -> bytes:
    buf = io.BytesIO()
    img.save(buf, format=formato, quality=95)
    buf.seek(0)
    return buf.getvalue()
