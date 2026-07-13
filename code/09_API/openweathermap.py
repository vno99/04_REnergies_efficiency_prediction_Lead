from datetime import datetime
import json
import requests
import os
import logging
from dotenv import load_dotenv
import boto3
from botocore.exceptions import ClientError
import pandas as pd

load_dotenv()

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3'
}

cities = [
    'Moulins',
    'Aurillac',
    'Saint-Etienne',
    'Annecy',
    'Nyons'
]

last_download_filename = f"openweathermap_last_download"

API_KEY_S3 = os.environ.get("AWS_ACCESS_KEY_ID")
API_SECRET_KEY_S3 = os.environ.get("AWS_SECRET_ACCESS_KEY")
bucket = "renergies99-lead-bucket"

class Owm:

    def __init__(self, 
                 dt,
                 sunrise,
                 sunset,
                 temp,
                 feels_like,
                 pressure,
                 humidity,
                 dew_point,
                 clouds,
                 wind_speed,
                 wind_deg,
                 rain,
                 snow,
                 city,
                 lat,
                 lon,
                 weather_main,
                 weather_desc):
        self.dt = dt
        self.sunrise = sunrise
        self.sunset = sunset
        self.temp = temp
        self.feels_like = feels_like
        self.pressure = pressure
        self.humidity = humidity
        self.dew_point = dew_point
        self.clouds = clouds
        self.wind_speed = wind_speed
        self.wind_deg = wind_deg
        self.rain = rain
        self.snow = snow
        self.city = city
        self.lat = lat
        self.lon = lon
        self.weather_main = weather_main
        self.weather_desc = weather_desc

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

def get_openweathermap_last_download():
    try:
        key = f"public/openweathermap/{last_download_filename}"

        obj = s3.get_object(Bucket=bucket, Key=key)
        ligne = obj["Body"].read().decode("utf-8")

    except:
        return "Cannot get openweathermap last download data"
    
    return ligne

def is_openweathermap_data_already_downloaded():
    return getNow() == get_openweathermap_last_download()

def get_city_data(cities=cities, filename="cities.json"):
    """
    Get the GPS coordinates of a list of cities

    Parameters
    ----------
    cities : list
        A list of cities to request
    """

    logging.info("GET_CITY_DATA")

    nominatim_base_url = "https://nominatim.openstreetmap.org/"
    search_city_url2 = "search"

    nominatim_cities_data = []
    
    key = f"public/openweathermap/{filename}"

    try:
        obj = s3.get_object(Bucket=bucket, Key=key)
    except ClientError as e:
        obj = None
    
    if obj:
        logging.info(f"Use of {filename}")
        
        contenu = obj["Body"].read()
        data = json.loads(contenu)

        return data

    for city in cities:
        
        params = {
            "format": "json",
            "limit": 1,
            "q": f"{city},france"
        }

        try:
            logging.info(f"get data for : {city}")
            nominatim_cities_data.append(requests.get(f"{nominatim_base_url}{search_city_url2}", params=params, headers=headers).json())

        except requests.exceptions.RequestException as e:
            logging.error(f"Error fetching data for {city}: {e}")
        except ValueError:
            logging.error(f"Error decoding JSON for {city}")

    res = { city[0]["name"]: {"lat": city[0]["lat"], "lon": city[0]["lon"]} for city in nominatim_cities_data }

    try:
        if len(res) == 0:
            logging.info(f"No data to write to : {filename}")
            return {}

        logging.info(f"write data to : {filename}")

        json_bytes = json.dumps(res, ensure_ascii=False, indent=4).encode("utf-8")

        s3.put_object(
            Bucket=bucket,
            Key=key,
            Body=json_bytes
        )

    except IOError as e:
        logging.error(f"Error writing to target file {filename}: {e}")

    return res


def load_openweathermap_data(cities_coord, file_basename="openweathermap_forecasts"):
    """
    Generate a forecast json file with Openweathermap

    Parameters
    ----------
    cities_coord : list
        A list of cities with gps coordinates
    file_basename : str
        Base name of the file
    """

    logging.info("GET_OPENWEATHERMAP")

    if len(cities_coord) == 0:
        logging.info(f"No city to process")
        return
    
    load_dotenv()

    OPENWEATHERMAP_KEY = os.environ["OPENWEATHERMAP_KEY"]
    if not OPENWEATHERMAP_KEY:
        logging.error("Error: OPENWEATHERMAP_KEY not found in environment variables. Please set it in the .env file.")
        exit(1)  

    openweathermap_base_url = "https://api.openweathermap.org/data/3.0/onecall"

    for city_name, coords in cities_coord.items():
        cities_coord[city_name]["daily"] = []

        params = {
            "lat": coords["lat"],
            "lon": coords["lon"],
            "units": "metric",
            "exclude": "current,minutely,hourly,alerts",
            "APPID": OPENWEATHERMAP_KEY
        }

        try:
            logging.info(f"Process {city_name}")

            response = requests.get(openweathermap_base_url, params=params)

            # Raise an exception for bad status codes (4xx or 5xx)
            response.raise_for_status()
            weather_data = response.json()
            
            if weather_data.get("daily"):
                cities_coord[city_name]["daily"].extend(weather_data["daily"])

        except requests.exceptions.RequestException as e:
            logging.error(f"Error fetching data for {city_name}: {e}")
        except ValueError:
            logging.error(f"Error decoding JSON for {city_name}")

    df = openweather_data_json_to_dataframe(cities_coord)
    
    filename = f"{file_basename}.csv"

    try:
        logging.info(f"write data to : {filename}")

        df.to_csv(
            f"s3://renergies99-lead-bucket/public/openweathermap/{filename}",
            index=False,
            storage_options={
                "key": API_KEY_S3,
                "secret": API_SECRET_KEY_S3,
            },
        )

    except IOError as e:
        logging.error(f"Error writing to target file {filename}: {e}")

    key = f"public/openweathermap/{last_download_filename}"

    s3.put_object(
        Bucket=bucket,
        Key=key,
        Body=getNow().encode("utf-8")
    )

def openweather_data_json_to_dataframe(cities_coord):
    print(type(cities_coord))

    cities = []
    DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

    for city_name, city_val in cities_coord.items():

        try:
            for daily in city_val["daily"]:
                a_city_obj = Owm(datetime.fromtimestamp(daily["dt"]).strftime(DATE_FORMAT), 
                                 datetime.fromtimestamp(daily["sunrise"]).strftime(DATE_FORMAT), 
                                 datetime.fromtimestamp(daily["sunset"]).strftime(DATE_FORMAT), daily["temp"]["day"], 
                                 daily["feels_like"]["day"], daily["pressure"], daily["humidity"], daily["dew_point"], 
                                 daily["clouds"], daily["wind_speed"], daily["wind_deg"], daily.get("rain", 0), 
                                 daily.get("snow", 0), city_name, city_val["lat"], city_val["lon"], 
                                 daily["weather"][0]["main"], daily["weather"][0]["description"])
                cities.append(vars(a_city_obj))
                
        except KeyError:
            continue

    df = pd.DataFrame(cities)

    return df


"""
if __name__ == "__main__":
    if not is_openweathermap_data_already_downloaded():
        cities_coord = get_city_data()
        load_openweathermap_data(cities_coord)
"""
