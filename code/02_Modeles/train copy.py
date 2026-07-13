#---- IMPORT LIBRAIRIES ----
import pandas as pd
import numpy as np
import mlflow
from mlflow.models.signature import infer_signature

from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline
from sklearn.linear_model import LinearRegression
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score, root_mean_squared_error

from dotenv import load_dotenv
import os

import json
from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import StandardScaler, FunctionTransformer

from datetime import timedelta
import pvlib 

# Function definition

def split_column_with_threshold(col, thresholds=[50], col_name='humidity'):
    """
    Split a column into 2 or 3 columns based on one or two thresholds.
    Parameters:
    col : pandas.Series
    thresholds : list of float (1 or 2 thresholds)
    col_name : str
    
    Returns:
    (numpy array, list of column names)
    """
    
    # 1 threshold, 2 columns
    if len(thresholds) == 1:
        t = thresholds[0]
        low  = np.where(col < t,  col, 0)
        high = np.where(col >= t, col, 0)

        new_cols = [f"{col_name}_low", f"{col_name}_high"]

        arr = np.column_stack([low, high])
        return arr, new_cols

    # 2 thresholds, 3 columns
    elif len(thresholds) == 2:
        t1, t2 = thresholds
        low = np.where(col < t1, col, 0)
        mid = np.where((col >= t1) & (col < t2), col, 0)
        high = np.where(col >= t2, col, 0)

        new_cols = [f"{col_name}_low", f"{col_name}_mid", f"{col_name}_high"]

        arr = np.column_stack([low, mid, high])
        return arr, new_cols

    else:
        raise ValueError("Only 1 or 2 thresholds are supported.")


def split_column_transformer(thresholds=[50], suffixes=['humidity']):
    all_new_cols = []  # variable capturée

    def transform(X):
        nonlocal all_new_cols  # permet de modifier la variable de l'extérieur
        feature_cols = [c for c in X.columns if any(c.endswith(s) for s in suffixes)]
        outputs = []
        all_new_cols = []

        for col_name in feature_cols:
            col = X[col_name]
            arr, new_cols = split_column_with_threshold(col, thresholds=thresholds, col_name=col_name)
            all_new_cols.extend(new_cols)
            df_tmp = pd.DataFrame(arr, columns=new_cols, index=X.index)
            outputs.append(df_tmp)

        return pd.concat(outputs, axis=1)

    def feature_names_out(self, input_features=None):
        return all_new_cols

    return FunctionTransformer(
        func=transform,
        validate=False,
        feature_names_out=feature_names_out
    )

#--------------COLLECT DATA FUNCTIONS---------------------------------------
#---Prod
def data_collection_prod(url='https://renergies99-lead-bucket.s3.eu-west-3.amazonaws.com/public/prod/eCO2mix_RTE_Auvergne-Rhone-Alpes_cleaned.csv'):

    # read csv
    df_prod = pd.read_csv(url)
    data_prod = df_prod.copy()

    # formatting the date for future data merge operations
    data_prod['Time'] = pd.to_datetime(data_prod['date']+" "+data_prod['heures'])
    return data_prod

#--Solar
def data_coll_solar(url='https://renergies99-lead-bucket.s3.eu-west-3.amazonaws.com/public/solar/raw_solar_data.csv'):
     # read csv
    df_solar = pd.read_csv(url)
    data_solar = df_solar.copy()
    # data_solar["date"] is the uploaded date of the data
    data_solar['Date'] = (pd.to_datetime(data_solar["date"], format="%Y-%m-%d") - timedelta(days=1)).apply(lambda a_date: a_date.strftime("%Y-%m-%d"))
    data_solar.drop(columns=["Unnamed: 0", "date"], inplace=True)

    data_solar['Time'] = pd.to_datetime(data_solar['Date'])
    
    return data_solar

#---LandSat
def data_coll_landsat(url ='https://renergies99-lead-bucket.s3.eu-west-3.amazonaws.com/public/LandSat/result_EarthExplorer_region_ARA.csv'):

    # read csv
    df_sat = pd.read_csv(url, encoding='ISO-8859-1', sep=';')
    data_sat = df_sat.copy()

    # formatting the date column "Start Time" for future data merge operations
    time1 = pd.to_datetime(data_sat['Start Time'].str[:16], format='%d/%m/%Y %H:%M', errors='coerce')
    time2 = pd.to_datetime(data_sat['Start Time'].str[:16], format='%Y-%m-%d %H:%M', errors='coerce')

    data_sat['Time'] = time1
    data_sat['Time'] = data_sat['Time'].fillna(time2)
    data_sat['Time']=data_sat['Time'].dt.round('30min') #to match the production data)
    return data_sat

