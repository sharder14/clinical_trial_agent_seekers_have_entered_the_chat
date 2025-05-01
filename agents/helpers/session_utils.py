"""
session_utils.py

Session state management and navigation helpers for the Streamlit clinical trial search app.

Functions:
- initialize_session_state(): Initializes all session state keys with default values used throughout the app.
- go_back_to_search(): Resets the view to the search page and clears search status.
- go_back_to_results(): Switches the current view to the results page without modifying state data.

This module helps maintain application state across user interactions and page transitions.
"""


import streamlit as st

def initialize_session_state():
    defaults = {
        'page': 'search',
        'search_results': None,
        'sites': None,
        'filtered_sites': None,
        'condition_markdown': None,
        'has_searched': False,
        'max_distance': 250,
        'condition': '',
        'location': '',
        'selected_trial_site': None,
        'selected_trial_markdown': None,
        'selected_drug_markdown': None,
        'selected_age_groups': ["Any"],
        'location_suggestions': [],
        'last_typed_location': '',
    }

    for key, value in defaults.items():
        st.session_state.setdefault(key, value)

# Helper functions
def go_back_to_search():
    st.session_state.page = 'search'
    st.session_state.has_searched = False

def go_back_to_results():
    st.session_state.page = 'results'