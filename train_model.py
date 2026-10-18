"""Gera curvas sintéticas rotuladas e treina um RandomForest. Uso: python train_model.py

Cada curva só entra no treino se cumprir a definição da sua classe (amostragem com rejeição),
então as classes não se sobrepõem e o modelo aprende padrões bem definidos.
"""
import numpy as np, joblib
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report
from features import FAIXAS, CLASSES, faixa_etaria, extrair, reversoes

rng = np.random.default_rng(42)


def curva(classe, lo, hi, insulina):
    n = int(rng.integers(4, 11))
    t = np.sort(np.concatenate([[0], rng.uniform(0.5, 12, n - 1)]))
    base = rng.uniform(lo + 10, hi - 20)
    if classe == "normal":
        g = base + rng.normal(0, 8, n)
    elif classe == "estresse":
        pico = rng.uniform(hi + 30, 330)
        g = base + (pico - base) * np.exp(-t / rng.uniform(0.7, 3)) + rng.normal(0, 6, n)
    elif classe == "hiperglicemia_persistente":
        g = rng.uniform(hi + 20, 450) + rng.normal(0, 20, n)
        if insulina: g = g - 60 * np.sin(np.pi * t / 12) * rng.uniform(0, 1)
    elif classe == "hipoglicemia":
        nadir = rng.uniform(10, lo - 3); sub = int(rng.integers(4)); tau = rng.uniform(1.5, 6)
        if sub == 0:   g = base - (base - nadir) * np.exp(-((t - rng.uniform(3, 9)) ** 2) / 6)   # queda e volta
        elif sub == 1: g = nadir + rng.normal(0, 8, n) + rng.uniform(0, 15)                         # baixa o tempo todo
        elif sub == 2: g = base - (base - nadir) * (1 - np.exp(-t / tau))                         # desce ao longo do tempo
        else:          g = nadir + (base - nadir) * (1 - np.exp(-t / tau))                         # começa baixa e recupera
        g = g + rng.normal(0, 5, n)
    else:  # oscilacao_ampla
        g = rng.uniform(120, 230) + rng.uniform(60, 140) * np.sin(2 * np.pi * t / 12 + rng.uniform(0, 6)) + rng.normal(0, 10, n)
    return t, np.clip(g, 5, 600)


def valida(c, g, lo, hi):
    mn, mx, rev = g.min(), g.max(), reversoes(g)
    if c == "normal":     return mn >= lo and mx <= hi
    if c == "estresse":   return g[0] > hi + 20 and mn >= lo and g[-1] <= hi and np.all(np.diff(g) <= 15) and rev < 2
    if c == "hiperglicemia_persistente": return mn >= lo and g.mean() > hi + 10 and g[-1] > hi and not (np.ptp(g) >= 70 and rev >= 2)
    if c == "hipoglicemia": return mn < lo
    return mn >= lo and mx > hi and np.ptp(g) >= 70 and rev >= 2   # oscilacao_ampla


X, y = [], []
for c in CLASSES:
    ok = 0
    while ok < 3500:
        idade = float(rng.choice([rng.uniform(0.1, 1), rng.uniform(1, 10), rng.uniform(10, 20)]))
        f = FAIXAS[faixa_etaria(idade)]; ins = rng.random() < (0.15 if c in ("normal", "estresse") else 0.5)
        t, g = curva(c, f["min"], f["max"], ins)
        if valida(c, g, f["min"], f["max"]):
            X.append(extrair(t, g, idade, ins)); y.append(c); ok += 1

Xtr, Xte, ytr, yte = train_test_split(X, y, test_size=0.2, random_state=1, stratify=y)
modelo = RandomForestClassifier(n_estimators=200, min_samples_leaf=2, random_state=1, n_jobs=-1).fit(Xtr, ytr)
print(classification_report(yte, modelo.predict(Xte)))
joblib.dump(modelo, "modelo.joblib", compress=3)
print("Modelo salvo em modelo.joblib")
