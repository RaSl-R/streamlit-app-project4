import streamlit as st
from streamlit_login import login_form, register_form, change_password_form, request_group_form, logout
from streamlit_data_browser import main_data_browser

st.set_page_config(layout="wide", page_title="RaSl Data browser")

def main():
    if "logged_in" not in st.session_state:
        st.session_state.logged_in = False

    if st.session_state.logged_in:
        st.sidebar.success(f"Přihlášen: {st.session_state.user_email}")

        if st.sidebar.button("Odhlásit"):
            logout()

        with st.sidebar.expander("🔑 Změnit heslo"):
            change_password_form()

        with st.sidebar.expander("🧭 Žádost o skupinu"):
            request_group_form()

        main_data_browser()

    else:
        page = st.radio("Vyber akci", ["Přihlášení", "Registrace"])
        if page == "Přihlášení":
            login_form()
        else:
            register_form()

if __name__ == "__main__":
    main()
