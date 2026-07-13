import mlflow 
import uvicorn
import pandas as pd 
from pydantic import BaseModel
from typing import Literal, List, Union
from fastapi import FastAPI, File, UploadFile, Query
import joblib
import app_func as af
import Model_func as mf
import boto3
from dotenv import load_dotenv
import os
import rte
import openweathermap as owm
import solar as sol
from datetime import date, timedelta, datetime
from io import StringIO
from enum import Enum
# data = pd.read_excel("ibm_hr_attrition.xlsx", index_col=0)
# model = joblib.load("model_ibm")

# Test GA

class RteType(str, Enum):
    national = "rte_national"
    regional = "rte_regional"

bucket = af.session_boto()

MLFLOW_TRACKING_URI = "https://renergies99lead-mlflow.hf.space/"

"""
# Set tracking URI to your Hugging Face application
mlflow.set_tracking_uri("https://renergies99lead-mlflow.hf.space/")
# TODO: Remove mlflow at startup ?
# Set your variables for your environment
EXPERIMENT_NAME="Default"
# Set experiment's info 
mlflow.set_experiment(EXPERIMENT_NAME)
# Get our experiment info
experiment = mlflow.get_experiment_by_name(EXPERIMENT_NAME)
# mlflow.sklearn.autolog()
"""

description = """
Description to be redone
Welcome to Jedha demo API. This app is made for you to understand how FastAPI works! Try it out 🕹️
## Introduction Endpoints
Here are two endpoints you can try:
* `/`: **GET** request that display a simple default message.
* `/greetings`: **GET** request that display a "hello message"
## Blog Endpoints
Imagine this API deals with blog articles. With the following endpoints, you can retrieve and create blog posts 
* `/blog-articles/{blog_id}`: **GET** request that retrieve a blog article given a `blog_id` as `int`.
* `/create-blog-article`: POST request that creates a new article
## Machine Learning
This is a Machine Learning endpoint that predict salary given some years of experience. Here is the endpoint:
* `/predict` that accepts `floats`
Check out documentation below 👇 for more information on each endpoint. 
"""

tags_metadata = [
    {
        "name": "Basic Endpoints",
        "description": "Simple endpoints to observe the data!",
    },

    {
        "name": "tbd Endpoints",
        "description": "More complex endpoints that deals with actual data with **GET** and **POST** requests."
    },

    {
        "name": "Machine Learning",
        "description": "Prediction Endpoint."
    }
]

app = FastAPI(
    title="🪐 Jedha Demo API",
    description=description,
    version="0.1",
    contact={
        "name": "Jedha",
        "url": "https://jedha.co",
    },
    openapi_tags=tags_metadata
)

class BlogArticles(BaseModel):
    title: str
    content: str
    author: str = "Anonymous Author"

class Item(BaseModel):
    name: list[str]

#class PredictionFeatures(BaseModel):
#    YearsExperience: float

def getNow():
    return datetime.now().strftime("%Y-%m-%d")

def getCurrentYear():
    return int(datetime.now().strftime("%Y"))

@app.get("/", tags=["Introduction Endpoints"])
async def index():
    """
    Simply returns a welcome message!
    """
    message = "Hello world! This `/` is the most simple and default endpoint. If you want to learn more, check out documentation of the api at `/docs`"
    return message

@app.post("/prep_data", tags=["Machine Learning"])
async def data_prep(urls: dict):
    """
    Preparation of the data for the prediction.
    In the list of urls, the first url must be the solar data, the second the weather data
    """

    solar_df = mf.data_coll_solar(urls["urls"][0])
    weather_df = mf.data_collection_weather(urls["urls"][1])
    data_df = mf.merge_weather_solar_data(weather_df, solar_df)

    cols = data_df.select_dtypes(include="number").columns.to_list()
    data_df[cols] = data_df[cols].astype(float)

    data_df

    af.to_boto(bucket, data_df.to_csv(), "data_compile_predi.csv")

    return data_df.to_json(orient="index")


@app.post("/predict", tags=["Machine Learning"])
async def predict():
    """
    Prediction of the Renewable Energies based on the input data 
    """
    mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)

    # Set your variables for your environment
    EXPERIMENT_NAME="REnergie-lead"
    # Set experiment's info 
    mlflow.set_experiment(EXPERIMENT_NAME)

    #print(type(predictionFeatures), predictionFeatures)
    # Read data 
    data = pd.read_csv("https://renergies99-lead-bucket.s3.eu-west-3.amazonaws.com/public/prediction/data_compile_predi.csv")
    #data = pd.read_json(StringIO(predictionFeatures), orient='index', dtype=False)

    #data = pd.DataFrame([predictionFeatures])
    #data = pd.DataFrame.from_dict(predictionFeatures, orient="index")

    # Log model from mlflow 
    #run = 'ce62ebaafd8c46fdb939ef6e5b0bfc7e' #marvelous-squid-316
    #logged_model = f'runs:/{run}/model'
    #logged_model = "s3://renergies99-lead-mlflow/4/models/m-07069184939b483ab341754dbdb501be/artifacts"

    # Log model from mlflow
    # MLFLOW_TRACKING_URI = os.environ["MLFLOW_TRACKING_URI"]
    # mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)

    logged_model = "models:/SolarProdModel@production"
    # logged_model = 'runs:/9c9501dd806242abaf63d6daf0fd2ac0/pipeline_model'
    #run = 'ce62ebaafd8c46fdb939ef6e5b0bfc7e' #marvelous-squid-316
    #logged_model = f'runs:/{run}/model'
    #logged_model = "s3://renergies99-lead-mlflow/4/models/m-07069184939b483ab341754dbdb501be/artifacts"
    
    
    # # Load model as a PyFuncModel.
    loaded_model = mlflow.pyfunc.load_model(logged_model)
    print('loaded model')
    prediction = loaded_model.predict(data)

    """
    artifact_uri = mlflow.get_run(run).info.artifact_uri
    errors = mlflow.artifacts.load_dict(artifact_uri + "/error.json")
    # errors = mlflow.artifacts.load_dict('s3://renergies99-lead-mlflow/5/9c9501dd806242abaf63d6daf0fd2ac0/artifacts/pipeline_model/error.json')
    errors_df = pd.DataFrame(errors)
    
    for predi in prediction.tolist():
        error_list.append(af.get_std(predi, errors_df))
    """
    print(prediction)

    error_list = [0, 0, 0]

    # Format response
    response = {"Date": data['Date'],
                "TCH_solaire_pred": prediction.tolist(),
                "Error": error_list}
    resp_df = pd.DataFrame(response, index=list(range(len(response["TCH_solaire_pred"]))))
