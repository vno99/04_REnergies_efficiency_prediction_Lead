
import pandas as pd
from datetime import date, timedelta

### General functions

##calculate mean from a list
def mean(liste):
    return sum(liste)/len(liste)

##Create a range from a start and a end date
def daterange(start_date: date, end_date: date):
    days = int((end_date - start_date).days)
    for n in range(days):
        yield start_date + timedelta(n)

def save_tocsv(df, path):
    """
    Saves the df by using the pd.to_csv method
    Placeholder for a future function saving to a S3
    """
    df.to_csv(path)

def save_toS3(df, path):
    """
    Saves to S3. Function to be written.
    """
    return