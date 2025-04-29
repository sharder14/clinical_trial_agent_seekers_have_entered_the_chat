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


import streamlit as st

# Set page config for a cleaner look
st.set_page_config(
    page_title="Clinical Trial Agent Seekers Have Entered the Chat",
    layout="wide"
)

import os
import folium
from streamlit_folium import folium_static
import pandas as pd
import numpy as np
from geopy.geocoders import Nominatim


try:
    from agents.agent_coordinator import AgentCoordinator
    
    # Initialize the coordinator once when the app starts
    @st.cache_resource
    def get_coordinator():
        return AgentCoordinator()

    # Initialize session state variables
    if 'page' not in st.session_state:
        st.session_state.page = 'search'  # Initial page is search
    if 'search_results' not in st.session_state:
        st.session_state.search_results = None
    if 'sites' not in st.session_state:
        st.session_state.sites = None
    if 'filtered_sites' not in st.session_state:
        st.session_state.filtered_sites = None
    if 'closest_trial_markdown' not in st.session_state:
        st.session_state.closest_trial_markdown = None
    if 'condition_markdown' not in st.session_state:
        st.session_state.condition_markdown = None
    if 'drug_markdown' not in st.session_state:
        st.session_state.drug_markdown = None
    if 'has_searched' not in st.session_state:
        st.session_state.has_searched = False
    if 'max_distance' not in st.session_state:
        st.session_state.max_distance = 250
    if 'condition' not in st.session_state:
        st.session_state.condition = ""
    if 'location' not in st.session_state:
        st.session_state.location = ""

    # Function to handle back button click
    def go_back_to_search():
        st.session_state.page = 'search'
        st.session_state.has_searched = False

    # SEARCH PAGE
    if st.session_state.page == 'search':
        st.title("Clinical Trial Agent Seekers have Entered the Chat")
        st.write("Welcome to the Clinical Trial Search Tool!")
        st.write("Find clinical trials based on your medical condition and location.")
        st.write("Please enter the medical condition and location to find relevant clinical trials.")
        st.write("")
        
        # Create a container for centered content
        container = st.container()
        
        # Add some vertical space before the search form
        st.write("")
        st.write("")
        st.write("")
        
        # Create a centered column layout
        col1, col2, col3 = st.columns([1, 2, 1])
        
        with col2:
            st.header("Find Clinical Trials")
            
            # Medical condition input
            condition = st.text_input(
                "Medical Condition or Disease:",
                value=st.session_state.condition,
                placeholder="e.g. Breast Cancer, Alzheimer's, Diabetes",
                help="Enter a medical condition, disease, or treatment you're interested in"
            )
            
            # Location input
            # Initialize the geolocator
            geolocator = Nominatim(user_agent="my_app")

            # Initialize location suggestions in session state if they don't exist
            if 'location_suggestions' not in st.session_state:
                st.session_state.location_suggestions = []
            if 'last_typed_location' not in st.session_state:
                st.session_state.last_typed_location = ""

            # Function to handle location input changes
            def on_location_change():
                location_input = st.session_state.location_input_field
                if location_input and location_input != st.session_state.last_typed_location:
                    st.session_state.last_typed_location = location_input
                    try:
                        # Use geolocator to search for location, restricting results to US
                        location_results = geolocator.geocode(location_input, exactly_one=False, country_codes='US')
                        if location_results:
                            # Get address options and store in session state
                            st.session_state.location_suggestions = [result.address for result in location_results[:5]]
                        else:
                            st.session_state.location_suggestions = []
                    except Exception as e:
                        st.session_state.location_suggestions = []

            # Location text input with key and on_change callback
            location = st.text_input(
                "Your Location:",
                value=st.session_state.location,
                placeholder="e.g. Boston, MA or 10001",
                help="Enter your city, state, or zip code to find nearby trials",
                key="location_input_field",
                on_change=on_location_change
            )
            
            # Display suggestions as a dropdown-style interface
            if st.session_state.location_suggestions:
                st.write("Select from suggestions:")
                for i, suggestion in enumerate(st.session_state.location_suggestions):
                    if st.button(suggestion, key=f"loc_button_{i}"):
                        # When suggestion is clicked, update location
                        st.session_state.location = suggestion
                        location = suggestion
            


            # Add better help text for location
            st.caption("Enter a US city, state (e.g., 'Boston, MA')")
            
            # Center the search button
            col_a, col_b, col_c = st.columns([1, 1, 1])
            with col_b:
                search_clicked = st.button("Find Trials", key="search_button", use_container_width=True)
            
            # Trigger search only when the "Find Trials" button is clicked
            if search_clicked:
                if location and condition:
                    if st.session_state.location_input_field != st.session_state.location or st.session_state.condition != condition:
                        search_clicked = True

            if search_clicked:
                if condition and location:
                    # Store inputs in session state
                    st.session_state.condition = condition
                    st.session_state.location = location
                    
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
                                    
                                    # Process age information to enable numeric filtering
                                    if 'minimum_age' in sites.columns:
                                        # Extract numeric values from age strings
                                        sites['min_age_val'] = sites['minimum_age'].apply(lambda x: 
                                            0 if pd.isna(x) or x == 'N/A' or not x else
                                            int(x.split()[0]) if x.split()[0].isdigit() else 0
                                        )
                                        
                                        # Convert units to years (approximate)
                                        sites['min_age_unit'] = sites['minimum_age'].apply(lambda x: 
                                            'Years' if pd.isna(x) or not x else
                                            x.split()[1] if len(x.split()) > 1 else 'Years'
                                        )
                                        
                                        # Convert Days/Months to fraction of years
                                        sites.loc[sites['min_age_unit'] == 'Days', 'min_age_val'] = sites.loc[sites['min_age_unit'] == 'Days', 'min_age_val'] / 365
                                        sites.loc[sites['min_age_unit'] == 'Months', 'min_age_val'] = sites.loc[sites['min_age_unit'] == 'Months', 'min_age_val'] / 12
                                    else:
                                        sites['min_age_val'] = 0
                                        sites['minimum_age'] = 'Not specified'
                                        
                                    if 'maximum_age' in sites.columns:
                                        # Extract numeric values from age strings
                                        sites['max_age_val'] = sites['maximum_age'].apply(lambda x: 
                                            120 if pd.isna(x) or x == 'N/A' or not x else
                                            int(x.split()[0]) if x.split()[0].isdigit() else 120
                                        )
                                        
                                        # Convert units to years (approximate)
                                        sites['max_age_unit'] = sites['maximum_age'].apply(lambda x: 
                                            'Years' if pd.isna(x) or not x else
                                            x.split()[1] if len(x.split()) > 1 else 'Years'
                                        )
                                        
                                        # Convert Days/Months to fraction of years
                                        sites.loc[sites['max_age_unit'] == 'Days', 'max_age_val'] = sites.loc[sites['max_age_unit'] == 'Days', 'max_age_val'] / 365
                                        sites.loc[sites['max_age_unit'] == 'Months', 'max_age_val'] = sites.loc[sites['max_age_unit'] == 'Months', 'max_age_val'] / 12
                                    else:
                                        sites['max_age_val'] = 120
                                        sites['maximum_age'] = 'Not specified'
                                    
                                    st.session_state.sites = sites
                                    st.session_state.filtered_sites = sites.copy()
                                    st.session_state.has_searched = True
                                    
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
                                            # Properly unpack the tuple returned by get_trial_explanation
                                            trial_data, trial_md = coordinator.get_trial_explanation(closest_site)
                                            st.session_state.closest_trial_summary = trial_data
                                            st.session_state.closest_trial_markdown = trial_md
                                            
                                            # Fetch knowledge resources about the condition and drugs
                                            with st.spinner("Gathering educational resources..."):
                                                condition_md, drug_md = coordinator.get_knowledge_resources(condition, trial_data['about'])
                                                st.session_state.condition_markdown = condition_md
                                                st.session_state.drug_markdown = drug_md
                                    
                                    # Switch to results page
                                    st.session_state.page = 'results'
                                    st.rerun()
                                    
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

    # RESULTS PAGE
    elif st.session_state.page == 'results':
        st.title("Clinical Trial Search Results")
        
        # Display filter interface after search completes
        if st.session_state.has_searched and st.session_state.sites is not None and not st.session_state.sites.empty:
            st.header("Filter Trials")
            
            # Get the original sites dataframe
            sites = st.session_state.sites
            
            # Add distance slider first (most important filter)
            if 'distance' in sites.columns:
                # Get the maximum distance from the data (or cap at 250 miles)
                max_dist = min(sites['distance'].max() + 10, 250)
                
                # Distance slider
                max_distance = st.slider(
                    "Maximum Distance (miles):",
                    min_value=0,
                    max_value=int(max_dist),
                    value=int(max_dist),
                    help="Show trials within this distance from your location"
                )
                st.session_state.max_distance = max_distance
            else:
                max_distance = st.session_state.max_distance
                
            # Add age range slider for filtering by age
            if ('min_age_val' in sites.columns) and ('max_age_val' in sites.columns):
                # Get min and max age values from the data
                min_possible_age = 0  # Always start at 0
                max_possible_age = int(sites['max_age_val'].max())
                
                # Add some buffer to the max age
                max_possible_age = min(120, max_possible_age + 5)  # Cap at 120 years
                
                # Default selected values
                default_min = min_possible_age
                default_max = max_possible_age
                
                st.subheader("Filter by Age")
                age_range = st.slider(
                    "Age Range (years):",
                    min_value=float(min_possible_age),
                    max_value=float(max_possible_age),
                    value=(float(default_min), float(default_max)),
                    step=1.0,
                    help="Show trials that accept participants in this age range"
                )
                
                # Store selected age range in session state
                st.session_state.selected_min_age = age_range[0]
                st.session_state.selected_max_age = age_range[1]
            else:
                # Set default values if age columns don't exist
                st.session_state.selected_min_age = 0
                st.session_state.selected_max_age = 120
            
            # Standardize N/A values in the phase column
            if 'phase' in sites.columns:
                # Replace various forms of N/A with a standardized "N/A" string
                sites['phase'] = sites['phase'].fillna('N/A')
                sites['phase'] = sites['phase'].replace(['', 'NA', 'N/A'], 'N/A')
                
            # Create filter columns for a cleaner layout
            filter_col1, filter_col2, filter_col3 = st.columns(3)
            
            with filter_col1:
                # Phase filter - dropdown
                if 'phase' in sites.columns:
                    # Get unique values and clean them
                    phases = sites['phase'].unique().tolist()
                    
                    # Sort phases - put N/A last, otherwise numerical order
                    phases = sorted([p for p in phases if p != 'N/A']) + ['N/A'] 
                    
                    selected_phase = st.selectbox(
                        "Phase:",
                        options=['All Phases'] + phases,
                        index=0,
                        help="Select trial phase to display",
                        key="phase_dropdown"
                    )
                else:
                    selected_phase = 'All Phases'
                    
            with filter_col2:
                # Gender filter - dropdown
                if 'gender' in sites.columns:
                    genders = sites['gender'].unique().tolist()
                    selected_gender = st.selectbox(
                        "Sex:",
                        options=['All'] + genders,
                        index=0,
                        help="Filter by participant sex eligibility",
                        key="gender_dropdown"
                    )
                else:
                    selected_gender = 'All'
                
            with filter_col3:
                # Recruitment status filter - dropdown
                if 'overall_status' in sites.columns:
                    statuses = sites['overall_status'].unique().tolist()
                    selected_status = st.selectbox(
                        "Recruitment Status:",
                        options=['All Statuses'] + statuses,
                        index=0,
                        help="Select recruitment status to display",
                        key="status_dropdown"
                    )
                else:
                    selected_status = 'All Statuses'
                
                # Study type filter - dropdown
                if 'study_type' in sites.columns:
                    study_types = sites['study_type'].unique().tolist()
                    selected_study_type = st.selectbox(
                        "Study Type:",
                        options=['All Types'] + study_types,
                        index=0,
                        help="Select study type to display",
                        key="study_type_dropdown"
                    )
                else:
                    selected_study_type = 'All Types'
                
                # Add filter button for a cleaner experience
                filter_clicked = st.button("Apply Filters", key="filter_button")
            
            # Apply filters when button is clicked or when first loading
            if filter_clicked or st.session_state.filtered_sites is None:
                # Start with all sites
                filtered_sites = sites.copy()
                
                # Apply distance filter (highest priority)
                if 'distance' in filtered_sites.columns:
                    filtered_sites = filtered_sites[filtered_sites['distance'] <= max_distance]
                
                # Apply age filters using numeric values
                if 'min_age_val' in filtered_sites.columns and 'max_age_val' in filtered_sites.columns:
                    selected_min_age = st.session_state.selected_min_age
                    selected_max_age = st.session_state.selected_max_age
                    
                    # A trial is eligible if:
                    # 1. The trial's maximum age is >= the selected minimum age AND
                    # 2. The trial's minimum age is <= the selected maximum age
                    filtered_sites = filtered_sites[
                        (filtered_sites['max_age_val'] >= selected_min_age) & 
                        (filtered_sites['min_age_val'] <= selected_max_age)
                    ]
                
                # Apply phase filter
                if selected_phase != 'All Phases' and 'phase' in filtered_sites.columns:
                    filtered_sites = filtered_sites[filtered_sites['phase'] == selected_phase]
                    
                # Apply study type filter
                if selected_study_type != 'All Types' and 'study_type' in filtered_sites.columns:
                    filtered_sites = filtered_sites[filtered_sites['study_type'] == selected_study_type]
                    
                # Apply gender filter
                if selected_gender != 'All' and 'gender' in filtered_sites.columns:
                    filtered_sites = filtered_sites[filtered_sites['gender'] == selected_gender]
                    
                # Apply recruitment status filter
                if selected_status != 'All Statuses' and 'overall_status' in filtered_sites.columns:
                    filtered_sites = filtered_sites[filtered_sites['overall_status'] == selected_status]
                
                # Store filtered sites
                st.session_state.filtered_sites = filtered_sites
                
                # Update trial summary based on the filtered sites
                if not filtered_sites.empty:
                    with st.spinner("Updating trial summary..."):
                        # Get the closest site from filtered results
                        closest_filtered_site = filtered_sites.iloc[0]
                        # Generate new markdown for the closest site after filtering
                        coordinator = get_coordinator()
                        trial_data, new_trial_md = coordinator.get_trial_explanation(closest_filtered_site)
                        st.session_state.closest_trial_summary = trial_data
                        st.session_state.closest_trial_markdown = new_trial_md
                        
                        # Refresh knowledge resources based on the new closest trial
                        condition_md, drug_md = coordinator.get_knowledge_resources(st.session_state.condition, trial_data['about'])
                        st.session_state.condition_markdown = condition_md
                        st.session_state.drug_markdown = drug_md
                
                # Display filter results
                num_results = len(filtered_sites)
                if num_results > 0:
                    st.success(f"Found {num_results} trial site{'' if num_results == 1 else 's'} matching your filters.")
                else:
                    st.warning("No trials match your current filters. Try adjusting your criteria.")
            else:
                filtered_sites = st.session_state.filtered_sites

            # Display the map section with filtered sites
            st.header("Clinical Trial Locations")

            # If we have filtered search results, display them on the map
            if st.session_state.filtered_sites is not None and not st.session_state.filtered_sites.empty:
                filtered_sites = st.session_state.filtered_sites
                
                # Sort filtered sites by distance to ensure closest is first
                if 'distance' in filtered_sites.columns:
                    filtered_sites = filtered_sites.sort_values('distance')
                
                # Get the closest trial site (first row after sorting by distance)
                closest_site = filtered_sites.iloc[0]
                min_distance = closest_site['distance'] if 'distance' in closest_site else 0
                
                # Check if the closest site has valid coordinates
                if pd.notna(closest_site['latitude']) and pd.notna(closest_site['longitude']):
                    # Center the map on the closest result
                    map_center = [closest_site['latitude'], closest_site['longitude']]
                    
                    # Determine zoom level based on max distance
                    if max_distance <= 10:
                        zoom_level = 12
                    elif max_distance <= 50:
                        zoom_level = 10
                    elif max_distance <= 100:
                        zoom_level = 9
                    else:
                        zoom_level = 8
                    
                    # Create map
                    m = folium.Map(
                        location=map_center, 
                        zoom_start=zoom_level
                    )
                    
                    # Define a small epsilon for comparing floating point distances
                    # Sites with distance within epsilon of min_distance will be green
                    epsilon = 0.01  # 0.01 miles = about 50 feet
                    
                    # Add all filtered sites to the map (limit to first 100 for performance)
                    for idx, site in filtered_sites.head(100).iterrows():
                        if pd.notna(site['latitude']) and pd.notna(site['longitude']):
                            # Calculate distance safely
                            distance_value = float(site['distance']) if 'distance' in site and pd.notna(site['distance']) else 0.0
                            
                            # Determine if this is one of the closest sites
                            # Mark as closest if within epsilon of minimum distance
                            is_closest = abs(distance_value - min_distance) < epsilon
                            marker_color = 'green' if is_closest else 'blue'
                            marker_icon = folium.Icon(color=marker_color, icon='plus' if is_closest else 'info-sign')
                            
                            # Create popup content with age information
                            age_range = ""
                            if 'minimum_age' in site and 'maximum_age' in site:
                                min_age = site['minimum_age'] if pd.notna(site['minimum_age']) else "Not specified"
                                max_age = site['maximum_age'] if pd.notna(site['maximum_age']) else "Not specified"
                                age_range = f"<strong>Age Range:</strong> {min_age} to {max_age}<br>"
                            
                            popup_html = f"""
                            <div style="width: 300px">
                                <h3>{site['name'] if 'name' in site and pd.notna(site['name']) else 'Clinical Trial Site'}</h3>
                                <p>
                                    <strong>Address:</strong> {site['city'] if 'city' in site and pd.notna(site['city']) else ''}, {site['state'] if 'state' in site and pd.notna(site['state']) else ''}<br>
                                    <strong>Distance:</strong> {distance_value:.1f} miles<br>
                                    <strong>Trial ID:</strong> {site['nct_id'] if 'nct_id' in site and pd.notna(site['nct_id']) else 'N/A'}<br>
                                    {age_range}
                                    <strong>Status:</strong> {site['overall_status'] if 'overall_status' in site and pd.notna(site['overall_status']) else 'Unknown'}<br>
                                    <strong>Phase:</strong> {site['phase'] if 'phase' in site and pd.notna(site['phase']) else 'N/A'}
                                </p>
                                {"<strong>✓ This is one of the closest trial sites</strong>" if is_closest else ""}
                            </div>
                            """
                            
                            # Add marker with custom icon
                            folium.Marker(
                                [site['latitude'], site['longitude']],
                                popup=folium.Popup(popup_html, max_width=300),
                                tooltip=f"{'CLOSEST: ' if is_closest else ''}{site['name'] if 'name' in site and pd.notna(site['name']) else 'Site'} ({distance_value:.1f} mi)",
                                icon=marker_icon
                            ).add_to(m)
                    
                    # Add a legend to the map
                    legend_html = '''
                    <div style="position: fixed; 
                        bottom: 50px; left: 50px; width: 200px; height: 100px; 
                        border:2px solid grey; z-index:9999; font-size:14px;
                        background-color:white; padding: 10px;
                        border-radius: 5px;">
                        <p><i class="fa fa-map-marker fa-2x" style="color:green"></i> Closest Trial Sites</p>
                        <p><i class="fa fa-map-marker fa-2x" style="color:blue"></i> Other Trial Sites</p>
                    </div>
                    '''
                    
                    # Add the legend to the map
                    m.get_root().html.add_child(folium.Element(legend_html))
                    
                    # Display the map
                    folium_static(m)
                    
                    # Display info about the closest site
                    site_name = closest_site['name'] if 'name' in closest_site and pd.notna(closest_site['name']) else 'Unknown'
                    site_city = closest_site['city'] if 'city' in closest_site and pd.notna(closest_site['city']) else ''
                    site_state = closest_site['state'] if 'state' in closest_site and pd.notna(closest_site['state']) else ''
                    site_distance = closest_site['distance'] if 'distance' in closest_site and pd.notna(closest_site['distance']) else 0
                    
                    # Format distance safely
                    try:
                        distance_str = f"{float(site_distance):.1f}"
                    except (ValueError, TypeError):
                        distance_str = "0.0"
                        
                    st.success(f"The closest trial site is {site_name} in {site_city}, {site_state} ({distance_str} miles away)")
                    
                    # Display age range for the closest site if available
                    if 'minimum_age' in closest_site and 'maximum_age' in closest_site:
                        min_age = closest_site['minimum_age'] if pd.notna(closest_site['minimum_age']) else "Not specified"
                        max_age = closest_site['maximum_age'] if pd.notna(closest_site['maximum_age']) else "Not specified"
                        st.info(f"Age eligibility range: {min_age} to {max_age}")
                    
                    # Count total sites
                    total_sites = len(filtered_sites)
                    st.info(f"Showing {min(100, total_sites)} of {total_sites} sites within {max_distance} miles")
                    
                    # Display trial details and educational content
                    closest_trial_data = st.session_state.closest_trial_summary
                    
                    # Create tabs for different types of information
                    trial_tab, condition_tab, drug_tab = st.tabs(["Trial Details", "About the Condition", "Medication Information"])
                    
                    with trial_tab:
                        # Display trial summary if available
                        if 'closest_trial_markdown' in st.session_state and st.session_state.closest_trial_markdown:
                            st.markdown(st.session_state.closest_trial_markdown)
                        else:
                            st.warning("Trial details are not available.")
                            
                    with condition_tab:
                        # Display condition information if available
                        if 'condition_markdown' in st.session_state and st.session_state.condition_markdown:
                            st.markdown(st.session_state.condition_markdown)
                        else:
                            st.warning("Condition information is not available.")
                            
                    with drug_tab:
                        # Display drug information if available
                        if 'drug_markdown' in st.session_state and st.session_state.drug_markdown:
                            st.markdown(st.session_state.drug_markdown)
                        else:
                            st.info("No specific medication information is available for this trial.")
                    
                else:
                    st.warning("The closest trial site doesn't have valid location coordinates.")
                    
                    # Create a default map
                    m = folium.Map(
                        location=[39.8283, -98.5795],  # this is the center of the US
                        zoom_start=4
                    )
                    folium_static(m)
                
                # Display table of filtered trial sites
                st.subheader("Trial Sites")
                
                # Determine which columns are available in the dataframe
                display_columns = []
                rename_mapping = {}
                
                potential_columns = {
                    'nct_id': 'Trial ID', 
                    'name': 'Facility Name', 
                    'city': 'City', 
                    'state': 'State', 
                    'distance': 'Distance (miles)',
                    'phase': 'Phase',
                    'overall_status': 'Status',
                    'study_type': 'Study Type',
                    'minimum_age': 'Min Age',
                    'maximum_age': 'Max Age'
                }
                
                for col, new_name in potential_columns.items():
                    if col in filtered_sites.columns:
                        display_columns.append(col)
                        rename_mapping[col] = new_name
                
                # Prepare data for display
                if display_columns:
                    display_df = filtered_sites[display_columns].copy()
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
                
                st.info("No trial sites match your search and filters. Try adjusting your criteria.")

            # Information about synonyms used in search
            if st.session_state.search_results is not None and 'synonyms' in st.session_state.search_results:
                with st.expander("Related terms used in search"):
                    st.write(", ".join(st.session_state.search_results['synonyms']))
            
            # Back button in the bottom right
            col1, col2, col3 = st.columns([1, 1, 1])
            with col3:
                st.button("← Back to Search", on_click=go_back_to_search, key="back_button")
                
        else:
            st.warning("No search results to display. Please go back and search again.")
            # Back button when no results
            st.button("← Back to Search", on_click=go_back_to_search, key="back_button_no_results")
            
        # Information about the app (only shown when there are results)
        if st.session_state.has_searched and st.session_state.sites is not None and not st.session_state.sites.empty:
            with st.expander("About this tool"):
                st.markdown("""
                This clinical trial search tool:
                1. Generates synonyms for your condition to find more relevant trials
                2. Searches for clinical trials using these terms
                3. Displays results sorted by distance from your location
                4. Provides patient-friendly summaries of clinical trials
                5. Offers educational resources about medical conditions and treatments
                6. Allows filtering by distance, age, phase, study type, sex, and more
                """)

except Exception as e:
    st.error(f"An error occurred: {str(e)}")