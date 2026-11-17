# VGI — Ocarina of Time | Kit de comparacao (Windows)

Ferramenta **experimental** para comparar recompiladores usando capturas geradas pelo **Intel PresentMon Console**. O script nao instala programas, nao altera jogos, nao toca nos saves, nao apaga shaders e nao envia gravacoes para a internet. O verificador de releases consulta apenas fontes publicas quando solicitado.

## Preparar uma vez

1. Tenha Python 3.10+ (`py -3 --version`).
2. Baixe o **PresentMon Console x64** da [pagina de releases oficial](https://github.com/GameTechDev/PresentMon/releases), nao apenas a interface grafica. Copie seu executavel para esta pasta ou `tools/`, mantendo o nome `PresentMon*.exe`.
3. Extraia o ZIP em uma pasta propria (ex.: `C:\VGI-OoT-Teste`). Clique duas vezes em `INICIAR_VGI_OOT.cmd`.
4. Se o PresentMon mostrar falha de ETW/acesso, tente abrir o terminal como administrador **apenas para a captura**. Nao desative seguranca do Windows nem aplique alteracoes permanentes.

## Fazer o teste hoje

1. Abra **uma** recompilacao e entre em uma cena repetivel, como `Kokiri Forest` ou `Hyrule Field`.
2. No menu do kit, use **1. Capturar**. Escolha a versao, informe o nome exato do **processo do jogo** (veja o Gerenciador de Tarefas se necessario), versao do build, settings, FG e estado do cache. O kit sugere alguns processos em execucao.
3. Apos apertar Enter, volte ao jogo. A captura padrao dura **60 segundos** e encerra automaticamente. Evite abrir menus/entrar em outras cenas durante o trecho.
4. Repita a **mesma cena e configuracoes** em Ocarina Reborn, Longshot, NX2navi e Triforce; idealmente 2–3 vezes cada. Se Frame Generation estiver ligado, registre isso claramente e **nao misture** os resultados.
5. Use **3. Comparar**. O arquivo `results/COMPARATIVO.md` inclui FPS medio, 1% low, p99 e percentual de intervalos >33,3 ms, por configuracoes declaradas.
6. Use **4. Atualizacoes** para acompanhar releases (incluindo pre-releases) dos repositorios monitorados. A primeira consulta e referencia; a proxima exibe `NOVO` para versoes que mudaram. Sem tarefas agendadas ou auto-update.

## Resultados

Cada pasta em `results/` contem:
- `presentmon.csv`: CSV bruto do PresentMon (copiado, sem sobrescrever o original).
- `summary.json`, `resumo.md`, `meta.json`: metricas e condicoes declaradas.
- `frames.csv` e `session.json`: adaptador **generic** compativel com `python -m vgi analyze` do [VGI oficial](https://github.com/kauaaraujo-tech/visual-game-intelligence).

Exemplo opcional para executar o motor VGI (estando no diretorio do repositorio VGI, onde `python -m vgi` funciona):

```powershell
py -3 -m vgi analyze 'C:\VGI-OoT-Teste\results\MINHA-SESSAO\session.json' --out 'C:\VGI-OoT-Teste\results\MINHA-SESSAO\vgi-report'
```

O kit **nao chama isso automaticamente** porque a instalacao do VGI e separada e nao e garantida no PC.

## Interpretacao correta

- FPS medio e 1% low sao calculados a partir de `MsBetweenPresents`, que mede intervalos entre `Present()` do **processo monitorado**; **nao mede necessariamente FPS de simulacao nem quadros efetivamente exibidos**.
- Intervalos `MsBetweenDisplayChange` (se presentes) sao mostrados separadamente. Frame Generation e frames de app nao devem ser confundidos.
- `MsGPUBusy` e `MsCPUBusy` sao duracoes por quadro, **nao porcentagens de uso**. O kit ainda **nao coleta RAM nem VRAM** e nao afirma identificar gargalos automaticamente.
- Eventos de menu, carregamento e shader compilation podem distorcer o resultado. O programa nao classifica cenas; capture uma fase homogênea.
- Para escolher a melhor versao para **zerar**, cheque saves, compatibilidade com controle, travamentos, qualidade visual, updates e bugs alem de FPS.
- O marcador de releases no NX2navi pode apontar uma versao de transicao para o Triforce; **isso nao significa** que o compilador antigo automaticamente tenha melhor desempenho.
- Fontes de updates sao repositorios identificados no arquivo `vgi_oot.py`, com Longshot Recomper e Longshot madebyjordan separados. O programa **nunca baixa ou executa** atualizacoes.
- As linhas `frames.csv` usam sequencia temporal reconstruida a partir dos intervalos. **Nao sao timestamps ETW absolutos**, nem garantem alinhamento com capturas externas. O manifesto informa fase `unknown` para nao inventar anotacoes de gameplay.

A ferramenta roda no Windows; o parser `analyze` pode ser testado em qualquer sistema com Python 3.10+. Dependencias Python externas: **nenhuma**. Formatos CSV nao compatíveis exibem erro em vez de inventar FPS.

## Testes do kit e estado de validacao

A logica de CSV/importacao/comparacao passou em testes automatizados com dados **sinteticos** no ambiente de desenvolvimento. A captura real usando PresentMon e a interface em Windows **ainda nao foram validadas neste computador**; portanto o primeiro teste precisa confirmar se a versao CLI de PresentMon gera CSV no formato previsto. Erros de permissão/versao aparecem no terminal e nao sao escondidos.

Executar testes automatizados (opcional): `py -3 -m unittest discover -s tests -v` na pasta do kit.