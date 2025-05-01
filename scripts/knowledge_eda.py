"""
knowledge_eda.py

This is a whiteboard script for testing and developing the KnowledgeCuratorAgent. 
It walks through the full flow of retrieving medical and drug content from trusted public sources 
(MedlinePlus and DailyMed), cleaning the data, and summarizing it using OpenAI function-calling APIs.
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
from utils import sql_util, openai_util
import json
from agents.agent_coordinator import AgentCoordinator

import requests

azure_model_name = "gpt-4o-mini"
azure_deployment = "gpt-4o-mini"

#For condition use the input disease of the user....

#For drug always use the first listed...
#Test interventions to check first...
drugs=sql_util.get_table('select * from interventions')
drugs
drugs1=drugs.drop_duplicates('nct_id').reset_index(drop=True)
drugs1[drugs1['name']=='placebo']




#Search medlinePlus for the condition
# Search DailyMed for the drug
drug="Resmetirom"
#https://dailymed.nlm.nih.gov/dailymed/search.cfm?labeltype=all&query=Guselkumab&audience=consumer
url='https://dailymed.nlm.nih.gov/dailymed/search.cfm?labeltype=all&query='+drug+'&audience=consumer'

#Search for the condition on MedlinePlus
condition="NASH"
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

from typing import Dict
def medical_markdown(curated_page: Dict) -> str:
    """Turn the structured curated medical page into friendly markdown with emojis."""
    summary = curated_page.get("summary", {})
    links = curated_page.get("related_links", [])

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

md_out=medical_markdown(output)
md_out
#Write to data 
from IPython.display import display
from IPython.display import Markdown

display(Markdown(md_out))



#Now about the drug thats being investigated...
#Search medlinePlus for the condition
# Search DailyMed for the drug
drug="Resmetirom"
drug="tylenol"
drug="totally not a drug"
#https://dailymed.nlm.nih.gov/dailymed/search.cfm?labeltype=all&query=Guselkumab&audience=consumer
url='https://dailymed.nlm.nih.gov/dailymed/search.cfm?labeltype=all&query='+drug+'&audience=consumer'


headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3'
}

r=requests.get(url, headers=headers)
#Get the content of the response
content = r.content.decode('utf-8')
content

#First check if there are any results
#Get result info
soup = BeautifulSoup(content, 'html.parser')

#First check if there are search results
results = soup.find('span', class_='count')
if results:
    num_results=int(results.text.replace("(",'').replace(')','').split(' ')[0])
    if num_results>0:
        #Go to the first link
        results=soup.find('a',class_='drug-info-link')
        #Get href
        new_url=results['href']
        url='https://dailymed.nlm.nih.gov'+new_url
        #Now get data from this url
        r=requests.get(url, headers=headers)
        #Get the content of the response
        content = r.content.decode('utf-8')
        soup = BeautifulSoup(content, 'html.parser')
    else:
        #No Data!
        print('No data for this drug...')
#If there are no results check if there is drug-information

results = soup.find('div', class_='drug-label-sections')
#Extract the links from the results
main_content = results

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

import tiktoken

def count_tokens(text: str, model: str = "gpt-4o-mini") -> int:
    """Returns the number of tokens in a string for a given model."""
    enc = tiktoken.encoding_for_model(azure_model_name)
    tokens = enc.encode(text)
    return len(tokens)

count_tokens(cleaned_text)

#Now pass this to LLM to generate the info ...

class KnowledgeCuratorAgent:
    def __init__(self):
        """Initialize the KnowledgeCuratorAgent."""
        self.client = openai_util.get_azure_openai_client()




    def generate_drug_markdown_from_trial_about(self,trial_about_text,drug_info_text,source_url):

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

        # Now decide what markdown to return
        md = []

        if decision.get("is_drug_study", False) and drug_info_text:
            # Normal drug info flow
            md.append(self.curate_drug_page(drug_info_text, source_url))
        else:
            # No drug is being studied
            md.append("## 💬 No Specific Drug Being Studied\n")
            reason = decision.get("reason_if_no_drug", "This study focuses on something other than testing a drug.")
            md.append(f"{reason}\n")
            if source_url:
                md.append(f"\n---\n\n🔗 [**See Study Details**]({source_url})")

        return "\n".join(md).strip()

    def curate_drug_page(self, page_text, source_url):
        """
        Summarizes a MedlinePlus (or similar) medical page for patients and extracts essential links.
        """
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



# Example usage of the KnowledgeCuratorAgent class
#Example usage of the AgentCoordinator class
coordinator = AgentCoordinator()
#First try synonym generation
condition="Nash"
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
output = agent.generate_drug_markdown_from_trial_about(study_data['about'],cleaned_text,url)
output
display(Markdown(output))