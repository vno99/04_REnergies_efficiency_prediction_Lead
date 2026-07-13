import io
import requests
import zipfile
import pandas as pd
from datetime import datetime
from dotenv import load_dotenv
import os
import boto3
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from fastapi.responses import StreamingResponse
import csv
import io
import requests


load_dotenv()

path = "unzip"
last_download_filename = "rte_last_download"

API_KEY_S3 = os.environ.get("AWS_ACCESS_KEY_ID")
API_SECRET_KEY_S3 = os.environ.get("AWS_SECRET_ACCESS_KEY")
DATABASE_URL = os.environ.get("DATABASE_URL")

bucket = "renergies99-lead-bucket"

def s3_cred():
    load_dotenv()

    return boto3.client(
        "s3",
        aws_access_key_id=API_KEY_S3,
        aws_secret_access_key=API_SECRET_KEY_S3,
        region_name="eu-west-3"
    )

s3 = s3_cred()

def getNow():
    return datetime.now().strftime("%Y-%m-%d")

def get_rte_last_download():
    try:
        key = f"public/prod/{last_download_filename}"

        obj = s3.get_object(Bucket=bucket, Key=key)
        ligne = obj["Body"].read().decode("utf-8")

    except:
        return "Cannot get rte last download data"
    
    return ligne

def is_rte_data_already_downloaded():
    return getNow() == get_rte_last_download()


def fill_2024_columns(df):
    new_cols = [
        "Flux physiques d'Auvergne-Rhône-Alpes vers Auvergne-Rhône-Alpes",
        "Flux physiques de Bourgogne-Franche-Comté vers Auvergne-Rhône-Alpes",
        "Flux physiques de Bretagne vers Auvergne-Rhône-Alpes",
        "Flux physiques de Centre-Val de Loire vers Auvergne-Rhône-Alpes",
        "Flux physiques de Grand-Est vers Auvergne-Rhône-Alpes",
        "Flux physiques de Hauts-de-France vers Auvergne-Rhône-Alpes",
        "Flux physiques d'Ile-de-France vers Auvergne-Rhône-Alpes",
        "Flux physiques de Normandie vers Auvergne-Rhône-Alpes",
        "Flux physiques de Nouvelle-Aquitaine vers Auvergne-Rhône-Alpes",
        "Flux physiques d'Occitanie vers Auvergne-Rhône-Alpes",
        "Flux physiques de Pays-de-la-Loire vers Auvergne-Rhône-Alpes",
        "Flux physiques de PACA vers Auvergne-Rhône-Alpes",
        "Flux physiques de Auvergne-Rhône-Alpes vers Auvergne-Rhône-Alpes",
        "Flux physiques de Auvergne-Rhône-Alpes vers Bourgogne-Franche-Comté",
        "Flux physiques de Auvergne-Rhône-Alpes vers Bretagne",
        "Flux physiques de Auvergne-Rhône-Alpes vers Centre-Val de Loire",
        "Flux physiques de Auvergne-Rhône-Alpes vers Grand-Est",
        "Flux physiques de Auvergne-Rhône-Alpes vers Hauts-de-France",
        "Flux physiques de Auvergne-Rhône-Alpes vers Ile-de-France",
        "Flux physiques de Auvergne-Rhône-Alpes vers Normandie",
        "Flux physiques de Auvergne-Rhône-Alpes vers Nouvelle-Aquitaine",
        "Flux physiques de Auvergne-Rhône-Alpes vers Occitanie",
        "Flux physiques de Auvergne-Rhône-Alpes vers Pays-de-la-Loire",
        "Flux physiques de Auvergne-Rhône-Alpes vers PACA",
        "Flux physiques Allemagne vers Auvergne-Rhône-Alpes",
        "Flux physiques Belgique vers Auvergne-Rhône-Alpes",
        "Flux physiques Espagne vers Auvergne-Rhône-Alpes",
        "Flux physiques Italie vers Auvergne-Rhône-Alpes",
        "Flux physiques Luxembourg vers Auvergne-Rhône-Alpes",
        "Flux physiques Royaume-Uni vers Auvergne-Rhône-Alpes",
        "Flux physiques Suisse vers Auvergne-Rhône-Alpes",
        "Flux physiques de Auvergne-Rhône-Alpes vers Allemagne",
        "Flux physiques de Auvergne-Rhône-Alpes vers Belgique",
        "Flux physiques de Auvergne-Rhône-Alpes vers Espagne",
        "Flux physiques de Auvergne-Rhône-Alpes vers Italie",
        "Flux physiques de Auvergne-Rhône-Alpes vers Luxembourg",
        "Flux physiques de Auvergne-Rhône-Alpes vers Royaume-Uni",
        "Flux physiques de Auvergne-Rhône-Alpes vers Suisse"
    ]
    position = 16
    for i, col in enumerate(new_cols, start=1):
        df.insert(position+i, col, "-")


def get_previous_rte_data():
    xls_list = [
        "https://renergies99-lead-bucket.s3.eu-west-3.amazonaws.com/public/prod/unzipped/regional/eCO2mix_RTE_Auvergne-Rh%C3%B4ne-Alpes_Annuel-Definitif_2021.xls",
        "https://renergies99-lead-bucket.s3.eu-west-3.amazonaws.com/public/prod/unzipped/regional/eCO2mix_RTE_Auvergne-Rh%C3%B4ne-Alpes_Annuel-Definitif_2022.xls",
        "https://renergies99-lead-bucket.s3.eu-west-3.amazonaws.com/public/prod/unzipped/regional/eCO2mix_RTE_Auvergne-Rh%C3%B4ne-Alpes_Annuel-Definitif_2023.xls",
        "https://renergies99-lead-bucket.s3.eu-west-3.amazonaws.com/public/prod/unzipped/regional/eCO2mix_RTE_Auvergne-Rh%C3%B4ne-Alpes_Annuel-Definitif_2024.xls",
        "https://renergies99-lead-bucket.s3.eu-west-3.amazonaws.com/public/prod/unzipped/regional/eCO2mix_RTE_Auvergne-Rh%C3%B4ne-Alpes_Annuel-Definitif_2025.xls"
    ]

    df_array = []

    for xls_url in xls_list:
        df = pd.read_csv(f"{xls_url}", encoding="ISO-8859-1", sep="\t")

        if "2024" in xls_url:
            fill_2024_columns(df)

        df = df.iloc[:-1, :-1] #remove last line and last column

        df_array.append(df)

    return df_array


