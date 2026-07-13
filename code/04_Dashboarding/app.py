import streamlit as st
import pandas as pd
import plotly.express as px
import requests
import logging
import time
from datetime import datetime

# Configiration de l'application
st.set_page_config(
    page_title="eCO2mix – France vs Auvergne-Rhône-Alpes",
    layout="wide"
)

# Fonctions
# Préparation des dataframes
def prepare_df(df, zone):
    # datetime
    df["datetime"] = pd.to_datetime(
        df["Date"] + " " + df["Heures"],
        format="%Y-%m-%d %H:%M",
        errors="coerce"
    )
    df = df.sort_values("datetime")

    df["year"] = df["datetime"].dt.year
    df["month"] = df["datetime"].dt.month
    df["day"] = df["datetime"].dt.day
    df["hour"] = df["datetime"].dt.hour

    # Jours de semaine
    jours_fr = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"]
    df["weekday_num"] = df["datetime"].dt.dayofweek
    df["weekday_fr"] = df["weekday_num"].map(dict(enumerate(jours_fr)))
    df["is_weekend"] = df["weekday_fr"].isin(["Samedi", "Dimanche"])

    # Mix énergétique global
    prod_cols = [c for c in [
        "Nucléaire", "Gaz", "Charbon", "Fioul",
        "Hydraulique", "Eolien", "Solaire", "Bioénergies"
    ] if c in df.columns]

    if prod_cols:
        df["production_totale"] = df[prod_cols].sum(axis=1)
    else:
        df["production_totale"] = pd.NA

    # Colonne pour identifier la zone
    df["zone"] = zone

    return df

COL_TCH = "TCH_Solaire____"  # nom exact de la variable dans df_reg

def get_daily_tch_solaire_regional(df_reg: pd.DataFrame) -> pd.DataFrame:
    """Historique quotidien de TCH Solaire (%) pour Auvergne-Rhône-Alpes."""
    df_zone = df_reg.dropna(subset=["datetime", COL_TCH]).copy()

    df_zone["Date"] = df_zone["datetime"].dt.date
    df_daily = (
        df_zone
        .groupby("Date", as_index=False)[COL_TCH]
        .mean()
    )
    df_daily["Date"] = pd.to_datetime(df_daily["Date"], format="%Y-%m-%d")
    df_daily["type"] = "Historique"
    return df_daily

def load_data():
    # Datasets
    #df_nat = pd.read_csv("https://renergies99-lead-bucket.s3.eu-west-3.amazonaws.com/public/prod/eCO2mix_RTE_Annuel-Definitif.csv")
    df_nat = pd.read_csv(f"https://renergies99lead-api-renergy-lead.hf.space/rte_data?deb=2020&fin={datetime.now().strftime('%Y')}&type=rte_national")
    print("load_data load_data load_data", type(df_nat), df_nat.shape)
    df_nat_prep = prepare_df(df_nat, zone="France")

    return df_nat_prep

def load_regional_data():
    # Datasets
    #df_reg = pd.read_csv("https://renergies99-lead-bucket.s3.eu-west-3.amazonaws.com/public/prod/eCO2mix_RTE_Auvergne-Rhone-Alpes.csv")
    df_reg = pd.read_csv(f"https://renergies99lead-api-renergy-lead.hf.space/rte_data?deb=2021&fin={datetime.now().strftime('%Y')}&type=rte_regional")
    df_reg_prep = prepare_df(df_reg, zone="Auvergne-Rhône-Alpes")

    return df_reg_prep

def load_api_data(url, data_type):
    logging.info(f"LOAD {data_type}")

    max_retries = 3
    wait = 1

    for _ in range(max_retries):

        try:
            response = requests.get(url)
            response.raise_for_status()

            logging.info(response.content)
            break

        except requests.exceptions.HTTPError as e:
            if response.status_code == 429:
                retry_after = int(response.headers.get("Retry-After", wait))
                logging.error(f"Error 429. Wait for {retry_after} seconds...")
                time.sleep(retry_after)
                wait *= 2
            else:
                raise

    else:
        logging.error("Failure after {max_retries} retries")

