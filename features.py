"""Regras de referência e extração de features (compartilhado entre treino e app)."""
import numpy as np

# Faixas de referência de glicose (mg/dL) por faixa etária. Ajuste com seu veterinário.
FAIXAS = {
    "filhote": {"nome": "Filhote (até 1 ano)", "min": 70, "max": 160},
    "adulto":  {"nome": "Adulto (1 a 10 anos)", "min": 70, "max": 150},
    "senior":  {"nome": "Sênior (mais de 10 anos)", "min": 70, "max": 160},
}
CLASSES = ["normal", "estresse", "hiperglicemia_persistente", "hipoglicemia", "oscilacao_ampla"]


def faixa_etaria(idade_anos: float) -> str:
    return "filhote" if idade_anos < 1 else ("adulto" if idade_anos <= 10 else "senior")


def reversoes(g, tol=10):
    """Quantas vezes a curva troca de subida para descida (ignora variações < tol mg/dL)."""
    d = np.diff(np.asarray(g, float)); d = d[np.abs(d) >= tol]
    return int((np.sign(d[1:]) != np.sign(d[:-1])).sum()) if len(d) > 1 else 0


def extrair(t, g, idade, insulina):
    t, g = np.asarray(t, float), np.asarray(g, float)
    f = FAIXAS[faixa_etaria(idade)]; lo, hi = f["min"], f["max"]
    slope = np.polyfit(t, g, 1)[0] if len(t) > 1 and np.ptp(t) > 0 else 0.0
    d = np.abs(np.diff(g)) if len(g) > 1 else np.zeros(1)
    return [g.mean(), g.max(), g.min(), np.ptp(g), t[int(np.argmin(g))], slope, g[0], g[-1],
            (g > hi).mean(), (g < lo).mean(), idade, int(bool(insulina)),
            g.std(), (g < 50).mean(), len(g), np.ptp(t), d.max(), g.min() - lo, g.max() - hi,
            reversoes(g), g[-1] - g[0]]
