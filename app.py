"""
Streamlit app for the front end of the clinical trial search tool with dropdown filtering,
distance slider, properly highlighted closest trials, and knowledge hub.
"""

import os
import streamlit as st
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

    # Set up the main app structure
    st.title("Clinical Trial Search")

    # Create search interface
    st.header("Find Clinical Trials")

    # Initialize session state
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
        st.session_state.max_distance = 250  # Default maximum distance

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
                phases = sorted([p for p in phases if p != 'N/A']) + ['N/A']  # Put N/A at the end
                
                selected_phase = st.selectbox(
                    "Phase:",
                    options=['All Phases'] + phases,
                    index=0,
                    help="Select trial phase to display"
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
                    help="Filter by participant sex eligibility"
                )
            else:
                selected_gender = 'All'
            
            # Study type filter - dropdown
            if 'study_type' in sites.columns:
                study_types = sites['study_type'].unique().tolist()
                selected_study_type = st.selectbox(
                    "Study Type:",
                    options=['All Types'] + study_types,
                    index=0,
                    help="Select study type to display"
                )
            else:
                selected_study_type = 'All Types'
                
        with filter_col3:
            # Recruitment status filter - dropdown
            if 'overall_status' in sites.columns:
                statuses = sites['overall_status'].unique().tolist()
                selected_status = st.selectbox(
                    "Recruitment Status:",
                    options=['All Statuses'] + statuses,
                    index=0,
                    help="Select recruitment status to display"
                )
            else:
                selected_status = 'All Statuses'
            
            # Add filter button for a cleaner experience
            filter_clicked = st.button("Apply Filters", key="filter_button")
        
        # Apply filters when button is clicked or when first loading
        if filter_clicked or st.session_state.filtered_sites is None:
            # Start with all sites
            filtered_sites = sites.copy()
            
            # Apply distance filter (highest priority)
            if 'distance' in filtered_sites.columns:
                filtered_sites = filtered_sites[filtered_sites['distance'] <= max_distance]
            
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
                    condition_md, drug_md = coordinator.get_knowledge_resources(condition, trial_data['about'])
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
    if st.session_state.has_searched and st.session_state.filtered_sites is not None and not st.session_state.filtered_sites.empty:
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
                    
                    # Create popup content
                    popup_html = f"""
                    <div style="width: 300px">
                        <h3>{site['name'] if 'name' in site and pd.notna(site['name']) else 'Clinical Trial Site'}</h3>
                        <p>
                            <strong>Address:</strong> {site['city'] if 'city' in site and pd.notna(site['city']) else ''}, {site['state'] if 'state' in site and pd.notna(site['state']) else ''}<br>
                            <strong>Distance:</strong> {distance_value:.1f} miles<br>
                            <strong>Trial ID:</strong> {site['nct_id'] if 'nct_id' in site and pd.notna(site['nct_id']) else 'N/A'}<br>
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
            'study_type': 'Study Type'
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
        
        if st.session_state.has_searched and st.session_state.sites is not None:
            st.info("No trial sites match your search and filters. Try adjusting your criteria.")

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
    5. Offers educational resources about medical conditions and treatments
    6. Allows filtering by distance, phase, study type, sex, and more
    """)

except Exception as e:
    st.error(f"An error occurred: {str(e)}")