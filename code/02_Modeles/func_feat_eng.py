import numpy as np
import pandas as pd
from sklearn.preprocessing import FunctionTransformer

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


