### Importation of the libraries
import requests
import pandas as pd
from datetime import date, timedelta
from utils import mean, daterange
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
    

### Splitting the response text in different paragraphs
def split_response(text):
    # print(text)
    text_split_temp = text.split("\nA.")[1]
    text_A, text_split_temp = text_split_temp.split("\nB.")
    text_B, text_split_temp = text_split_temp.split("\nC. ") #Added the space to prevent confusion with "UTC."
    text_C, text_split_temp = text_split_temp.split("\nD.")
    text_D, text_split_temp = text_split_temp.split("\nE.")
    text_E, text_F = text_split_temp.split("\nF.")
    return text_A, text_B, text_C, text_D, text_E, text_F

def split_predi(text):
    return

### data collection for the different paragraphs
#Treatment of section A : event occurences
# At the moment, only the number of events is saved, 
# but the pipeline is ready for more complex treatment
def coll_data_A(text_A, daily):
    #hard codding the data limits for later separation.
    indices = [1, 6, 11, 17, 22, 29, 35, 38, 45, 49, 68]
    data = []
    test_A = text_A.splitlines()[1:]
    for line in range(len(test_A)):
        if line == 0:
            #colnames are stored in the first line kept
            col = test_A[line].split()
        else:
            #retrieval of the data based on the previously stored indices
            data.append([test_A[line][indices[i]:indices[i+1]].strip() for i in range(len(indices)-1)])

    events_df = pd.DataFrame(data, columns=col)

    daily.update({'nb_event' : len(events_df)})
    return daily

#Traitement des sections B, C, F
def coll_data_text(text_ini, daily):
    text = text_ini.splitlines()
    if len(text) > 1:
        text = ' '.join(text)
    else:
        text = text[0]
    text_split_temp = text.split(':')
    text_col = text_split_temp[0]
    if len(text_split_temp) < 3:
        text_content = text_split_temp[1]
    else:
        text_content = ' '.join(text_split_temp[1:])
    daily.update({text_col.strip() : text_content.strip()})
    return daily

#Traitement de la section E
def coll_data_E(text_E, daily):
    test_E = text_E.splitlines()
    dailies_E = test_E[1].split() #Line with the base data
    proton_E = test_E[3].split() #Line with the proton data
    K_index_Boulder, K_index_Planetary = test_E[9].split('Planetary')
    K_index_Boulder = K_index_Boulder.split() #.remove('Boulder')
    K_index_Boulder.pop(0)
    K_index_Boulder = [float(x) if x != '?' else 0 for x in K_index_Boulder]
    K_index_Planetary = [float(x) if x != '?' else 0 for x in K_index_Planetary.split()]
    # print(K_index_Boulder)
    try:
     float(dailies_E[2])
    except:
     d_10cm = 0
    else:
        d_10cm = float(dailies_E[2])
    daily.update({
        "10cm" : d_10cm,
        "SSN" : dailies_E[4],
        "Afr" : dailies_E[6].split('/')[0],
        "Ap" : dailies_E[6].split('/')[1],
        "Xray Bg" : dailies_E[9].lstrip('B'),
        "Proton Fluence (GT1MeV)" : proton_E[3],
        "Proton Fluence (GT10MeV)" : proton_E[7],
        "Electron Fluence (GT2MeV)" : test_E[6].split()[3], #reaching directly for the line containing the electron data
        "K index Boulder" : mean(K_index_Boulder),
        "K index Planetary" : mean(K_index_Planetary)
    })
    return daily

### The complete workflow for a single file, returning a one-line dataframe.
def extract_date(base_url, single_date, objective):
    data, daily = req_solar(base_url, single_date, objective=objective)
    if len(data) >1:
        text_A, text_B, text_C, _, text_E, text_F = split_response(data) #The section D of the text is not used because obsolete
        daily = coll_data_A(text_A, daily)
        daily = coll_data_text(text_B, daily)
        daily = coll_data_text(text_C, daily)
        daily = coll_data_E(text_E, daily)
        daily = coll_data_text(text_F, daily)

        date_df = pd.DataFrame(daily, index=[single_date])
        return date_df


#--- saving to s3
def session_boto():
    # """
    # create a boto session
    # """
    
    load_dotenv()

    API_KEY_S3 = os.environ["AWS_ACCESS_KEY_ID"]
    API_SECRET_KEY_S3 = os.environ["AWS_SECRET_ACCESS_KEY"]

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
        ACL = 'public-read-write'
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

    return df