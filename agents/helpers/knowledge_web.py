"""
knowledge_web.py

This module provides helper functions for the Knowledge Curator Agent to retrieve and clean medical information
about conditions and drugs from trusted public sources.

Functions:
- get_condition_page(condition): Fetches and extracts simplified textual content about a medical condition from MedlinePlus by simulating a search and cleaning the resulting HTML page.
- get_drug_page(drug): Searches for a consumer-friendly drug label on DailyMed and extracts readable content from the label's page, removing navigation and extraneous elements.
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
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse, parse_qs 

#condition="Nash"
def get_condition_page(condition):
    #Search url
    url='https://vsearch.nlm.nih.gov/vivisimo/cgi-bin/query-meta?v%3Aproject=medlineplus&v%3Asources=medlineplus-bundle&query='+condition
    #Put headers in for a more realistic request
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3'
    }

    r=requests.get(url, headers=headers)
    #Get the content of the response
    content = r.content.decode('utf-8')

    #Extract ol class="results"

    soup = BeautifulSoup(content, 'html.parser')
    results = soup.find('ol', class_='results')
    #Extract the links from the results
    links = results.find_all('a', href=True)
    #Extract the href attributes from the links
    hrefs = [link['href'] for link in links]

    try:
        #Go to the first href
        first_href = hrefs[0]
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

        parsed_url = urlparse(first_href)
        query_params = parse_qs(parsed_url.query)
        url = query_params.get('url', [None])[0]


        #Now make a request to the first href
        r = requests.get(url, headers=headers)
        #Get the content of the response
        content = r.content.decode('utf-8')

        #Extract div id="mplus-content"
        soup = BeautifulSoup(content, 'html.parser')
        main_content = soup.find('div', id='mplus-content')

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
            text = elem.get_text(separator=" ",strip=True)
            if text:
                cleaned_text += f"{text}\n\n"
    except:
        cleaned_text='Issue pulling page data for condition'
    return cleaned_text

#Usage
"""
condition='Cancer'
cleaned_page_data=get_condition_page(condition)
cleaned_page_data
"""

def get_drug_page(drug):

    url='https://dailymed.nlm.nih.gov/dailymed/search.cfm?labeltype=all&query='+drug+'&audience=consumer'

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3'
    }

    r=requests.get(url, headers=headers)
    #Get the content of the response
    content = r.content.decode('utf-8')

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
            return 'No data for this drug',''
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
        text = elem.get_text(separator=" ",strip=True)
        if text:
            cleaned_text += f"{text}\n\n"

    return cleaned_text,url

"""
#Usage
drug="ibuprofen"
cleaned_page_data=get_drug_page(drug)
cleaned_page_data
"""