#---OpenWeather
def data_coll_weather(url ='https://renergies99-lead-bucket.s3.eu-west-3.amazonaws.com/public/openweathermap/merge_openweathermap_cleaned.csv'):
    # read csv
    df_weather = pd.read_csv(url)
    data_weather = df_weather.copy()

    # formatting the date for future data merge operations
    data_weather['Time'] = pd.to_datetime(data_weather['dt'])
    data_weather['Month'] = data_weather['Time'].dt.month
    return data_weather

def get_solarposition(time, latitude, longitude):
    """
    Get the solar position depending on time, latitude and longitude
    Returns a dataframe with apparent_zenith, zenith, apparent_elevation, 
            elevation, azimuth, equation_of_time
    """
    return pvlib.solarposition.get_solarposition(time, latitude, longitude)

def add_day_length_column(df, df_name):
    if 'sunrise' not in df.columns:
        raise ValueError(f"The DataFrame {df_name} does not contain a 'sunrise' column.")
    if 'sunset' not in df.columns:
        raise ValueError(f"The DataFrame {df_name} does not contain a 'sunset' column.")
    df['sunrise'] = pd.to_datetime(df['sunrise'])
    df['sunset'] = pd.to_datetime(df['sunset'])
    day_length_temp = df['sunset'] - df['sunrise']
    df['day_length'] = day_length_temp.dt.total_seconds() / 3600
    return df

def split_data_weather_by_city(data_weather, Cities='city'):
    """
    Split the dataframe data_weather into 5 separate dataframes (1 for each city).
    Returns a dictionary {"city" : dataframe}.
    """
    dict_dfs_cities = {}
    for city in data_weather[Cities].unique():
        key_name = f"{city}"  # name of the dataframe=city
        dict_dfs_cities[key_name] = data_weather[data_weather[Cities]==city].copy()
    return dict_dfs_cities

# def concat_data_weather_by_city(dict_dfs_cities):
#     """
#     Concat columns of the 5 dataframes data_weather_by_city 
#     Add the name of the city in the columns names
#     Keep only one column 'Time'
#     Returns a Dataframe
#     """
#     # Sort each DataFrame by 'Date' if the column exists
#     sorted_dfs = {}
#     for name, df in dict_dfs_cities.items():
#         if 'Time' in df.columns:
#             sorted_df = df.sort_values('Time').reset_index(drop=True)
#             sorted_dfs[name] = sorted_df
#         else:
#             raise ValueError(f"The DataFrame '{name}' does not contain a 'Time' column.")
#     # check if 'Time' columns are identical in each Dataframe
#     time_columns = [df['Time'] for df in dict_dfs_cities.values()]
#     if not all(time_columns[0].equals(tc) for tc in time_columns[1:]):
#         raise ValueError("The 'Time' columns are not identical across DataFrames.")

#     # Concatenate columns with a prefix for each DataFrame
#     final_df = pd.concat([df.add_prefix(f"{name}_") for name, df in dict_dfs_cities.items()], axis=1)
#     # keep only one columns 'Time"
#     time_cols = [col for col in final_df.columns if col.endswith('Time')]
#     final_df['Time'] = final_df[time_cols[0]]
#     final_df = final_df.drop(columns=time_cols)
#     return final_df

def merge_solar_position(weather_data, data_solar_position):
    """
    Function designed to merge the data_solar_position to the data_weather dataframe.
    """
    solar_position_columns_to_use = data_solar_position.columns
    solar_position_data_limited = data_solar_position[solar_position_columns_to_use]
    
    targeted_weather_data = weather_data.merge(solar_position_data_limited, left_on='Time', right_on="dt", how='inner')

    return targeted_weather_data

