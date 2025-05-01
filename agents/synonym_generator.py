"""
synonym_generator.py

This module defines the SynonymGeneratorAgent, an agent that expands disease or condition names into clinically relevant synonyms 
using OpenAI's function-calling API.

Key Method:
- generate_synonyms(disease_description): Returns up to 10 related disease terms to improve the reach and accuracy of clinical trial matching.
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
from utils import openai_util
import json


azure_model_name = "gpt-4o-mini"
azure_deployment = "gpt-4o-mini"
#github_model_name = "openai/gpt-4o-mini"

class SynonymGeneratorAgent:
    def __init__(self):
        """
        Initialize the SynonymGeneratorAgent.
        """

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
                model=azure_deployment
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
disease="Breast Cancer"
SynonymGeneratorAgent=SynonymGeneratorAgent()
synonyms = SynonymGeneratorAgent.generate_synonyms(disease)
print(synonyms)
#Output: ['Breast Cancer', 'Mammary Carcinoma', 'Breast Neoplasm', 'Breast Tumor', 'Breast Neoplasms', 'Breast Neoplasm, Malignant', 'Breast Neoplasm, Invasive', 'Invasive Breast Carcinoma', 'Invasive Lobular Carcinoma', 'Invasive Ductal Carcinoma']
"""