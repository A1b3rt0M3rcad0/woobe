#!/usr/bin/env python3
"""Audit complete roadmap coverage and reproducibly render its delivery assessment."""
import collections, json, pathlib, re, sys
root = pathlib.Path(__file__).resolve().parent.parent
plan = (root / 'docs/PLAN.md').read_text().split('## 18. Roadmap de implantação')[1].split('### 18.1.')[0]
expected = {}
for phase, part in enumerate(re.split(r'### Fase \d+ — ', plan)[1:]):
    for number, text in enumerate(re.findall(r'^- \[ \] (.*)', part, re.M), 1):
        expected[f'{phase}.{number}'] = text
ledger = json.loads((root / 'docs/COMPLETENESS.json').read_text())
items = ledger['items']
assert len(items) == len(expected) == 101
assert len({item['id'] for item in items}) == len(items)
for item in items:
    assert expected[item['id']] == item['requirement']
    assert item['status'] in ('done', 'partial', 'pending') and item['evidence']
counts = collections.Counter(item['status'] for item in items)
percentage = 100 * counts['done'] / len(items)
lines = ['# Completude do planejamento integral', '',
         'Auditoria histórica do roadmap original de 101 itens. A nova skill de terminal é uma entrega adicional; veja [STATUS.md](STATUS.md) e [AGENT_SKILL.md](AGENT_SKILL.md) para o estado atual. Este percentual não mede essa entrega nem certifica produção.', '',
         f"**{percentage:.1f}% — {counts['done']}/{len(items)} entregas concluídas; {counts['partial']} parciais e {counts['pending']} pendentes.**", '',
         'Base: todas as 101 entregas das fases 0–9 do §18 de PLAN.md, com peso igual. Concluída=1; parcial=0; pendente=0. A classificação é uma avaliação de engenharia com evidência por item, não estimativa de esforço, cobertura de código ou certificação de produção.', '',
         'O denominador inclui backend, CLI, documentação e distribuição. Concluída significa implementação entregue no boundary indicado; evidências de API real/E2E estão registradas por item e no PR do backend. Nenhuma das 10 fases tem seu aceite integral verificado contra todos os seus critérios.', '',
         '| Fase | Concluídas | Parciais | Pendentes | Entregas concluídas |',
         '| --- | --- | --- | --- | --- |']
for phase in range(10):
    phase_items = [item for item in items if item['phase'] == phase]
    c = collections.Counter(item['status'] for item in phase_items)
    lines.append(f"| {phase} | {c['done']} | {c['partial']} | {c['pending']} | {c['done']}/{len(phase_items)} |")
lines += ['', '## Avaliação item a item', '', '| ID | Entrega | Estado | Evidência / limite |', '| --- | --- | --- | --- |']
for item in items:
    values = [item['id'], item['requirement'], {'done':'concluída','partial':'parcial','pending':'pendente'}[item['status']], item['evidence']]
    lines.append('| ' + ' | '.join(str(value).replace('|', '\\|') for value in values) + ' |')
rendered = '\n'.join(lines) + '\n'
path = root / 'docs/COMPLETENESS.md'
if '--write' in sys.argv:
    path.write_text(rendered)
else:
    assert path.read_text() == rendered, 'Run python3 scripts/completeness.py --write'
print(json.dumps(dict(total=len(items), **counts, completed_percent=round(percentage, 1))))
