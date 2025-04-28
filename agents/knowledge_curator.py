"""
Agent that curates knowledge of the condition and drug being studied...
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
from agents.helpers import trial_filters, knowledge_web
#from importlib import reload
#reload(trial_filters)
from typing import Dict
from IPython.display import display
from IPython.display import Markdown

azure_model_name = "gpt-4o-mini"
azure_deployment = "gpt-4o-mini"
#github_model_name = "openai/gpt-4o-mini"




class KnowledgeCuratorAgent:
    def __init__(self):
        """Initialize the KnowledgeCuratorAgent."""
        self.client = openai_util.get_azure_openai_client()


    def curate_medical_page(self, condition):
        """
        Summarizes a MedlinePlus (or similar) medical page for patients and extracts essential links.
        """

        #Get page text from condition
        page_text=knowledge_web.get_condition_page(condition)

        system_message = """
        You are a helpful medical explainer assistant.
        Given a chunk of patient education content from a trusted source like MedlinePlus,
        extract a structured, patient-friendly summary and a list of essential links.

        The summary should be clear, simple, and written at a 6th-8th grade reading level.
        Do not copy text verbatim. Simplify medical jargon where possible.
        Only include links that are most helpful for patients.
        """

        messages = [
            {"role": "system", "content": system_message},
            {"role": "user", "content": f"Please summarize and extract useful links from the following content:\n\n{page_text}"}
        ]

        functions = [
            {
                "name": "curate_medical_page",
                "description": "Extracts a structured medical summary and essential patient-friendly links from medical content.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "summary": {
                            "type": "object",
                            "properties": {
                                "what_it_is": {
                                    "type": "string",
                                    "description": "A plain-language, easy-to-read explanation of what this condition is and how it affects the body."
                                },
                                "symptoms": {
                                    "type": "string",
                                    "description": "A simple summary of common symptoms or signs of this condition. If not mentioned, leave blank."
                                },
                                "causes": {
                                    "type": "string",
                                    "description": "A short explanation of what causes the condition or what risk factors increase the chance of having it. If not mentioned, leave blank."
                                },
                                "diagnosis_and_tests": {
                                    "type": "string",
                                    "description": "Brief explanation of how this condition is diagnosed or what tests are typically done. If not mentioned, leave blank."
                                },
                                "treatments_and_therapies": {
                                    "type": "string",
                                    "description": "A patient-friendly overview of treatment options and therapies used to manage the condition. If not mentioned, leave blank."
                                }
                            }
                        },
                        "related_links": {
                            "type": "array",
                            "description": "A list of the most essential and patient-useful links found in the page, each with a description of what the link is for and where it comes from. Pay special attention that the links provided are the exact url found in the content",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "title": {
                                        "type": "string",
                                        "description": "A clear, friendly title for the link (e.g. 'Managing Diabetes Guide')"
                                    },
                                    "description": {
                                        "type": "string",
                                        "description": "A short description of what the patient will find at this link."
                                    },
                                    "url": {
                                        "type": "string",
                                        "description": "The full URL of the resource."
                                    },
                                    "source": {
                                        "type": "string",
                                        "description": "The source organization or site providing the link (e.g. 'MedlinePlus', 'NIH', 'CDC')"
                                    }
                                },
                                "required": ["title", "description", "url", "source"]
                            }
                        }
                    },
                    "required": ["summary", "related_links"]
                }
            }
        ]

        response = self.client.chat.completions.create(

            messages=messages,
            temperature=0.7,
            max_tokens=4096,
            functions=functions,
            function_call={"name": "curate_medical_page"},
            model=azure_deployment
        )

        output_data = json.loads(response.choices[0].message.function_call.arguments)

        """Turn the structured curated medical page into friendly markdown with emojis."""
        summary = output_data.get("summary", {})
        links = output_data.get("related_links", [])

        md = []

        if summary.get("what_it_is"):
            md.append("## 🩺 What is this condition?\n")
            md.append(f"{summary['what_it_is']}\n")

        if summary.get("symptoms"):
            md.append("\n## ⚡ Symptoms\n")
            md.append(f"{summary['symptoms']}\n")

        if summary.get("causes"):
            md.append("\n## 🧬 Causes\n")
            md.append(f"{summary['causes']}\n")

        if summary.get("diagnosis_and_tests"):
            md.append("\n## 🧪 Diagnosis and Tests\n")
            md.append(f"{summary['diagnosis_and_tests']}\n")

        if summary.get("treatments_and_therapies"):
            md.append("\n## 💊 Treatments and Therapies\n")
            md.append(f"{summary['treatments_and_therapies']}\n")

        if links:
            md.append("\n## 🔗 Helpful Resources\n")
            for link in links:
                md.append(f"- **[{link['title']}]({link['url']})**  \n  {link['description']} _(Source: {link['source']})_\n")

        return "\n".join(md).strip()

    def generate_drug_markdown_from_trial_about(self,trial_about_text):

        system_message = {
            "role": "system",
            "content": "You are a clinical trial explainer. Determine if a study is testing a specific drug based on the study description. If yes, explain about the drug. If not, explain that no specific drug is being tested."
        }
        user_message = {
            "role": "user",
            "content": f"Based on this study description, determine if a drug is being tested:\n\n{trial_about_text}"
        }

        functions = [
            {
                "name": "identify_drug_study",
                "description": "Decides if a study tests a drug and optionally identifies it.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "is_drug_study": {"type": "boolean", "description": "True if a drug is the main focus, False otherwise."},
                        "drug_name": {"type": "string", "description": "Name of the drug if applicable, otherwise empty."},
                        "reason_if_no_drug": {"type": "string", "description": "Explain why this is not a drug study in simple terms if no drug is involved."}
                    },
                    "required": ["is_drug_study", "drug_name", "reason_if_no_drug"]
                }
            }
        ]

        response = self.client.chat.completions.create(
            model=azure_deployment,
            messages=[system_message, user_message],
            functions=functions,
            function_call={"name": "identify_drug_study"},
            temperature=0.7,
            max_tokens=1024
        )

        decision = json.loads(response.choices[0].message.function_call.arguments)
        print(decision)
        # Now decide what markdown to return
        md = []

        if decision.get("is_drug_study", False):
            # Normal drug info flow
            md.append(self.curate_drug_page(decision['drug_name']))
        else:
            # No drug is being studied
            md.append("## 💬 No Specific Drug Being Studied\n")
            reason = decision.get("reason_if_no_drug", "This study focuses on something other than testing a drug.")
            md.append(f"{reason}\n")

        return "\n".join(md).strip()

    def curate_drug_page(self, drug_name):
        """
        Summarizes a MedlinePlus (or similar) medical page for patients and extracts essential links.
        """

        #Given the drug name use the helper function to get the relevant page and text
        page_text,source_url=knowledge_web.get_drug_page(drug_name)

        system_message = {
            "role": "system",
            "content": "You are a helpful medical explainer specializing in medications. Read drug information and create a simple, friendly patient summary."
        }
        user_message = {
            "role": "user",
            "content": f"Summarize the following drug information into patient-friendly fields:\n\n{page_text}"
        }

        functions = [
            {
                "name": "curate_drug_summary",
                "description": "Creates a structured, patient-friendly summary from drug text.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "what_is_this_drug": {"type": "string", "description": "Simple explanation of what the drug treats or helps with."},
                        "how_to_take_it": {"type": "string", "description": "Plain instructions for how to take the drug (if described)."},
                        "warnings_and_precautions": {"type": "string", "description": "Important warnings, risks, or precautions."},
                        "possible_side_effects": {"type": "string", "description": "Common side effects in friendly language."}
                    },
                    "required": ["what_is_this_drug", "how_to_take_it", "warnings_and_precautions", "possible_side_effects"]
                }
            }
        ]

        response = self.client.chat.completions.create(
            model=azure_deployment,
            messages=[system_message, user_message],
            functions=functions,
            function_call={"name": "curate_drug_summary"},
            temperature=0.7,
            max_tokens=4096
        )

        curated_info = json.loads(response.choices[0].message.function_call.arguments)

        # Generate sweet Markdown
        md = []

        if curated_info.get("what_is_this_drug"):
            md.append("## 🩺 What is this drug?\n")
            md.append(f"{curated_info['what_is_this_drug']}\n")

        if curated_info.get("how_to_take_it"):
            md.append("\n## 💊 How should I take it?\n")
            md.append(f"{curated_info['how_to_take_it']}\n")

        if curated_info.get("warnings_and_precautions"):
            md.append("\n## ⚠️ Warnings and Precautions\n")
            md.append(f"{curated_info['warnings_and_precautions']}\n")

        if curated_info.get("possible_side_effects"):
            md.append("\n## 🤕 Possible Side Effects\n")
            md.append(f"{curated_info['possible_side_effects']}\n")
        
        if source_url:
            md.append(f"\n---\n\n🔗 [**See More Details**]({source_url})")

        return "\n".join(md).strip()

"""
#Example usage
coordinator = AgentCoordinator()
#First try synonym generation
condition="MS"
synonyms = coordinator.get_synonyms(condition)
#Now get matching trials for the synonyms
matching_trials = coordinator.find_matching_trials_from_synonyms(synonyms)
#Now get matching trial sites for the input location
location="Levittown, PA"
matching_trial_sites = coordinator.find_matching_trials_from_location(matching_trials,location)
matching_trial_sites
#Grab the first result as our study_site_pair
study_site_pair=matching_trial_sites.loc[1]
study_data=coordinator.get_trial_explanation(study_site_pair)
study_data
#Now get knowledge resources...
agent = KnowledgeCuratorAgent()
#First get condition knowledge
condition_md=agent.curate_medical_page(condition)
#Display the markdown
display(Markdown(condition_md))
#Now drug knowledge
drug_md = agent.generate_drug_markdown_from_trial_about(study_data['about'])
display(Markdown(drug_md))



"""
