"""
Given a nct_id get the relevant information about the trial
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
from utils import sql_util, openai_util
import json
from agents.agent_coordinator import AgentCoordinator



condition="arthritis"
location="Branson, MO"


coordinator = AgentCoordinator()
#First try synonym generation
synonyms = coordinator.get_synonyms(condition)
#Now get matching trials for the synonyms
matching_trials = coordinator.find_matching_trials_from_synonyms(synonyms)
#Now get matching trial sites for the input location
matching_trial_sites = coordinator.find_matching_trials_from_location(matching_trials, location)
matching_trial_sites

#Now pick a study/site pair to get the trial information
study_site_pair = matching_trial_sites.iloc[0]
study_site_pair

study_details_sql=f"""
SELECT * from studies
WHERE nct_id = '{study_site_pair['nct_id']}'
"""
study_details=sql_util.get_table(study_details_sql)
study_details
study_details.columns
#Column of interest:
'''
'nct_id', 'start_month_year','start_date','study_type',
'brief_title', 'official_title',
'overall_status','phase'
'''

study_details=study_details[[
    'nct_id', 'start_month_year','start_date','study_type',
       'brief_title', 'official_title',
       'overall_status','phase'
]]




