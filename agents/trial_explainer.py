"""
Agent that explains the trials
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
#Load in agent helpers
from agents.helpers import trial_filters
#from importlib import reload
#reload(trial_filters)


azure_model_name = "gpt-4o-mini"
azure_deployment = "gpt-4o-mini"
#github_model_name = "openai/gpt-4o-mini"

class TrialExplainerAgent:
    def __init__(self):
        """
        Initialize the TrialExplainerAgent.
        """

    def explain_trial(self,study_site_pair):
        """
        Function to generate synonyms for a disease name using the OpenAI API.
        """
        # Get the OpenAI client
        client = openai_util.get_azure_openai_client()


        trial_dfs=trial_filters.get_trial_details(study_site_pair)
        study_details=trial_dfs['study_details']
        trial_dfs.keys()
        eligibilities=trial_dfs['eligibilities']
        designs=trial_dfs['designs']
        design_groups=trial_dfs['design_groups']
        interventions=trial_dfs['interventions']
        design_outcomes=trial_dfs['design_outcomes']
        central_contacts=trial_dfs['central_contacts']

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
        if not central_contacts.empty:
            contact_details={
                'contact_name':central_contacts.loc[0]['name'],
                'contact_phone':central_contacts.loc[0]['phone'],
                'contact_email':central_contacts.loc[0]['email']
        }
        else:
            contact_details={
                'contact_name':'Not Currently Available',
                'contact_phone':'Not Currently Available',
                'contact_email':'Not Currently Available'
        }


        out={
            'title':{
                'trial_name':trial_name,
                'trial_link':trial_link
            },
            'about':output['what_is_this_study_about'],
            'who':output['who_can_join_this_study'],
            'what':output['what_happens_in_this_study']['summary_of_activities'],
            'contacts':{
                'site_details':site_details,
                'contact_details':contact_details
            }
        }

        return out 
    

    def generate_trial_markdown(self,trial_data) -> str:
        """Generate patient-friendly Markdown from the new structured trial output."""
        md = []

        # Title and trial link
        title_info = trial_data.get("title", {})
        if title_info.get("trial_name"):
            md.append(f"# 🧪 {title_info['trial_name']}\n")
        if title_info.get("trial_link"):
            md.append(f"[View full study details 🔗]({title_info['trial_link']})\n")

        # About section
        if trial_data.get("about"):
            md.append("\n## 📋 What is this study about?\n")
            md.append(f"{trial_data['about']}\n")

        # Who can join
        who_info = trial_data.get("who", {})
        if who_info:
            md.append("\n## 👥 Who can join this study?\n")
            inclusions = who_info.get("inclusion_criteria", [])
            exclusions = who_info.get("exclusion_criteria", [])

            if inclusions:
                md.append("\n**✅ You may be eligible if:**\n")
                for item in inclusions:
                    md.append(f"- {item}")

            if exclusions:
                md.append("\n\n**🚫 You may NOT be eligible if:**\n")
                for item in exclusions:
                    md.append(f"- {item}")

        # What happens in the study
        if trial_data.get("what"):
            md.append("\n\n## 🛠️ What happens in this study?\n")
            md.append(f"{trial_data['what']}\n")

        # Contacts
        contact_info = trial_data.get("contacts", {})
        if contact_info:
            md.append("\n## 📞 Who to contact\n")

            site = contact_info.get("site_details", {})
            if site:
                md.append(f"**Site:** {site.get('site_name', '')}\n")
                md.append(f"**Location:** {site.get('city', '')}, {site.get('state', '')} {site.get('zip', '')}\n")

            contact = contact_info.get("contact_details", {})
            if contact:
                md.append(f"\n**Contact Name:** {contact.get('contact_name', '')}\n")
                md.append(f"**Phone:** {contact.get('contact_phone', '')}\n")
                md.append(f"**Email:** {contact.get('contact_email', '')}\n")

        return "\n".join(md).strip()



    

#Example usage
"""
TrialExplainerAgent=TrialExplainerAgent()
#Get one study...
nct_id='NCT04929210'
study_site_pair=sql_util.get_table(f'select * from facilities where nct_id=\'{nct_id}\'')
study_site_pair=study_site_pair.loc[0]
output=TrialExplainerAgent.explain_trial(study_site_pair)
output
output['title']
"""

