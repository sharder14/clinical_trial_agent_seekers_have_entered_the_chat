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
import numpy as np
from utils import sql_util, openai_util
import json
from agents.agent_coordinator import AgentCoordinator

import requests

azure_model_name = "gpt-4o-mini"
azure_deployment = "gpt-4o-mini"



#Search medlinePlus for the condition
# Search DailyMed for the drug
drug="Resmetirom"
#https://dailymed.nlm.nih.gov/dailymed/search.cfm?labeltype=all&query=Guselkumab&audience=consumer
url='https://dailymed.nlm.nih.gov/dailymed/search.cfm?labeltype=all&query='+drug+'&audience=consumer'

#Search for the condition on MedlinePlus
condition="Diabetes Mellitus"
#Search url
url='https://vsearch.nlm.nih.gov/vivisimo/cgi-bin/query-meta?v%3Aproject=medlineplus&v%3Asources=medlineplus-bundle&query='+condition
#Put headers in for a more realistic request
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3'
}

r=requests.get(url, headers=headers)
#Get the content of the response
content = r.content.decode('utf-8')
content
#Extract ol class="results"
from bs4 import BeautifulSoup
soup = BeautifulSoup(content, 'html.parser')
results = soup.find('ol', class_='results')
#Extract the links from the results
links = results.find_all('a', href=True)
#Extract the href attributes from the links
hrefs = [link['href'] for link in links]
hrefs
#Go to the first href
first_href = hrefs[0]
# Print the first href
print(first_href)
"""
The actual url of the first search is contained like so:
....&url=https://medlineplus.gov/diabetesmellitus.html&....
To extract the actual URL, we need to parse the `first_href` string to find the `url` parameter. Here's how you can do that:

```pythonfrom urllib.parse import urlparse, parse_qs
from urllib.parse import urlparse, parse_qs 

# Parse the first_href to extract the actual URL
parsed_url = urlparse(first_href)
query_params = parse_qs(parsed_url.query)
actual_url = query_params.get('url', [None])[0]
"""

from urllib.parse import urlparse, parse_qs 
parsed_url = urlparse(first_href)
query_params = parse_qs(parsed_url.query)
url = query_params.get('url', [None])[0]


#Now make a request to the first href
r = requests.get(url, headers=headers)
#Get the content of the response
content = r.content.decode('utf-8')
content

#Extract div id="mplus-content"
soup = BeautifulSoup(content, 'html.parser')
mplus_content = soup.find('div', id='mplus-content')
mplus_content
main_content = mplus_content

# Remove unwanted elements
for unwanted in main_content.find_all(["nav", "footer", "aside", "script", "style"]):
    unwanted.decompose()

# Optionally remove anything after 'References'
refs = main_content.find(string=lambda text: "References" in text)
if refs:
    for elem in refs.find_all_next():
        elem.decompose()

# Convert remaining content to plain text with newlines for headings
cleaned_text = ""
for elem in main_content.find_all(["h1", "h2", "h3", "p", "ul", "ol"]):
    text = elem.get_text(strip=True)
    if text:
        cleaned_text += f"{text}\n\n"

cleaned_text


#Make it look pretty
soup = BeautifulSoup(content, 'html.parser')
#Show the content of the page
print(soup.prettify())

#Get all the info from the section  id="topsum_section"
topsum_section = soup.find(id="topsum_section")
#Extract the text from the topsum_section
topsum_text = topsum_section.get_text(strip=True, separator=' ')
topsum_text



class KnowledgeCuratorAgent:
    def __init__(self):
        """Initialize the KnowledgeCuratorAgent."""
        self.client = openai_util.get_azure_openai_client()

    def curate_medical_page(self, page_text):
        """
        Summarizes a MedlinePlus (or similar) medical page for patients and extracts essential links.
        """
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
        return output_data


# Example usage of the KnowledgeCuratorAgent class
agent = KnowledgeCuratorAgent()
output = agent.curate_medical_page(cleaned_text)
#Now get output
output.get('summary', {})
output.get('related_links', [])