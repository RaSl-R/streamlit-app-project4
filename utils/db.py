import streamlit as st
from sqlalchemy import create_engine

# Připojovací údaje – ideálně časem dát do .env
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_HOST = os.getenv("DB_HOST")
DB_NAME = os.getenv("DB_NAME")

@st.cache_resource
def get_engine():
    conn_str = f"postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}@{DB_HOST}/{DB_NAME}"
    return create_engine(conn_str, connect_args={"sslmode": "require"})

@st.cache_resource
def get_connection():
    return get_engine().connect()
