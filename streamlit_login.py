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

def get_user_permissions(conn, email: str) -> dict:
    query = text("""
        SELECT p.schema_name, MAX(p.permission) as max_permission
        FROM auth.users u
        JOIN auth.user_groups ug ON u.id = ug.user_id
        JOIN auth.group_schema_permissions p ON ug.group_id = p.group_id
        WHERE u.email = :email
        GROUP BY p.schema_name;
    """)
    result = conn.execute(query, {"email": email})
    # Vytvoří slovník, např. {'public': 'write', 'demo': 'read'}
    return {row[0]: row[1] for row in result}

# Zjednodušená funkce check_login, vrací True/False
def check_login(email: str, password: str, conn) -> bool:
    result = conn.execute(
        text("SELECT password_hash FROM auth.users WHERE email = :email"),
        {"email": email}
    ).fetchone()
    if not result:
        return False
    # [cite_start]Ověření hesla [cite: 39]
    return verify_password(password, result[0])

# --- UI ---
def login_form():
    st.subheader("Přihlášení")
    with st.form("login_form"):
        email = st.text_input("Email")
        password = st.text_input("Heslo", type="password")
        submitted = st.form_submit_button("Přihlásit")
        if submitted:
            with engine.begin() as conn:
                # [cite_start]Upravená logika po přihlášení [cite: 52-58]
                if check_login(email, password, conn):
                    st.session_state.logged_in = True
                    st.session_state.user_email = email
                    # Načteme a uložíme oprávnění do session state
                    st.session_state.permissions = get_user_permissions(conn, email)
                    st.success(f"Přihlášen jako {email}")
                    st.rerun()
                else:
                    st.error("Neplatné přihlašovací údaje")

def get_groups(conn):
    result = conn.execute(text("SELECT id, name FROM auth.groups ORDER BY name"))
    return {row[1]: row[0] for row in result} # Vrací dict {'název': id}

def register_form():
    st.subheader("Registrace")
    with st.form("register_form"):
        email = st.text_input("Email")
        password = st.text_input("Heslo", type="password")
        confirm = st.text_input("Potvrzení hesla", type="password")

        with engine.connect() as conn:
            groups_dict = get_groups(conn)
            # [cite_start]Nahrazení původního selectboxu [cite: 67]
            requested_group_name = st.selectbox("Požadovaná skupina", options=list(groups_dict.keys()))

        submitted = st.form_submit_button("Registrovat")
        if submitted:
            if password != confirm:
                st.error("Hesla se neshodují")
                return

            hashed = hash_password(password)
            requested_group_id = groups_dict.get(requested_group_name)

            try:
                with engine.begin() as conn:
                    # [cite_start]Aktualizovaný INSERT příkaz [cite: 79-82]
                    conn.execute(
                        text("""
                            INSERT INTO auth.users (email, password_hash, requested_group_id)
                            VALUES (:email, :hash, :requested_group_id)
                        """),
                        {"email": email, "hash": hashed, "requested_group_id": requested_group_id}
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

def request_group_form():
    st.subheader("Žádost o skupinu")

    engine = get_engine()

    with engine.connect() as conn:
        groups_dict = {}
        try:
            # Načteme seznam skupin pro selectbox
            result = conn.execute(
                text("SELECT id, name FROM auth.groups ORDER BY name")
            )
            groups_dict = {row.name: row.id for row in result}

            # Načteme aktuální stav žádosti včetně názvu skupiny
            current_req_row = conn.execute(
                text("""
                    SELECT g.name, u.requested_group_id
                    FROM auth.users u
                    LEFT JOIN auth.groups g ON u.requested_group_id = g.id
                    WHERE u.email = :email
                """),
                {"email": st.session_state.user_email}
            ).first()

            if current_req_row:
                current_req_name = current_req_row.name
                current_req_id = current_req_row.requested_group_id
            else:
                current_req_name = None
                current_req_id = None

        except Exception as e:
            st.error(f"Chyba při načítání dat: {e}")
            return

    # Zobrazení aktuálního stavu
    if current_req_id is None:
        st.caption("Aktuálně nemáš podanou žádost o skupinu.")
    else:
        st.caption(f"Aktuálně požádáno o skupinu: {current_req_name}")

    if not groups_dict:
        st.info("Nejsou dostupné žádné skupiny.")
        return

    # Formulář
    with st.form("request_group_form"):
        requested_group_name = st.selectbox(
            "Požadovaná skupina",
            options=list(groups_dict.keys())
        )
        submitted = st.form_submit_button("Odeslat žádost")

    if submitted:
        requested_group_id = groups_dict.get(requested_group_name)
        try:
            with engine.begin() as conn:
                conn.execute(
                    text("""
                        UPDATE auth.users
                        SET requested_group_id = :requested_group_id
                        WHERE email = :email
                    """),
                    {
                        "requested_group_id": requested_group_id,
                        "email": st.session_state.user_email
                    }
                )
            st.cache_data.clear()
            st.success(f"Žádost o skupinu „{requested_group_name}“ byla odeslána.")
            st.experimental_rerun()
        except Exception as e:
            st.error(f"Chyba při odesílání žádosti: {e}")

def logout():
    st.session_state.clear()
    st.rerun()