def merge_weather_dfs_by_city(dict_dfs_cities):
    """
    Merge (inner joint) columns of the 5 dataframes in the dict_dfs_cities
    Add the name of the city in the columns names
    Keep only one column 'Time'
    Returns a Dataframe
    """
    merged_df = None

    for city, df in dict_dfs_cities.items():
        if 'Time' not in df.columns:
            raise ValueError(f"The DataFrame for '{city}' does not contain a 'Time' column.")

        data_solar_position = get_solarposition(df["dt"], df["lat"], df["lon"])
        df = merge_solar_position(df, data_solar_position)
        df = add_day_length_column(df, city)

        df_prefixed = df.rename(columns={col: f"{city}_{col}" for col in df.columns if col != 'Time'})

        # Merge with inner joint
        if merged_df is None:
            merged_df = df_prefixed
        else:
            merged_df = pd.merge(merged_df, df_prefixed, on='Time', how='inner')

    merged_df = merged_df.sort_values('Time').reset_index(drop=True)
    return merged_df

def data_collection_weather(data_path):
    weather_data = data_coll_weather(data_path)
    dfs_by_city = split_data_weather_by_city(weather_data)
    collected_data = merge_weather_dfs_by_city(dfs_by_city)
    return collected_data

#---------------MERGE COLLECTED DATA------------------------------
def merge_weather_solar_data(weather_df, solar_df):
    """
    Function designed to merge the solar_dataframe to the data_weather dataframe.
    the data_weather dataframe is a merge from dataframes by cities 
        (see also split_data_weather_by_city() and  merge_weather_dfs_by_city())
    """
    weather_data = weather_df.copy()
    solar_data = solar_df.copy()

    weather_data['Time_temp'] = pd.to_datetime(weather_data['Time'].dt.date)
    merged_data = weather_data.merge(solar_data, left_on='Time_temp', right_on='Time', how='inner', suffixes=(None, '_y'))
    
    merged_data = merged_data.drop(columns=['Time_temp', 'Time_y'])

    return merged_data


def merge_weather_solar_landsat_data(weather_df, solar_df, landsat_df):
    weather_data = weather_df.copy()
    solar_data = solar_df.copy()
    landsat_data = landsat_df.copy()

    df_weather_solar = merge_weather_solar_data(weather_data, solar_data)

    # df_weather_solar['Time_temp'] = pd.to_datetime(df_weather_solar['Time'].dt.date)
    # landsat_data['Time_temp'] = pd.to_datetime(landsat_data['Time'].dt.date)

    merged_data = df_weather_solar.merge(landsat_data, on='Time', how='left', suffixes=(None, '_sat'))
    # merged_data = merged_data.drop(columns=['Time_temp'])
        
    return merged_data

#------------- DATA PREP --------------------------------------
# Data prep = data collect + merge the 3 datasets
def data_prep(weather_data_path, solar_data_path, landsat_data_path):
    """
    Collect data from the 3 sources openweather, solar and landsat
    Returns a dataframe with :
     - all columns from sources
     - columns with solar position 
     - a column 'Time' (datetime) + a column month
     """
    collected_weather_data = data_collection_weather(weather_data_path)
    collected_solar_data = data_coll_solar(solar_data_path)
    collected_landsat_data = data_coll_landsat(landsat_data_path)

    merged_data = merge_weather_solar_landsat_data(
        collected_weather_data, collected_solar_data, collected_landsat_data)
    return merged_data

#--------------ADD TARGET---------------------------------------
def add_target(df_data, df_target, target_columns_to_use=['Time', 'tch_solaire_(%)']):
    """
    Function designed to add a target column (from df_target) to the df_data dataframe.
    Returns a dataframe with merged dataframes (inner joint)
    """
    # select columns from df_target
    df_target_limited = df_target[target_columns_to_use]

    targeted_data = df_data.merge(df_target_limited, on='Time', how='inner')
    return targeted_data


def add_target_column_sat(data_sat, data_prod):
    """
    Function designed to add a target column (from prod_data) to the data_sat dataframe.
    Returns a dataset with selected columns (not all columns)
    Warning : the sat_data are grouped by 'Time', and the target is 'tch_solaire_(%)'
    """
    # group the landsat data by the time variable to aggregate the images data
    sat_columns_to_use = ['Land Cloud Cover', 'Scene Cloud Cover L1','Sun Elevation L0RA', 'Sun Azimuth L0RA']
    data_sat_grouped = data_sat.groupby('Time')[sat_columns_to_use].mean().reset_index()

    targeted_sat_data = add_target(data_sat_grouped, data_prod)
    return targeted_sat_data
