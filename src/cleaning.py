"""
Limpieza y transformación de los datos del proyecto EDA (campañas de marketing bancario).

Uso:  python src/cleaning.py
Entrada : data/raw/bank-additional.csv, data/raw/customer-details.xlsx
Salida  : data/processed/bank_clean.csv, data/processed/bank_customers_merged.csv
"""
from pathlib import Path
import pandas as pd
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
RAW, PROCESSED = ROOT / "data" / "raw", ROOT / "data" / "processed"

MESES = {"enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6,
         "julio": 7, "agosto": 8, "septiembre": 9, "octubre": 10, "noviembre": 11, "diciembre": 12}
COLS_DECIMAL_COMA = ["cons.price.idx", "cons.conf.idx", "euribor3m", "nr.employed"]
COLS_CATEGORICAS = ["job", "marital", "education", "contact", "poutcome"]


def cargar_banco() -> pd.DataFrame:
    """Lee el CSV; los campos con coma decimal se leen como texto y se convierten después."""
    df = pd.read_csv(RAW / "bank-additional.csv")
    return df.drop(columns="Unnamed: 0")  # índice residual de una exportación previa


def cargar_clientes() -> pd.DataFrame:
    """Une las 3 hojas del Excel (una por año de alta) en un único DataFrame."""
    hojas = pd.read_excel(RAW / "customer-details.xlsx", sheet_name=None)
    df = pd.concat([h.assign(anio_alta_hoja=int(nombre)) for nombre, h in hojas.items()],
                   ignore_index=True)
    return df.drop(columns="Unnamed: 0")


def parsear_fecha_es(serie: pd.Series) -> pd.Series:
    """'14-septiembre-2016' -> fecha real. Los nulos se mantienen como NaT."""
    partes = serie.str.split("-", expand=True)
    return pd.to_datetime(
        {"year": partes[2].astype(float), "month": partes[1].map(MESES), "day": partes[0].astype(float)},
        errors="coerce")


def limpiar_banco(df: pd.DataFrame, informe: dict) -> pd.DataFrame:
    df = df.copy()
    informe["filas_iniciales"] = len(df)
    informe["duplicados"] = int(df.duplicated(subset="id_").sum())
    df = df.drop_duplicates(subset="id_")

    # 1) Tipos: coma decimal -> float
    for c in COLS_DECIMAL_COMA:
        df[c] = pd.to_numeric(df[c].astype(str).str.replace(",", ".", regex=False), errors="coerce")

    # 2) Texto homogéneo (MARRIED -> married, etc.)
    for c in COLS_CATEGORICAS:
        df[c] = df[c].str.strip().str.lower()

    # 3) Fechas en español -> datetime + variables derivadas (contact_month / contact_year)
    df["date"] = parsear_fecha_es(df["date"])
    df["contact_month"] = df["date"].dt.month
    df["contact_year"] = df["date"].dt.year

    # 4) Variable objetivo binaria
    df["y"] = df["y"].map({"yes": 1, "no": 0}).astype(int)

    # 5) Valores desconocidos: las categóricas nulas pasan a 'unknown'
    #    (se conserva el hecho de que no se conoce, en lugar de eliminar filas)
    informe["nulos_antes"] = df.isna().sum()[lambda s: s > 0].to_dict()
    for c in COLS_CATEGORICAS:
        df[c] = df[c].fillna("unknown")
    for c in ["default", "housing", "loan"]:
        df[c] = df[c].map({0.0: "no", 1.0: "yes"}).fillna("unknown")

    # 6) Variables macroeconómicas: son indicadores del periodo; filas con igual
    #    (emp.var.rate, nr.employed, cons.conf.idx) comparten valor casi idéntico
    #    -> se imputa con la mediana de ese grupo.
    clave = ["emp.var.rate", "nr.employed", "cons.conf.idx"]
    for c in ["cons.price.idx", "euribor3m"]:
        df[c] = df[c].fillna(df.groupby(clave)[c].transform("median"))

    # 7) Edad: se marca la imputación y se rellena con la mediana por profesión
    df["age_imputada"] = df["age"].isna()
    df["age"] = df["age"].fillna(df.groupby("job")["age"].transform("median")).fillna(df["age"].median())
    df["age"] = df["age"].astype(int)

    # 8) pdays=999 significa "nunca contactado antes": indicador + NaN en lugar de 999
    df["contactado_antes"] = (df["pdays"] != 999).astype(int)
    df["pdays"] = df["pdays"].replace(999, np.nan)

    # 9) Variables derivadas
    df["grupo_edad"] = pd.cut(df["age"], bins=[0, 25, 35, 45, 55, 65, 120],
                              labels=["<=25", "26-35", "36-45", "46-55", "56-65", "66+"])
    df["duration_min"] = df["duration"] / 60

    informe["nulos_despues"] = df.isna().sum()[lambda s: s > 0].to_dict()
    return df


def limpiar_clientes(df: pd.DataFrame, informe: dict) -> pd.DataFrame:
    df = df.copy()
    informe["clientes_filas"] = len(df)
    informe["clientes_duplicados"] = int(df.duplicated(subset="ID").sum())
    df = df.drop_duplicates(subset="ID")
    df["Dt_Customer"] = pd.to_datetime(df["Dt_Customer"])
    informe["clientes_hoja_incoherente"] = int((df["Dt_Customer"].dt.year != df["anio_alta_hoja"]).sum())
    df["Hijos_total"] = df["Kidhome"] + df["Teenhome"]
    df["tramo_ingresos"] = pd.qcut(df["Income"], 4, labels=["Q1 (bajo)", "Q2", "Q3", "Q4 (alto)"])
    return df.drop(columns="anio_alta_hoja")


def main() -> None:
    informe: dict = {}
    banco = limpiar_banco(cargar_banco(), informe)
    clientes = limpiar_clientes(cargar_clientes(), informe)

    # validate="one_to_one" garantiza que el cruce no duplica ni pierde filas por error
    fusion = banco.merge(clientes, left_on="id_", right_on="ID", how="left",
                         validate="one_to_one", indicator=True)
    informe["sin_match_en_clientes"] = int((fusion["_merge"] != "both").sum())
    informe["clientes_sin_contacto_en_banco"] = int((~clientes["ID"].isin(banco["id_"])).sum())
    fusion = fusion.drop(columns=["ID", "_merge"])
    informe["contacto_antes_de_alta"] = int((fusion["date"] < fusion["Dt_Customer"]).sum())

    PROCESSED.mkdir(parents=True, exist_ok=True)
    banco.to_csv(PROCESSED / "bank_clean.csv", index=False)
    fusion.to_csv(PROCESSED / "bank_customers_merged.csv", index=False)
    for k, v in informe.items():
        print(f"{k}: {v}")


if __name__ == "__main__":
    main()
