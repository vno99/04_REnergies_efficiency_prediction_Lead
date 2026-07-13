import pandas as pd
from utils import daterange, save_tocsv
from solar_data_func import extract_date, to_boto, session_boto
from datetime import date, timedelta, datetime
from dotenv import load_dotenv
import os

objective = 'historic'
s3 = 'https://renergies99-lead-bucket.s3.eu-west-3.amazonaws.com/'
folder = 'public/solar/'
variable = {
    'predi': {
        'base_url' : 'https://www.ngdc.noaa.gov/stp/space-weather/swpc-products/daily_reports/daypre',
        'dest_key': 'predi_data.csv'},
    'historic':{
        'base_url' : "https://www.ngdc.noaa.gov/stp/space-weather/swpc-products/daily_reports/solar_geophysical_activity_summaries",
        'dest_key': 'raw_solar_data.csv'}
        }
###Base variables
base_url = variable[objective]['base_url']
# dest_url = 
start_date = date(2020, 1, 1)
end_date = datetime.today().date()


stored_data = pd.DataFrame()
### Update date
try:
    stored_data = pd.read_csv(f"{s3}{folder}{variable[objective]['dest_key']}", index_col=0)
except:
    pass

if stored_data.shape[0] > 0:
    start_date = (pd.to_datetime(max(stored_data.index))+timedelta(days=1)).date()

### Retrieval loop between start_date and end_date
solar_data = pd.DataFrame()
for single_date in daterange(start_date, end_date):
    print(single_date.strftime("%Y-%m-%d"))
    df_temp = extract_date(base_url, single_date, objective=objective)
    solar_data = pd.concat([solar_data, df_temp])

if stored_data.shape[0] > 0:
    solar_data = pd.concat([stored_data, solar_data])

# url = "https://renergies99-lead-bucket.s3.eu-west-3.amazonaws.com/public/solar/raw_solar_data.csv"
#to_s3(solar_data)
#storage of the data in a csv
print(solar_data.head())
bucket = session_boto()
to_boto(bucket, folder, variable[objective]['dest_key'], solar_data.to_csv())

# save_tocsv(solar_data, 'data/solar/raw_solar_data.csv')
# solar_data.to_csv('data/solar/raw_solar_data.csv')