#--------------------------------------------------------------------
def clean_data(df):
    df_clean = df.dropna()
    return df_clean


def data_prep_for_ML(df, features):
    cols_to_keep = [col for col in df.columns if col.endswith(tuple(features))]
    if not cols_to_keep:
        raise ValueError(f"No column found ending with {features}")
    temp_df = df[cols_to_keep]
    prep_data = clean_data(temp_df)

    return prep_data

import pandas as pd
from sklearn.preprocessing import StandardScaler
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.linear_model import LinearRegression

def preprocessing_and_pipeline(X, estimator=LinearRegression(), suffixes=['humidity'], split_thresholds=[50]):
    """
    Prepare the preprocessing and model estimation pipeline.
    
    The pipeline applies:
    - split + StandardScaler to all columns ending with any of the specified suffixes
    - StandardScaler to all other numeric columns
    - All numeric columns are converted to float
    
    Inputs: 
     - X : pandas DataFrame
     - estimator : sklearn estimator (default: LinearRegression)
     - suffixes : list of strings, column suffixes to apply split + scale (default ['humidity'])
     - split_thresholds : thresholds to pass to split_column_transformer (default [50])
     
    Returns:
        dict with "preprocessor" and "pipeline"
    """
    # Identify numeric columns
    numeric_cols = X.select_dtypes(include='number').columns.tolist()
    
    # Convert all numeric columns to float
    X[numeric_cols] = X[numeric_cols].astype(float)
    
    # Columns ending with any of the given suffixes
    split_cols = [c for c in numeric_cols if any(c.endswith(s) for s in suffixes)]
    
    # Remaining numeric columns
    other_numeric_cols = [c for c in numeric_cols if c not in split_cols]
    
    # Transformer for selected columns: split + scale
    split_transformer = split_column_transformer(thresholds=split_thresholds)
    split_pipeline = Pipeline([
        ('split', split_transformer),
        ('scale', StandardScaler())
    ])
    
    # Preprocessor combining both
    preprocessor = ColumnTransformer([
        ('split_cols', split_pipeline, split_cols),
        ('numeric', StandardScaler(), other_numeric_cols)
    ])
    
    # Full pipeline with estimator
    pipeline = Pipeline([
        ('preprocessor', preprocessor),
        ('estimator', estimator)
    ])
    
    return {
        "preprocessor": preprocessor,
        "pipeline": pipeline
    }

  
def error_stat(x_test, y_test, pipeline):
    """
    Returns a dataframe with target-value intervals and, for each interval,
    the average prediction and its associated standard deviation. 
    It also returns the minimum and maximum bounds of the intervals.
    
    Takes as input a validation set x_test, y_test, and a pipeline model.
    """
    df = pd.DataFrame({
        'y_test': y_test,
        'y_pred': pipeline.predict(x_test)
    })

    df['quantile_group'] = pd.qcut(df['y_test'], q=10, duplicates='drop')

    # Grouper et calculer moyenne et écart-type
    table = df.groupby('quantile_group', observed=False)['y_pred'].agg(['mean', 'std']).reset_index()

    # Ajouter les valeurs min et max de chaque intervalle
    table['min'] = table['quantile_group'].apply(lambda x: x.left)
    table['max'] = table['quantile_group'].apply(lambda x: x.right)
    table['min'] = table['min'].astype(float)
    table['max'] = table['max'].astype(float)

    return table

def log_json_artifact(data, filename):
    """
    Save an object (dict, list) in a json file
    """
    with open(filename, "w") as f:
        json.dump(data, f)
    mlflow.log_artifact(filename)

