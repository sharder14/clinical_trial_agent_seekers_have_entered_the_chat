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