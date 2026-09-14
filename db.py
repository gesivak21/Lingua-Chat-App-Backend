import os
import psycopg
from dotenv import load_dotenv
load_dotenv()

DATABASE_URL = os.environ.get("DATABASE_URL")

def get_connection():
    if DATABASE_URL:
        return psycopg.connect(DATABASE_URL)
    db_user = os.environ.get("DB_USER") 
    db_password = os.environ.get("DB_PASSWORD") 
    db_name = os.environ.get("DB_NAME") 
    instance_connection_name = os.environ.get("INSTANCE_CONNECTION_NAME") 
    return psycopg.connect(dbname=db_name, 
                           user=db_user, 
                           password=db_password, 
                           host=f"/cloudsql/{instance_connection_name}")