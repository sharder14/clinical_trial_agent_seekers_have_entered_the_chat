"""
The Agent Coordinator would serve as the orchestration layer for your intelligent components, managing the flow of information and tasks between the specialized agents. 

AgentCoordinator
├── initialize_session()
├── process_search_request(condition, location)
├── generate_synonyms(condition)
├── find_matching_trials(synonyms, location)
├── explain_trial(trial_id)
├── gather_knowledge_resources(condition, synonyms)

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
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np

#Load in specialized agents
from agents.synonym_generator import SynonymGeneratorAgent
from agents.trial_explainer import TrialExplainerAgent
from agents.knowledge_curator import KnowledgeCuratorAgent
from agents.location_fixer import LocationFixerAgent

#Load in agent helpers
from agents.helpers import trial_filters
from IPython.display import display, Markdown
#from importlib import reload
#reload(trial_filters)


class AgentCoordinator:
    def __init__(self):
        # Initialize the specialized agents
        self.synonym_agent = SynonymGeneratorAgent()
        self.explainer_agent = TrialExplainerAgent()
        self.knowledge_agent = KnowledgeCuratorAgent()
        self.location_agent= LocationFixerAgent()
                
        
    def process_search_request(self, condition, location, filters=None):
        """
        Main coordination method that handles the entire search flow
        """
        # Step 1: Generate synonyms for the condition
        synonyms = self.get_synonyms(condition)
        
        # Step 2: Find matching trials based on synonyms and location
        trials = self.find_matching_trials(synonyms, location)
        
        # Step 3: Apply any additional filters
        if filters:
            trials = self.apply_filters(trials, filters)
            
        # Return the results
        return {
            "condition": condition,
            "synonyms": synonyms,
            "location": location,
            "trials": trials
        }
    
    def get_synonyms(self, input_condition):
        """
        Use the Synonym Generator Agent to expand the condition term
        """
      
        # Generate new synonyms
        synonyms = self.synonym_agent.generate_synonyms(input_condition)
                
        return synonyms
    
    def find_matching_trials_from_synonyms(self, synonyms):

        matching_trials = trial_filters.get_relevant_studies_from_conditions(synonyms)

        return matching_trials


    def find_matching_trials_from_location_with_age_gender(self, trials, location):
        """
        Get matching trial sites for the input location with age information
        """
        matching_trial_sites = trial_filters.get_sites_sorted_by_distance_with_age_gender(trials, location)
        
        return matching_trial_sites
    
    
    def get_trial_explanation(self, ssp):
        """
        Get simplified explanation of a specific trial
        """

        # Get simplified trial explanation data from study site pair
        trial_data = self.explainer_agent.explain_trial(ssp)

        trial_md=self.explainer_agent.generate_trial_markdown(trial_data)

        return trial_data,trial_md
    
    def get_knowledge_resources(self, condition, trial_about):

        condition_md=self.knowledge_agent.curate_medical_page(condition)
        drug_md = self.knowledge_agent.generate_drug_markdown_from_trial_about(trial_about)
                
        return condition_md,drug_md
    
    def get_condition_md(self, condition):
        condition_md=self.knowledge_agent.curate_medical_page(condition)
        return condition_md

    def get_drug_md(self, trial_about):
        drug_md = self.knowledge_agent.generate_drug_markdown_from_trial_about(trial_about)
                
        return drug_md


    def parse_age_string(self, age_string):
        age = trial_filters.parse_age(age_string)
        return age
    
    def determine_age_group(self, min_age, max_age):
        """
        Determine the age group based on the age value
        """
        age_groups = trial_filters.determine_age_groups(min_age, max_age)
        return age_groups
    
    def fix_location(self,input_location):

        return self.location_agent.fix_location(input_location)




"""
#Example usage of the AgentCoordinator class
coordinator = AgentCoordinator()
#First try synonym generation
condition="MS"
synonyms = coordinator.get_synonyms(condition)
#Now get matching trials for the synonyms
matching_trials = coordinator.find_matching_trials_from_synonyms(synonyms)
#Now get matching trial sites for the input location
location="Allentown, PA"
matching_trial_sites = coordinator.find_matching_trials_from_location(matching_trials,location)
matching_trial_sites
#Get condition md one once it'll persist over all studies
condition_md=coordinator.get_condition_md(condition)
display(Markdown(condition_md))


#Now users can click a site to drill into that study...

#Grab the first result as our study_site_pair
study_site_pair=matching_trial_sites.loc[1]
study_data,study_md=coordinator.get_trial_explanation(study_site_pair)
study_data
display(Markdown(study_md))
#WE ALREADY HAVE THE CONDITION MARKDOWN FROM ABOVE DONT NEED TO REGNEERATE
#Now get DRUG MD
drug_md=coordinator.get_drug_md(study_data['about'])
display(Markdown(drug_md))


#Fix a location
coordinator.fix_location('PA')

"""