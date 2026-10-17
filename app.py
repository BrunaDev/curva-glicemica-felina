import hmac, html, json, os, re, time, uuid, urllib.request
import joblib, numpy as np
from flask import Flask, jsonify, render_template, request
from features import FAIXAS, faixa_etaria, extrair

BASE = os.path.dirname(os.path.abspath(__file__))
modelo = joblib.load(os.path.join(BASE, "modelo.joblib"))  # gere com train_model.py e faça commit
app = Flask(__name__, static_folder="public", static_url_path="")

# ---- Armazenamento: Upstash Redis (Vercel) se houver variáveis de ambiente; senão, arquivo local ----
REDIS_URL = os.environ.get("KV_REST_API_URL") or os.environ.get("UPSTASH_REDIS_REST_URL")
REDIS_TOKEN = os.environ.get("KV_REST_API_TOKEN") or os.environ.get("UPSTASH_REDIS_REST_TOKEN")
SENHA = os.environ.get("APP_PASSWORD")
ARQ = os.path.join("/tmp" if os.environ.get("VERCEL") else BASE, "medicoes.json")


def _redis(*cmd):
    req = urllib.request.Request(REDIS_URL, json.dumps(cmd).encode(),
                                 {"Authorization": f"Bearer {REDIS_TOKEN}", "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=8) as r:
        return json.load(r)["result"]


def _ler():
    try:
        return json.load(open(ARQ, encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def db_listar():
    itens = [json.loads(v) for v in (_redis("HGETALL", "medicoes") or [])[1::2]] if REDIS_URL else list(_ler().values())
    return sorted(itens, key=lambda m: (m["data"], m["criado"]), reverse=True)


def db_salvar(m):
    if REDIS_URL: _redis("HSET", "medicoes", m["id"], json.dumps(m))
    else:
        d = _ler(); d[m["id"]] = m; json.dump(d, open(ARQ, "w", encoding="utf-8"))


def db_apagar(i):
    if REDIS_URL: _redis("HDEL", "medicoes", i)
    else:
        d = _ler(); d.pop(i, None); json.dump(d, open(ARQ, "w", encoding="utf-8"))


def autorizado():
    return not SENHA or hmac.compare_digest(request.headers.get("X-Senha", ""), SENHA)


TEXTOS = {
    "normal": ("Curva dentro do esperado", "Os valores ficaram na faixa de referência para a idade."),
    "estresse": ("Padrão de hiperglicemia por estresse",
                 "Valores altos no início que normalizam ao longo do tempo são comuns em gatos estressados (coleta, clínica). Não indica diabetes por si só."),
    "hiperglicemia_persistente": ("Hiperglicemia persistente",
                 "Glicose acima da faixa durante a maior parte da curva. Vale levar ao veterinário para avaliar diabetes (frutosamina, urina)."),
    "hipoglicemia": ("Queda para hipoglicemia", "Houve queda abaixo da faixa de referência. Fale com o veterinário."),
    "oscilacao_ampla": ("Oscilação ampla", "Grande variação entre picos e vales ao longo do dia. Leve a curva ao veterinário."),
}
EXTRA_INSULINA = {
    "normal": "Com insulina, bom sinal de controle, mas confirme a dose com o veterinário.",
    "hiperglicemia_persistente": "Com insulina, pode indicar dose insuficiente. Não ajuste sem orientação veterinária.",
    "hipoglicemia": "Com insulina, risco real: não aplique a próxima dose sem falar com o veterinário.",
    "oscilacao_ampla": "Com insulina, o fundo da curva (nadir) e a duração do efeito devem ser avaliados pelo veterinário.",
}


@app.get("/")
def index():
    return render_template("index.html", faixas=FAIXAS)


@app.post("/api/analisar")
def analisar():
    d = request.get_json(force=True)
    try:
        idade = float(d["idade"]); insulina = bool(d["insulina"])
        pts = sorted((float(p["t"]), float(p["g"])) for p in d["leituras"])
    except (KeyError, ValueError, TypeError):
        return jsonify(erro="Dados inválidos."), 400
    if len(pts) < 3 or idade < 0:
        return jsonify(erro="Informe a idade e ao menos 3 leituras."), 400
    t, g = zip(*pts)
    fk = faixa_etaria(idade); f = FAIXAS[fk]
    proba = modelo.predict_proba([extrair(t, g, idade, insulina)])[0]
    classe = str(modelo.classes_[int(np.argmax(proba))])
    titulo, texto = TEXTOS[classe]
    if insulina and classe in EXTRA_INSULINA: texto += " " + EXTRA_INSULINA[classe]
    ga = np.array(g); i = int(np.argmin(ga))
    alertas = []
    if ga.min() < 50: alertas.append("Glicose abaixo de 50 mg/dL: possível emergência. Procure atendimento veterinário imediatamente.")
    elif ga.min() < f["min"]: alertas.append("Há leitura abaixo da faixa de referência.")
    if ga.max() > 300: alertas.append("Leitura acima de 300 mg/dL: converse com o veterinário.")
    return jsonify(
        faixa={"chave": fk, **f}, classe=classe, titulo=titulo, texto=texto, alertas=alertas,
        confianca=round(float(proba.max()) * 100),
        resumo={"media": round(float(ga.mean())), "maxima": int(ga.max()), "minima": int(ga.min()),
                "hora_nadir": t[i], "no_alvo": round(float(((ga >= f["min"]) & (ga <= f["max"])).mean()) * 100)})


@app.get("/api/medicoes")
def medicoes_listar():
    if not autorizado(): return jsonify(erro="Não autorizado."), 401
    return jsonify(db_listar())


@app.post("/api/medicoes")
def medicoes_salvar():
    if not autorizado(): return jsonify(erro="Não autorizado."), 401
    d = request.get_json(force=True)
    try:
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(d["data"])): raise ValueError
        rows = []
        for r in d["rows"][:60]:
            a = str(r["a"])
            if not re.fullmatch(r"\d{1,2}:\d{2}|\d+(\.\d+)?", a): raise ValueError
            rows.append({"a": a, "g": str(float(r["g"])).rstrip("0").rstrip("."),
                         "c": html.escape(str(r.get("c") or "").strip()[:200])})
        r = d["resumo"]
        m = {"id": uuid.uuid4().hex[:12], "criado": time.time(), "data": d["data"], "idade": float(d["idade"]),
             "insulina": bool(d["insulina"]), "rows": rows, "classe": html.escape(str(d["classe"])[:40]),
             "titulo": html.escape(str(d["titulo"])[:80]),
             "resumo": {k: float(r[k]) for k in ("media", "maxima", "minima", "no_alvo")}}
    except (KeyError, ValueError, TypeError):
        return jsonify(erro="Dados inválidos."), 400
    db_salvar(m)
    return jsonify(m), 201


@app.delete("/api/medicoes/<i>")
def medicoes_apagar(i):
    if not autorizado(): return jsonify(erro="Não autorizado."), 401
    db_apagar(re.sub(r"\W", "", i))
    return "", 204


if __name__ == "__main__":
    app.run(debug=True)
