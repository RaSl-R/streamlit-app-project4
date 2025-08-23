import streamlit as st
import pandas as pd
from sqlalchemy import text
from passlib.context import CryptContext
from utils.db import get_engine

engine = get_engine()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# --- Helpers ---
def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def check_login(email: str, password: str, conn) -> str | None:
    result = conn.execute(
        text("SELECT password_hash, role FROM auth.users WHERE email = :email"),
        {"email": email}
    ).fetchone()
    if not result:
        return None
    stored_hash, role = result
    if verify_password(password, stored_hash):
        return role
    return None

# --- UI ---
def login_form():
    st.subheader("Přihlášení")
    with st.form("login_form"):
        email = st.text_input("Email")
        password = st.text_input("Heslo", type="password")
        submitted = st.form_submit_button("Přihlásit")

    if submitted:
        with engine.begin() as conn:
            role = check_login(email, password, conn)
        if role:
            st.session_state.logged_in = True
            st.session_state.user_email = email
            st.session_state.user_role = role
            st.success(f"Přihlášen jako {email} ({role})")
            st.rerun()
        else:
            st.error("Neplatné přihlašovací údaje")

def register_form():
    st.subheader("Registrace")
    with st.form("register_form"):
        email = st.text_input("Email")
        password = st.text_input("Heslo", type="password")
        confirm = st.text_input("Potvrzení hesla", type="password")
        requested_role = st.selectbox("Požadovaná role", ["viewer", "editor", "admin"])
        submitted = st.form_submit_button("Registrovat")

    if submitted:
        if password != confirm:
            st.error("Hesla se neshodují")
            return
        hashed = hash_password(password)
        try:
            with engine.begin() as conn:
                conn.execute(
                    text("""
                        INSERT INTO auth.users (email, password_hash, role, requested_role) 
                        VALUES (:email, :hash, 'viewer', :requested_role)
                    """),
                    {"email": email, "hash": hashed, "requested_role": requested_role}
                )
            st.success("Registrace proběhla úspěšně, nyní se přihlaste.")
        except Exception as e:
            st.error(f"Chyba: {e}")

def change_password_form():
    st.subheader("Změna hesla")
    with st.form("change_password_form"):
        old_password = st.text_input("Staré heslo", type="password")
        new_password = st.text_input("Nové heslo", type="password")
        confirm = st.text_input("Potvrzení nového hesla", type="password")
        submitted = st.form_submit_button("Změnit heslo")

    if submitted:
        if new_password != confirm:
            st.error("Nová hesla se neshodují")
            return
        with engine.begin() as conn:
            role = check_login(st.session_state.user_email, old_password, conn)
            if not role:
                st.error("Staré heslo není správné")
                return
            hashed = hash_password(new_password)
            conn.execute(
                text("UPDATE auth.users SET password_hash = :hash WHERE email = :email"),
                {"hash": hashed, "email": st.session_state.user_email}
            )
        st.success("Heslo bylo změněno")

def logout():
    st.session_state.clear()
    st.rerun()

