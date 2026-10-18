"""
Análisis descriptivo y visualización.  Uso: python src/analysis.py
Entrada: data/processed/bank_customers_merged.csv  |  Salida: figures/*.png + resumen en consola
"""
from pathlib import Path
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import seaborn as sns
from scipy import stats

ROOT = Path(__file__).resolve().parent.parent
FIG = ROOT / "figures"
FIG.mkdir(exist_ok=True)
sns.set_theme(style="whitegrid", palette="deep")
MESES = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]


def tasa(df: pd.DataFrame, col: str) -> pd.DataFrame:
    """Tasa de conversión (%) y nº de clientes por categoría, ordenada de mayor a menor."""
    t = df.groupby(col, observed=True)["y"].agg(clientes="size", tasa_pct=lambda s: s.mean() * 100)
    return t.sort_values("tasa_pct", ascending=False).round(2)


def guardar(nombre: str) -> None:
    plt.tight_layout()
    plt.savefig(FIG / f"{nombre}.png", dpi=130)
    plt.close()


def barras_tasa(df, col, titulo, nombre, orden=None, horizontal=False):
    t = tasa(df, col)
    if orden is not None:
        t = t.reindex(orden)
    fig, ax = plt.subplots(figsize=(8, 4.5))
    base = df["y"].mean() * 100
    if horizontal:
        sns.barplot(x=t["tasa_pct"], y=t.index.astype(str), color="#4c72b0", ax=ax)
        ax.axvline(base, color="red", ls="--", label=f"Media global {base:.1f}%")
        ax.set_xlabel("Tasa de conversión (%)"); ax.set_ylabel("")
    else:
        sns.barplot(x=t.index.astype(str), y=t["tasa_pct"], color="#4c72b0", ax=ax)
        ax.axhline(base, color="red", ls="--", label=f"Media global {base:.1f}%")
        ax.set_ylabel("Tasa de conversión (%)"); ax.set_xlabel("")
    ax.set_title(titulo); ax.legend()
    guardar(nombre)
    return t