#---- COLLECT DATA -----
def create_full_dataset(weather_data_path: str,
                        solar_data_path: str,
                        landsat_data_path: str,
                        prod_data_path: str,
                        cities_list: list,
                        col_solar: list,
                        target: str) -> pd.DataFrame:
    """
    Collects weather, solar, landsat, and production data, merges them into a single dataset
    with features and target.
    Inputs:
        weather_data_path: url to weather data
        solar_data_path: url to solar data
        landsat_data_path: url to landsat data
        prod_data_path: url to production data
        cities_list: List of cities to keep from the weather data.
        col_solar: List of columns to keep from the solar data (must include 'Time').
        target : Name of the target column in production data.
    Returns:
        Merged dataframe with features and target (1 row per day).
    """
    #collect
    collected_weather_data = data_coll_weather(weather_data_path)
    limited_weather_data = collected_weather_data[collected_weather_data['city'].isin(cities_list)]
    dfs_by_city = split_data_weather_by_city(limited_weather_data)
    weather_data = merge_weather_dfs_by_city(dfs_by_city)

    collected_solar_data = data_coll_solar(solar_data_path)
    solar_data = collected_solar_data[col_solar]

    landsat_data = data_coll_landsat(landsat_data_path)

    #merge
    features_dataset = merge_weather_solar_landsat_data(weather_data, solar_data, landsat_data)

    #add target
    prod_data = data_collection_prod(prod_data_path)
    full_dataset = add_target(features_dataset, prod_data, target_columns_to_use=['Time', target])

    return full_dataset

#---- CLEAN DATA -------
def handle_nan(df):
    """
    handle_nan in a pandas dataframe
    for now, just drop columns with Nan
    """
    df = df.dropna(axis=1)
    return df

def convert_numeric_to_float(df):
    """
    Convert all numeric columns (type='number') in a dataFrame to float,
    Leave non-numeric columns (object, datetime, etc.) unchanged.
    """
    numeric_cols = df.select_dtypes(include='number').columns
    df.loc[:, numeric_cols] = df.loc[:, numeric_cols].astype(float)
    return df

def select_columns_by_type(df, column_type='numeric'):
    """
    Select columns from a DataFrame based on their type.
    input:
     - dataframe df
     - column_type : 'numeric', 'object', 'non-object', 'all'
    Returns:
        list of columns to keep based on the type.
    """
    column_type = column_type.lower()
    mapping = {
        'numeric': df.select_dtypes(include=['number']).columns.tolist(),
        'object': df.select_dtypes(include=['object']).columns.tolist(),
        'non-object': df.select_dtypes(exclude=['object']).columns.tolist(),
        'all': df
    }
    if column_type not in mapping:
        raise ValueError("column_type must be one of ['numeric', 'object', 'non-object', 'all']")
    return mapping[column_type]

def drop_single_value_columns(df):
    """
    Removes columns from a dataFrame that contain only a single unique value.
    Input: dataframe
    Returns dataFrame with single-value columns removed.
    """
    single_value_cols = [col for col in df.columns if df[col].nunique() == 1]
    return df.drop(columns=single_value_cols)

def clean_dataframe(df, type):
    """
    Clean a dataframe by:
    - converting integers to floats (for calculations),
    - keeping only columns from the specified type (default='numeric)
    - removing columns containing a single unique value
     - removing outlier with iqr method
    Returns:
    cleaned dataframe
    """
    df = convert_numeric_to_float(df)
    col_type = select_columns_by_type(df, type)
    df = df[col_type]
    df = drop_single_value_columns(df)
    #df = remove_outliers_iqr(df, target, iqr_factor)
    return df

#---- OUTLIERS
def iqr_params(serie, iqr_factor=1.5):
    """
    calculate parameters to detect outliers with iqr method
    input : pandas serie and iqr_factor
    returns lower_iqr and upper_iqr

    """
    temp_col = serie.dropna()
    q1, q3 = temp_col.quantile([0.25, 0.75])
    iqr = q3 - q1
    lower_iqr = q1 - iqr_factor * iqr
    upper_iqr = q3 + iqr_factor * iqr
    return (lower_iqr, upper_iqr)


