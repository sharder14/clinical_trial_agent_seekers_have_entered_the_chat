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
"""

import streamlit as st
from geopy.geocoders import Nominatim
import pandas as pd
import numpy as np
import folium
from streamlit_folium import folium_static
import random
import string
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode
from agents.agent_coordinator import AgentCoordinator
from agents.helpers.session_utils import initialize_session_state, go_back_to_results, go_back_to_search


# Set page config for a cleaner look
st.set_page_config(
    page_title="Clinical Trial Agent Seekers Have Entered the Chat",
    layout="wide"
)

# Initialize the coordinator once when the app starts
@st.cache_resource
def get_coordinator():
    return AgentCoordinator()

# Initialize all session state variables
initialize_session_state()

def select_trial_site(site_idx):
    # Get the selected site from filtered sites
    site = st.session_state.filtered_sites.iloc[int(site_idx)]
    st.session_state.selected_trial_site = site
    
    # Generate trial details and drug info for the selected site
    coordinator = get_coordinator()
    trial_data, trial_md = coordinator.get_trial_explanation(site)
    drug_md = coordinator.get_drug_md(trial_data['about'])
    
    # Store in session state
    st.session_state.selected_trial_markdown = trial_md
    st.session_state.selected_drug_markdown = drug_md
    
    # Switch to trial details page
    st.session_state.page = 'trial_details'
    st.rerun()



# SEARCH PAGE
if st.session_state.page == 'search':
    st.title("Clinical Trial Agent Seekers Have Entered the Chat")
    st.write("Welcome to your personal clinical trial search tool!")
    st.write("Find clinical trials tailored to your medical condition and location.")
    
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

        with st.form("search_form", clear_on_submit=False):
            # Input: medical condition
            condition = st.text_input(
                "Medical Condition or Disease:",
                value=st.session_state.condition,
                placeholder="e.g. Breast Cancer, Alzheimer's, Diabetes"
            )

            # Input: location
            location = st.text_input(
                "Your Location:",
                value=st.session_state.location,
                placeholder="e.g. Boston, MA or 10001"
            )

            # Submit button (also triggered by hitting Enter)
            submitted = st.form_submit_button("Find Trials")

        if submitted:
            st.session_state.condition = condition
            st.session_state.location = location
            with st.spinner("🔍 Searching for clinical trials..."):
                try:
                    coordinator = get_coordinator()

                    # Fix location
                    try:
                        location = coordinator.fix_location(location)
                        st.session_state.location = location
                        st.info(f"Interpreted location as: **{location}**")
                    except Exception as e:
                        st.error(f"Location fixer failed: {str(e)}")
                        st.stop()

                    # Synonyms + Matching trials
                    synonyms = coordinator.get_synonyms(condition)
                    matching_trials = coordinator.find_matching_trials_from_synonyms(synonyms)

                    if not matching_trials.empty:
                        sites = coordinator.find_matching_trials_from_location_with_age_gender(
                            matching_trials, location, max_distance=st.session_state.get("max_distance", 250)
                        )

                        if sites.empty:
                            st.warning("No trials located in this area. Try searching in a different location.")
                            st.stop()

                        sites['min_age_val'] = sites['minimum_age'].apply(coordinator.parse_age_string).fillna(0)
                        sites['max_age_val'] = sites['maximum_age'].apply(coordinator.parse_age_string).fillna(120)
                        sites['phase'] = sites['phase'].fillna("N/A")
                        sites['phase'] = sites['phase'].replace({None: 'NA', 'N/A': 'NA'}).fillna('NA')

                        sites['age_groups'] = sites.apply(
                            lambda row: coordinator.determine_age_group(row['minimum_age'], row['maximum_age']),
                            axis=1
                        )

                        st.session_state.sites = sites
                        st.session_state.filtered_sites = sites.copy()
                        st.session_state.has_searched = True

                        st.session_state.search_results = {
                            'condition': condition,
                            'location': location,
                            'synonyms': synonyms,
                            'trials': matching_trials
                        }

                        # Remove spinner
                        condition_md = coordinator.get_condition_md(condition)
                        st.session_state.condition_markdown = condition_md

                        st.session_state.page = 'results'
                        st.rerun()
                    else:
                        st.warning(f"No clinical trials found for {condition}. Try a different condition.")
                except Exception as e:
                    st.error(f"An error occurred: {str(e)}")

# RESULTS PAGE
elif st.session_state.page == 'results':
    st.title("Clinical Trial Search Results")

    if st.button("← Back to Home"):
        go_back_to_search()
        st.rerun()

    # Check for URL parameters to handle trial selection
    params = st.query_params
    if 'selected_trial' in params:
        try:
            site_idx = int(params['selected_trial'][0])
            select_trial_site(site_idx)
        except (ValueError, IndexError, KeyError) as e:
            st.error(f"Error loading trial details: {str(e)}")


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
        
        # Create filter columns for a cleaner layout
        filter_col1, filter_col2, filter_col3 = st.columns(3)
        
        # Move the age group filter into the filter columns
        with filter_col1:
            # Phase filter - dropdown
            if 'phase' in sites.columns:
                # Get unique values and clean them
                phase_order = [
                    "EARLY_PHASE1", "PHASE1", "PHASE1/PHASE2", "PHASE2", 
                    "PHASE2/PHASE3", "PHASE3", "PHASE4", "NA"
                ]
                phases_in_data = sorted(set(sites['phase'].unique()), key=lambda x: phase_order.index(x) if x in phase_order else 999)

                
                selected_phase = st.selectbox(
                    "Phase:",
                    options=['All Phases'] + phases_in_data,
                    index=0,
                    help="Select trial phase to display",
                    key="phase_dropdown"
                )

            else:
                selected_phase = 'All Phases'

            age_groups = ["Any", "Child: 0-17", "Adult: 18-64", "Senior: 65+"]
            selected_age_group = st.selectbox(
                "Age Group:",
                options=age_groups,
                index=0, 
                help="Show trials that accept this age group",
                key="age_group_dropdown"
            )
                    
            # Store the selection in session state as a list for compatibility
            st.session_state.selected_age_groups = [selected_age_group]
                
        with filter_col2:
            # Gender filter - dropdown
            if 'gender' in sites.columns:
                genders = sites['gender'].dropna().unique().tolist()

                # Standardize case to avoid duplicate 'All'/'ALL'
                genders = [g.upper() for g in genders]

                # Insert 'ALL' at the top if not already present
                if 'ALL' not in genders:
                    genders.insert(0, 'ALL')

                selected_gender = st.selectbox(
                    "Sex:",
                    options=genders,
                    index=0,
                    help="Filter by participant sex eligibility",
                    key="gender_dropdown"
                )
            else:
                selected_gender = 'ALL'

                
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
            
            # Debug information
            starting_count = len(filtered_sites)
            
            # Apply distance filter
            if 'distance' in filtered_sites.columns:
                # Debug print to check distance values
                max_distance_value = filtered_sites['distance'].max()
                min_distance_value = filtered_sites['distance'].min()
                
                # Make sure distance is numeric
                filtered_sites['distance'] = pd.to_numeric(filtered_sites['distance'], errors='coerce')
                
                # Apply filter with explicit comparison
                filtered_sites = filtered_sites[filtered_sites['distance'] <= float(max_distance)]
                after_distance_count = len(filtered_sites)
            else:
                after_distance_count = starting_count
            
            # Apply age group filter
            if 'age_groups' in filtered_sites.columns:
                selected_groups = st.session_state.selected_age_groups
                
                # If "Any" is not selected, apply filter
                if "Any" not in selected_groups:
                    # Use a more lenient filter approach with explicit error handling
                    try:
                        # Check if the list contains the selected age groups
                        filtered_sites = filtered_sites[
                            filtered_sites['age_groups'].apply(
                                lambda groups: any(group in selected_groups for group in groups) if isinstance(groups, list) else False
                            )
                        ]
                    except Exception as e:
                        st.error(f"Error in age group filtering: {e}")
                
                after_age_count = len(filtered_sites)
            else:
                after_age_count = after_distance_count
            
            # Apply phase filter - handle None values properly
            if selected_phase != 'All Phases' and 'phase' in filtered_sites.columns:
                filtered_sites = filtered_sites[
                    (filtered_sites['phase'] == selected_phase)
                ]
                after_phase_count = len(filtered_sites)
            else:
                after_phase_count = after_age_count
            
            # Apply study type filter - handle None values properly
            if selected_study_type != 'All Types' and 'study_type' in filtered_sites.columns:
                filtered_sites = filtered_sites[
                    (filtered_sites['study_type'] == selected_study_type) | 
                    ((filtered_sites['study_type'].isna()) & (selected_study_type == 'None'))
                ]
                after_study_type_count = len(filtered_sites)
            else:
                after_study_type_count = after_phase_count
            
            # Apply gender filter - handle None values properly
            if selected_gender != 'ALL' and 'gender' in filtered_sites.columns:
                filtered_sites = filtered_sites[
                    (filtered_sites['gender'] == selected_gender) | 
                    ((filtered_sites['gender'].isna()) & (selected_gender == 'None'))
                ]
                after_gender_count = len(filtered_sites)
            else:
                after_gender_count = after_study_type_count
            
            # Apply recruitment status filter - handle None values properly
            if selected_status != 'All Statuses' and 'overall_status' in filtered_sites.columns:
                filtered_sites = filtered_sites[
                    (filtered_sites['overall_status'] == selected_status) | 
                    ((filtered_sites['overall_status'].isna()) & (selected_status == 'None'))
                ]
                after_status_count = len(filtered_sites)
            else:
                after_status_count = after_gender_count
            
            # Store filtered sites
            st.session_state.filtered_sites = filtered_sites
            
            # Display filter results with debugging info
            num_results = len(filtered_sites)
            if num_results > 0:
                st.success(f"Found {min(num_results, 100)} trial site{'' if min(num_results, 100) == 1 else 's'} matching your filters.")
            else:
                st.warning(f"No trials match your current filters. Try adjusting your criteria. Filter counts: Start: {starting_count}, After distance: {after_distance_count}, After age: {after_age_count}, After phase: {after_phase_count}, After type: {after_study_type_count}, After gender: {after_gender_count}, After status: {after_status_count}")
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
            
            # Limit to top 100 sites
            display_sites = filtered_sites.head(100).copy()
            
            # Get the closest trial site (first row after sorting by distance)
            closest_site = display_sites.iloc[0]
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
                
                # Get user location coordinates using geopy
                geolocator = Nominatim(user_agent="clinical_trial_finder", timeout=10)
                try:
                    location_geo = geolocator.geocode(st.session_state.location, exactly_one=True, country_codes='US')
                    if location_geo:
                        user_lat = location_geo.latitude
                        user_lon = location_geo.longitude
                    else:
                        user_lat = None
                        user_lon = None
                except:
                    user_lat = None
                    user_lon = None


                # Create map
                m = folium.Map(
                    location=map_center, 
                    zoom_start=zoom_level,
                    control_scale=False,
                    zoom_control=False,
                    dragging=False,
                    scrollWheelZoom=False,
                    touchZoom=False   
                )


                # Add a red marker for the user's location
                if user_lat is not None and user_lon is not None:
                    folium.Marker(
                        [user_lat, user_lon],
                        popup="Your Location",
                        icon=folium.Icon(color="red", icon="home")
                    ).add_to(m)


                # all sites within this range of the closest site will be green
                epsilon = 0.01  # 0.01 miles = about 50 feet
                
                # Add all filtered sites to the map (limit to first 100 for performance)
                for idx, site in display_sites.iterrows():
                    if pd.notna(site['latitude']) and pd.notna(site['longitude']):
                        # Calculate distance safely
                        distance_value = float(site['distance']) if 'distance' in site and pd.notna(site['distance']) else 0.0
                        
                        # Determine if this is one of the closest sites
                        is_closest = abs(distance_value - min_distance) < epsilon
                        marker_color = 'green' if is_closest else 'blue'
                        marker_icon = folium.Icon(color=marker_color, icon='plus' if is_closest else 'info-sign')
                        
                        # Convert age groups to friendly display
                        age_groups_str = ", ".join(site['age_groups']) if 'age_groups' in site else "Any"
                        
                        # Create a special onClick handler (WIP)
                        popup_html = f"""
                        <div style="width: 300px">
                            <h3>{site['name'] if 'name' in site and pd.notna(site['name']) else 'Clinical Trial Site'}</h3>
                            <p>
                                <strong>Address:</strong> {site['city'] if 'city' in site and pd.notna(site['city']) else ''}, {site['state'] if 'state' in site and pd.notna(site['state']) else ''}<br>
                                <strong>Distance:</strong> {distance_value:.1f} miles<br>
                                <strong>Trial ID:</strong> {site['nct_id'] if 'nct_id' in site and pd.notna(site['nct_id']) else 'N/A'}<br>
                                <strong>Age Groups:</strong> {age_groups_str}<br>
                                <strong>Status:</strong> {site['overall_status'] if 'overall_status' in site and pd.notna(site['overall_status']) else 'Unknown'}<br>
                                <strong>Phase:</strong> {site['phase'] if 'phase' in site and pd.notna(site['phase']) else 'N/A'}
                            </p>
                            {"<strong>✓ This is one of the closest trial sites</strong>" if is_closest else ""}
                            <p>
                                <a href="?selected_trial=X" target="_parent">
                                    <button style="...">View Trial Details</button>
                                </a>
                                    View Trial Details
                                </button>
                            </p>
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
                # Render the map on the page
                folium_static(m, width=None, height=500)
                
                # Add the legend to the map
                m.get_root().html.add_child(folium.Element(legend_html))
                
                # Display clickable table of filtered trial sites
                st.subheader("All Trial Sites")
                
                # Determine which columns are available in the dataframe
                display_columns = []
                rename_mapping = {}
                
                potential_columns = {
                    'nct_id': 'nct_id', 
                    'name': 'Facility Name', 
                    'city': 'City', 
                    'state': 'State',
                    'distance': 'Distance (miles)',
                    'age_range': 'Age Eligibility',
                    'phase': 'Phase',
                    'overall_status': 'Status',
                    'study_type': 'Study Type',
                    'gender': 'Sex Eligibility'
                }
                
                for col, new_name in potential_columns.items():
                    if col in filtered_sites.columns:
                        display_columns.append(col)
                        rename_mapping[col] = new_name
                
                # Add the age_groups column for display
                if 'age_groups' in filtered_sites.columns:
                    display_columns.append('age_groups')
                    rename_mapping['age_groups'] = 'Age Groups'
                
                # Prepare data for display
                if display_columns:
                    display_df = filtered_sites[display_columns].copy()
                    if 'distance' in display_df.columns:
                        display_df['distance'] = display_df['distance'].round(1)
                    
                    # Convert age_groups list to string for display
                    if 'age_groups' in display_df.columns:
                        display_df['age_groups'] = display_df['age_groups'].apply(lambda x: ", ".join(x))
                    
                    # Rename columns
                    display_df = display_df.rename(columns=rename_mapping)
                    
                    # Create two columns for table and buttons
                    table_col, button_col = st.columns([3, 1])
                    
                    with table_col:
                        st.write("### Click a row to view trial details")

                        # Reset index and ensure nct_id is included for selection
                        display_df = filtered_sites.copy().reset_index(drop=True)

                        # Convert lists to strings for display (like age_groups)
                        if 'age_groups' in display_df.columns:
                            display_df['age_groups'] = display_df['age_groups'].apply(lambda x: ", ".join(x) if isinstance(x, list) else x)

                        # Build GridOptions
                        gb = GridOptionsBuilder.from_dataframe(display_df)
                        gb.configure_selection(selection_mode='single', use_checkbox=True)

                        # Optionally hide internal columns (e.g., nct_id, latitude, longitude)
                        gb.configure_column('nct_id', hide=True)
                        if 'latitude' in display_df.columns:
                            gb.configure_column('latitude', hide=True)
                        if 'longitude' in display_df.columns:
                            gb.configure_column('longitude', hide=True)

                        grid_options = gb.build()

                        # Show the AgGrid interactive table
                        grid_response = AgGrid(
                            display_df,
                            gridOptions=grid_options,
                            update_mode=GridUpdateMode.SELECTION_CHANGED,
                            height=400,
                            use_container_width=True,
                            key="aggrid_trials"
                        )

                        # Get selected row
                        selected = grid_response['selected_rows']
                        if selected is not None and len(selected) > 0 and 'nct_id' in selected.columns:
                            selected_nct_id = selected.iloc[0]['nct_id']
                            selected_trial = filtered_sites[filtered_sites['nct_id'] == selected_nct_id].iloc[0]

                            # Load trial details
                            st.session_state.selected_trial_site = selected_trial
                            coordinator = get_coordinator()
                            trial_data, trial_md = coordinator.get_trial_explanation(selected_trial)
                            drug_md = coordinator.get_drug_md(trial_data['about'])

                            st.session_state.selected_trial_markdown = trial_md
                            st.session_state.selected_drug_markdown = drug_md
                            st.session_state.page = 'trial_details'
                            st.rerun()




                else:
                    st.info("No detailed trial site information available to display in table format.")

                # Display condition information below the columns
                st.header("About the Condition")
                if 'condition_markdown' in st.session_state and st.session_state.condition_markdown:
                    st.markdown(st.session_state.condition_markdown)
                else:
                    st.warning("Condition information is not available.")
                
                # Create two columns for map and trial details
                map_col, details_col = st.columns([1, 1])


