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

#Load in agent helpers
from agents.helpers import trial_filters
#from importlib import reload
#reload(trial_filters)


class AgentCoordinator:
    def __init__(self):
        # Initialize the specialized agents
        self.synonym_agent = SynonymGeneratorAgent()
        self.explainer_agent = TrialExplainerAgent()
        #self.knowledge_agent = KnowledgeCuratorAgent()
                
        
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


    def find_matching_trials_from_location(self,trials,location):

        sorted_trials = trial_filters.get_sites_sorted_by_distance(trials,location)
        
        return sorted_trials
    
    def apply_filters(self, trials, filters):
        """
        Apply additional filters specified by the user
        """
        return self.trial_filter.apply_filters(trials, filters)
    
    def get_trial_explanation(self, ssp):
        """
        Get simplified explanation of a specific trial
        """

        # Get simplified trial explanation data from study site pair
        trial_data = self.explainer_agent.explain_trial(ssp)


        return trial_data
    
    def get_knowledge_resources(self, condition, synonyms=None):
        """
        Get educational resources for a condition
        """
        # Use provided synonyms or generate them
        if synonyms is None:
            synonyms = self.generate_synonyms(condition)
            
        
        # Gather knowledge resources
        resources = self.knowledge_agent.curate_resources(condition, synonyms)
                
        return resources
    



"""
#Example usage of the AgentCoordinator class
coordinator = AgentCoordinator()
#First try synonym generation
synonyms = coordinator.get_synonyms("Nash")
#Now get matching trials for the synonyms
matching_trials = coordinator.find_matching_trials_from_synonyms(synonyms)
#Now get matching trial sites for the input location
matching_trial_sites = coordinator.find_matching_trials_from_location(matching_trials,"Ithaca, NY")
matching_trial_sites
#Grab the first result as our study_site_pair
study_site_pair=matching_trial_sites.loc[0]
study_data=coordinator.get_trial_explanation(study_site_pair)
study_data
#Now get knowledge resources...


"""