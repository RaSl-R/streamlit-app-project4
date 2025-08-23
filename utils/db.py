import streamlit as st
from sqlalchemy import create_engine

# Připojovací údaje – ideálně časem dát do .env
DB_USER = "neondb_owner"
DB_PASSWORD = "npg_bqIR6D2UkALc"
DB_HOST = "ep-icy-moon-a2bfjmyb-pooler.eu-central-1.aws.neon.tech"
DB_NAME = "neondb"

@st.cache_resource
def get_engine():
    conn_str = f"postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}@{DB_HOST}/{DB_NAME}"
    return create_engine(conn_str, connect_args={"sslmode": "require"})

@st.cache_resource
def get_connection():
    return get_engine().connect()
