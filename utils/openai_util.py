"""
Utility functions for Azure OpenAI API interactions.
"""

import os
import sys
from dotenv import load_dotenv
load_dotenv()

#File specific imports
from openai import AzureOpenAI, OpenAI
import json
from azure.ai.inference import ChatCompletionsClient
from azure.ai.inference.models import SystemMessage, UserMessage
from azure.core.credentials import AzureKeyCredential


azure_endpoint = os.getenv('azure_openai_endpoint')
azure_subscription_key = os.getenv('azure_openai_key')
azure_api_version = "2024-12-01-preview"

github_endpoint = os.getenv('github_endpoint')
github_ai_token = os.getenv('github_ai_token')


def get_azure_openai_client():
    # Create the Azure OpenAI client
    client = AzureOpenAI(
        api_version=azure_api_version,
        azure_endpoint=azure_endpoint,
        api_key=azure_subscription_key,
    )

    return client



#Example usage of the client
'''
client = get_azure_openai_client()
'''