def en_cours_rte_data():
    response = requests.get("https://eco2mix.rte-france.com/download/eco2mix/eCO2mix_RTE_Auvergne-Rhone-Alpes_En-cours-TR.zip")
    response.raise_for_status()

    with zipfile.ZipFile(io.BytesIO(response.content)) as zip_ref:
        zip_ref.extractall(path)

    # the file is upposed to be encoded in ISO-8859-1
    df = pd.read_csv(f"{path}/eCO2mix_RTE_Auvergne-Rhone-Alpes_En-cours-TR.xls", encoding="ISO-8859-1", sep="\t")
    df = df.iloc[:-1, :-1] #remove last line and last column
    df = df[df["Date"] != getNow()]
    
    return df


def rte_df_to_csv(df):
    final_csv_filename = "eCO2mix_RTE_Auvergne-Rhone-Alpes.csv"
    
    df = df[~df["Heures"].str.contains(":15|:45")]

    # Sélection automatique des colonnes TCO... (%) ou TCH... (%) si besoin
    cols_pct = [c for c in df.columns if "TCO" in c or "TCH" in c]

    # Conversion en float
    df[cols_pct] = df[cols_pct].apply(
        lambda col: pd.to_numeric(col, errors="coerce")
    )

    df.to_csv(
        f"s3://renergies99-lead-bucket/public/prod/{final_csv_filename}",
        index=False,
        storage_options={
            "key": API_KEY_S3,
            "secret": API_SECRET_KEY_S3,
        },
    )

    key = f"public/prod/{last_download_filename}"

    s3.put_object(
        Bucket=bucket,
        Key=key,
        Body=getNow().encode("utf-8")
    )

def rte_data(deb, fin, type):
    engine = create_engine(DATABASE_URL)

    def generate_csv():
        with engine.connect() as conn:
            columns = conn.execute(
                text("""
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name = :table
                """),
                {"table": type}
            ).fetchall()
            columns = [col[0] for col in columns]

            desired = ["Date", "Heures", "Nucleaire", "Gaz", "Charbon", "Fioul", 
                   "Hydraulique", "Eolien", "Solaire", "Bioenergies", "Consommation", "Ech__physiques", "Taux_de_Co2", "TCH_Solaire____"]
            
            selected_columns = [col for col in desired if col in columns]

            sql = f"""
                SELECT {', '.join('"' + c + '"' for c in selected_columns)}
                FROM public.{type}
                WHERE EXTRACT(YEAR FROM TO_DATE("Date", 'YYYY-MM-DD')) between :deb and :fin 
                ORDER BY "Date", "Heures"
            """

            result = conn.execute(
                text(sql),
                    {"deb": deb, "fin": fin}
                )
            
            writer = csv.writer(io.StringIO())
            yield ",".join(result.keys()) + "\n"

            for row in result:
                yield ",".join(map(str, row)) + "\n"

    return StreamingResponse(
        generate_csv(),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={type}.csv"}
    )

def rte_daily_data(date):
    date_str = datetime.strptime(date, "%d/%m/%Y").strftime("%Y-%m-%d")
    response = requests.get(f"https://eco2mix.rte-france.com/curves/eco2mixDl?date={date}")
    response.raise_for_status()

    with zipfile.ZipFile(io.BytesIO(response.content)) as zip_ref:
        zip_ref.extractall(path)

    # the file is supposed to be encoded in ISO-8859-1
    df = pd.read_csv(f"{path}/eCO2mix_RTE_{date_str}.xls", encoding="ISO-8859-1", sep="\t", index_col=False)

    df = df.iloc[:-1, :-1] #remove last line and last column
    df["Heures"] = df["Heures"] + ":00"

    df.to_excel(f"s3://renergies99-lead-bucket/public/raw/rte/daily/eCO2mix_RTE_{date_str}.xlsx")

    df = df[~df["Heures"].astype(str).str.endswith(("15:00", "45:00"))]

    # Colonnes à convertir en float (exclusions)
    cols_float = [
        c for c in df.columns
        if c not in ["Périmètre","Nature","Date", "Heures"]
    ]

    # Conversion en float (les valeurs invalides deviennent NaN)
    df[cols_float] = df[cols_float].apply(
        lambda col: pd.to_numeric(col, errors="coerce")
    )

    # Convertir le DataFrame en CSV et résidant en mémoire
    # csv_buffer = io.StringIO()
    df.to_csv(f"s3://renergies99-lead-bucket/public/prod/daily/eCO2mix_RTE_{date_str}.csv", index=False, encoding="utf-8")

    
if __name__ == "__main__":
    """
    if not is_rte_data_already_downloaded():
        previous_data = get_previous_rte_data()
        en_cours_data = en_cours_rte_data()

        previous_data.append(en_cours_data)

        df = pd.concat(previous_data, ignore_index=True)

        rte_df_to_csv(df)

        rte_daily_data("08/01/2025")
    """
