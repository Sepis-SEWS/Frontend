"""SEWS application entrypoint: streamlit run app.py."""
import streamlit as st

from components.layout import render_shell
from config import Settings
from services.api_client import ApiGateway
from services.demo import DemoGateway
from state import initialize

st.set_page_config(page_title="SEWS · ICU 조기 경보", page_icon="✚", layout="wide")
initialize(st.session_state)
try:
    settings = Settings.from_env()
except ValueError as exc:
    st.error(f"설정 오류: {exc}")
    st.stop()
st.session_state.settings = settings
if "gateway" not in st.session_state or st.session_state.get("gateway_settings") != settings:
    st.session_state.gateway = DemoGateway() if settings.mode == "demo" else ApiGateway(settings)
    st.session_state.gateway_settings = settings
    st.session_state.read_results.clear()
    st.session_state.read_errors.clear()
pages = {"monitor": st.Page("views/monitor.py", title="통합 모니터", default=True, url_path="monitor"),
         "detail": st.Page("views/patient_detail.py", title="환자 상세", url_path="patient"),
         "alerts": st.Page("views/alerts.py", title="경보 이력", url_path="alerts")}
page = st.navigation(list(pages.values()), position="hidden")
render_shell(st.session_state.gateway, settings.mode == "demo", pages)
if "notice" in st.session_state:
    st.success(st.session_state.pop("notice"))
page.run()
