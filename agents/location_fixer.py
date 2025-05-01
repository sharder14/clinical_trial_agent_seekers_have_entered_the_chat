"""
location_fixer.py

This module defines the `LocationFixerAgent` class, which standardizes and corrects free-text location inputs provided by users.

Core Method:
- fix_location(location_text): Accepts a free-text location input and returns a corrected, standardized U.S. location or '-1' if invalid.
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

class LocationFixerAgent:
    def __init__(self):
        """
        Initialize the LocationFixerAgent.
        """

    def fix_location(self,location_text):
        """
        Function to correct and format a free-text U.S. location input into a properly structured United States location.
        If the input is not a valid U.S. location, return '-1'.
        """
        client = openai_util.get_azure_openai_client()

        system_message = """
        You are a helpful assistant that corrects user-entered location text to valid United States city or state names.
        
        - If the input is a city abbreviation (e.g., "LA"), return the full city and state (e.g., "Los Angeles, California").
        - If the input is a state abbreviation (e.g., "PA"), return the full state name (e.g., "Pennsylvania").
        - If the input contains typos (e.g., "nwe york"), correct them (e.g., "New York").
        """

        messages = [
            {"role": "system", "content": system_message},
            {"role": "user", "content": f"Correct and format this U.S. location: '{location_text}'"}
        ]

        functions = [
            {
                "name": "get_location",
                "description": "Takes in a valid US Location and returns it's zip code and state",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "location": {
                            "type": "string",
                            "description": "Proper U.S. location string (e.g., 'New York, New York' or 'Los Angeles, California'). Or a specific State or address. If the input is not a valid U.S. location the argument should be '-1'."
                        }
                    },
                    "required": ["location"]
                }
            }
        ]

        response = client.chat.completions.create(
            messages=messages,
            functions=functions,
            function_call={"name": "get_location"},
            model=azure_deployment,
            max_tokens=1000,
            temperature=0.3,
            top_p=1.0
        )

        try:
            output_data = response.choices[0].message.function_call.arguments
            output_data = json.loads(output_data)
            return output_data.get('location', None)
        except (KeyError, json.JSONDecodeError, AttributeError):
            return None
    

"""
#Example usage
location="Paris, France"
agent=LocationFixerAgent()
fixed_location = agent.fix_location(location)
print(fixed_location)
"""