import json
import os
import logging
import glob

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def merge_openweathermap_jsons(source_path="./", target="./merge_openweathermap.json", file_pattern="openweathermap_*.json"):
    """
    Merge the openweathermap json into one file

    Parameters
    ----------
    source_path : str
        Path of json files
    target : str
        Name of the merged file
    file_pattern : str
        Pattern of json file to search
    """

    merged = {}

    logging.info("MERGE_OPENWEATHERMAP_JSONS")
    
    search_pattern = os.path.join(source_path, file_pattern)

    for filepath in glob.glob(search_pattern):

        logging.info(f"process {filepath}")

        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)

            for city, city_data in data.items():
                if city not in merged:
                    merged[city] = {
                        "lat": city_data["lat"],
                        "lon": city_data["lon"],
                        "data": city_data["data"].copy()
                    }
                else:
                    merged[city]["data"].extend(city_data["data"])

        except json.JSONDecodeError as e:
            logging.error(f"Error decoding JSON from {filepath}: {e}")
        except Exception as e:
            logging.error(f"An unexpected error occurred while processing {filepath}: {e}")


    logging.info(f"write data to : {target}")
    try:
        with open(target, "w", encoding="utf-8") as f_out:
            json.dump(merged, f_out, indent=4, ensure_ascii=False)

    except IOError as e:
        logging.error(f"Error writing to target file {target}: {e}")


if __name__ == "__main__":
    merge_openweathermap_jsons()