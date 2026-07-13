# functions used to collect an clean data for eda and ml training

#---- IMPORTS -----
import pandas as pd

import Model_func as mf
from scipy.stats import zscore

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
    collected_weather_data = mf.data_coll_weather(weather_data_path)
    limited_weather_data = collected_weather_data[collected_weather_data['city'].isin(cities_list)]
    dfs_by_city = mf.split_data_weather_by_city(limited_weather_data)
    weather_data = mf.merge_weather_dfs_by_city(dfs_by_city)

    collected_solar_data = mf.data_coll_solar(solar_data_path)
    solar_data = collected_solar_data[col_solar]

    landsat_data = mf.data_coll_landsat(landsat_data_path)

    #merge
    features_dataset = mf.merge_weather_solar_landsat_data(weather_data, solar_data, landsat_data)

    #add target
    prod_data = mf.data_collection_prod(prod_data_path)
    full_dataset = mf.add_target(features_dataset, prod_data, target_columns_to_use=['Time', target])

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


# def detect_outliers(df, z_thresh=3, iqr_factor=1.5, quantile_bounds=(0.05, 0.95)):
#     """
#     Detect outliers in numerical columns using three methods:
#     IQR, Z-score and Quantile thresholds.
#     Returns a DataFrame with outlier counts per column and per method.
#     """
#     numeric_cols = df.select_dtypes(include='number').columns
#     result = {}

#     for col in numeric_cols:
#         temp_col = df[col].dropna()

#         # IQR
#         lower_iqr, upper_iqr = iqr_params(temp_col, iqr_factor=iqr_factor)
#         outliers_iqr = temp_col[(temp_col < lower_iqr) | (temp_col > upper_iqr)]

#         # Z-score
#         z_scores = zscore(temp_col)
#         outliers_z = temp_col[abs(z_scores) > z_thresh]

#         # Quantiles
#         q_low, q_high = temp_col.quantile(quantile_bounds)
#         outliers_quantile = temp_col[(temp_col < q_low) | (temp_col > q_high)]

#         result[col] = {
#             "outliers_z": len(outliers_z),
#             "outliers_iqr": len(outliers_iqr),
#             "outliers_quantile": len(outliers_quantile)
#         }
#     return pd.DataFrame(result).T

# def get_columns_with_outliers(df, method="iqr", z_thresh=3, iqr_factor=1.5, quantile_bounds=(0.05, 0.95)):
#     """
#     Returns a list of columns that have outliers according to the chosen method.
#     Parameters:
#     - df: dataframe
#     - method: "z", "iqr", or "quantile"
#     - threshold (z_thresh, iqr_factor or quantile_bounds)
#     Returns:
#     - list of columns with at least one outlier according to the chosen method
#     """
#     outliers_df = detect_outliers(df, z_thresh=z_thresh, iqr_factor=iqr_factor, quantile_bounds=quantile_bounds)
#     method_col = f"outliers_{method}"
#     if method_col not in outliers_df.columns:
#         raise ValueError(f"Invalid method '{method}'. Choose from: z, iqr, quantile")
    
#     return outliers_df.index[outliers_df[method_col] > 0].tolist()

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




