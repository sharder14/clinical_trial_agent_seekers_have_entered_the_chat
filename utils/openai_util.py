"""
Utility functions for Azure OpenAI API interactions.
"""

import os
import sys
from dotenv import load_dotenv
load_dotenv()

#File specific imports
from openai import AzureOpenAI
import json

endpoint = os.getenv('azure_openai_endpoint')
subscription_key = os.getenv('azure_openai_key')
api_version = "2024-12-01-preview"


def get_azure_openai_client():
    """
    Get Azure OpenAI client with specified model and deployment.
    """
    # Create the Azure OpenAI client
    client = AzureOpenAI(
        api_version=api_version,
        azure_endpoint=endpoint,
        api_key=subscription_key,
    )

    return client