"""Gera curvas sintéticas rotuladas e treina um RandomForest. Uso: python train_model.py"""
import numpy as np, joblib
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report
from features import FAIXAS, CLASSES, faixa_etaria, extrair

rng = np.random.default_rng(42)


def curva(classe, idade, insulina):
    f = FAIXAS[faixa_etaria(idade)]; lo, hi = f["min"], f["max"]
    n = int(rng.integers(4, 11))
    t = np.sort(np.concatenate([[0], rng.uniform(0.5, 12, n - 1)]))
    if classe == "normal":
        g = rng.uniform(lo + 10, hi - 25) + rng.normal(0, 8, n)
    elif classe == "estresse":
        pico = rng.uniform(180, 320); base = rng.uniform(lo + 10, hi - 25)
        g = base + (pico - base) * np.exp(-t / rng.uniform(1, 3)) + rng.normal(0, 8, n)
    elif classe == "hiperglicemia_persistente":
        g = rng.uniform(hi + 40, 420) + rng.normal(0, 20, n)
        if insulina: g = g - 60 * np.sin(np.pi * t / 12) * rng.uniform(0, 1)
    elif classe == "hipoglicemia":
        base = rng.uniform(lo, hi); nadir = rng.uniform(25, lo - 5); c = rng.uniform(3, 9)
        g = base - (base - nadir) * np.exp(-((t - c) ** 2) / 6) + rng.normal(0, 5, n)
    else:  # oscilacao_ampla
        m = rng.uniform(150, 230); a = rng.uniform(70, 140)
        g = m + a * np.sin(2 * np.pi * t / 12 + rng.uniform(0, 6)) + rng.normal(0, 10, n)
    return t, np.clip(g, 20, 600)


X, y = [], []
for _ in range(12000):
    c = CLASSES[int(rng.integers(len(CLASSES)))]
    idade = float(rng.choice([rng.uniform(0.1, 1), rng.uniform(1, 10), rng.uniform(10, 20)]))
    ins = rng.random() < (0.15 if c in ("normal", "estresse") else 0.5)
    t, g = curva(c, idade, ins)
    X.append(extrair(t, g, idade, ins)); y.append(c)

Xtr, Xte, ytr, yte = train_test_split(X, y, test_size=0.2, random_state=1, stratify=y)
modelo = RandomForestClassifier(n_estimators=100, min_samples_leaf=3, random_state=1, n_jobs=-1).fit(Xtr, ytr)
print(classification_report(yte, modelo.predict(Xte)))
joblib.dump(modelo, "modelo.joblib", compress=3)
print("Modelo salvo em modelo.joblib")
