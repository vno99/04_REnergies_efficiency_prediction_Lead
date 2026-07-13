import pandas as pd
#from func_utils.utils import save_tocsv

import json

from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LinearRegression

from dotenv import load_dotenv
import os
import mlflow
from datetime import timedelta
import pvlib 

import func_feat_eng as ffe

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
    split_transformer = ffe.split_column_transformer(thresholds=split_thresholds)
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
