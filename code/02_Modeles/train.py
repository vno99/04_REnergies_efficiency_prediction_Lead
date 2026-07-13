#---- IMPORT LIBRAIRIES ----

import mlflow
from mlflow.models.signature import infer_signature
from mlflow import MlflowClient

from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline
from sklearn.linear_model import LinearRegression
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score, root_mean_squared_error

from dotenv import load_dotenv
import os

import func_cleaning as fc

load_dotenv()

#---- VARIABLES ----
weather_data_path = 'https://renergies99-lead-bucket.s3.eu-west-3.amazonaws.com/public/openweathermap/merge_openweathermap_cleaned.csv'
solar_data_path = 'https://renergies99-lead-bucket.s3.eu-west-3.amazonaws.com/public/solar/raw_solar_data.csv'
landsat_data_path = 'https://renergies99-lead-bucket.s3.eu-west-3.amazonaws.com/public/LandSat/result_EarthExplorer_region_ARA.csv'
prod_data_path = 'https://renergies99-lead-bucket.s3.eu-west-3.amazonaws.com/public/prod/eCO2mix_RTE_Auvergne-Rhone-Alpes_cleaned.csv'

target = 'tch_solaire_(%)'
col_solar = ['Time', 'Ap', '10cm', 'K index Planetary'] # ALWAYS include a 'Time' column (used to merge datasets)
cities_list = ['Moulins', 'Annecy', 'Nyons', 'Saint-Étienne', 'Aurillac']

# Variables training
os.environ["MLFLOW_TRACKING_URI"] = "https://renergies99lead-mlflow.hf.space/"
EXPERIMENT_NAME = "renergie-lead"
model_name = "standard_scaler_linear_regression"
test_size = 0.25
registered_model_name = "SolarProdModel"
alias = "challenger"

#---- Data Collection ----
full_dataset = fc.create_full_dataset(weather_data_path, solar_data_path, landsat_data_path, prod_data_path, 
                                   cities_list, col_solar, target)

print("Data collected")

#---- DATA CLEANING ----

df = full_dataset.copy()
#print(f'df shape: {df.shape}')

# gestion des Nan
df_no_Nan = fc.handle_nan(df)
#print(f'df_no_Nan shape: {df_no_Nan.shape}')

# clean data (convert int to float, select type columns, remove unique values)
df_clean = fc.clean_dataframe(df_no_Nan, type='numeric')
#print(f'df_clean shape: {df_clean.shape}')
cols = df_clean.select_dtypes(include=["int64", "int32"]).columns.to_list()
df_clean[cols] = df_clean[cols].astype(float) # Modif liée à la signature dans MLFlow qui retournait une erreur

#suppression des outliers
df_no_outliers = fc.remove_outliers(df_clean, target, method='iqr')
#print(f'df_no_outliers shape: {df_no_outliers.shape}')

print("Data cleaned")
print(f'Dataset shape : {df_no_outliers.shape}')

#------------------------------------------------------
#---------------------- TRAINING ----------------------
#------------------------------------------------------

print("Training in progress....")

# Features and target definition
X = df_no_outliers.drop(target, axis=1)
y = df_no_outliers[target]

x_train, x_test, y_train, y_test = train_test_split(
    X, y, test_size=test_size, random_state=24
)

input_example = x_train.iloc[:3]

# MLflow config
mlflow.set_tracking_uri(os.environ["MLFLOW_TRACKING_URI"])
mlflow.set_experiment(EXPERIMENT_NAME)

experiment = mlflow.get_experiment_by_name(EXPERIMENT_NAME)

# Pipeline (Scaler + Model)
# pas de ColumnTransformer car seulement des colonnes numériques
pipeline = Pipeline(
    steps=[
        ("scaler", StandardScaler()),
        ("model", LinearRegression())
    ]
)

run_description = (
    f"Target: {target}\n"
    "Estimator: Linear Regression\n"
    "StandardScaler + LinearRegression\n"
    "Base run with solarposition, basic cleaning and outliers removal (IQR)\n"
    "No feature engineering"
)

# MLflow run
with mlflow.start_run(experiment_id=experiment.experiment_id, description=run_description):
    # Train
    pipeline.fit(x_train, y_train)

    # Predict
    y_pred = pipeline.predict(x_test)

    # Metrics
    mae = mean_absolute_error(y_test, y_pred)
    mse = mean_squared_error(y_test, y_pred)
    rmse = root_mean_squared_error(y_test, y_pred)
    r2 = r2_score(y_test, y_pred)

    n = len(y_test)
    p = x_test.shape[1]
    adj_r2 = 1 - (1 - r2) * (n - 1) / (n - p - 1)

    # MLflow signature
    signature = infer_signature(x_train, pipeline.predict(x_train))

    # Log metrics
    mlflow.log_metrics({
        "MAE": mae,
        "MSE": mse,
        "RMSE": rmse,
        "R2": r2,
        "Adjusted_R2": adj_r2
    })

    # Log params
    mlflow.log_param("scaler", "StandardScaler")
    mlflow.log_param("model", "LinearRegression")
    mlflow.log_param("test_size", test_size)


    # Log model
    mlflow.sklearn.log_model(
        pipeline,
        name=model_name,
        registered_model_name = registered_model_name,
        input_example=input_example,
        signature=signature,
        code_paths=["func_feat_eng.py", "Model_func.py"]
    )

#--- Set registered model alias
client = MlflowClient()

model = client.get_registered_model(registered_model_name)
latest_version = model.latest_versions[-1].version

client.set_registered_model_alias(registered_model_name, alias, latest_version)
print(f"Attribution de l'alias '{alias}' à la version {latest_version} du model {registered_model_name}")
print("End of model training")