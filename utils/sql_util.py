"""
Utility functions for SQL queries and database connections to AACT database.
"""


import os
from dotenv import load_dotenv
load_dotenv()

#File specific imports
import pandas as pd
import psycopg




def connect_to_aact():
    """Connect to AACT database using environment variables"""
    
    conn = psycopg.connect(
        dbname="aact",
        user=os.getenv('aact_username'),
        password=os.getenv('aact_password'),
        host="aact-db.ctti-clinicaltrials.org",
        port="5432"
    )
    return conn



def get_table(query):
    """
    Get table from AACT database using SQL query
    """
    
    conn = connect_to_aact()
    
    # Execute the SQL query and fetch the results into a DataFrame
    df = pd.read_sql(query, conn)
    
    # Close the connection
    conn.close()
    
    return df