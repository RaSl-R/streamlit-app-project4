import streamlit as st
from streamlit_login import login_form, register_form, change_password_form, logout
from streamlit_data_browser import main_data_browser

st.set_page_config(layout="wide", page_title="Moje Streamlit app")

def main():
    st.title("Databázová aplikace")

    if "logged_in" not in st.session_state:
        st.session_state.logged_in = False


    if st.session_state.logged_in:
        st.sidebar.success(f"  {st.session_state.user_email} ({st.session_state.user_role})")
        if st.sidebar.button("Odhlásit"):
            logout()

        # Přidáme expander do postranního panelu
        with st.sidebar.expander("🔑 Změnit heslo"):
            change_password_form() # <-- Formulář se nyní vykreslí zde

        # podle role – pro jednoduchost všem dáme data browser
        if st.session_state.user_role in ["viewer", "editor", "admin"]:
            main_data_browser()
        else:
            st.error("Neznámá role")
    else:
        page = st.radio("Vyber akci", ["Přihlášení", "Registrace"])
        if page == "Přihlášení":
            login_form()
        else:
            register_form()

if __name__ == "__main__":
    main()

