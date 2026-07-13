### Importation of the libraries
import requests
import pandas as pd
from datetime import date, timedelta, datetime
# from utils import mean, daterange
import boto3
import os
from dotenv import load_dotenv

### General functions

# ##calculate mean from a list
# def mean(liste):
#     return sum(liste)/len(liste)

# ##Create a range from a start and a end date
# def daterange(start_date: date, end_date: date):
#     days = int((end_date - start_date).days)
#     for n in range(days):
#         yield start_date + timedelta(n)

###Requesting the data

# 

load_dotenv()

last_download_filename = "solar_last_download"

API_KEY_S3 = os.environ["AWS_ACCESS_KEY_ID"]
API_SECRET_KEY_S3 = os.environ["AWS_SECRET_ACCESS_KEY"]
bucket_name = "renergies99-lead-bucket"

def req_solar(base_url, date, objective='predi'):

    objective_dic = {'predi' : "daypre.txt",
                'historic' : "SGAS.txt"}

    file= f'{date.year}'+f'{date.month:02}'+f'{date.day:02}'+objective_dic[objective]
    url = f"{base_url}/{date.year}/{f'{date.month:02}'}/{file}"
    daily = {"date" : date}
    print(url)
    response = requests.get(url)
    if response.status_code == 200:
        return response.text, daily
    else:
        #Return an empty list to avoid breaking the data collection process if missing file.
        return [], daily


#--- saving to s3
def session_boto():
    # """
    # create a boto session
    # """
    
    load_dotenv()

    API_KEY_S3 = os.environ.get("AWS_ACCESS_KEY_ID")
    API_SECRET_KEY_S3 = os.environ.get("AWS_SECRET_ACCESS_KEY")

    bucket_name = "renergies99-lead-bucket"
    

    # Liste des dossiers locaux à uploader
    folders_to_upload = ["prod", "solar", "LandSat", "openweathermap"]

    # Session Boto3
    session = boto3.Session(
        aws_access_key_id=API_KEY_S3,
        aws_secret_access_key=API_SECRET_KEY_S3,
        region_name="eu-west-3",
    )

    s3 = session.resource("s3")
    bucket = s3.Bucket(bucket_name)
    return bucket

def to_boto(bucket, folder, key, file):
    nope = {'predi' : "predi_data.csv",
            'historic' : "raw_solar_data.csv"}
    bucket.put_object(
        Body = file,
        Key = folder+key,
        #ACL = 'public-read-write'
    )

#----Extractiont Prediction data------

def get_date(info):
    day = info[2].split()
    ind = [f'{day[x]}-{day[x+1]}-{day[x+2]}' for x in range(0,len(day), 3)]
    ind = pd.to_datetime(ind)
    return ind

def get_data(info):

    data = []
    info_joined = ' '.join(info)
    info_split = info_joined.splitlines()[2:]
    for line in info_split:
        if 'Solar' in info_joined:
            data.append([float(x) for x in line.split()])
        else:
            data.append([float(x) for x in line.split()[1:]])
        df_temp = pd.DataFrame(data)
    return df_temp.mean().tolist()


def solar_predi_parse(text):
    col_name = {
        'Geomagnetic_A_indices' : 'Ap',
        'Pred_Mid_k' : 'K index Planetary',
        '10cm_flux' : '10cm'
    }
    # col = []
    test_split = text.split('#')[6:]
    for i in range(0, len(test_split), 2):
        if len(test_split[i]) > 3:
            info = test_split[i].split(':')
            if i == 0:
                ind = get_date(info)
                print(ind)
                # col.append(info[3])
                data = get_data(info[4:])
                df = pd.DataFrame(data, columns=[info[3]], index=ind)
                df['date'] = ind
                print(df)
                # df.index.set_names()
            else:
                print(info)
                if info[1] not in ['Polar_cap', 'Reg_Prob']:
                    
                    data = get_data(info)
                    print(data)
                    df[info[1]] = data

    df = df.rename(columns=col_name)
    return df

def fetch_predi(base_url, day, objective):
    data, _ = req_solar(base_url, day, objective)
    df = solar_predi_parse(data) 
    bucket = session_boto()
    to_boto(bucket, "public/solar/", "predi_data.csv", df.to_csv())

    to_boto(bucket, "public/solar/", last_download_filename, getNow().encode("utf-8"))

    return df

def api_fetch_predi():
    return fetch_predi('https://www.ngdc.noaa.gov/stp/space-weather/swpc-products/daily_reports/daypre',  
                       (datetime.today().date()-timedelta(days=1)), 
                       "predi")

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

def get_solar_last_download():
    try:
        key = f"public/solar/{last_download_filename}"

        obj = s3.get_object(Bucket=bucket_name, Key=key)
        ligne = obj["Body"].read().decode("utf-8")

    except:
        return "Cannot get rte last download data"
    
    return ligne


def is_solar_data_already_downloaded():
    return getNow() == get_solar_last_download()