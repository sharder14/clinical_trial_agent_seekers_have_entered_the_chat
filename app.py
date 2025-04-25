"""
Streamlit app for the front end of the clinical trial search tool.

1. Search page where user can input a disease name and location.
2. Display results
    - Top of the page filters for phase, age, and recruitment status etc...
    - Main part of the page shows map with sites/trial asssiated
    - Bottom of page shows table with trials and their simple details
    - Trials are clickable to get more details either from pop up in map or from 
        table below
3. Study details page where user can see all the details of a specific trial
    Example of ctgov full study details page:
    https://clinicaltrials.gov/study/NCT05500222

    - What the trial is actually studying
    - Who can participate (eligibility criteria)
    - What participating would involve
    - The potential benefits and risks

    - ALso include contact information for the study team and a link to the full study page on clinicaltrials.gov

4. Within Study Details we want a tab for knowledge hub 
       this will show all of the links and then below a section
       that we will output LLM generated summaries of the links


"""


# app.py
import streamlit as st
from agents.agent_coordinator import AgentCoordinator
from ui.search_view import render_search_view
from ui.results_view import render_results_view
from ui.detail_view import render_trial_detail
from ui.knowledge_view import render_knowledge_hub

# Initialize the coordinator once when the app starts
@st.cache_resource
def get_coordinator():
    return AgentCoordinator()

coordinator = get_coordinator()

# Set up the main app structure
st.title("Clinical Trial Agent Seekers Have Entered The Chat")

# Create tabs for different views
tab1, tab2, tab3 = st.tabs(["Find Trials", "Trial Details", "Knowledge Hub"])

# Session state to track the current view and data
if 'view' not in st.session_state:
    st.session_state.view = 'search'
if 'search_results' not in st.session_state:
    st.session_state.search_results = None
if 'selected_trial' not in st.session_state:
    st.session_state.selected_trial = None

# Tab 1: Search and Results
with tab1:
    # If we're in search mode or have no results yet
    if st.session_state.view == 'search' or st.session_state.search_results is None:
        condition, location = render_search_view()
        
        if st.button("Find Trials"):
            # Use the coordinator to process the search
            with st.spinner("Our agents are searching for trials..."):
                results = coordinator.process_search_request(condition, location)
                st.session_state.search_results = results
                st.session_state.view = 'results'
                st.experimental_rerun()
    
    # If we have results, show them
    elif st.session_state.view == 'results':
        # Get any filter selections from the UI
        filters = render_results_view(st.session_state.search_results)
        
        # If filters change, update results
        if filters and st.button("Apply Filters"):
            with st.spinner("Updating results..."):
                filtered_results = coordinator.apply_filters(
                    st.session_state.search_results['trials'], 
                    filters
                )
                st.session_state.search_results['trials'] = filtered_results
                st.experimental_rerun()
        
        # Handle trial selection
        if 'selected_trial_id' in st.session_state and st.session_state.selected_trial_id:
            st.session_state.selected_trial = st.session_state.selected_trial_id
            st.session_state.view = 'detail'
            # Switch to the details tab
            st.experimental_set_query_params(tab='Trial Details')
            st.experimental_rerun()

# Tab 2: Trial Detail
with tab2:
    if st.session_state.selected_trial:
        # Get the explanation from the coordinator
        trial_explanation = coordinator.get_trial_explanation(st.session_state.selected_trial)
        
        # Render the detail view
        render_trial_detail(trial_explanation)
        
        if st.button("Back to Results"):
            st.session_state.view = 'results'
            st.session_state.selected_trial = None
            st.experimental_set_query_params(tab='Find Trials')
            st.experimental_rerun()

# Tab 3: Knowledge Hub
with tab3:
    if 'search_results' in st.session_state and st.session_state.search_results:
        # Get knowledge resources from the coordinator
        knowledge = coordinator.get_knowledge_resources(
            st.session_state.search_results['condition'],
            st.session_state.search_results['synonyms']
        )
        
        # Render the knowledge hub
        render_knowledge_hub(knowledge)
    else:
        st.info("Search for a condition first to see relevant resources")