"""Deterministic reports preserving the boundary between facts and hypotheses."""
from __future__ import annotations
import copy
import html
import hashlib
import json
import shutil
import shlex
from pathlib import Path
from urd import __version__
from urd.analysis import analyze
from urd.model import sha256_file


def build_report(session: dict, *, visual: bool=False) -> dict:
    report = analyze(session)
    report.update(tool={'name':'VGI — Visual Game Intelligence','version':__version__},
                  metadata=copy.deepcopy(session['metadata']), provenance=copy.deepcopy(session['provenance']),
                  session_context={'events':copy.deepcopy(session['events']), 'captures':copy.deepcopy(session['captures'])},
                  reproduction={'command':'python -m vgi analyze '+shlex.quote(session['metadata'].get('manifest_file','session.json'))+(' --visual' if visual else '')+' --out NEW_OUTPUT_DIRECTORY',
                                'requirements':'Python >=3.10; same input bytes and VGI version; no network required',
                                'input_manifest':session['metadata'].get('manifest_file','session.json')},
                  _input_root=session.get('_input_root'))
    from urd.sources import correlate_sources
    report['source_correlations'] = correlate_sources(report)
    if visual:
        from urd.visual import analyze_visual
        report['visual'] = analyze_visual(session)
    return report


def _text(value) -> str:
    text = html.escape(str(value), quote=False)
    for char in ('\\','`','*','_','[',']','|','#'):
        text=text.replace(char,'\\'+char)
    return text.replace('\n',' ')


def markdown(report: dict) -> str:
    lines=['# VGI — Visual Game Intelligence', '',
           '**DADOS SINTÉTICOS — teste do software; nenhum resultado real do jogo.**' if report['synthetic'] else '**Evidência importada — origem declarada real pelo manifesto; autenticidade não verificada.**', '',
           f'Sessão: {_text(report["session_id"])}', f'Estado: {_text(report["status"])}', '',
           '## Evidências e incidentes', '']
    for incident in report['incidents']:
        lines += [f'### {_text(incident["id"])}', '',
                  f'Quadros: {_text(incident["frame_ids"])}. Intervalo monotônico local: {incident["start_ns"]}–{incident["end_ns"]} ns.',
                  f'Baseline: {incident["baseline_ms"]:.3f} ms; pico: {incident["peak_ms"]:.3f} ms; limiar: {incident["threshold_ms"]:.3f} ms.', '',
                  'Eventos associados (correlação temporal/identidade; causalidade não comprovada):', '']
        for item in incident.get('events',[]):
            event=item['event']; source=event.get('source',{})
            lines.append(f'- {_text(event["id"])} — {_text(event["kind"])}; {_text(item["association"])}; {_text(source.get("file","?"))}:{source.get("line","?")}; {_text(event.get("message",""))}')
        if not incident.get('events'): lines.append('Nenhum evento interno alinhado disponível.')
        lines += ['', 'Capturas associadas:', '']
        for item in incident.get('captures',[]):
            cap=item['capture']
            lines.append(f'- {_text(cap.get("relative_path",Path(cap["path"]).name))} — {_text(item["association"])}; quadro {_text(cap.get("frame_id"))}.')
            if cap.get('report_image'):
                lines += ['', f'![Captura de evidência]({cap["report_image"]})','']
        if not incident.get('captures'): lines.append('Nenhuma captura alinhada disponível.')
        lines += ['', 'Hipóteses — **Não comprovada**:', '']
        for hypothesis in incident.get('hypotheses',[]):
            lines.append(f'- {_text(hypothesis.get("claim",""))} Confiança: {_text(hypothesis.get("confidence","low"))}. Evidências: {_text(hypothesis.get("evidence_ids",[]))}. Próximo teste: {_text(hypothesis.get("next_test",""))}')
        for limitation in incident.get('limitations',[]): lines.append(f'- Limitação: {_text(limitation)}')
        lines.append('')
    if not report['incidents']:
        lines += ['Nenhuma queda relativa detectada com evidência suficiente; isto não comprova desempenho adequado.', '']
    lines += ['## Limitações e próximos passos', '',
              'Gargalo de hardware versus ineficiência do port: inconclusivo sem medições e experimentos controlados. Uso elevado de GPU, espera ou compilação correlacionada não prova causa.',
              'Repetir o mesmo trecho com as mesmas condições; mudar uma variável por vez; registrar build, driver, cache frio/quente, energia e frame generation.', '']
    for text in report.get('limitations',[])+report.get('warnings',[]): lines.append('- '+_text(text))
    if report.get('source_correlations'):
        lines += ['', '## Referências no código', '', 'Referências apontam à emissão da instrumentação inspecionada; não identificam código defeituoso nem comprovam a versão instalada.', '']
        for ref in report['source_correlations']:
            lines.append(f'- {_text(ref["evidence_id"])} → [emissão de {_text(ref["metric"])}]({ref["url"]})')
    if 'visual' in report:
        visual=report['visual']
        lines += ['', '## Análise visual', '', f'Estado: {_text(visual["status"])}. Candidatos visuais são indícios, não bugs confirmados.', '']
        for candidate in visual.get('candidates',[]):
            lines.append(f'- {_text(candidate["kind"])}; confiança {_text(candidate["confidence"])}; {_text(candidate["status"])}.')
            for evidence in candidate.get('evidence',[]):
                lines.append(f'  Quadro {_text(evidence.get("frame_id"))}; SHA256 {_text(evidence.get("sha256","ver entradas"))}.')
                if evidence.get('report_image'):
                    lines += ['', f'![Evidência do candidato visual]({evidence["report_image"]})','']
        for limitation in visual.get('limitations',[]): lines.append('- '+_text(limitation))
    lines += ['', '## Contexto da sessão', '',
              f'{len(report["session_context"]["events"])} evento(s) importado(s); somente os explicitamente associados acima pertencem ao incidente.',
              'O JSON preserva os eventos não alinhados e suas referências. Nomes de arquivos e mtime não são usados como relógio.', '',
              '## Reprodução', '', '```text', report['reproduction']['command'], '```', '',
              report['reproduction']['requirements'], '', 'Entradas (SHA256):', '']
    for entry in report['provenance']: lines.append(f'- {_text(entry["file"])} — sha256 `{entry["sha256"]}`')
    lines += ['', f'Ferramenta VGI {__version__} (experimental). Os parâmetros do detector estão no JSON. Não há chamadas externas automáticas.', '']
    return '\n'.join(lines)


