#!/usr/bin/env python3
"""VGI OoT Companion: non-invasive PresentMon importer, local run comparison, release watch.
Independent stdlib companion. Does not start/modify games, install software, or upload traces.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import statistics
import subprocess
import sys
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parent
RESULTS = ROOT / 'results'
WATCH_FILE = ROOT / 'updates' / 'last_seen.json'
SOURCES = {
    'Longshot (Recomper)': ('github', 'Recomper/Longshot', 'https://github.com/Recomper/Longshot/releases'),
    'Longshot (madebyjordan)': ('github', 'madebyjordan/Longshot', 'https://github.com/madebyjordan/Longshot/releases'),
    'NX2navi': ('github', 'tangerineturtle1/NX2navi', 'https://github.com/tangerineturtle1/NX2navi/releases'),
    'Ocarina Reborn': ('github', 'misterrageguy-cyber/OoT2026-PC-Recomp', 'https://github.com/misterrageguy-cyber/OoT2026-PC-Recomp/releases'),
    'Triforce': ('rss', 'https://git.triforceproject.com/triforce/downloads/releases.rss', 'https://git.triforceproject.com/triforce/downloads/releases'),
    'Hookshot': ('rss', 'https://git.notrexed.dev/Hookshot/Hookshot/releases.rss', 'https://git.notrexed.dev/Hookshot/Hookshot/releases'),
}
RECOMPS = ['Ocarina Reborn', 'Longshot (Recomper)', 'Longshot (madebyjordan)', 'NX2navi', 'Triforce', 'Hookshot']
HEADERS = {'User-Agent': 'VGI-OoT-Companion/0.1 (+local-read-only-update-check)', 'Accept': 'application/vnd.github+json, application/xml, text/xml, */*'}


def nice(s):
    return re.sub(r'[^a-zA-Z0-9_-]+', '-', s.lower()).strip('-')[:45] or 'run'


def roundf(x):
    return round(x, 3) if x is not None and math.isfinite(x) else None


def qtile(data, p):
    a = sorted(data)
    pos = (len(a) - 1) * p
    i = int(pos)
    return a[i] + (a[min(i + 1, len(a) - 1)] - a[i]) * (pos - i)


def fps_summary(intervals):
    if len(intervals) < 30:
        return None
    fps = sorted(1000.0 / x for x in intervals)
    k = max(1, math.ceil(len(fps) * 0.01))
    k01 = max(1, math.ceil(len(fps) * 0.001))
    total = math.fsum(intervals)
    return {
        'samples': len(intervals), 'recorded_seconds': roundf(total / 1000),
        'avg_fps': roundf(1000 * len(intervals) / total),
        'low_1pct_fps': roundf(statistics.mean(fps[:k])),
        'low_0_1pct_fps': roundf(statistics.mean(fps[:k01])),
        'p50_ms': roundf(qtile(intervals, .50)),
        'p95_ms': roundf(qtile(intervals, .95)),
        'p99_ms': roundf(qtile(intervals, .99)),
        'over_33ms_pct': roundf(100 * sum(x > 33.333 for x in intervals) / len(intervals)),
        'over_50ms_pct': roundf(100 * sum(x > 50 for x in intervals) / len(intervals)),
    }


def numeric(s):
    try:
        n = float(str(s).strip())
        return n if math.isfinite(n) and n > 0 else None
    except (ValueError, TypeError, OverflowError):
        return None


def find_field(cols, options):
    norm = {str(c).strip().lstrip('\ufeff').lower(): c for c in cols if c is not None}
    for name in options:
        if name.lower() in norm:
            return norm[name.lower()]
    return None


def parse_presentmon(path, expected_process=''):
    """Import a single-process single-swapchain trace; never silently mix processes.
    MsBetweenPresents: app present intervals, NOT delivered display FPS.
    MsBetweenDisplayChange: independent display intervals when available.
    """
    raw = Path(path).read_bytes()
    if len(raw) > 200_000_000:
        raise ValueError('CSV >200 MB; divida a captura para evitar consumo excessivo.')
    try:
        text = raw.decode('utf-8-sig')
    except UnicodeDecodeError as e:
        raise ValueError('CSV nao e UTF-8; exporte novamente com PresentMon.') from e
    reader = csv.DictReader(text.splitlines())
    if not reader.fieldnames:
        raise ValueError('CSV sem cabecalho.')
    app_key = find_field(reader.fieldnames, ('Application', 'ProcessName'))
    pid_key = find_field(reader.fieldnames, ('ProcessID', 'PID'))
    chain_key = find_field(reader.fieldnames, ('SwapChainAddress',))
    present_key = find_field(reader.fieldnames, ('MsBetweenPresents', 'msBetweenPresents'))
    display_key = find_field(reader.fieldnames, ('MsBetweenDisplayChange', 'msBetweenDisplayChange'))
    gpu_key = find_field(reader.fieldnames, ('MsGPUBusy', 'GPUBusy'))
    cpu_key = find_field(reader.fieldnames, ('MsCPUBusy', 'CPUBusy'))
    if present_key is None:
        raise ValueError('Coluna MsBetweenPresents ausente; CSV nao compativel com PresentMon 2.x. Colunas: ' + ', '.join(reader.fieldnames[:20]))
    groups = {}
    seen_process = set()
    for row in reader:
        if None in row:
            continue
        app = (row.get(app_key) or 'unknown').strip() if app_key else 'unknown'
        if expected_process and app.casefold() != expected_process.casefold():
            continue
        pid = (row.get(pid_key) or '') if pid_key else ''
        chain = (row.get(chain_key) or '') if chain_key else ''
        key = (app, pid, chain)
        seen_process.add(app)
        n = numeric(row.get(present_key))
        if n is None:
            continue
        group = groups.setdefault(key, {'present_ms': [], 'display_ms': [], 'gpu_busy_ms': [], 'cpu_busy_ms': []})
        group['present_ms'].append(n)
        if display_key and numeric(row.get(display_key)) is not None:
            group['display_ms'].append(numeric(row.get(display_key)))
        if gpu_key and numeric(row.get(gpu_key)) is not None:
            group['gpu_busy_ms'].append(numeric(row.get(gpu_key)))
        if cpu_key and numeric(row.get(cpu_key)) is not None:
            group['cpu_busy_ms'].append(numeric(row.get(cpu_key)))
    if not groups:
        raise ValueError('Nenhum quadro valido encontrado. Confirme exe e arquivo CSV.')
    if len(seen_process) > 1:
        raise ValueError('Mais de um processo encontrado: ' + ', '.join(sorted(seen_process)) + '. Informe --process para escolher um.')
    # One dominant swapchain per process. Multiple chains must not be interleaved into a fabricated timeline.
    chosen_key, chosen = max(groups.items(), key=lambda pair: len(pair[1]['present_ms']))
    if len(chosen['present_ms']) < 30:
        raise ValueError('Menos de 30 quadros validos. Grave uma sessao maior.')
    others = sum(len(g['present_ms']) for k, g in groups.items() if k != chosen_key)
    return {'process': chosen_key[0], 'pid': chosen_key[1], 'swapchain': chosen_key[2],
            'other_swapchain_frames_excluded': others, 'trace_sha256': hashlib.sha256(raw).hexdigest(),
            'raw': chosen, 'app': fps_summary(chosen['present_ms']),
            'display': fps_summary(chosen['display_ms']),
            'gpu_busy_mean_ms': roundf(statistics.mean(chosen['gpu_busy_ms'])) if chosen['gpu_busy_ms'] else None,
            'cpu_busy_mean_ms': roundf(statistics.mean(chosen['cpu_busy_ms'])) if chosen['cpu_busy_ms'] else None}


def json_dump(p, obj):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')


def ensure_export(session_dir, res, meta):
    """Export valid VGI generic session; reconstructed duration is NOT ETW/QPC clock."""
    trace = session_dir / 'frames.csv'
    t_ns = 0
    with trace.open('w', encoding='utf-8', newline='') as f:
        w = csv.writer(f)
        w.writerow(['frame_id', 't_ns', 'frame_ms', 'phase'])
        for i, duration in enumerate(res['raw']['present_ms'], 1):
            w.writerow([i, t_ns, f'{duration:.9f}', 'unknown'])
            t_ns += round(duration * 1_000_000)
    manifest = {
        'schema_version': 1, 'adapter': 'generic', 'session_id': session_dir.name,
        'synthetic': False, 'frames': 'frames.csv', 'captures': [],
        'metadata': {'clock_domain': 'presentmon.app_present_reconstructed_monotonic',
                     'scenario': meta.get('scenario', 'unknown'), 'build': meta.get('version', 'unknown'),
                     'hardware': meta.get('hardware', 'unknown'), 'settings': meta.get('settings', 'unknown'),
                     'frame_generation': meta.get('frame_generation', 'unknown'),
                     'collector': 'PresentMon', 'sample_kind': 'application_presents',
                     'cache_state': meta.get('cache_state', 'unknown'),
                     'phase': 'unknown',
                     'provenance_note': 'Timeline reconstructed from per-present durations. Not an absolute clock or verified gameplay label.'}}
    json_dump(session_dir / 'session.json', manifest)


def report_lines(meta, res):
    app, disp = res['app'], res['display']
    lines = [f'# VGI OoT: {meta.get("recomp", "Sem identificacao")}', '',
             f'- Cenario declarado: **{meta.get("scenario", "nao informado")}**',
             f'- Build: `{meta.get("version", "nao informada")}`',
             f'- Processo: `{res["process"]}` · swapchain: `{res["swapchain"]}`',
             f'- Configuracoes declaradas: `{meta.get("settings", "nao informadas")}`',
             f'- Frame Generation: `{meta.get("frame_generation", "nao informado")}`',
             f'- Cache: `{meta.get("cache_state", "nao informado")}`',
             f'- SHA256 do CSV: `{res["trace_sha256"]}`', '']
    def table(label, x):
        lines.append('## ' + label)
        if x is None:
            lines.extend(['Sem amostras suficientes para essa metrica.', ''])
            return
        lines.extend(['| Metrica | Resultado |', '|---|---:|',
            f'| Quadros | {x["samples"]:,} |',
            f'| FPS medio (harmonico no tempo) | {x["avg_fps"]:.2f} |',
            f'| 1% low (media dos 1% piores FPS instantaneos) | {x["low_1pct_fps"]:.2f} |',
            f'| 0,1% low | {x["low_0_1pct_fps"]:.2f} |',
            f'| p95 / p99 frame time | {x["p95_ms"]:.2f} / {x["p99_ms"]:.2f} ms |',
            f'| Intervalos acima de 33,33 ms | {x["over_33ms_pct"]:.2f}% |',
            f'| Intervalos acima de 50 ms | {x["over_50ms_pct"]:.2f}% |', ''])
    table('Intervalos de Present() do processo monitorado (nao garantem FPS da simulacao do jogo)', app)
    table('Intervalos na exibicao (nao e FPS nativo)', disp)
    lines.extend(['## Observacoes',
      f'- Quadros de outras swapchains excluidos: **{res["other_swapchain_frames_excluded"]}**.',
      f'- Media de GPU ocupada por quadro: **{res["gpu_busy_mean_ms"] if res["gpu_busy_mean_ms"] is not None else "sem dados"} ms** (nao equivale a utilizacao GPU em %).',
      f'- Media de CPU ocupada por quadro: **{res["cpu_busy_mean_ms"] if res["cpu_busy_mean_ms"] is not None else "sem dados"} ms** (nao equivale a utilizacao CPU em %).',
      '- A coleta nao mede uso de RAM/VRAM, taxa de acertos de shader cache, latencia de entrada ou problemas graficos.',
      '- Os CSVs nao classificam menu, carregamento nem gameplay: capture apenas um trecho definido do jogo.',
      '- Sem validacao do cenario e repeticoes, diferencas nao comprovam superioridade causal.',
      '- Se houver geracao de quadros, separe as metricas do aplicativo e as da exibicao.',
      '- Para uma escolha definitiva, teste qualidade visual, crashes, saves, controles e atualizacoes de cada port.', ''])
    return '\n'.join(lines)


def analyze(csv_path, *, recomp='Nao especificado', scenario='nao informado',
            version='desconhecida', settings='nao informadas', frame_generation='unknown',
            cache_state='unknown', hardware='Ryzen 5 5500; RX 9060 XT 16GB; 32GB; 1080p 200Hz',
            process='', dest=None, overwrite=False):
    src = Path(csv_path).resolve()
    if not src.is_file():
        raise ValueError(f'CSV nao existe: {src}')
    if dest is None:
        now = dt.datetime.now().strftime('%Y%m%d-%H%M%S-%f')
        dest = RESULTS / f'{now}-{nice(recomp)}-{nice(scenario)}'
    dest = Path(dest).resolve()
    if dest.exists() and any(dest.iterdir()) and not overwrite:
        raise ValueError('Pasta de destino nao esta vazia; nao sobrescreveremos capturas anteriores.')
    dest.mkdir(parents=True, exist_ok=True)
    res = parse_presentmon(src, expected_process=process)
    if src != dest / 'presentmon.csv':
        shutil.copyfile(src, dest / 'presentmon.csv')
    meta = {'recomp': recomp, 'scenario': scenario, 'version': version, 'settings': settings,
            'frame_generation': frame_generation, 'cache_state': cache_state, 'hardware': hardware,
            'process': res['process'], 'collected_at_local': dt.datetime.now().astimezone().isoformat()}
    json_dump(dest / 'meta.json', meta)
    exported = {k: v for k, v in res.items() if k != 'raw'}
    exported['metadata'] = meta
    json_dump(dest / 'summary.json', exported)
    (dest / 'resumo.md').write_text(report_lines(meta, res), encoding='utf-8')
    ensure_export(dest, res, meta)
    return dest, exported


def compare_runs(root=RESULTS):
    entries = []
    for path in sorted(root.glob('*/summary.json')):
        try:
            x = json.loads(path.read_text(encoding='utf-8'))
            if x.get('app') and x.get('metadata'):
                entries.append((path.parent, x))
        except (OSError, ValueError):
            continue
    if not entries:
        print('Nenhuma sessao valida registrada. Grave/importa CSVs primeiro.')
        return
    buckets = {}
    for path, x in entries:
        m = x['metadata']
        key = tuple(m.get(k, 'unknown') for k in ('scenario', 'settings', 'hardware', 'frame_generation', 'cache_state'))
        buckets.setdefault(key, []).append((path, x))
    output = ['# Comparativo VGI OoT', '', 'Estatisticas descritivas; nao representam um teste A/B controlado ou comprovacao de causa.', '']
    for key, runs in buckets.items():
        output += [f'## Cenario: {key[0]} | Settings: {key[1]} | FG: {key[3]} | Cache: {key[4]}', '',
                   '| Recomp | Rodada | FPS med. | 1% low | p99 ms | >33ms |', '|---|---|---:|---:|---:|---:|']
        for folder, x in sorted(runs, key=lambda p: (-p[1]['app']['low_1pct_fps'], -p[1]['app']['avg_fps'])):
            m = x['metadata']; a = x['app']
            output += [f'| {m["recomp"]} | `{folder.name}` | {a["avg_fps"]:.2f} | {a["low_1pct_fps"]:.2f} | {a["p99_ms"]:.2f} | {a["over_33ms_pct"]:.2f}% |']
        names = {x['metadata']['recomp'] for _, x in runs}
        if len(names) == 1:
            output += ['', '_Uma unica recomp presente neste grupo; nao existe confronto._', '']
        elif len(runs) < 4:
            output += ['', '_Comparacao inicial: repita os mesmos trechos para reduzir a variabilidade._', '']
        output += ['']
    output += ['**Cuidado:** comparar FPS de execucoes com menus, carregamentos, FPS caps, FG ou cenas diferentes distorce o resultado.',
               'O ranking acima e ordenacao de registros comparaveis por metadados declarados; nao um diagnostico automatico de gargalo.']
    target = root / 'COMPARATIVO.md'
    target.write_text('\n'.join(output) + '\n', encoding='utf-8')
    print('\n'.join(output))
    print(f'\nRelatorio salvo em {target}')


def http_bytes(url):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=12) as r:
        data = r.read(2_000_001)
    if len(data) > 2_000_000:
        raise ValueError('Resposta de rede excessivamente grande')
    return data


def upstream_release(kind, loc):
    if kind == 'github':
        data = json.loads(http_bytes(f'https://api.github.com/repos/{loc}/releases?per_page=10').decode('utf-8'))
        if not isinstance(data, list):
            raise ValueError('GitHub API nao retornou lista de releases')
        for item in data:
            if not item.get('draft'):
                return {'version': item.get('tag_name') or item.get('name') or 'sem tag',
                        'date': item.get('published_at'), 'url': item.get('html_url'), 'prerelease': bool(item.get('prerelease'))}
        return None
    xml = ET.fromstring(http_bytes(loc))
    items = xml.findall('./channel/item')
    if items:
        item = items[0]
        return {'version': (item.findtext('title') or '').strip(), 'date': (item.findtext('pubDate') or '').strip(),
                'url': (item.findtext('link') or '').strip(), 'prerelease': None}
    ns = {'a': 'http://www.w3.org/2005/Atom'}
    e = xml.find('a:entry', ns)
    if e is None:
        return None
    link = e.find('a:link', ns)
    return {'version': (e.findtext('a:title', default='', namespaces=ns) or '').strip(),
            'date': e.findtext('a:updated', default='', namespaces=ns),
            'url': link.attrib.get('href', '') if link is not None else '', 'prerelease': None}


def updates():
    try:
        old = json.loads(WATCH_FILE.read_text(encoding='utf-8')) if WATCH_FILE.is_file() else {}
    except ValueError:
        old = {}
    now = dict(old)
    out = ['# Atualizacoes de recompiladores', '', f'Consulta local: {dt.datetime.now().astimezone().isoformat()}', '',
           'Sem instalacao/atualizacao automatica. O primeiro resultado estabelece referencia, nao historico.', '']
    for label, (kind, loc, fallback) in SOURCES.items():
        try:
            item = upstream_release(kind, loc)
            if item is None:
                out.append(f'- **{label}**: sem release detectada. Consulte {fallback}')
                continue
            previous = old.get(label, {}).get('version')
            v = item['version']
            state = 'NOVO' if previous and previous != v else ('sem mudanca' if previous else 'primeira consulta')
            marker = ' (pre-release)' if item.get('prerelease') else ''
            out.append(f'- **{label}**: `{v}`{marker} | {state} | {item.get("date") or "sem data"} | {item.get("url") or fallback}')
            now[label] = item
        except (OSError, ValueError, urllib.error.URLError, ET.ParseError) as e:
            out.append(f'- **{label}**: falhou checagem ({type(e).__name__}). Verifique manualmente: {fallback}')
    WATCH_FILE.parent.mkdir(parents=True, exist_ok=True)
    json_dump(WATCH_FILE, now)
    result = '\n'.join(out) + '\n'
    report = WATCH_FILE.parent / 'ULTIMAS_ATUALIZACOES.md'
    report.write_text(result, encoding='utf-8')
    print(result)
    print('Relatorio:', report)


def running_processes():
    if sys.platform != 'win32':
        return []
    try:
        proc = subprocess.run(['tasklist', '/FO', 'CSV', '/NH'], capture_output=True, text=True, timeout=10)
        text = proc.stdout
        rows = csv.reader(text.splitlines())
        names = sorted({row[0] for row in rows if row and row[0].lower().endswith('.exe')})
        return [x for x in names if any(k in x.lower() for k in ['ocarina', 'longshot', 'triforce', 'nx2', 'hookshot', 'oot'])]
    except (OSError, subprocess.TimeoutExpired):
        return []


def find_presentmon():
    candidates = list(ROOT.glob('PresentMon*.exe')) + list((ROOT / 'tools').glob('PresentMon*.exe'))
    exe = shutil.which('PresentMon.exe')
    if exe:
        candidates.append(Path(exe))
    for p in candidates:
        if p.is_file():
            return p.resolve()
    return None


def prompt(label, default=''):
    value = input(f'{label}' + (f' [{default}]' if default else '') + ': ').strip()
    return value or default


def run_capture():
    if sys.platform != 'win32':
        raise RuntimeError('Captura automatica pelo PresentMon exige Windows. Importe CSV para teste em outros sistemas.')
    print('\nVERSOES')
    for i, name in enumerate(RECOMPS, 1):
        print(f'{i}. {name}')
    choice = prompt('Numero da versao', '1')
    idx = int(choice) - 1
    if not 0 <= idx < len(RECOMPS):
        raise ValueError('Versao nao cadastrada.')
    recomp = RECOMPS[idx]
    observed = running_processes()
    if observed:
        print('Executaveis possivelmente relevantes rodando: ' + ', '.join(observed))
    process = prompt('Nome EXATO do processo do jogo (.exe)', observed[0] if len(observed) == 1 else 'ocarina.exe')
    if not process.lower().endswith('.exe') or '\\' in process or '/' in process:
        raise ValueError('Informe apenas o nome do processo, ex.: ocarina.exe, nao o caminho.')
    scenario = prompt('Local / trecho fixo (ex.: kokiri, hyrule-field)', 'hyrule-field')
    version = prompt('Versao/build do port', 'nao informada')
    settings = prompt('Config (p.ex. 1080p-ultra-FSRoff-capoff)', '1080p-ultra-FSRoff-capoff')
    frame_generation = prompt('Frame Generation (off/on/unknown)', 'off')
    cache_state = prompt('Shaders/cache (warm/cold/unknown)', 'warm')
    duration = int(prompt('Tempo da gravacao em segundos', '60'))
    if not 10 <= duration <= 600:
        raise ValueError('Use entre 10 e 600 segundos.')
    pm = find_presentmon()
    if pm is None:
        entered = prompt('PresentMon CLI nao encontrado. Informe caminho do EXE')
        pm = Path(entered.strip('"')).expanduser()
    if not pm.is_file():
        raise FileNotFoundError('PresentMon CLI nao encontrado. Baixe o Console x64 da pagina oficial do GitHub e coloque ao lado deste script.')
    day = dt.datetime.now().strftime('%Y%m%d-%H%M%S-%f')
    dest = RESULTS / f'{day}-{nice(recomp)}-{nice(scenario)}'
    dest.mkdir(parents=True, exist_ok=False)
    raw = dest / 'presentmon.csv'
    cmd = [str(pm), '--process_name', process, '--output_file', str(raw), '--timed', str(duration), '--terminate_after_timed']
    print(f'\nCapture somente a cena de {scenario}; coloque o jogo em primeiro plano.')
    input('Aperte ENTER e volte ao jogo para comecar o teste...')
    proc = subprocess.run(cmd, timeout=duration + 55, cwd=dest)
    if proc.returncode != 0:
        raise RuntimeError(f'PresentMon retornou codigo {proc.returncode}. Confirme se voce usou o executavel Console (CLI), e autorizacoes do ETW.')
    if not raw.exists():
        raise RuntimeError('Nenhum CSV foi gerado. Confirme processo, permissoes ETW e versao Console do PresentMon.')
    dest, data = analyze(raw, recomp=recomp, process=process, scenario=scenario, version=version,
                          settings=settings, frame_generation=frame_generation, cache_state=cache_state,
                          dest=dest, overwrite=True)
    print('Concluido:', dest / 'resumo.md')
    print('FPS medio:', data['app']['avg_fps'], '| 1% low:', data['app']['low_1pct_fps'])


def menu():
    while True:
        print('\n=== VGI | Ocarina of Time ===')
        print('1. Capturar 60s de jogo (PresentMon CLI)')
        print('2. Importar CSV existente')
        print('3. Comparar testes')
        print('4. Consultar atualizacoes dos projetos')
        print('5. Abrir pasta de resultados')
        print('0. Sair')
        choice = prompt('Opcao', '0')
        try:
            if choice == '1':
                run_capture()
            elif choice == '2':
                src = prompt('Caminho completo do CSV').strip('"')
                for i, name in enumerate(RECOMPS, 1):
                    print(f'{i}: {name}')
                idx = int(prompt('Numero da recomp', '1')) - 1
                if not 0 <= idx < len(RECOMPS):
                    raise ValueError('Numero invalido')
                scene = prompt('Trecho', 'hyrule-field')
                settings = prompt('Configuracao', '1080p-ultra-FSRoff-capoff')
                fg = prompt('Frame Generation (off/on/unknown)', 'off')
                cache = prompt('Cache (warm/cold/unknown)', 'warm')
                proc = prompt('Processo (.exe, vazio para ler do CSV)')
                folder, metrics = analyze(src, recomp=RECOMPS[idx], scenario=scene, settings=settings,
                                          frame_generation=fg, cache_state=cache, process=proc)
                print('Importado:', folder, '| FPS:', metrics['app']['avg_fps'])
            elif choice == '3':
                compare_runs()
            elif choice == '4':
                updates()
            elif choice == '5':
                RESULTS.mkdir(parents=True, exist_ok=True)
                if sys.platform == 'win32':
                    os.startfile(RESULTS)
                else:
                    print(RESULTS)
            elif choice == '0':
                return
            else:
                print('Opcao invalida.')
        except (ValueError, OSError, RuntimeError, subprocess.TimeoutExpired) as e:
            print('ERRO:', e)


def main(argv=None):
    ap = argparse.ArgumentParser(description='VGI OoT Companion: captura, analise e atualizacoes (somente leitura).')
    sp = ap.add_subparsers(dest='action')
    sp.add_parser('menu')
    sp.add_parser('capture')
    sp.add_parser('compare')
    sp.add_parser('updates')
    a = sp.add_parser('analyze')
    a.add_argument('csv', type=Path)
    a.add_argument('--recomp', default='Nao especificado')
    a.add_argument('--scenario', default='nao informado')
    a.add_argument('--version', default='desconhecida')
    a.add_argument('--settings', default='nao informadas')
    a.add_argument('--frame-generation', default='unknown')
    a.add_argument('--cache-state', default='unknown')
    a.add_argument('--process', default='')
    a.add_argument('--out', type=Path)
    args = ap.parse_args(argv)
    if args.action in (None, 'menu'):
        menu()
    elif args.action == 'capture':
        run_capture()
    elif args.action == 'updates':
        updates()
    elif args.action == 'compare':
        compare_runs()
    elif args.action == 'analyze':
        p, _ = analyze(args.csv, recomp=args.recomp, scenario=args.scenario,
                       version=args.version, settings=args.settings, frame_generation=args.frame_generation,
                       cache_state=args.cache_state, process=args.process, dest=args.out)
        print('Salvo em', p)
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (ValueError, OSError, RuntimeError, subprocess.TimeoutExpired) as e:
        print('ERRO:', e, file=sys.stderr)
        sys.exit(1)