def load_rte_data():
    rte_last_download_response = requests.get("https://renergies99lead-api-renergy-lead.hf.space/rte_last_download")
    if rte_last_download_response.json() != datetime.now().strftime("%Y-%m-%d"):
        load_api_data("https://renergies99lead-api-renergy-lead.hf.space/load_rte_data", "RTE")

    return load_regional_data()

def load_predictions_file() -> pd.DataFrame:
    """
   À adapter :
    - le chemin du fichier
    - le nom de la colonne de prédiction si différent
    """ 
    # WARNING : A adapter avec le chemin vers le fichier sur le S3
    df_pred = pd.read_csv("https://renergies99-lead-bucket.s3.eu-west-3.amazonaws.com/public/prediction/pred_tch_solaire_rhone_alpes.csv")

    df_pred["Date"] = pd.to_datetime(df_pred["Date"], format="%Y-%m-%d", errors="coerce")

    # Harmonisation du nom de la colonne de prédiction
    if COL_TCH in df_pred.columns:
        pass
    elif "TCH_solaire_pred" in df_pred.columns:
        df_pred = df_pred.rename(columns={"TCH_solaire_pred": COL_TCH})
    else:
        st.error(
            f"Le fichier de prédiction doit contenir une colonne '{COL_TCH}' "
            "ou 'TCH_solaire_pred'."
        )
        return pd.DataFrame()

    df_pred["type"] = "Prédiction"
    return df_pred[["Date", COL_TCH, "type"]]

def call_predict():
    predi_last_download_response = requests.get("https://renergies99lead-api-renergy-lead.hf.space/predi_last_download")
    if predi_last_download_response.json() == datetime.now().strftime("%Y-%m-%d"):
        return "Prediction data is already downloaded today"

    urls = [
        "https://renergies99-lead-bucket.s3.eu-west-3.amazonaws.com/public/solar/predi_data.csv",
        "https://renergies99-lead-bucket.s3.eu-west-3.amazonaws.com/public/openweathermap/openweathermap_forecasts.csv"
    ]

    payload = {"urls": urls}

    data = requests.post("https://renergies99lead-api-renergy-lead.hf.space/prep_data", json=payload)
    json_data = data.json()
    print("json_data", json_data)

    response = requests.post("https://renergies99lead-api-renergy-lead.hf.space/predict")
    print("response.content", response.content)
    

# Principes de navigation
st.sidebar.title("Navigation")
mode = st.sidebar.radio(
    "Choix du type de dashboard :",
    ["Descriptif", "Prédiction"],
    index=0
)

# Chargement des données en cache
df_nat = load_data()

df_reg = load_rte_data()


#load_api_data("https://renergies99lead-api-renergy-lead.hf.space/load_rte_data", "RTE")
#load_api_data("https://renergies99lead-api-renergy-lead.hf.space/load_openweathermap_forecasts", "OPENWEATHERMAP FORECASTS")
#load_api_data("https://renergies99lead-api-renergy-lead.hf.space/load_solar_data", "SOLAR FORECAST")

#call_predict()

