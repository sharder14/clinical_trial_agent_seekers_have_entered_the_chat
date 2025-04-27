"""
Given a nct_id get the relevant information about the trial

1. trial name then link to study on clinical trial .gov
2. What is this study about
3. Who can join this study
4. What happens in this study (join the study treatment and how long will it last to this part)
5. Who to contact, and site details

Relevent data from the db for each piece above:


1. studies table
    columns: nct_id, brief_title and link to study on clinical trial .gov

2. studies
    official_title, brief_summary, 
   optional: outcomes table with primary outcome

3. eligibilities
    all columns

4. Designs
    allocation, intervention_model, masking, primary_purpose
   Design_groups
    group_type, title, description
   Interventions

5. central_contacts
    all columns from central_contacts table
   facilities 

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

azure_model_name = "gpt-4o-mini"
azure_deployment = "gpt-4o-mini"

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

#Now lets get the relevant info from the database
study_details_sql=f"""
SELECT * from studies
WHERE nct_id = '{study_site_pair['nct_id']}'
"""
study_details=sql_util.get_table(study_details_sql)
study_details
sorted(study_details.columns)

eligibilities_sql=f"""
SELECT * from eligibilities
WHERE nct_id = '{study_site_pair['nct_id']}'
"""
eligibilities=sql_util.get_table(eligibilities_sql)
eligibilities

designs_sql=f"""
SELECT * from designs
WHERE nct_id = '{study_site_pair['nct_id']}'
"""
designs=sql_util.get_table(designs_sql)
designs

design_groups_sql=f"""
SELECT * from design_groups
WHERE nct_id = '{study_site_pair['nct_id']}'
"""
design_groups=sql_util.get_table(design_groups_sql)
design_groups

interventions_sql=f"""
SELECT * from interventions
WHERE nct_id = '{study_site_pair['nct_id']}'
"""
interventions=sql_util.get_table(interventions_sql)
interventions

design_outcomes_sql=f"""
select * from design_outcomes
where nct_id= '{study_site_pair['nct_id']}'
and outcome_type='primary'
"""
design_outcomes=sql_util.get_table(design_outcomes_sql)
design_outcomes

central_contacts_sql=f"""
SELECT * from central_contacts
WHERE nct_id = '{study_site_pair['nct_id']}'
"""
central_contacts=sql_util.get_table(central_contacts_sql)
central_contacts

#We already have the site details from study_site_pair

#Now lets work on our outputs

#1. Trial name and link to study on clinical trial .gov
trial_name = study_details['brief_title'].values[0]
trial_link = f"https://clinicaltrials.gov/study/{study_site_pair['nct_id']}"

#2-4 are generated from LLM tool calling so we send payload of
#  the study details for it to parse



arm_payload=design_groups[['group_type','title','description']].to_json(orient='records')
interventions_payload=interventions[['intervention_type','name','description']].to_json(orient='records')

trial_payload={
  "brief_summary": study_details.loc[0]["brief_title"],
  "official_title": study_details.loc[0]["official_title"],
  "eligibility_criteria": eligibilities.loc[0]["criteria"],
  "gender": eligibilities.loc[0]['gender'],
  "minimum_age": eligibilities.loc[0]['minimum_age'],
  "maximum_age": eligibilities.loc[0]['maximum_age'],
  "design_details": {
    "allocation": designs.loc[0]['allocation'],
    "intervention_model": designs.loc[0]['intervention_model'],
    "masking": designs.loc[0]['masking'],
    "primary_purpose": designs.loc[0]['primary_purpose']
  },
  "arms": arm_payload,
  "interventions": interventions_payload,
  "primary_outcome_measurements": [
    {
      "measure": design_outcomes.loc[0]['measure'],
      "time_frame": design_outcomes.loc[0]['time_frame']
    }
  ]
}

functions = [
    {
        "name": "generate_patient_friendly_trial_summary",
        "description": "Creates a clear and easy-to-understand structured summary from clinical trial data, written for a patient audience.",
        "parameters": {
            "type": "object",
            "properties": {
                "what_is_this_study_about": {
                    "type": "string",
                    "description": "In 2-4 sentences, clearly explain the main goal of this study. Include the condition being studied and what the study hopes to find out. Use simple, reassuring language appropriate for patients."
                },
                "who_can_join_this_study": {
                    "type": "object",
                    "properties": {
                        "inclusion_criteria": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "List of simple, patient-friendly bullet points summarizing who CAN join the study based on inclusion criteria."
                        },
                        "exclusion_criteria": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "List of simple, patient-friendly bullet points summarizing who CANNOT join the study based on exclusion criteria."
                        }
                    },
                    "description": "Summarizes the eligibility criteria into two friendly lists: who can and who cannot join the study."
                },
                "what_happens_in_this_study": {
                    "type": "object",
                    "properties": {
                        "summary_of_activities": {
                            "type": "string",
                            "description": "Brief paragraph (3-6 sentences) explaining what participants will do during the study. Include how treatments are given, how long it lasts, any important study procedures (like blood tests), and any important outcome goals. Focus on what the participant experience will be like."
                        }
                    },
                    "description": "Summarizes the design, treatments, activities, and duration of participation into a single, easy-to-read paragraph."
                }
            },
            "required": [
                "what_is_this_study_about",
                "who_can_join_this_study",
                "what_happens_in_this_study"
            ]
        }
    }
]


client = openai_util.get_azure_openai_client()

system_message = {
    "role": "system",
    "content": "You are a clinical trial explainer agent tasked with summarizing and structuring trial information for patients."
}
user_message = {
    "role": "user",
    "content": f"Summarize the following trial information into patient-friendly fields:\n\n{json.dumps(trial_payload, indent=2)}"
}


response = client.chat.completions.create(
    model=azure_deployment,
    messages=[system_message, user_message],
    functions=functions,
    function_call={"name": "generate_patient_friendly_trial_summary"},
    temperature=0.7,
    max_tokens=4096
)

output=json.loads(response.choices[0].message.function_call.arguments)
output
output['what_is_this_study_about']
output['who_can_join_this_study']
output['who_can_join_this_study']['inclusion_criteria']
output['who_can_join_this_study']['exclusion_criteria']
output['what_happens_in_this_study']['summary_of_activities']

#Lastly site details and contacts...
site_details={
    'site_name':study_site_pair['name'],
    'city':study_site_pair['city'],
    'state':study_site_pair['state'],
    'zip':study_site_pair['zip'],
}
contact_details={
    'contact_name':central_contacts.loc[0]['name'],
    'contact_phone':central_contacts.loc[0]['phone'],
    'contact_email':central_contacts.loc[0]['email']
}