def main() -> None:
    df = pd.read_csv(ROOT / "data" / "processed" / "bank_customers_merged.csv", parse_dates=["date", "Dt_Customer"])
    out = {}
    print(f"Registros: {len(df):,} | Conversión global: {df.y.mean()*100:.2f}% ({df.y.sum():,} suscripciones)\n")

    # ---------- Descriptivo numérico ----------
    num = ["age", "duration", "campaign", "previous", "pdays", "emp.var.rate", "cons.price.idx",
           "cons.conf.idx", "euribor3m", "nr.employed", "Income", "Kidhome", "Teenhome", "NumWebVisitsMonth"]
    desc = df[num].describe().T
    desc["mediana"] = df[num].median()
    desc["asimetria"] = df[num].skew()
    print(desc[["count", "mean", "mediana", "std", "min", "max", "asimetria"]].round(2).to_string(), "\n")

    # ---------- Fig 1: distribución de la variable objetivo y variables clave ----------
    fig, ax = plt.subplots(1, 3, figsize=(15, 4))
    df["y"].map({0: "No", 1: "Sí"}).value_counts().plot.bar(ax=ax[0], color=["#c44e52", "#55a868"], rot=0)
    ax[0].set_title("Suscripción del depósito (y)"); ax[0].set_xlabel("")
    sns.histplot(df["age"], bins=30, kde=True, ax=ax[1]); ax[1].set_title("Distribución de la edad")
    sns.histplot(df["duration"].clip(upper=1500), bins=50, ax=ax[2]); ax[2].set_title("Duración de la llamada (s, recortada a 1500)")
    guardar("01_distribuciones")

    # ---------- Fig 2: duración vs conversión ----------
    print("Duración mediana (s) por resultado:\n", df.groupby("y")["duration"].median().to_string())
    fig, ax = plt.subplots(figsize=(7, 4.5))
    sns.boxplot(data=df, x=df["y"].map({0: "No suscribe", 1: "Suscribe"}), y="duration", showfliers=False, ax=ax)
    ax.set_title("Duración de la llamada según resultado"); ax.set_xlabel(""); ax.set_ylabel("Segundos")
    guardar("02_duracion_vs_y")

    # ---------- Fig 3: canal, contacto previo ----------
    for col, tit, nom in [("contact", "Conversión por canal de contacto", "03_canal"),
                          ("poutcome", "Conversión según resultado de la campaña anterior", "04_poutcome")]:
        print(f"\n{tit}\n", barras_tasa(df, col, tit, nom).to_string())

    # ---------- Fig 5-6: perfil (profesión, educación, edad) ----------
    print("\nConversión por profesión\n", barras_tasa(df, "job", "Conversión por profesión", "05_profesion", horizontal=True).to_string())
    print("\nConversión por educación\n", barras_tasa(df, "education", "Conversión por nivel educativo", "06_educacion", horizontal=True).to_string())
    orden_edad = ["<=25", "26-35", "36-45", "46-55", "56-65", "66+"]
    print("\nConversión por grupo de edad\n", barras_tasa(df, "grupo_edad", "Conversión por grupo de edad", "07_edad", orden_edad).to_string())

    # ---------- Fig 8: estacionalidad y evolución anual ----------
    m = df.groupby("contact_month")["y"].mean().mul(100)
    a = df.groupby("contact_year")["y"].mean().mul(100)
    print("\nConversión por mes:\n", m.round(2).to_string(), "\nConversión por año:\n", a.round(2).to_string())
    fig, ax = plt.subplots(1, 2, figsize=(13, 4))
    ax[0].plot([MESES[int(i) - 1] for i in m.index], m.values, marker="o"); ax[0].set_title("Conversión por mes de contacto (%)")
    ax[0].set_ylim(0, None)
    ax[1].plot(a.index.astype(int), a.values, marker="o"); ax[1].set_title("Conversión por año de contacto (%)"); ax[1].set_ylim(0, None)
    ax[1].set_xticks(a.index.astype(int))
    guardar("08_temporal")

    # ---------- Fig 9: nº de contactos ----------
    df["campaign_cap"] = df["campaign"].clip(upper=10)
    t = df.groupby("campaign_cap")["y"].mean().mul(100)
    print("\nConversión según nº de contactos (10 = 10 o más):\n", t.round(2).to_string())
    fig, ax = plt.subplots(figsize=(8, 4.5))
    sns.barplot(x=t.index, y=t.values, color="#4c72b0", ax=ax)
    ax.set_title("Conversión según nº de contactos en la campaña"); ax.set_xlabel("Contactos (10 = 10 o más)"); ax.set_ylabel("%")
    guardar("09_n_contactos")

    # ---------- Datos del Excel: ingresos, hijos, visitas web ----------
    t_inc = tasa(df, "tramo_ingresos").sort_index()
    print("\nConversión por tramo de ingresos (cuartiles)\n", t_inc.to_string())
    print("\nConversión por nº de hijos\n", tasa(df, "Hijos_total").sort_index().to_string())
    df["tramo_web"] = pd.qcut(df["NumWebVisitsMonth"], 4, duplicates="drop")
    print("\nConversión por visitas web mensuales (cuartiles)\n", tasa(df, "tramo_web").sort_index().to_string())
    fig, ax = plt.subplots(1, 3, figsize=(15, 4))
    t_inc["tasa_pct"].plot.bar(ax=ax[0], rot=0); ax[0].set_title("Conversión por cuartil de ingresos (%)"); ax[0].set_xlabel("")
    tasa(df, "Hijos_total").sort_index()["tasa_pct"].plot.bar(ax=ax[1], rot=0); ax[1].set_title("Conversión por nº de hijos (%)"); ax[1].set_xlabel("")
    tasa(df, "tramo_web").sort_index()["tasa_pct"].plot.bar(ax=ax[2], rot=0); ax[2].set_title("Conversión por visitas web/mes (%)"); ax[2].set_xlabel("")
    guardar("10_datos_cliente")

    # ---------- Macroeconomía ----------
    df["euribor_tramo"] = pd.cut(df["euribor3m"], [0, 1, 2, 4, 5.5])
    print("\nConversión por tramo de Euribor 3m\n", tasa(df, "euribor_tramo").sort_index().to_string())
    fig, ax = plt.subplots(figsize=(7, 4.5))
    tasa(df, "euribor_tramo").sort_index()["tasa_pct"].plot.bar(ax=ax, rot=0)
    ax.set_title("Conversión según Euribor a 3 meses (%)"); ax.set_xlabel("")
    guardar("11_euribor")

    # ---------- Correlaciones ----------
    cols_corr = ["y", "age", "duration", "campaign", "previous", "emp.var.rate", "cons.price.idx",
                 "cons.conf.idx", "euribor3m", "nr.employed", "Income", "Kidhome", "Teenhome", "NumWebVisitsMonth"]
    corr = df[cols_corr].corr()
    print("\nCorrelación con y:\n", corr["y"].drop("y").sort_values(key=abs, ascending=False).round(3).to_string())
    fig, ax = plt.subplots(figsize=(10, 8))
    sns.heatmap(corr, annot=True, fmt=".2f", cmap="coolwarm", center=0, ax=ax, annot_kws={"size": 7})
    ax.set_title("Matriz de correlación")
    guardar("12_correlaciones")

    # ---------- Contrastes estadísticos ----------
    print("\n--- Contrastes ---")
    for col in ["contact", "poutcome", "job", "education", "marital", "housing", "loan"]:
        chi2, p, _, _ = stats.chi2_contingency(pd.crosstab(df[col], df["y"]))
        print(f"chi2 {col:10s} p={p:.2e}")
    for col in ["Income", "NumWebVisitsMonth", "age", "Kidhome", "Teenhome"]:
        t_, p = stats.ttest_ind(df.loc[df.y == 1, col], df.loc[df.y == 0, col], equal_var=False)
        print(f"t-test {col:18s} media yes={df.loc[df.y==1,col].mean():.2f} no={df.loc[df.y==0,col].mean():.2f} p={p:.3f}")

    # ---------- Outliers (IQR) ----------
    print("\n--- Outliers (regla 1.5*IQR) ---")
    for c in ["age", "duration", "campaign"]:
        q1, q3 = df[c].quantile([.25, .75]); i = q3 - q1
        n = ((df[c] < q1 - 1.5 * i) | (df[c] > q3 + 1.5 * i)).sum()
        print(f"{c}: {n} ({n/len(df)*100:.1f}%)")

    # Tabla resumen de conversión por perfil de cliente más/menos favorable
    print("\nCasos extremos de conversión (job x contact, n>=200):")
    t = df.groupby(["job", "contact"])["y"].agg(["size", "mean"]).query("size>=200").sort_values("mean")
    print(t.round(3).head(3).to_string()); print(t.round(3).tail(3).to_string())
    print("\nDefault:", df["default"].value_counts().to_dict())
    print("Housing:", df["housing"].value_counts().to_dict())


if __name__ == "__main__":
    main()