def remove_outliers(
    df, target, method="iqr",
    iqr_factor=1.5, z_thresh=3, quantile_bounds=(0.05, 0.95),
    exclude_cols=None
):
    """
    Remove rows containing outliers using IQR, Z-score, or Quantile methods.
    Optimized: precompute masks for all columns, then filter in one step.
    
    Parameters:
    - df : pandas DataFrame
    - target : str, name of the target column (never filtered)
    - method : "iqr", "z", or "quantile"
    - iqr_factor : float, IQR multiplier
    - z_thresh : float, Z-score threshold
    - quantile_bounds : tuple (low, high) for quantile method
    - exclude_cols : list of columns to exclude from filtering
    
    Returns:
    - df_clean : filtered DataFrame
    """
    
    if exclude_cols is None:
        exclude_cols = []
        
    exclude = set(exclude_cols) | {target}
    
    numeric_cols = df.select_dtypes(include="number").columns
    cols_to_check = [c for c in numeric_cols if c not in exclude]

    # Create a DataFrame to store boolean masks
    masks = pd.DataFrame(True, index=df.index, columns=cols_to_check)

    for col in cols_to_check:
        s = df[col]

        if method == "iqr":
            low, up = iqr_params(s, iqr_factor)
            masks[col] = (s >= low) & (s <= up)

        elif method == "z":
            z = (s - s.mean()) / s.std()
            masks[col] = abs(z) <= z_thresh

        elif method == "quantile":
            low, up = s.quantile(quantile_bounds)
            masks[col] = (s >= low) & (s <= up)

        else:
            raise ValueError("method must be one of: 'iqr', 'z', 'quantile'")

    # Combine all column masks (row-wise AND)
    global_mask = masks.all(axis=1)

    # Filter the DataFrame once
    df_clean = df[global_mask]

    return df_clean



if __name__ == "__main__":

    #---- VARIABLES ----
    weather_data_path = 'https://renergies99-lead-bucket.s3.eu-west-3.amazonaws.com/public/openweathermap/merge_openweathermap_cleaned.csv'
    solar_data_path = 'https://renergies99-lead-bucket.s3.eu-west-3.amazonaws.com/public/solar/raw_solar_data.csv'
    landsat_data_path = 'https://renergies99-lead-bucket.s3.eu-west-3.amazonaws.com/public/LandSat/result_EarthExplorer_region_ARA.csv'
    prod_data_path = 'https://renergies99-lead-bucket.s3.eu-west-3.amazonaws.com/public/prod/eCO2mix_RTE_Auvergne-Rhone-Alpes_cleaned.csv'

    target = 'tch_solaire_(%)'
    col_solar = ['Time', 'Ap', '10cm', 'K index Planetary'] # ALWAYS include a 'Time' column (used to merge datasets)
    cities_list = ['Moulins', 'Annecy', 'Nyons', 'Saint-Étienne', 'Aurillac']

    #---- Data Collection ----
    full_dataset = create_full_dataset(weather_data_path, solar_data_path, landsat_data_path, prod_data_path, 
                                    cities_list, col_solar, target)

    print("Data collected")

    #---- DATA CLEANING ----

    df = full_dataset.copy()
    #print(f'df shape: {df.shape}')

    # gestion des Nan
    df_no_Nan = handle_nan(df)
    #print(f'df_no_Nan shape: {df_no_Nan.shape}')

    # clean data (convert int to float, select type columns, remove unique values)
    df_clean = clean_dataframe(df_no_Nan, type='numeric')
    #print(f'df_clean shape: {df_clean.shape}')
    cols = df_clean.select_dtypes(include=["int64", "int32"]).columns.to_list()
    df_clean[cols] = df_clean[cols].astype(float) # Modif liée à la signature dans MLFlow qui retournait une erreur

    #suppression des outliers
    df_no_outliers = remove_outliers(df_clean, target, method='iqr')
    #print(f'df_no_outliers shape: {df_no_outliers.shape}')

    print("Data cleaned")
    print(f'Dataset shape : {df_no_outliers.shape}')

    #------------------
    #---- TRAINING ----
    #------------------

    print("Training in progress....")

    # Variables
    load_dotenv()
    os.environ["MLFLOW_TRACKING_URI"] = "https://renergies99lead-mlflow.hf.space/"
    EXPERIMENT_NAME = "renergie-lead"


    # Features and target definition
    X = df_no_outliers.drop(target, axis=1)
    y = df_no_outliers[target]

    x_train, x_test, y_train, y_test = train_test_split(
        X, y, test_size=0.3, random_state=24
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
        mlflow.log_param("test_size", 0.3)


        # Log model
        mlflow.sklearn.log_model(
            pipeline,
            name="standard_scaler_linear_regression",
            input_example=input_example,
            signature=signature,
            code_paths=["app/func_feat_eng.py", "app/Model_func.py"]
        )

