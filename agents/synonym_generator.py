"""
Agent that generates synonyms for a disease name using the OpenAI API.
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

class SynonymGeneratorAgent:
    def __init__(self):
        """
        Initialize the SynonymGeneratorAgent.
        """
        self.client = openai_util.get_azure_openai_client()
        self.model_name = model_name
        self.deployment = deployment

    def generate_synonyms(self,disease_description):
        """
        Function to generate synonyms for a disease name using the OpenAI API.
        """
        # Get the OpenAI client
        client = openai_util.get_azure_openai_client()



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

        #Add the original disease name to the front of the list of synonyms
        output_data = [disease_description] + output_data
        return output_data
    

"""
#Example usage
synonyms = SynonymGeneratorAgent.generate_synonyms("Breast Cancer")
print(synonyms)
#Output: ['Breast Cancer', 'Mammary Carcinoma', 'Breast Neoplasm', 'Breast Tumor', 'Breast Neoplasms', 'Breast Neoplasm, Malignant', 'Breast Neoplasm, Invasive', 'Invasive Breast Carcinoma', 'Invasive Lobular Carcinoma', 'Invasive Ductal Carcinoma']
"""