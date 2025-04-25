"""
This is a module that contains functions to filter clinical trial data based on various criteria.
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


from sentence_transformers import SentenceTransformer
import torch

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
    synonym_embeddings

    #Get the cosine similarity between the synonyms and the condition embeddings
    cosine_similarities = cosine_similarity(synonym_embeddings, condition_embeddings)
    cosine_similarities

    inds,vals=np.argsort(cosine_similarities, axis=1)[:, ::-1],np.sort(cosine_similarities, axis=1)[:, ::-1]
    vals
    inds

    #Write vals and inds to pandas dataframe
    similarity_df=pd.DataFrame({'condition_ind':inds.flatten(),'similarity':vals.flatten()})
    similarity_df.sort_values('similarity', ascending=False, inplace=True)
    similarity_df=similarity_df.reset_index(drop=True)
    similarity_df

    #Subset similarity df to only those studies that have similarity >=similarity_score_threshold
    similarity_df=similarity_df[similarity_df['similarity']>=similarity_score_threshold].reset_index(drop=True)
    similarity_df
    #Now we want to get the nct_ids for the conditions that are similar to the synonyms
    similarity_df['nct_ids'] = similarity_df['condition_ind'].apply(lambda x: conditions_df.iloc[x]['nct_ids'])
    similarity_df

    #Now expand the nct_ids column out so that there is one row per condition_ind, nct_id, and similarity
    similarity_df = similarity_df.explode('nct_ids').reset_index(drop=True)
    #Now drop duplicates on NCT_ID
    relevant_trials_df = similarity_df.drop_duplicates(subset=['nct_ids'], keep='first').reset_index(drop=True)
    return relevant_trials_df