from datetime import datetime, timedelta
import json
import requests
import os
import logging
from dotenv import load_dotenv


logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3'
}


def get_city_data(cities, filename="./cities.json"):
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
    
    if os.path.exists(filename):
        logging.info(f"Use of {filename}")
        with open(filename, "r", encoding="utf-8") as f:
            data = json.load(f)

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

        with open(filename, "w", encoding="utf-8") as f:
            json.dump(res, f, ensure_ascii=False, indent=4)

    except IOError as e:
        logging.error(f"Error writing to target file {filename}: {e}")

    return res


def get_openweathermap(cities_coord, start_date, nb_days=1, file_basename="openweathermap"):
    """
    Generate a json file with Openweathermap

    Parameters
    ----------
    cities_coord : list
        A list of cities with gps coordinates
    start_date : datetime
        First date to request
    nb_days : int
        Number of days to request until the start_date
    file_basename : str
        Base name of the file
    """

    logging.info("GET_OPENWEATHERMAP")

    load_dotenv()

    OPENWEATHERMAP_KEY = os.environ["OPENWEATHERMAP_KEY"]
    if not OPENWEATHERMAP_KEY:
        logging.error("Error: OPENWEATHERMAP_KEY not found in environment variables. Please set it in the .env file.")
        exit(1)  

    openweathermap_base_url = "https://api.openweathermap.org/data/3.0/onecall/timemachine"
    start_date_str = start_date.date().isoformat()
    count = 0

    for city_name, coords in cities_coord.items():

        cities_coord[city_name]["data"] = []

        for i in range(nb_days):
            current_date = start_date - timedelta(days=i)
            dt_timestamp = int(current_date.timestamp())

            params = {
                "lat": coords["lat"],
                "lon": coords["lon"],
                "units": "metric",
                "dt": dt_timestamp,
                "APPID": OPENWEATHERMAP_KEY
            }
            
            try:
                # log every 20 calls
                if count > 0 and count % 20 == 0:
                    logging.info(f"Process {city_name} - {current_date}")

                response = requests.get(openweathermap_base_url, params=params)

                # Raise an exception for bad status codes (4xx or 5xx)
                response.raise_for_status()
                weather_data = response.json()
                
                if weather_data.get("data"):
                    cities_coord[city_name]["data"].extend(weather_data["data"])

            except requests.exceptions.RequestException as e:
                logging.error(f"Error fetching data for {city_name}: {e}")
            except ValueError:
                logging.error(f"Error decoding JSON for {city_name}")
            finally:
                count += 1

    end_date_str = current_date.date().isoformat()
    filename = f"{file_basename}_{end_date_str}_{start_date_str}.json"
    
    try:
        logging.info(f"write data to : {filename}")

        with open(filename, "w", encoding="utf-8") as f:
            json.dump(cities_coord, f, ensure_ascii=False, indent=4)

    except IOError as e:
        logging.error(f"Error writing to target file {filename}: {e}")
    

start_time = datetime(2023, 6, 27, 12, 0, 0)

# Beware You have only 1000 free requests on Openweathermap
# Adjust the nb of days with this limit
# nb_days x len(cities) < 1000 requests
nb_days = 100
cities = [
    'Moulins',
    'Aurillac',
    'Saint-Etienne',
    'Annecy',
    'Nyons'
]


cities_coord = get_city_data(cities)
print(cities_coord)

get_openweathermap(cities_coord, start_time, nb_days)