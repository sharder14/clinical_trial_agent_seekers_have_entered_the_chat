"""
Given an nct_id find the sites associated with it and their locations

Given a location, sort the trials by distance from that location

"""

import os
import sys
from dotenv import load_dotenv
load_dotenv()
base_dir = os.getenv('base_dir')
#Change the working directory to the base directory
os.chdir(base_dir)
sys.path.append(base_dir)
#File specific imports
import pandas as pd
import numpy as np
from utils import sql_util, openai_util
import json
from agents.agent_coordinator import AgentCoordinator


#Given a set of nct_ids, find the sites associated with them and their locations

#First get 

#Example usage of the AgentCoordinator class
coordinator = AgentCoordinator()
#First try synonym generation
synonyms = coordinator.get_synonyms("Diabetes Mellitus")
#Now get matching trials for the synonyms
matching_trials = coordinator.find_matching_trials_from_synonyms(synonyms)
matching_trials

#Now get sites associated with all of the trials
matching_nct_ids = matching_trials['nct_ids'].unique().tolist()
#Make them a tuple so we can use them in the sql query
matching_nct_ids = tuple(matching_nct_ids)

site_sql=f"""
SELECT * from facilities
WHERE nct_id IN {matching_nct_ids}
""" 
sites=sql_util.get_table(site_sql)
sites

#Now get input location from user
from geopy.geocoders import Nominatim

# Create geolocator instance
geolocator = Nominatim(user_agent="testing_sh_app")

# Geocode a location name to lat/lon
location = geolocator.geocode("Boston, MA")

print(f"Address: {location.address}")
print(f"Latitude: {location.latitude}, Longitude: {location.longitude}")

# Haversine function (vectorized for DataFrame)
def haversine(lat1, lon1, lat2, lon2):
    # Convert decimal degrees to radians
    lat1, lon1, lat2, lon2 = map(np.radians, [lat1, lon1, lat2, lon2])
    
    # Haversine formula
    dlat = lat2 - lat1 
    dlon = lon2 - lon1 
    a = np.sin(dlat/2)**2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon/2)**2
    c = 2 * np.arcsin(np.sqrt(a))
    r = 6371  # Radius of earth in kilometers
    return c * r


# Calculate distances
sites['distance'] = haversine(location.latitude, location.longitude, sites['latitude'], sites['longitude'])

sites = sites.sort_values(by='distance')
sites.reset_index(drop=True, inplace=True)
sites

