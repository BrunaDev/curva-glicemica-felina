import functools, html, json, os, re, time, uuid, urllib.request
import joblib, numpy as np
from flask import Flask, jsonify, render_template, request, session
from werkzeug.security import check_password_hash, generate_password_hash
from features import FAIXAS, faixa_etaria, extrair

BASE = os.path.dirname(os.path.abspath(__file__))
modelo = joblib.load(os.path.join(BASE, "modelo.joblib"))  # gere com train_model.py e faça commit
app = Flask(__name__, static_folder="public", static_url_path="")

# ---- Armazenamento: Upstash Redis (Vercel) se houver variáveis de ambiente; senão, arquivo local ----
REDIS_URL = os.environ.get("KV_REST_API_URL") or os.environ.get("UPSTASH_REDIS_REST_URL")
REDIS_TOKEN = os.environ.get("KV_REST_API_TOKEN") or os.environ.get("UPSTASH_REDIS_REST_TOKEN")
ARQ = os.path.join("/tmp" if os.environ.get("VERCEL") else BASE, "dados.json")

if os.environ.get("VERCEL") and not os.environ.get("SECRET_KEY"):
    raise RuntimeError("Defina a variável de ambiente SECRET_KEY na Vercel.")
app.secret_key = os.environ.get("SECRET_KEY") or "dev-local-key"
app.config.update(SESSION_COOKIE_SAMESITE="Lax", SESSION_COOKIE_SECURE=bool(os.environ.get("VERCEL")),
                  PERMANENT_SESSION_LIFETIME=60 * 60 * 24 * 30)


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


def _local():
    if os.environ.get("VERCEL"):  # disco da Vercel é temporário: sem Redis, os dados seriam perdidos
        raise RuntimeError("Banco de dados não configurado: conecte o Upstash Redis ao projeto na Vercel.")
    return _ler()


def hall(k):
    if REDIS_URL:
        f = _redis("HGETALL", k) or []
        return dict(zip(f[::2], f[1::2]))
    return _local().get(k, {})


def hget(k, f):
    return _redis("HGET", k, f) if REDIS_URL else _local().get(k, {}).get(f)


def hset(k, f, v):
    if REDIS_URL: return _redis("HSET", k, f, v)
    d = _local(); d.setdefault(k, {})[f] = v; json.dump(d, open(ARQ, "w", encoding="utf-8"))


def hdel(k, f):
    if REDIS_URL: return _redis("HDEL", k, f)
    d = _local(); d.get(k, {}).pop(f, None); json.dump(d, open(ARQ, "w", encoding="utf-8"))


def db_listar(u):
    itens = [json.loads(v) for v in hall("medicoes:" + u).values()]
    return sorted(itens, key=lambda m: (m["data"], m["criado"]), reverse=True)


def db_salvar(u, m): hset("medicoes:" + u, m["id"], json.dumps(m))
def db_apagar(u, i): hdel("medicoes:" + u, i)


# ---- Contas e sessão ----
USER_RE = re.compile(r"[a-z0-9_.-]{3,30}")


def login_obrigatorio(f):
    @functools.wraps(f)
    def w(*a, **k):
        if not session.get("u"): return jsonify(erro="Faça login."), 401
        return f(*a, **k)
    return w


def _cred():
    d = request.get_json(force=True, silent=True) or {}
    return str(d.get("usuario", "")).strip().lower(), str(d.get("senha", ""))


@app.errorhandler(RuntimeError)
def sem_banco(e):
    return jsonify(erro=str(e)), 503


@app.post("/api/cadastro")
def cadastro():
    if os.environ.get("ALLOW_SIGNUP", "true").lower() == "false":
        return jsonify(erro="Cadastro desativado."), 403
    u, s = _cred()
    if not USER_RE.fullmatch(u): return jsonify(erro="Usuário: 3 a 30 caracteres (letras, números, . _ -)."), 400
    if not 8 <= len(s) <= 128: return jsonify(erro="A senha deve ter de 8 a 128 caracteres."), 400
    if hget("users", u): return jsonify(erro="Esse usuário já existe."), 409
    primeiro = not hall("users")
    hset("users", u, json.dumps({"hash": generate_password_hash(s, method="pbkdf2:sha256"), "criado": time.time()}))
    if primeiro:  # a primeira conta herda as medições salvas antes de existir login
        for i, v in hall("medicoes").items(): hset("medicoes:" + u, i, v)
    session.clear(); session.permanent = True; session["u"] = u
    return jsonify(usuario=u), 201


@app.post("/api/login")
def login():
    u, s = _cred()
    if REDIS_URL and int(_redis("GET", "fail:" + u) or 0) >= 8:
        return jsonify(erro="Muitas tentativas. Tente de novo em 15 minutos."), 429
    r = hget("users", u)
    if not (r and check_password_hash(json.loads(r)["hash"], s)):
        if REDIS_URL: _redis("INCR", "fail:" + u); _redis("EXPIRE", "fail:" + u, 900)
        return jsonify(erro="Usuário ou senha incorretos."), 401
    if REDIS_URL: _redis("DEL", "fail:" + u)
    session.clear(); session.permanent = True; session["u"] = u
    return jsonify(usuario=u)


@app.post("/api/logout")
def logout():
    session.clear()
    return "", 204


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
    return render_template("index.html", usuario=session.get("u"))


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
    conf = float(proba.max())
    if conf < 0.6:
        titulo, texto = "Padrão pouco definido", "A curva não se encaixa com clareza em nenhum padrão conhecido. Leve os valores ao veterinário."
    else:
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
@login_obrigatorio
def medicoes_listar():
    return jsonify(db_listar(session["u"]))


@app.post("/api/medicoes")
@login_obrigatorio
def medicoes_salvar():
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
    db_salvar(session["u"], m)
    return jsonify(m), 201


@app.delete("/api/medicoes/<i>")
@login_obrigatorio
def medicoes_apagar(i):
    db_apagar(session["u"], re.sub(r"\W", "", i))
    return "", 204


if __name__ == "__main__":
    app.run(debug=True)
