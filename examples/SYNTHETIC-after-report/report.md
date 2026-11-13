# VGI — Visual Game Intelligence

**DADOS SINTÉTICOS — teste do software; nenhum resultado real do jogo.**

Sessão: SYNTHETIC-HOOKSHOT-NATIVE
Estado: no\_anomaly

## Evidências e incidentes

Nenhuma queda relativa detectada com evidência suficiente; isto não comprova desempenho adequado.

## Limitações e próximos passos

Gargalo de hardware versus ineficiência do port: inconclusivo sem medições e experimentos controlados. Uso elevado de GPU, espera ou compilação correlacionada não prova causa.
Repetir o mesmo trecho com as mesmas condições; mudar uma variável por vez; registrar build, driver, cache frio/quente, energia e frame generation.

- Thresholds are heuristic; an incident indicates relative degradation, not a proven cause.
- At least 12 preceding continuous gameplay frames are required; startup and changes before that baseline may be missed.
- Native parser schema inspected at e9975d6c245275aaf89a34e8d17a6bbe8badab46; this does not verify the producing executable's build/version
- Performance timeline reconstructed by summing rounded ms intervals; no absolute monotonic timestamps exported. Start uncertainty accumulates 5000 ns per preceding row; interval duration uncertainty is 5000 ns
- First performance row marked warmup: metric deltas can aggregate startup; its diagnostic events omitted
- Performance counters share row identity but durations can overlap and do not prove a cause
- Phase annotation supplied by manifest; replay/scene equivalence is declared, not independently verified

## Análise visual

Estado: insufficient\_data. Candidatos visuais são indícios, não bugs confirmados.

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

- session.json — sha256 `709db2114b3f0aa00dd04fee0dde176b4e21fc03e7a94f0f309762c99620dd12`
- hookshot\_frames.csv — sha256 `0b6be69184d64cb85d281314f26cfcb5cb3b9cb9ae19934ae55c820653acde1f`
- SYNTHETIC-frame31.ppm — sha256 `15ebfb44a6db5e4a698eab2ae4004c94e8c4228f2cd41ef0b71343fe662d865a`

Ferramenta VGI 0.1.1 (experimental). Os parâmetros do detector estão no JSON. Não há chamadas externas automáticas.
