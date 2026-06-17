# Ranking gamificado — pódio + progresso

## CSS (injetar via st.markdown)

```css
.au-podio {
  display: flex; align-items: flex-end; justify-content: center;
  gap: 10px; padding: 20px 0 4px;
}
.au-podio-lugar {
  display: flex; flex-direction: column; align-items: center;
  background: #fff; border-radius: 14px 14px 0 0; padding: 16px 16px 10px;
  box-shadow: 0 4px 12px rgba(171,103,116,.1); min-width: 110px;
}
.au-podio-1 { padding-top: 28px; transform: translateY(-10px); }
.au-podio-avatar {
  width: 44px; height: 44px; border-radius: 50%;
  background: linear-gradient(135deg, #F5EBEC, #C89199);
  display: flex; align-items: center; justify-content: center;
  font-family: 'Cormorant Garamond', Georgia, serif;
  font-size: 16px; font-weight: 600; color: #AB6774;
}
.au-podio-1 .au-podio-avatar {
  width: 56px; height: 56px; font-size: 20px;
  border: 2px solid #C4985A;
}
.au-podio-nome {
  font-family: 'Jost', sans-serif; font-size: 12px; font-weight: 600;
  color: #2A1A1F; margin-top: 8px; text-align: center;
}
.au-podio-valor {
  font-family: 'Cormorant Garamond', Georgia, serif;
  font-size: 14px; color: #AB6774; font-weight: 600;
}
.au-podio-pos {
  font-family: 'Jost', sans-serif; font-size: 10px; font-weight: 600;
  letter-spacing: .05em; color: #7A6068; margin-top: 4px;
}
.au-podio-1 .au-podio-pos { color: #C4985A; }
.au-coroa { font-size: 14px; color: #C4985A; }

.au-barra-wrap {
  background: rgba(171,103,116,.1); border-radius: 999px;
  height: 5px; overflow: hidden; margin-top: 4px; flex: 1;
}
.au-barra-fill {
  height: 100%;
  background: linear-gradient(90deg, #E8D5A3, #C4985A);
  border-radius: 999px;
  transition: width .8s cubic-bezier(.22,1,.36,1);
}
.au-rank-item {
  display: flex; align-items: center; gap: 10px;
  background: #fff; border-radius: 10px; padding: 10px 14px;
  border: 1px solid rgba(171,103,116,.1); margin-bottom: 6px;
  transition: transform .15s ease;
}
.au-rank-item:hover { transform: translateX(3px); }
```

## HTML do pódio (gerar via Python f-string)

```python
def podio_html(top3: list) -> str:
    """top3: lista de (nome, valor) ordenada por valor decrescente"""
    ini = lambda n: "".join(w[0].upper() for w in n.split()[:2])
    pnome = lambda n: n.split()[0]
    _R = lambda v: f"R$ {v:,.2f}".replace(",","X").replace(".",",").replace("X",".")
    
    return f"""
    <div class="au-podio">
      <div class="au-podio-lugar" style="order:1">
        <div class="au-podio-avatar">{ini(top3[1][0])}</div>
        <div class="au-podio-nome">{pnome(top3[1][0])}</div>
        <div class="au-podio-valor">{_R(top3[1][1])}</div>
        <div class="au-podio-pos">2º lugar</div>
      </div>
      <div class="au-podio-lugar au-podio-1" style="order:2">
        <div class="au-coroa">✦</div>
        <div class="au-podio-avatar">{ini(top3[0][0])}</div>
        <div class="au-podio-nome">{pnome(top3[0][0])}</div>
        <div class="au-podio-valor">{_R(top3[0][1])}</div>
        <div class="au-podio-pos">1º lugar</div>
      </div>
      <div class="au-podio-lugar" style="order:3">
        <div class="au-podio-avatar">{ini(top3[2][0])}</div>
        <div class="au-podio-nome">{pnome(top3[2][0])}</div>
        <div class="au-podio-valor">{_R(top3[2][1])}</div>
        <div class="au-podio-pos">3º lugar</div>
      </div>
    </div>
    """
```

## Lista com barra de progresso (4º em diante)

```python
def rank_item_html(pos: int, nome: str, vendas: float, meta_tier: float, label_meta: str) -> str:
    ini = "".join(w[0].upper() for w in nome.split()[:2])
    pct = min(100, round(vendas / max(meta_tier, 0.01) * 100))
    _R = lambda v: f"R$ {v:,.2f}".replace(",","X").replace(".",",").replace("X",".")
    falta = max(0, meta_tier - vendas)
    return f"""
    <div class="au-rank-item">
      <span style="font-family:'Jost',sans-serif;font-size:11px;font-weight:600;color:#AB6774;width:22px">{pos}º</span>
      <div style="width:30px;height:30px;border-radius:50%;background:linear-gradient(135deg,#F5EBEC,#C89199);
           display:flex;align-items:center;justify-content:center;
           font-family:'Cormorant Garamond',serif;font-size:11px;font-weight:600;color:#AB6774;flex-shrink:0">
        {ini}
      </div>
      <div style="flex:1;min-width:0">
        <div style="font-family:'Jost',sans-serif;font-size:12px;font-weight:600;color:#2A1A1F">{nome}</div>
        <div style="display:flex;align-items:center;gap:6px;margin-top:3px">
          <div class="au-barra-wrap"><div class="au-barra-fill" style="width:{pct}%"></div></div>
          <span style="font-family:'Jost',sans-serif;font-size:10px;color:#7A6068;white-space:nowrap">
            {f"faltam {_R(falta)} p/ {label_meta}" if falta > 0 else f"✦ Meta {label_meta} atingida"}
          </span>
        </div>
      </div>
      <div style="font-family:'Cormorant Garamond',serif;font-size:15px;font-weight:600;color:#AB6774">{_R(vendas)}</div>
    </div>
    """
```

## Regra de uso

Sempre acompanhar o pódio com a lista de progresso individual. Pódio só comunica competição; barra de progresso comunica evolução pessoal. As duas juntas fazem a gamificação funcionar para todo o grupo.
