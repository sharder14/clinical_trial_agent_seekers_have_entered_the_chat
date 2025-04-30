"""
Agent that takes in free text location and converts it to United States best match location
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
        Function to fix the input location to United States
        """
        # Get the OpenAI client
        client = openai_util.get_azure_openai_client()

        # Define the messages
        system_message = """
        You are a useful assitant, answer the question to the best of your abilities. Use the tools at your disposal.
        """


        messages = [
            {
                "role": "system",
                "content": system_message        
            },
            {
                "role": "user",
                "content": f"Given the input free text location, format it so that it is structed cleanly and it a United States valid location: {location_text}"
            }
        ]

        # Define the function
        functions = [
            {
                "name": "fix_location",
                "description": "Format the location into a clean United States address format, for example if we are given state abbreviations write out the full text.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "location": {
                            "type": "string",
                            "description": "Correctly formatted US location text"
                        }
                    },
                    "required": ["location"]
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
                function_call={"name": "fix_location"},
                model=azure_deployment
        )

        # Extract the function call and parse the arguments
        output_data=response.choices[0].message.function_call.arguments
        output_data = json.loads(output_data)
        return output_data['location']
    

"""
#Example usage
location="PA"
agent=LocationFixerAgent()
fixed_location = agent.fix_location(location)
print(fixed_location)
"""