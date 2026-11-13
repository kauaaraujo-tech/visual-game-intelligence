# VGI — Visual Game Intelligence

**DADOS SINTÉTICOS — teste do software; nenhum resultado real do jogo.**

Sessão: SYNTHETIC-HOOKSHOT-NATIVE
Estado: incidents\_detected

## Evidências e incidentes

### incident-0001

Quadros: \[31, 32, 33\]. Intervalo monotônico local: 480000000–701000000 ns.
Baseline: 16.000 ms; pico: 85.000 ms; limiar: 24.000 ms.

Eventos associados (correlação temporal/identidade; causalidade não comprovada):

- performance:33:pipe\_wait\_ms — pipe\_wait\_ms; exact\_frame; hookshot\_frames.csv:33; Hookshot same-interval aggregate pipe\_wait\_ms=45 ms; not a causal attribution

Capturas associadas:

- SYNTHETIC-frame31.ppm — exact\_frame; quadro 32.

![Captura de evidência](evidence/15ebfb44a6db5e4a698eab2ae4004c94e8c4228f2cd41ef0b71343fe662d865a.ppm)


Hipóteses — **Não comprovada**:

- Additional workload or waiting may explain this degradation relative to the preceding local baseline. Confiança: low. Evidências: \['frame:31', 'frame:32', 'frame:33'\]. Próximo teste: Repeat the same scene with synchronized CPU/GPU timing and internal traces; compare incident frames with the preceding baseline.
- Associated internal events may be related to the slowdown; temporal association does not establish causation. Confiança: medium. Evidências: \['performance:33:pipe\_wait\_ms', 'frame:31', 'frame:32', 'frame:33'\]. Próximo teste: Inspect the associated event durations and repeat a controlled run with the suspected operation isolated or instrumented.
- Blocking shader/pipeline availability is a concrete investigation candidate. Aggregate durations can overlap; correlation is not causal proof. Confiança: medium. Evidências: \['performance:33:pipe\_wait\_ms', 'frame:31', 'frame:32', 'frame:33'\]. Próximo teste: Repeat the same replay with separately recorded cold/warm cache state and identical build/driver; inspect pipeline wait counts and program-cache reuse. Do not infer unnecessary recompilation from this metric alone.
- Limitação: The local baseline is observational; scene or workload changes may explain a relative slowdown.
- Limitação: GPU busy timing is missing for some or all incident frames; hardware limits and port behavior cannot be distinguished from these data.

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

## Referências no código

Referências apontam à emissão da instrumentação inspecionada; não identificam código defeituoso nem comprovam a versão instalada.

- performance:33:pipe\_wait\_ms → [emissão de pipe\_wait\_ms](https://github.com/NotRexed/Hookshot/blob/e9975d6c245275aaf89a34e8d17a6bbe8badab46/gpu/vk/vk_replay.cpp#L3251)

## Análise visual

Estado: insufficient\_data. Candidatos visuais são indícios, não bugs confirmados.

- Luminance-grid heuristics identify visual candidates, not rendering bugs or their causes.
- Loading, fades, exposure changes, effects, menus, and intentional stillness can resemble anomalies.
- Only consecutive explicitly identified frames are compared; filenames and mtime never establish chronology.
- A 16x9 luminance grid can miss small, color-only, HUD, and spatially cancelling defects.
- No candidate does not establish visual correctness; sparse capture cannot resolve a one-frame event.

## Contexto da sessão

1 evento(s) importado(s); somente os explicitamente associados acima pertencem ao incidente.
O JSON preserva os eventos não alinhados e suas referências. Nomes de arquivos e mtime não são usados como relógio.

## Reprodução

```text
python -m vgi analyze session.json --visual --out NEW_OUTPUT_DIRECTORY
```

Python >=3.10; same input bytes and VGI version; no network required

Entradas (SHA256):

- session.json — sha256 `370b2152b9216848a7ef8a11a94b40a8d6306e0a978dfb9797951f1b283529aa`
- hookshot\_frames.csv — sha256 `ca2411671bc8265d3a1b7a17bd0f4aaf18b6ea0e02364eaa0934cb7d59aaa2d6`
- SYNTHETIC-frame31.ppm — sha256 `15ebfb44a6db5e4a698eab2ae4004c94e8c4228f2cd41ef0b71343fe662d865a`

Ferramenta VGI 0.1.1 (experimental). Os parâmetros do detector estão no JSON. Não há chamadas externas automáticas.