#    try:
#        hist_df = pd.read_csv('https://renergies99-lead-bucket.s3.eu-west-3.amazonaws.com/public/prediction/predi.csv')
#    except: 
#        all_predi = resp_df   
#    else:
#        all_predi = pd.concat([resp_df, hist_df])

    resp_toboto = resp_df.to_csv()
    af.to_boto(bucket, resp_toboto, "pred_tch_solaire_rhone_alpes.csv")

    af.to_boto(bucket, getNow().encode("utf-8"), "predi_last_download")
    return response

@app.post("/predict_live", tags=["Machine Learning"])
async def predict(file: UploadFile= File(...)):
    """
    Prediction of solar panel output based on weather and solar data 
    """
    
    data = pd.read_csv(file.file)
    time = data['time']
    data = data.drop('time', axis=1)
    print(data)
    # Read data 
    # data_employee = pd.DataFrame([prediction_data])

    mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)

    # Log model from mlflow 
    logged_model = 'runs:/51febeee1eb74612b4492dd0e4c8169e/pipeline_model'

    # # Load model as a PyFuncModel.
    # loaded_model = mlflow.pyfunc.load_model(logged_model)

    # If you want to load model persisted locally
    loaded_model = mlflow.pyfunc.load_model(logged_model)

    prediction = loaded_model.predict(data)

    # Format response
    response = {"prediction": prediction.tolist()}
    return response

@app.get("/predi_last_download", tags=["Machine Learning"])
async def predi_last_download():
    """
    Get the date of the last downloaded version of Prediction
    """
    return mf.get_predi_last_download()

@app.get("/load_rte_data", tags=["RTE"])
async def load_rte_data():
    """
    Load RTE data
    """
    if not rte.is_rte_data_already_downloaded():
        try:
            previous_data = rte.get_previous_rte_data()
            en_cours_data = rte.en_cours_rte_data()

            previous_data.append(en_cours_data)

            df = pd.concat(previous_data, ignore_index=True)

            rte.rte_df_to_csv(df)
            
            return "RTE data successfully uploaded"

        except Exception as e:
            return e
    
    return "RTE data is already downloaded today"

@app.get("/rte_last_download", tags=["RTE"])
async def rte_last_download():
    """
    Get the date of the last downloaded version of RTE data
    """
    return rte.get_rte_last_download()

@app.get("/rte_data", 
         tags=["RTE"],
         summary="RTE data for dashboard")
async def rte_data(
    deb: int = Query(2012, description="First year"), 
    fin: int = Query(getCurrentYear(), description="Last year"), 
    type: RteType = Query(RteType.national, description="type of data to search (rte_national | rte_regional)")
    ):
    """
    Get RTE data for dashboard
    """
    return rte.rte_data(deb, fin, type.value)

"""
@app.get("/rte_daily_data", 
         tags=["RTE"],
         summary="RTE get daily data")
async def rte_daily_data(
    date: str = Query(getNow(), description="Day to download in format DD/MM/YYYY")
    ):
    return rte.rte_daily_data(date)
"""

@app.post("/rte_extract", 
         tags=["RTE"],
         summary="RTE get daily data and put in S3")
async def rte_extract():
    pass

@app.post("/rte_transform",
         tags=["RTE"],
         summary="RTE clean / update data and put in S3")
async def rte_transform(
    extract_id: str = Query(..., description="id of the extraction")
    ):
    pass

@app.post("/rte_load",
         tags=["RTE"],
         summary="RTE Put data in database")
async def rte_load(
    transform_id: str = Query(..., description="id of the transform")
    ):
    pass

@app.get("/load_openweathermap_forecasts", tags=["Openweathermap"])
async def load_openweathermap_forecasts():
    """
    Load Openweathermap data for forecasting
    """
    if not owm.is_openweathermap_data_already_downloaded():
        try:
            cities_coord = owm.get_city_data()
            owm.load_openweathermap_data(cities_coord)
            
            return "Openweathermap data successfully uploaded"

        except Exception as e:
            return e
    
    return "Openweathermap data is already downloaded today"

@app.get("/openweathermap_last_download", tags=["Openweathermap"])
async def openweathermap_last_download():
    """
    Get the date of the last downloaded version of Openweathermap data
    """
    return owm.get_openweathermap_last_download()

@app.get("/load_solar_data", tags=["Solar"])
async def load_solar_data():
    """
    Load Solar data
    """
    if not sol.is_solar_data_already_downloaded():
        try:
            sol.api_fetch_predi()
            
            return "Solar data successfully uploaded"

        except Exception as e:
            return e

@app.get("/solar_last_download", tags=["Solar"])
async def solar_last_download():
    """
    Get the date of the last downloaded version of Solar data
    """
    return sol.get_solar_last_download()