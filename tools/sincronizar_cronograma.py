#!/usr/bin/env python3
"""Atualiza a cópia dos cronogramas dentro do app público (app/index.html) a partir
dos documentos do banco do artefato Minha Viagem Rodamoinho.

Uso: python3 tools/sincronizar_cronograma.py <pasta_com_cronograma/*.json> app/index.html

Regras (fixas, para nunca vazar nada):
- Só atualiza documentos que JÁ existem na cópia do app (lista abaixo é conferida contra ela).
- Nunca copia: e-mails da equipe, pastas privadas, ajustes da agenda (só os da ficha da viagem), documentos internos,
  agenda da planilha, nada do clipe.
- No controle de visibilidade, só mantém as pastas que o app conhece.
- Não mexe em nenhum outro trecho do arquivo. Sem mudança real => não grava nada.
"""
import json, re, sys, os, datetime

NUNCA = re.compile(r'(equipe-emails|pastas-privadas|-docs$|agenda-planilha|clipe)')
# notas-dia (v172, Daniel 28/10): a equipe do evento lê as notas do dia -> só as notas de cronogramas que o app JÁ tem, nunca do clipe
# ficha-overrides: só a parte "viagem" (ajustes de hotel/aviso feitos pelo dono, só das pastas que o app conhece)
# e "novos" (eventos que o dono adiciona direto no calendário).
# Os ajustes da agenda ("shows") nunca vão para o app.

def carregar(pasta):
    docs = {}
    base = os.path.join(pasta, 'cronograma') if os.path.isdir(os.path.join(pasta, 'cronograma')) else pasta
    for fn in os.listdir(base):
        if not fn.endswith('.json'):
            continue
        o = json.load(open(os.path.join(base, fn), encoding='utf-8'))
        docs['cronograma/' + fn[:-5]] = o.get('data', o) if isinstance(o, dict) and 'data' in o and 'id' in o else o
    return docs

def sem_data(x):
    return {k: v for k, v in x.items() if k != 'atualizadoEm'} if isinstance(x, dict) else x

def main():
    pasta, app = sys.argv[1], sys.argv[2]
    db = carregar(pasta)
    s = open(app, encoding='utf-8').read()
    m_snap = re.search(r'(var SNAP = )(\{.*?\})(;\n)', s, re.S)
    m_ret = re.search(r'(<script id="crono-retrato" type="application/json">)(.*?)(</script>)', s, re.S)
    if not m_snap or not m_ret:
        sys.exit('ERRO: não achei a cópia dos cronogramas no app')
    snap = json.loads(m_snap.group(2)); ret = json.loads(m_ret.group(2))
    wids = set(re.findall(r"^\s{4}(\w+): \{ ?id:", s, re.M)) | set(re.findall(r'^\s{4}(\w+): \{"id":', s, re.M))
    mudou = []
    if 'cronograma/notas-dia' in db:
        snap.setdefault('cronograma/notas-dia', {'notas': {}})
        ret.setdefault('cronograma/notas-dia', {'notas': {}})
    for k in sorted(snap):
        if NUNCA.search(k) or k not in db:
            continue
        novo = json.loads(json.dumps(db[k]))
        if k == 'cronograma/ficha-overrides':
            v = novo.get('viagem') if isinstance(novo.get('viagem'), dict) else {}
            nv = novo.get('novos') if isinstance(novo.get('novos'), dict) else {}
            co = novo.get('cardOculto') if isinstance(novo.get('cardOculto'), dict) else {}
            ce = novo.get('calEquipe') if isinstance(novo.get('calEquipe'), dict) else {}
            novo = {'atualizadoEm': novo.get('atualizadoEm', ''), 'viagem': {w: x for w, x in v.items() if w in wids}, 'novos': nv}
            ce = {k2: {'equipe': x['equipe'], 'em': x.get('em', '')} for k2, x in ce.items() if 'clipe' not in k2.lower() and isinstance(x, dict) and isinstance(x.get('equipe'), bool)}
            if ce:  # cadeado do calendário escolhido pelo dono (só exibição); clipe nunca vai ao app
                novo['calEquipe'] = ce
            if co:  # cards ocultos só da lista "Compromissos" (o evento segue no calendário): só a chave e a data do ajuste
                novo['cardOculto'] = {k2: {'em': (x or {}).get('em', '') if isinstance(x, dict) else ''} for k2, x in co.items()}
        if k == 'cronograma/notas-dia':
            conhecidos = {d for d in snap if d.startswith('cronograma/') and d != k}
            nt = novo.get('notas') if isinstance(novo.get('notas'), dict) else {}
            novo = {'notas': {ch: {'texto': str(x.get('texto', '')), 'em': str(x.get('em', ''))} for ch, x in nt.items()
                              if isinstance(x, dict) and ch.split('|')[0] in conhecidos and 'clipe' not in ch.lower() and str(x.get('texto', '')).strip()}}
        if k == 'cronograma/visibilidade' and isinstance(novo.get('liberados'), dict):
            novo['liberados'] = {w: v for w, v in novo['liberados'].items() if w in wids}
        if sem_data(novo) != sem_data(snap[k]):
            snap[k] = novo; mudou.append(k)
            if k in ret:
                ret[k] = novo
    if not mudou:
        print('SEM MUDANCAS'); return
    agora = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=-3)))
    ret['_em'] = agora.strftime('%d/%m %H:%M')
    s = s[:m_ret.start(2)] + json.dumps(ret, ensure_ascii=False) + s[m_ret.end(2):]
    m_snap = re.search(r'(var SNAP = )(\{.*?\})(;\n)', s, re.S)
    s = s[:m_snap.start(2)] + json.dumps(snap, ensure_ascii=False) + s[m_snap.end(2):]
    s = re.sub(r'window\.__mvSnapshotEm = "[^"]*";', 'window.__mvSnapshotEm = "%s";' % agora.strftime('%d/%m/%Y %H:%M'), s, count=1)
    if re.search(r'clipeteto|people-data-clipe', s):
        sys.exit('ERRO: conteúdo do clipe apareceu no app; nada gravado')
    open(app, 'w', encoding='utf-8').write(s)
    print('ATUALIZADO: ' + ', '.join(mudou))

if __name__ == '__main__':
    main()