# MODE 1 : DESCRIPTIF
if mode == "Descriptif":

    # Sidebar filtres
    st.sidebar.subheader("Filtres descriptifs")

    vue = st.sidebar.radio(
        "Vue",
        ["France", "Auvergne-Rhône-Alpes", "Comparaison"],
        index=2
    )

    # Filtrage simple
    if vue == "France":
        df_current = df_nat.copy()
    elif vue == "Auvergne-Rhône-Alpes":
        df_current = df_reg.copy()
    else:
        df_current = pd.concat([df_nat, df_reg], ignore_index=True)

    # Sélection période (filtre par année)
    annees_dispo = sorted(df_current["year"].dropna().unique())
    annee_min, annee_max = int(annees_dispo[0]), int(annees_dispo[-1])

    annee_range = st.sidebar.slider(
        "Filtre sur l'année",
        min_value=annee_min,
        max_value=annee_max,
        value=(annee_min, annee_max),
        step=1
    )

    mask_year = (df_current["year"] >= annee_range[0]) & (df_current["year"] <= annee_range[1])
    df_current = df_current[mask_year]

    # Titre principal
    st.title("eCO2mix – Comparaison France / Auvergne-Rhône-Alpes")

    if vue == "Comparaison":
        st.caption("Comparaison des indicateurs entre la France entière et la région Auvergne-Rhône-Alpes.")
    else:
        st.caption(f"Vue détaillée : **{vue}**")

    # Onglets principaux
    tab_cons, tab_mix, tab_co2, tab_ech = st.tabs(
        [" Consommation", "Mix énergétique", "CO₂", "Échanges"]
    )

    # 1. Consommation
    with tab_cons:
        st.subheader("Évolution de la consommation")

        # Consommation moyenne quotidienne
        df_daily = (
            df_current.dropna(subset=["Date", "Consommation"])
                     .groupby(["Date", "zone"], as_index=False)["Consommation"]
                     .mean()
        )
        df_daily["Date"] = pd.to_datetime(df_daily["Date"], format="%Y-%m-%d", errors="coerce")

        if vue == "Comparaison":
            fig = px.line(
                df_daily,
                x="Date",
                y="Consommation",
                color="zone",
                title="Consommation moyenne quotidienne – France vs Auvergne-Rhône-Alpes"
            )
        else:
            fig = px.line(
                df_daily,
                x="Date",
                y="Consommation",
                title=f"Consommation moyenne quotidienne – {vue}"
            )

        st.plotly_chart(fig, use_container_width=True)

        # Saisonnalité horaire
        st.markdown("### Profil horaire moyen de consommation")

        df_hour = (
            df_current.dropna(subset=["hour", "Consommation"])
                      .groupby(["hour", "zone"], as_index=False)["Consommation"]
                      .mean()
        )

        if vue == "Comparaison":
            fig2 = px.line(
                df_hour,
                x="hour",
                y="Consommation",
                color="zone",
                markers=True,
                title="Consommation moyenne par heure de la journée"
            )
        else:
            fig2 = px.bar(
                df_hour,
                x="hour",
                y="Consommation",
                title=f"Consommation moyenne par heure de la journée – {vue}"
            )

        st.plotly_chart(fig2, use_container_width=True)

        # Heatmap heure x jour de semaine
        st.markdown("### Consommation moyenne par heure et jour de semaine")

        if vue == "Comparaison":
            zone_heatmap = st.selectbox(
                "Zone pour la heatmap",
                ["France", "Auvergne-Rhône-Alpes"],
                index=0
            )
            df_heat = df_current[df_current["zone"] == zone_heatmap]
        else:
            df_heat = df_current

        pivot = (
            df_heat.dropna(subset=["weekday_fr", "hour", "Consommation"])
                   .groupby(["weekday_fr", "hour"], as_index=False)["Consommation"]
                   .mean()
        )

        # Forcer l'ordre des jours
        jours_fr = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"]
        pivot["weekday_fr"] = pd.Categorical(pivot["weekday_fr"], categories=jours_fr, ordered=True)
        pivot = pivot.sort_values(["weekday_fr", "hour"])

        fig3 = px.density_heatmap(
            pivot,
            x="hour",
            y="weekday_fr",
            z="Consommation",
            nbinsx=24,
            histfunc="avg",
            color_continuous_scale="YlOrRd",
            title=f"Consommation moyenne par heure et jour de semaine – {vue if vue != 'Comparaison' else zone_heatmap}"
        )
        st.plotly_chart(fig3, use_container_width=True)

    # 2. Mix énergétique
    with tab_mix:
        st.subheader("Répartition du mix énergétique")

        prod_cols = [c for c in [
            "Nucléaire", "Gaz", "Charbon", "Fioul",
            "Hydraulique", "Eolien", "Solaire", "Bioénergies"
        ] if c in df_current.columns]

        if not prod_cols:
            st.warning("Colonnes de production non trouvées dans le dataset courant.")
        else:
            mix_global = (
                df_current.groupby("zone")[prod_cols]
                          .mean()
                          .reset_index()
                          .melt(
                              id_vars="zone",
                              value_vars=prod_cols,
                              var_name="source",
                              value_name="production_moyenne"
                          )
            )

            if vue == "Comparaison":
                fig_mix = px.bar(
                    mix_global,
                    x="source",
                    y="production_moyenne",
                    color="zone",
                    barmode="group",
                    title="Production moyenne par filière – France vs Auvergne-Rhône-Alpes"
                )
            else:
                fig_mix = px.pie(
                    mix_global[mix_global["zone"] == df_current["zone"].iloc[0]],
                    names="source",
                    values="production_moyenne",
                    title=f"Répartition moyenne du mix énergétique – {vue}",
                    hole=0.4
                )
                fig_mix.update_traces(textposition="inside", textinfo="percent+label")

            st.plotly_chart(fig_mix, use_container_width=True)

            st.markdown("### Profil horaire moyen de production par filière")

            df_hour_prod = (
                df_current.groupby(["hour", "zone"])[prod_cols]
                          .mean()
                          .reset_index()
                          .melt(
                              id_vars=["hour", "zone"],
                              var_name="source",
                              value_name="production_moyenne"
                          )
            )

            if vue == "Comparaison":
                fig_hp = px.line(
                    df_hour_prod,
                    x="hour",
                    y="production_moyenne",
                    color="source",
                    line_dash="zone",
                    title="Profil horaire moyen de production par filière (France vs Auvergne-Rhône-Alpes)"
                )
            else:
                fig_hp = px.line(
                    df_hour_prod,
                    x="hour",
                    y="production_moyenne",
                    color="source",
                    title=f"Profil horaire moyen de production par filière – {vue}"
                )

            st.plotly_chart(fig_hp, use_container_width=True)

    # 3. CO₂
    with tab_co2:
        st.subheader("Intensité carbone")

        if "Taux_de_Co2" not in df_current.columns:
            st.info("La colonne 'Taux de Co2' n'est pas disponible dans ce dataset.")
        else:
            df_co2 = df_current.dropna(subset=["datetime", "Taux_de_Co2"])

            if vue == "Comparaison":
                fig_co2 = px.line(
                    df_co2.sort_values("datetime"),
                    x="datetime",
                    y="Taux_de_Co2",
                    color="zone",
                    title="Évolution du taux de CO₂ (gCO₂/kWh) – France vs Auvergne-Rhône-Alpes"
                )
            else:
                fig_co2 = px.line(
                    df_co2.sort_values("datetime"),
                    x="datetime",
                    y="Taux_de_Co2",
                    title=f"Évolution du taux de CO₂ (gCO₂/kWh) – {vue}"
                )

            st.plotly_chart(fig_co2, use_container_width=True)

            # Profil horaire moyen
            st.markdown("### Taux moyen de CO₂ par heure de la journée")

            df_hour_co2 = (
                df_co2.groupby(["hour", "zone"], as_index=False)["Taux_de_Co2"]
                      .mean()
            )

            if vue == "Comparaison":
                fig_h_co2 = px.line(
                    df_hour_co2,
                    x="hour",
                    y="Taux_de_Co2",
                    color="zone",
                    markers=True,
                    title="Taux moyen de CO₂ par heure – comparaison des zones"
                )
            else:
                fig_h_co2 = px.bar(
                    df_hour_co2,
                    x="hour",
                    y="Taux_de_Co2",
                    title=f"Taux moyen de CO₂ par heure – {vue}"
                )

            st.plotly_chart(fig_h_co2, use_container_width=True)

    # 4. Échanges
    with tab_ech:
        st.subheader("Échanges physiques")

        # Colonne commune "Ech__physiques"
        if "Ech__physiques" not in df_current.columns:
            st.info("La colonne 'Ech. physiques' n'est pas disponible dans ce dataset.")
        else:
            df_ech = (
                df_current.groupby(["Date", "zone"], as_index=False)["Ech__physiques"]
                          .mean()
                          .dropna()
            )
            df_ech["Date"] = pd.to_datetime(df_ech["Date"], format="%Y-%m-%d", errors="coerce")

            if vue == "Comparaison":
                fig_ech = px.line(
                    df_ech,
                    x="Date",
                    y="Ech__physiques",
                    color="zone",
                    title="Solde global des échanges physiques (import + / export -)"
                )
            else:
                fig_ech = px.line(
                    df_ech,
                    x="Date",
                    y="Ech__physiques",
                    title=f"Solde global des échanges physiques – {vue}"
                )

            fig_ech.add_hline(y=0, line_dash="dash")
            st.plotly_chart(fig_ech, use_container_width=True)

        st.caption("À faire : ajouter les visualisations détaillant les flux par pays / région")