def write_report(report: dict, directory: Path | str):
    root=Path(directory).resolve()
    source=report.get('_input_root')
    if source and (root==Path(source).resolve() or Path(source).resolve().is_relative_to(root)):
        raise ValueError('Output must not overwrite/contain the input evidence directory')
    if root.exists() and any(root.iterdir()):
        raise ValueError('Output directory is not empty; choose a new directory')
    root.mkdir(parents=True,exist_ok=True)
    result=copy.deepcopy(report)
    result.pop('_input_root',None)
    # One verified byte snapshot per evidence image; hash and copied bytes cannot diverge.
    captures=[]
    for incident in result['incidents']:
        captures.extend(item['capture'] for item in incident.get('captures', []))
    for candidate in result.get('visual', {}).get('candidates', []):
        captures.extend(candidate.get('evidence', []))
    expected_hashes={p['file']:p['sha256'] for p in result['provenance']}
    saved={}
    for capture in captures:
        path=Path(capture['path'])
        if str(path) not in saved:
            data=path.read_bytes()
            digest=hashlib.sha256(data).hexdigest()
            expected=expected_hashes.get(capture.get('relative_path'))
            if expected and expected!=digest:
                raise ValueError('Capture changed after import')
            if capture.get('sha256') and capture['sha256']!=digest:
                raise ValueError('Visual evidence changed after analysis')
            suffix=path.suffix.lower()
            dest=None
            if suffix in ('.png','.jpg','.jpeg','.ppm','.webp'):
                dest=Path('evidence')/(digest+suffix)
                (root/'evidence').mkdir(exist_ok=True)
                (root/dest).write_bytes(data)
            saved[str(path)]=dest.as_posix() if dest else None
        if saved[str(path)]:
            capture['report_image']=saved[str(path)]
    # Original paths in serialized records remain session-relative and portable.
    for capture in captures+result['session_context']['captures']:
        capture['path']=capture.get('relative_path',Path(capture['path']).name)
    (root/'report.json').write_text(json.dumps(result,indent=2,sort_keys=True,ensure_ascii=False,allow_nan=False)+'\n',encoding='utf-8')
    (root/'report.md').write_text(markdown(result),encoding='utf-8')
