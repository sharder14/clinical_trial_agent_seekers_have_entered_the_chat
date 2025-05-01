"""
trial_filters.py

This module contains utility functions to filter and retrieve clinical trial data based on condition similarity,
geographic distance, age eligibility, and trial characteristics.

Key Functions:
- get_relevant_studies_from_conditions(): Uses sentence embedding similarity to identify trials matching input conditions.
- get_sites_sorted_by_distance(): Finds clinical trial sites geographically close to a user's location.
- get_sites_sorted_by_distance_with_age_gender(): Adds age and gender filtering on top of distance-based site filtering.
- get_trial_details(): Retrieves detailed metadata (design, eligibility, outcomes, contacts) for a specific trial.
- parse_age(): Converts age strings (e.g. "18 Years") into numeric values.
- determine_age_groups(): Categorizes trials by age eligibility groups (Child, Adult, Senior).
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
from utils import sql_util
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np
from sentence_transformers import SentenceTransformer
import torch
from geopy.geocoders import Nominatim
import random
import string

# Check if GPU is available
device = 'cuda' if torch.cuda.is_available() else 'cpu'
print(f"Using device: {device}")

# Load model and move it to GPU
model = SentenceTransformer('all-MiniLM-L6-v2', device=device)

active_trials_w_conditions_object = pd.read_pickle(os.path.join(base_dir, 'data', 'active_trials_w_condition_embeddings.pkl'))
active_trials_w_conditions = active_trials_w_conditions_object['active_trials_w_conditions']
conditions_df = active_trials_w_conditions_object['conditions_df']
condition_embeddings = active_trials_w_conditions_object['condition_embeddings']


"""
Function that takes in list of conditions and returns nct_ids that have conditions most similar to the input conditions.
"""

def get_relevant_studies_from_conditions(conditions, similarity_score_threshold=0.8):
    """
    Function that takes in list of conditions and returns nct_ids that have conditions most similar to the input conditions.
    """
    #Get the embeddings for the synonyms
    synonym_embeddings = model.encode(conditions, device=device)

    #Get the cosine similarity between the synonyms and the condition embeddings
    cosine_similarities = cosine_similarity(synonym_embeddings, condition_embeddings)

    inds,vals=np.argsort(cosine_similarities, axis=1)[:, ::-1],np.sort(cosine_similarities, axis=1)[:, ::-1]

    #Write vals and inds to pandas dataframe
    similarity_df=pd.DataFrame({'condition_ind':inds.flatten(),'similarity':vals.flatten()})
    similarity_df.sort_values('similarity', ascending=False, inplace=True)
    similarity_df=similarity_df.reset_index(drop=True)

    #Subset similarity df to only those studies that have similarity >=similarity_score_threshold
    similarity_df=similarity_df[similarity_df['similarity']>=similarity_score_threshold].reset_index(drop=True)
    #Now we want to get the nct_ids for the conditions that are similar to the synonyms
    similarity_df['nct_ids'] = similarity_df['condition_ind'].apply(lambda x: conditions_df.iloc[x]['nct_ids'])

    #Now expand the nct_ids column out so that there is one row per condition_ind, nct_id, and similarity
    similarity_df = similarity_df.explode('nct_ids').reset_index(drop=True)
    #Now drop duplicates on NCT_ID
    relevant_trials_df = similarity_df.drop_duplicates(subset=['nct_ids'], keep='first').reset_index(drop=True)
    
    #Only return studies that are active
    active_studies=sql_util.get_table("""
        select nct_id from aact.ctgov.studies s  
        where overall_status in ('ENROLLING_BY_INVITATION','NOT_YET_RECRUITING','RECRUITING')
    """)

    relevant_trials_df=relevant_trials_df[relevant_trials_df['nct_ids'].isin(active_studies['nct_id'])].reset_index(drop=True)

    return relevant_trials_df


# Haversine function (vectorized for DataFrame)
def haversine(lat1, lon1, lat2, lon2):
    # Convert decimal degrees to radians
    lat1, lon1, lat2, lon2 = map(np.radians, [lat1, lon1, lat2, lon2])
    
    # Haversine formula
    dlat = lat2 - lat1 
    dlon = lon2 - lon1 
    a = np.sin(dlat/2)**2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon/2)**2
    c = 2 * np.arcsin(np.sqrt(a))
    r = 3958.8  # Radius of earth in miles
    return c * r

def generate_random_string(length=12):
    chars = string.ascii_letters + string.digits
    return ''.join(random.choices(chars, k=length))

#print(generate_random_string())

def get_sites_sorted_by_distance(trials, user_location, max_distance=250):
    #Now get sites associated with all of the trials
    matching_nct_ids = trials['nct_ids'].unique().tolist()

    if not matching_nct_ids:
        return pd.DataFrame()

    matching_nct_ids = tuple(matching_nct_ids)

    site_sql = f"""
    SELECT * from facilities
    WHERE nct_id IN {matching_nct_ids}
    and status in ('ENROLLING_BY_INVITATION','NOT_YET_RECRUITING','RECRUITING')
    """ 
    sites = sql_util.get_table(site_sql)

    # Create geolocator instance
    user_agent_name=generate_random_string()    
    geolocator = Nominatim(user_agent=user_agent_name)

    # Geocode a location name to lat/lon
    location = geolocator.geocode(user_location)
    
    # Check if geocoding was successful
    if location is None:
        raise ValueError(f"Could not geocode the location: '{user_location}'. Please try a different format or a more general location like 'City, State'.")

    print(f"Address: {location.address}")
    print(f"Latitude: {location.latitude}, Longitude: {location.longitude}")

    # Calculate distances
    sites['distance'] = haversine(location.latitude, location.longitude, sites['latitude'], sites['longitude'])

    # Filter by distance and limit to 100 closest
    sites = sites[sites['distance'] <= max_distance]
    sites = sites.sort_values(by='distance').head(100).reset_index(drop=True)


    # Drop rows where distance could not be computed
    sites = sites.dropna(subset=['distance'])

    sites = sites.sort_values(by='distance')
    sites.reset_index(drop=True, inplace=True)

    #Now get relevant study details per
    
    study_details_sql=f"""
    SELECT * from studies
    WHERE nct_id IN {matching_nct_ids}
    """ 
    study_details=sql_util.get_table(study_details_sql)
    study_details

    #Merge to get proper columns
    sites=sites.merge(study_details[['nct_id','phase','study_type','overall_status']],on='nct_id')

    return sites


#Get relevent tables for explaining trial

def get_trial_details(study_site_pair):
    study_details_sql=f"""
    SELECT * from studies
    WHERE nct_id = '{study_site_pair['nct_id']}'
    """
    study_details=sql_util.get_table(study_details_sql)

    eligibilities_sql=f"""
    SELECT * from eligibilities
    WHERE nct_id = '{study_site_pair['nct_id']}'
    """
    eligibilities=sql_util.get_table(eligibilities_sql)

    designs_sql=f"""
    SELECT * from designs
    WHERE nct_id = '{study_site_pair['nct_id']}'
    """
    designs=sql_util.get_table(designs_sql)

    design_groups_sql=f"""
    SELECT * from design_groups
    WHERE nct_id = '{study_site_pair['nct_id']}'
    """
    design_groups=sql_util.get_table(design_groups_sql)

    interventions_sql=f"""
    SELECT * from interventions
    WHERE nct_id = '{study_site_pair['nct_id']}'
    """
    interventions=sql_util.get_table(interventions_sql)

    design_outcomes_sql=f"""
    select * from design_outcomes
    where nct_id= '{study_site_pair['nct_id']}'
    and outcome_type='primary'
    """
    design_outcomes=sql_util.get_table(design_outcomes_sql)

    central_contacts_sql=f"""
    SELECT * from central_contacts
    WHERE nct_id = '{study_site_pair['nct_id']}'
    """
    central_contacts=sql_util.get_table(central_contacts_sql)


    out={
           'study_details':study_details,
           'eligibilities':eligibilities,
           'designs':designs,
           'design_groups':design_groups,
           'interventions':interventions,
           'design_outcomes':design_outcomes,
           'central_contacts':central_contacts
    }

    


    return out

# Helper function to parse age strings into numeric values
def parse_age(age_string):
    """Parse age string into a numeric value in years."""
    if pd.isna(age_string) or not age_string or age_string == 'N/A':
        return None
    
    parts = age_string.split()
    if len(parts) < 2:
        return None
    
    try:
        value = float(parts[0])
        unit = parts[1].lower()
        
        # Convert to years
        if unit.startswith('year'):
            return value
        elif unit.startswith('month'):
            return 0  # Treat as 0 years
        elif unit.startswith('day'):
            return 0  # Treat as 0 years
        elif unit.startswith('week'):
            return 0  # Treat as 0 years
        else:
            return None
    except (ValueError, IndexError):
        return None
    

def determine_age_groups(min_age, max_age):
    """
    Determine which age groups a trial belongs to based on min and max ages.
    Returns a list of applicable age groups.
    """
    # Parse ages to integers, handling None values
    min_age_val = 0 if min_age is None else parse_age(min_age) or 0
    max_age_val = 120 if max_age is None else parse_age(max_age) or 120
    
    groups = []
    
    # Child: 0-17
    if min_age_val <= 17 and max_age_val >= 0:
        groups.append("Child: 0-17")
    
    # Adult: 18-64
    if min_age_val <= 65 and max_age_val >= 18:
        groups.append("Adult: 18-64")
    
    # Senior: 65+
    if max_age_val >= 65:
        groups.append("Senior: 65+")
    
    return groups

    
def get_sites_sorted_by_distance_with_age_gender(trials, user_location, max_distance=250):
    """Get sites sorted by distance and include age eligibility information"""
    # First get the regular sorted sites
    sites = get_sites_sorted_by_distance(trials, user_location, max_distance)

    if sites.empty:
        return sites
    
    # Get unique NCT IDs from the sites
    matching_nct_ids = tuple(sites['nct_id'].unique().tolist())
    
    # Fetch eligibility data for these trials
    if len(matching_nct_ids) == 1:
        # Handle the case of a single NCT ID differently to avoid SQL syntax errors
        nct_id = matching_nct_ids[0]
        eligibilities_sql = f"""
        SELECT nct_id, gender, minimum_age, maximum_age 
        FROM eligibilities
        WHERE nct_id = '{nct_id}'
        """
    else:
        eligibilities_sql = f"""
        SELECT nct_id, gender, minimum_age, maximum_age 
        FROM eligibilities
        WHERE nct_id IN {matching_nct_ids}
        """
    
    eligibilities = sql_util.get_table(eligibilities_sql)
    
    # Merge the eligibility data with sites
    sites = sites.merge(eligibilities[['nct_id', 'minimum_age', 'maximum_age', 'gender']], 
                        on='nct_id', how='left')
    
    # Parse age values
    sites['min_age_val'] = sites['minimum_age'].apply(parse_age).fillna(0)
    sites['max_age_val'] = sites['maximum_age'].apply(parse_age).fillna(120)
    sites['gender'] = sites['gender'].fillna('ALL')
    
    # Create human-readable age range column
    sites['age_range'] = sites.apply(
        lambda row: f"{row['minimum_age'] if pd.notna(row['minimum_age']) else 'Any'} to {row['maximum_age'] if pd.notna(row['maximum_age']) else 'Any'}", 
        axis=1
    )
    
    # Determine age groups for filtering
    sites['age_groups'] = sites.apply(
        lambda row: determine_age_groups(row['minimum_age'], row['maximum_age']), 
        axis=1
    )
    
    return sites