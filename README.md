# 🐾 Curva Glicêmica Felina

App web simples para registrar e analisar a curva de glicose de gatos. Funciona com ou sem insulina e considera a faixa etária do animal. Um modelo de machine learning em Python (scikit-learn) classifica o padrão da curva.

> **Aviso:** ferramenta educativa. Não diagnostica nem substitui o veterinário. Os valores de referência são aproximações configuráveis, e o modelo foi treinado com dados **sintéticos** (veja "Limitações").

## Como rodar

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python train_model.py            # gera o modelo.joblib (obrigatório antes de rodar o app)
python app.py
```

Abra http://127.0.0.1:5000. (O gráfico usa Chart.js via CDN, então precisa de internet no navegador.)

## Como usar

1. Informe a **idade** do gato em anos (aceita decimais, ex.: `0.5`).
2. **Uso de insulina**: deixe desmarcado se o gato não usa (caso de monitoramento para diagnóstico). Marque se usa.
3. Preencha as leituras e a glicose em mg/dL. **Sem insulina**, informe o **horário real** de cada medição (ex.: 08:00, 10:30; a virada da meia-noite é tratada automaticamente, em ordem cronológica). **Com insulina**, informe as **horas após a aplicação da insulina** (ex.: 0, 2, 4, 6...). Mínimo de 3 leituras; 6 a 12 ao longo de 12 h dão melhor resultado.
4. Clique em **Analisar curva**.

Você recebe o gráfico com a faixa de referência sombreada, média, máxima, mínima (nadir), % do tempo na faixa, a classificação do padrão e alertas.

## Faixas por idade (`features.py`, dicionário `FAIXAS`)

| Faixa | Idade | Referência (mg/dL) |
|---|---|---|
| Filhote | < 1 ano | 70–160 |
| Adulto | 1 a 10 anos | 70–150 |
| Sênior | > 10 anos | 70–160 |

Edite os números com a orientação do seu veterinário. O treino e o app usam as mesmas faixas; se mudar, rode `python train_model.py` de novo.

## Padrões que o modelo reconhece

- **normal**: dentro da faixa de referência.
- **estresse**: pico alto no início que normaliza (comum em coleta/clínica; não indica diabetes sozinho).
- **hiperglicemia_persistente**: acima da faixa na maior parte da curva (investigar diabetes).
- **hipoglicemia**: queda abaixo da faixa.
- **oscilacao_ampla**: grandes picos e vales.

Com insulina marcada, o texto do resultado inclui observações específicas (ex.: dose insuficiente, risco de hipoglicemia). O app **nunca** sugere ajuste de dose.

Alertas por regra, independentes do modelo: leitura abaixo de 50 mg/dL (possível emergência) e acima de 300 mg/dL.

## Como funciona

- `features.py`: faixas por idade e extração de features da curva (média, máx, mín, amplitude, horário do nadir, inclinação, primeira/última leitura, % acima/abaixo da faixa, idade, insulina).
- `train_model.py`: gera 12.000 curvas sintéticas rotuladas, treina um `RandomForestClassifier` e imprime o relatório de métricas (salva `modelo.joblib`).
- `app.py`: API Flask (`POST /api/analisar`, `/api/medicoes`) e página.
- `templates/index.html`: interface (responsiva, com modo escuro automático).

## Limitações e próximos passos

- **Dados sintéticos**: as métricas altas do treino refletem o gerador, não a realidade clínica. Para uso sério, substitua por curvas reais rotuladas por veterinários: ajuste `train_model.py` para ler um CSV e manter `extrair()`.
- Curvas com poucas leituras ou muito espaçadas perdem precisão.
- Ideias: salvar histórico por gato (SQLite), comparar curvas, exportar PDF para levar à consulta, adicionar frutosamina.

## Modo visitante e conta

- **Sem conta (visitante):** gera a curva, vê a análise e baixa o **gráfico** e o **resultado** (PNG). Nada é salvo: ao atualizar a página, ou entrar e sair, tudo é perdido.
- **Com conta:** além disso, salva medições e observações no histórico (reabrir, excluir) e também baixa gráfico e resultado.

## Contas, histórico e deploy na Vercel

Cada pessoa tem sua conta (usuário + senha). Valores, histórico e observações são **separados por usuário**: ninguém vê as medições de outra conta. A senha é guardada só como hash, e o login fica em um cookie assinado (30 dias).

**Onde salva:** localmente, em `dados.json`. Na Vercel o disco é temporário, então o app usa **Upstash Redis** via REST.

Passo a passo:

1. Rode `python train_model.py` e **faça commit do `modelo.joblib`** (a Vercel não treina no servidor).
2. Suba o projeto no GitHub e importe na Vercel (ela detecta o Flask em `app.py`).
3. **Storage → Marketplace → Upstash for Redis**: crie e conecte. Isso injeta `KV_REST_API_URL` e `KV_REST_API_TOKEN`.
4. **Settings → Environment Variables**, em Production, Preview e Development:
   - `SECRET_KEY` (obrigatória): gere com `python -c "import secrets; print(secrets.token_hex(32))"`. Trocar o valor desconecta todo mundo.
   - `ALLOW_SIGNUP` (opcional): `false` bloqueia novos cadastros. Padrão: liberado.
5. Faça o redeploy.
6. Abra o site e crie sua conta. **A primeira conta criada herda as medições salvas antes do login existir.**
7. Depois de criar as contas necessárias, defina `ALLOW_SIGNUP=false` e faça redeploy para fechar o cadastro. Para criar uma conta nova depois, volte para `true` temporariamente.

`APP_PASSWORD` não é mais usada e pode ser removida. Após 8 senhas erradas seguidas, o usuário fica bloqueado por 15 minutos.
