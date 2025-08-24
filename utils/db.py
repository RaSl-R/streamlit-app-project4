import streamlit as st
import psycopg2
from sqlalchemy import create_engine

conn = psycopg2.connect(
    host=st.secrets["database"]["host"],
    port=st.secrets["database"]["port"],
    user=st.secrets["database"]["user"],
    password=st.secrets["database"]["password"],
    database=st.secrets["database"]["database"]
)

@st.cache_resource
def get_engine():
    conn_str = f"postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}@{DB_HOST}/{DB_NAME}"
    return create_engine(conn_str, connect_args={"sslmode": "require"})

@st.cache_resource
def get_connection():
    return get_engine().connect()
