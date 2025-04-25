"""
Script that initializes the study condition embeddings and also updates the embeddings when new rows are added to the database.
"""

import os
import sys
from dotenv import load_dotenv
# Load environment variables
load_dotenv()
base_dir = os.getenv('base_dir')
# Change the working directory to the base directory
os.chdir(base_dir)
sys.path.append(base_dir)
import pandas as pd
from utils import sql_util
import json
from sentence_transformers import SentenceTransformer
import torch

# Check if GPU is available
device = 'cuda' if torch.cuda.is_available() else 'cpu'
print(f"Using device: {device}")

# Load model and move it to GPU
model = SentenceTransformer('all-MiniLM-L6-v2', device=device)



def main():

    # Check if data file exists in the data folder, if it does, read it in
    if os.path.exists(os.path.join(base_dir, 'data', 'active_trials_w_condition_embeddings.pkl')):
        active_trials_w_conditions_object = pd.read_pickle(os.path.join(base_dir, 'data', 'active_trials_w_condition_embeddings.pkl'))
        condition_embeddings = active_trials_w_conditions_object['condition_embeddings']
        active_trials_w_conditions = active_trials_w_conditions_object['active_trials_w_conditions']
        conditions_df = active_trials_w_conditions_object['conditions_df']

    # Get the trial data from the SQL database
    active_trials_w_conditions_query = """
    with active_trials as (select 
        nct_id from aact.ctgov.studies s  
        where overall_status in ('ENROLLING_BY_INVITATION','NOT_YET_RECRUITING','RECRUITING')
    )
    select at.nct_id, c.downcase_name as condition 
    from active_trials at 
    join aact.ctgov.conditions c on at.nct_id=c.nct_id
    """
    current_active_trials_w_conditions = sql_util.get_table(active_trials_w_conditions_query)

    # Merge the new data with existing data if it exists
    if 'active_trials_w_conditions' in locals():
        new_active_trials_w_conditions = pd.concat([current_active_trials_w_conditions, active_trials_w_conditions], ignore_index=True)
        new_active_trials_w_conditions = new_active_trials_w_conditions.drop_duplicates(subset=['nct_id', 'condition'], keep='last').reset_index(drop=True)
    else:
        new_active_trials_w_conditions = current_active_trials_w_conditions

    # Create a dataframe with unique_id for condition, condition name, and a list of nct_ids with that condition
    new_conditions_df = new_active_trials_w_conditions.groupby('condition')['nct_id'].apply(list).reset_index(name='nct_ids')
    new_conditions_df['unique_id'] = new_conditions_df.index
    new_conditions_df = new_conditions_df[['unique_id', 'condition', 'nct_ids']]

    # Embed the condition names
    new_condition_embeddings = model.encode(new_conditions_df['condition'], device=device)

    # Append new data to the existing data to overwrite the pickle file
    if 'condition_embeddings' in locals():
        condition_embeddings = torch.cat((condition_embeddings, new_condition_embeddings), dim=0)
    else:   
        condition_embeddings = new_condition_embeddings

    if 'conditions_df' in locals():
        conditions_df = pd.concat([conditions_df, new_conditions_df], ignore_index=True)
        conditions_df = conditions_df.drop_duplicates(subset=['condition'], keep='last').reset_index(drop=True)
    else:
        conditions_df = new_conditions_df

    if 'active_trials_w_conditions' in locals():
        active_trials_w_conditions = pd.concat([active_trials_w_conditions, new_active_trials_w_conditions], ignore_index=True)
        active_trials_w_conditions = active_trials_w_conditions.drop_duplicates(subset=['nct_id', 'condition'], keep='last').reset_index(drop=True)
    else:
        active_trials_w_conditions = new_active_trials_w_conditions

    # Write the object out as a pickle file
    out = {
        'condition_embeddings': condition_embeddings,
        'conditions_df': conditions_df,
        'active_trials_w_conditions': active_trials_w_conditions
    }

    out_file = os.path.join(base_dir, 'data', 'active_trials_w_condition_embeddings.pkl')
    with open(out_file, 'wb') as f:
        pd.to_pickle(out, f)

if __name__ == "__main__":
    main()