# TRIAL DETAILS PAGE
elif st.session_state.page == 'trial_details':
    # First ensure we have the necessary data

    if (st.session_state.selected_trial_site is not None and 
        st.session_state.selected_trial_markdown is not None):

        # Back button to return to results
        if st.button("← Back to Search Results"):
            go_back_to_results()
            st.rerun()
        

        # Show map zoomed on the selected trial site
        site = st.session_state.selected_trial_site

        if pd.notna(site['latitude']) and pd.notna(site['longitude']):
            m = folium.Map(
                location=[site['latitude'], site['longitude']],
                zoom_start=13,  # Zoom in closer to the site
                control_scale=False,
                zoom_control=False,
                dragging=False,
                scrollWheelZoom=False,
                touchZoom=False,
                double_click_zoom=False
            )

            popup_html = f"""
            <strong>{site.get('name', 'Trial Site')}</strong><br>
            {site.get('city', '')}, {site.get('state', '')}<br>
            {site.get('nct_id', '')}
            """

            folium.Marker(
                [site['latitude'], site['longitude']],
                popup=popup_html,
                icon=folium.Icon(color="blue", icon="plus")
            ).add_to(m)

            folium_static(m, width=None, height=400)

                
        site = st.session_state.selected_trial_site
        
        # Get site name (with fallback)
        site_name = site['name'] if 'name' in site and pd.notna(site['name']) else 'Clinical Trial Site'
        
        # Page title
        st.title(f"Trial Details: {site_name}")
        
        # Create tabs for different types of information
        trial_tab, drug_tab, location_tab = st.tabs(["Trial Information", "Medication Details", "Location Details"])
        
        with trial_tab:
            # Display the trial markdown
            st.markdown(st.session_state.selected_trial_markdown)
            
            # Add a direct link to the clinical trials gov page
            if 'nct_id' in site and pd.notna(site['nct_id']):
                st.markdown(f"[View full study details on ClinicalTrials.gov](https://clinicaltrials.gov/study/{site['nct_id']})")
        
        with drug_tab:
            # Display drug information if available
            if st.session_state.selected_drug_markdown:
                st.markdown(st.session_state.selected_drug_markdown)
            else:
                st.info("No specific medication information is available for this trial.")
        
        with location_tab:
            st.subheader("Site Location")
            location_info = []
            if 'name' in site and pd.notna(site['name']):
                location_info.append(f"**Facility:** {site['name']}")

            address_parts = []
            for field in ['city', 'state', 'zip']:
                if field in site and pd.notna(site[field]):
                    address_parts.append(site[field])

            if address_parts:
                location_info.append(f"**Address:** {', '.join(address_parts)}")

            if 'distance' in site and pd.notna(site['distance']):
                location_info.append(f"**Distance:** {site['distance']:.1f} miles")

            if location_info:
                for info in location_info:
                    st.markdown(info)
            else:
                st.info("No detailed location information available.")

    
    else:
        st.error("Sorry, there was a problem loading the trial details.")
        if st.button("Return to Search Results"):
            go_back_to_results()
            st.rerun()