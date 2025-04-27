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


import os
import streamlit as st
import folium
from streamlit_folium import folium_static
import pandas as pd

from geopy.geocoders import Nominatim


try:
    from agents.agent_coordinator import AgentCoordinator
    
    # Initialize the coordinator once when the app starts
    @st.cache_resource
    def get_coordinator():
        return AgentCoordinator()

    # Set up the main app structure
    st.title("Clinical Trial Search")

    # Create search interface
    st.header("Find Clinical Trials")

    # Initialize session state
    if 'search_results' not in st.session_state:
        st.session_state.search_results = None
    if 'sites' not in st.session_state:
        st.session_state.sites = None
    if 'closest_trial_summary' not in st.session_state:
        st.session_state.closest_trial_summary = None

    # Create columns for the search inputs
    col1, col2 = st.columns(2)

    with col1:
        condition = st.text_input(
            "Medical Condition or Disease:",
            placeholder="e.g. Breast Cancer, Alzheimer's, Diabetes",
            help="Enter a medical condition, disease, or treatment you're interested in"
        )

    with col2:
        # Initialize the geolocator
        geolocator = Nominatim(user_agent="my_app")
        
        # Text input for location search
        location_input = st.text_input(
            "Your Location:",
            placeholder="e.g. Boston, MA or 10001",
            help="Enter your city, state, or zip code to find nearby trials"
        )
        
        if location_input:
            # Use geolocator to search for location, restricting results to US
            location_results = geolocator.geocode(location_input, exactly_one=False, country_codes='US')
            if location_results:
                # Get address options
                place_names = [result.address for result in location_results]
                
                # Allow the user to select a location from the list
                location = st.selectbox('Select a location:', place_names)
                
                # Optionally display the selected location
                # st.write(f'You selected: {location}')
            else:
                st.write("No matching US locations found.")
                location = location_input
        else:
            location = location_input
        
        # Add better help text for location
        st.caption("Enter a US city, state (e.g., 'Boston, MA')")

    # Search button
    search_clicked = st.button("Find Trials", key="search_button")
    
    if search_clicked:
        if condition and location:
            # Show spinner while processing
            with st.spinner("Searching for clinical trials..."):
                try:
                    # Initialize coordinator
                    coordinator = get_coordinator()
                    
                    # Get synonyms for the condition
                    synonyms = coordinator.get_synonyms(condition)
                    
                    # Find matching trials based on synonyms
                    matching_trials = coordinator.find_matching_trials_from_synonyms(synonyms)
                    
                    # If we have matching trials, find sites by location
                    if not matching_trials.empty:
                        try:
                            sites = coordinator.find_matching_trials_from_location(matching_trials, location)
                            st.session_state.sites = sites
                            
                            # Store the results
                            st.session_state.search_results = {
                                'condition': condition,
                                'location': location,
                                'synonyms': synonyms,
                                'trials': matching_trials
                            }
                            
                            # Get the trial explanation for the closest site
                            if not sites.empty:
                                with st.spinner("Generating trial summary..."):
                                    closest_site = sites.iloc[0]
                                    trial_summary = coordinator.get_trial_explanation(closest_site)
                                    st.session_state.closest_trial_summary = trial_summary
                        except ValueError as e:
                            if "Could not geocode the location" in str(e):
                                st.error(f"Location error: {str(e)}")
                                st.info("Try using a simpler format like 'City, State' or a ZIP/postal code.")
                            else:
                                st.error(f"An error occurred: {str(e)}")
                    else:
                        st.warning(f"No clinical trials found for {condition}. Try a different condition.")
                except Exception as e:
                    st.error(f"An error occurred: {str(e)}")
        else:
            st.warning("Please enter both a condition and location to search.")



    # Display the map section
    st.subheader("Closest Clinical Trial Location")


    # If we have search results, display the closest one on the map
    if st.session_state.sites is not None and not st.session_state.sites.empty:
        sites = st.session_state.sites
        
        # Get the closest trial site (first row after sorting by distance)
        closest_site = sites.iloc[0]
        
        # Check if the closest site has valid coordinates
        if pd.notna(closest_site['latitude']) and pd.notna(closest_site['longitude']):
            map_center = [closest_site['latitude'], closest_site['longitude']]
            
            # Zoom in
            zoom_level = 12  
                
            m = folium.Map(
                location=map_center, 
                zoom_start=zoom_level
            )
            
            # Create popup content for the closest site
            popup_html = f"""
            <div style="width: 300px">
                <h3>{closest_site.get('name', 'Clinical Trial Site')}</h3>
                <p>
                    <strong>Address:</strong> {closest_site.get('city', '')}, {closest_site.get('state', '')}, {closest_site.get('country', '')}<br>
                    <strong>Distance:</strong> {closest_site.get('distance', 0):.1f} miles<br>
                    <strong>Trial ID:</strong> {closest_site.get('nct_id', 'N/A')}
                </p>
            </div>
            """
            
            # Add marker for the closest site
            folium.Marker(
                [closest_site['latitude'], closest_site['longitude']],
                popup=folium.Popup(popup_html, max_width=300),
                tooltip=f"Closest Site: {closest_site.get('name', 'Clinical Trial Site')}"
            ).add_to(m)
            
            # Display the map
            folium_static(m)
            
            # Display info about the closest site
            st.success(f"The closest trial site is {closest_site.get('name', 'Unknown')} in {closest_site.get('city', '')}, {closest_site.get('state', '')} ({closest_site.get('distance', 0):.1f} miles away)")
            
            # Display trial summary if available
            if st.session_state.closest_trial_summary is not None:
                st.subheader("Closest Trial Summary")
                
                summary = st.session_state.closest_trial_summary
                
                # Create expanders for different sections of the summary
                with st.expander("About this study", expanded=True):
                    st.markdown(f"### {summary['title']['trial_name']}")
                    st.markdown(summary['about'])
                    st.markdown(f"[View on ClinicalTrials.gov]({summary['title']['trial_link']})")
                
                with st.expander("Who can join this study"):
                    st.markdown("#### Inclusion Criteria:")
                    for item in summary['who']['inclusion_criteria']:
                        st.markdown(f"- {item}")
                    
                    st.markdown("#### Exclusion Criteria:")
                    for item in summary['who']['exclusion_criteria']:
                        st.markdown(f"- {item}")
                
                with st.expander("What happens in this study"):
                    st.markdown(summary['what'])
                
                with st.expander("Contact Information"):
                    site_details = summary['contacts']['site_details']
                    contact_details = summary['contacts']['contact_details']
                    
                    st.markdown(f"**Site:** {site_details['site_name']}")
                    st.markdown(f"**Location:** {site_details['city']}, {site_details['state']} {site_details['zip']}")
                    
                    if contact_details.get('contact_name'):
                        st.markdown(f"**Contact:** {contact_details['contact_name']}")
                    if contact_details.get('contact_phone'):
                        st.markdown(f"**Phone:** {contact_details['contact_phone']}")
                    if contact_details.get('contact_email'):
                        st.markdown(f"**Email:** {contact_details['contact_email']}")
            
        else:
            st.warning("The closest trial site doesn't have valid location coordinates.")
            
            # Create a default map
            m = folium.Map(
                location=[39.8283, -98.5795],  # this is the center of the US
                zoom_start=4
            )
            folium_static(m)
        
        # Display table of trial sites
        st.subheader("Trial Sites")
        
        # Determine which columns are available in the dataframe
        display_columns = []
        rename_mapping = {}
        
        potential_columns = {
            'nct_id': 'Trial ID', 
            'name': 'Facility Name', 
            'city': 'City', 
            'state': 'State', 
            'country': 'Country', 
            'distance': 'Distance (miles)'
        }
        
        for col, new_name in potential_columns.items():
            if col in sites.columns:
                display_columns.append(col)
                rename_mapping[col] = new_name
        
        # Prepare data for display
        if display_columns:
            display_df = sites[display_columns].copy()
            if 'distance' in display_df.columns:
                display_df['distance'] = display_df['distance'].round(1)
            
            # Rename columns
            display_df = display_df.rename(columns=rename_mapping)
            
            # Display the table
            st.dataframe(
                display_df, 
                hide_index=True,
                use_container_width=True
            )
        else:
            st.info("No detailed trial site information available to display in table format.")
    else:
        # Create a default map (centered on United States)
        m = folium.Map(
            location=[39.8283, -98.5795],  # Center of the US
            zoom_start=4
        )
        
        # Display the map
        folium_static(m)
        
        if condition and location and st.session_state.sites is not None:
            st.info(f"No trial sites found for {condition} near {location}.")

    # Information about synonyms used in search
    if st.session_state.search_results is not None and 'synonyms' in st.session_state.search_results:
        with st.expander("Related terms used in search"):
            st.write(", ".join(st.session_state.search_results['synonyms']))
    
    # Information about the app
    st.markdown("""
    ### About this tool:
    This clinical trial search tool:
    1. Generates synonyms for your condition to find more relevant trials
    2. Searches for clinical trials using these terms
    3. Displays results sorted by distance from your location
    4. Provides patient-friendly summaries of clinical trials
    """)

except Exception as e:
    st.error(f"An error occurred: {str(e)}")
