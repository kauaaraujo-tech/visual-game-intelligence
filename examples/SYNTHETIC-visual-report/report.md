# VGI — Visual Game Intelligence

**DADOS SINTÉTICOS — teste do software; nenhum resultado real do jogo.**

Sessão: SYNTHETIC-VISUAL
Estado: insufficient\_data

## Evidências e incidentes

Nenhuma queda relativa detectada com evidência suficiente; isto não comprova desempenho adequado.

## Limitações e próximos passos

Gargalo de hardware versus ineficiência do port: inconclusivo sem medições e experimentos controlados. Uso elevado de GPU, espera ou compilação correlacionada não prova causa.
Repetir o mesmo trecho com as mesmas condições; mudar uma variável por vez; registrar build, driver, cache frio/quente, energia e frame generation.

- Thresholds are heuristic; an incident indicates relative degradation, not a proven cause.
- At least 12 preceding continuous gameplay frames are required; startup and changes before that baseline may be missed.

## Análise visual

Estado: candidates\_detected. Candidatos visuais são indícios, não bugs confirmados.

- isolated\_local\_flash; confiança low; candidate\_not\_proven.
  Quadro 1; SHA256 8804a6930fc5fa9ede4ba5709a18c067967b2862b870ee93a66691964716ed7a.

![Evidência do candidato visual](evidence/8804a6930fc5fa9ede4ba5709a18c067967b2862b870ee93a66691964716ed7a.ppm)

  Quadro 2; SHA256 10989df9db338bd8a86373d26f68126b5d06638d56a5fafa53be5bda2114651b.

![Evidência do candidato visual](evidence/10989df9db338bd8a86373d26f68126b5d06638d56a5fafa53be5bda2114651b.ppm)

  Quadro 3; SHA256 8804a6930fc5fa9ede4ba5709a18c067967b2862b870ee93a66691964716ed7a.

![Evidência do candidato visual](evidence/8804a6930fc5fa9ede4ba5709a18c067967b2862b870ee93a66691964716ed7a.ppm)

- Luminance-grid heuristics identify visual candidates, not rendering bugs or their causes.
- Loading, fades, exposure changes, effects, menus, and intentional stillness can resemble anomalies.
- Only consecutive explicitly identified frames are compared; filenames and mtime never establish chronology.
- A 16x9 luminance grid can miss small, color-only, HUD, and spatially cancelling defects.
- No candidate does not establish visual correctness; sparse capture cannot resolve a one-frame event.

## Contexto da sessão

0 evento(s) importado(s); somente os explicitamente associados acima pertencem ao incidente.
O JSON preserva os eventos não alinhados e suas referências. Nomes de arquivos e mtime não são usados como relógio.

## Reprodução

```text
python -m vgi analyze session.json --visual --out NEW_OUTPUT_DIRECTORY
```

Python >=3.10; same input bytes and VGI version; no network required

Entradas (SHA256):

- session.json — sha256 `1f219decb72074073bbc24c37330a804a2b3f7c3fcde4810430859009b41267d`
- frames.csv — sha256 `6ac9e04ab5c1409698b27e56b99cfbe657574af5f5dd74d069cc38372b0bd118`
- SYNTHETIC-0.ppm — sha256 `8804a6930fc5fa9ede4ba5709a18c067967b2862b870ee93a66691964716ed7a`
- SYNTHETIC-1.ppm — sha256 `8804a6930fc5fa9ede4ba5709a18c067967b2862b870ee93a66691964716ed7a`
- SYNTHETIC-2.ppm — sha256 `10989df9db338bd8a86373d26f68126b5d06638d56a5fafa53be5bda2114651b`
- SYNTHETIC-3.ppm — sha256 `8804a6930fc5fa9ede4ba5709a18c067967b2862b870ee93a66691964716ed7a`
- SYNTHETIC-4.ppm — sha256 `8804a6930fc5fa9ede4ba5709a18c067967b2862b870ee93a66691964716ed7a`

Ferramenta VGI 0.1.1 (experimental). Os parâmetros do detector estão no JSON. Não há chamadas externas automáticas.