# MODE 2 : PRÉDICTION
elif mode == "Prédiction":
    st.title("Taux de charge solaire en (%) – Auvergne-Rhône-Alpes")

    # Vérifier que la colonne existe bien dans df_reg
    if COL_TCH not in df_reg.columns:
        st.error(f"La colonne '{COL_TCH}' n'existe pas dans le dataset régional.")
        st.stop()

    # 1) HISTORIQUE : 7 derniers jours
    df_hist_all = get_daily_tch_solaire_regional(df_reg).sort_values("Date")

    if df_hist_all.empty:
        st.error("Impossible de calculer l'historique quotidien sur df_reg.")
        st.stop()

    # 7 derniers jours (au sens des 7 dernières dates disponibles)
    df_hist_7 = df_hist_all.tail(7)

    # 2) PREDICTIONS : 3 prochains jours
    df_pred_all = load_predictions_file()

    if df_pred_all.empty:
        df_pred_3 = pd.DataFrame()
        st.info("Aucune prédiction valide chargée (vérifier le fichier de prédiction).")
    else:
        df_pred_all = df_pred_all.sort_values("Date")
        # 7 premiers jours de prédiction
        df_pred_3 = df_pred_all.head(3)

        # Raccord historique / prédiction
        # Ajoute comme premier point de la série "Prédiction"
        # Puis dernier point historique
        last_hist_date = df_hist_7["Date"].max()
        last_hist_value = df_hist_7[COL_TCH].iloc[-1]
        first_pred_date = df_pred_3["Date"].min()

        if first_pred_date > last_hist_date:
            raccord = pd.DataFrame({
                "Date": [last_hist_date],
                COL_TCH: [last_hist_value],
                "type": ["Prédiction"]
            })
            df_pred_3 = pd.concat([raccord, df_pred_3], ignore_index=True)

    # 3) DATAFRAME FINAL POUR LE GRAPHIQUE
    if not df_pred_3.empty:
        df_plot = pd.concat([df_hist_7, df_pred_3], ignore_index=True)
    else:
        df_plot = df_hist_7.copy()

    # 4) GRAPHIQUE
    fig = px.line(
        df_plot,
        x="Date",
        y=COL_TCH,  
        color="type",
        title="Prédiction taux de charge solaire en (%) – Auvergne-Rhône-Alpes",
        labels={
            "Date": "Date",
            COL_TCH: "TCH Solaire (%)",
            "type": "Série"
        }
    )

    st.plotly_chart(fig, use_container_width=True)

    # 5) Récap en dur des intervalles de dates historique et prédiction
    col1, col2 = st.columns(2)
    with col1:
        st.write("**Historique (7 jours)**")
        st.write(
            f"du {df_hist_7['Date'].min().date()} "
            f"au {df_hist_7['Date'].max().date()}"
        )
    with col2:
        if not df_pred_3.empty:
            # On ignore éventuellement le point de raccord s'il tombe le même jour
            pred_start = df_pred_3["Date"].min().date()
            pred_end = df_pred_3["Date"].max().date()
            st.write("**Prédiction (3 jours)**")
            st.write(f"du {pred_start} au {pred_end}")
        else:
            st.write("**Prédiction** : aucune donnée affichée")