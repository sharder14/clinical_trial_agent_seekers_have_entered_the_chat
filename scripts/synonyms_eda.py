"""
This script performs exploratory data analysis (EDA) on how to extract synonyms from a given input disease/condition name.

See study_condition_embeddings_init.py for the script that initializes the study condition embeddings and also updates the embeddings when new rows are added to the database.

Run that file first to create the embeddings and then run this file to perform EDA on the synonyms.
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


model_name = "gpt-4o-mini"
deployment = "gpt-4o-mini"


client = openai_util.get_azure_openai_client()

disease_description = "breast cancer"

# Define the messages
system_message = """
You are a clinical terminology expert. Generate approximate synonyms for diseases, including common names, abbreviations, and other clinically relevant terms. "
The synonyms should be semantically similar to the input disease name. Specifically we are looking for synonyms of the given disease name that are used in clinical trials.
"""


messages = [
    {
        "role": "system",
        "content": system_message        
    },
    {
        "role": "user",
        "content": f"Generate up to 10 clinically relevant synonyms for: {disease_description}"
    }
]

# Define the function
functions = [
    {
        "name": "generate_disease_synonyms",
        "description": "Generates up to 10 clinically relevant synonyms for a disease",
        "parameters": {
            "type": "object",
            "properties": {
                "synonyms": {
                    "type": "array",
                    "items": {
                        "type": "string"
                    },
                    "description": "List of clinically relevant synonyms for the disease"
                }
            },
            "required": ["synonyms"]
        }
    }
]

# Make the API call
response = client.chat.completions.create(
   messages=messages,
    max_tokens=4096,
    temperature=1.0,
    top_p=1.0,
    functions=functions,
    function_call={"name": "generate_disease_synonyms"},
    model=deployment
)

# Extract the function call and parse the arguments
output_data=response.choices[0].message.function_call.arguments
output_data = json.loads(output_data)
output_data = output_data.get('synonyms', [])
output_data

#Add the original disease name to the front of the list of synonyms
output_data = [disease_description] + output_data
output_data

#Now we want to use the synonyms to match to semantically similar indications as the primary indication in a trial
#We will use the trial data from the SQL database and match the synonyms to the indications in the trial data


from sentence_transformers import SentenceTransformer
import torch

# Check if GPU is available
device = 'cuda' if torch.cuda.is_available() else 'cpu'
print(f"Using device: {device}")

# Load model and move it to GPU
model = SentenceTransformer('all-MiniLM-L6-v2', device=device)

#Load in the active trials data from the data folder
active_trials_w_conditions_object = pd.read_pickle(os.path.join(base_dir, 'data', 'active_trials_w_condition_embeddings.pkl'))
active_trials_w_conditions = active_trials_w_conditions_object['active_trials_w_conditions']
conditions_df = active_trials_w_conditions_object['conditions_df']
condition_embeddings = active_trials_w_conditions_object['condition_embeddings']

#Now we want to get sentence similarity between all the synonyms and the conditions in the active trials data
#We will use the condition embeddings to do this

#Get the embeddings for the synonyms
synonym_embeddings = model.encode(output_data, device=device)
synonym_embeddings

#Now we want to get the cosine similarity between the synonyms and the condition embeddings
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np

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

#Subset similarity df to only those studies that have similarity >=.8
similarity_df=similarity_df[similarity_df['similarity']>=.8].reset_index(drop=True)
similarity_df
#Now we want to get the nct_ids for the conditions that are similar to the synonyms
similarity_df['nct_ids'] = similarity_df['condition_ind'].apply(lambda x: conditions_df.iloc[x]['nct_ids'])
similarity_df

#Now expand the nct_ids column out so that there is one row per condition_ind, nct_id, and similarity
similarity_df = similarity_df.explode('nct_ids').reset_index(drop=True)
#Now drop duplicates on NCT_ID
relevant_trials_df = similarity_df.drop_duplicates(subset=['nct_ids'], keep='first').reset_index(drop=True)
relevant_trials_df


