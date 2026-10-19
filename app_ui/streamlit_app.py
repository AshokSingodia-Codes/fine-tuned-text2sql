"""Guarded Text-to-SQL Assistant - Streamlit Interactive UI."""

import json
import os
from pathlib import Path

import pandas as pd
import requests
import streamlit as st

st.set_page_config(
    page_title="Guarded Text-to-SQL Assistant",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded",
)

API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")

# Custom Styling
st.markdown(
    """
    <style>
    .main-header { font-size: 2.2rem; font-weight: 700; color: #1E293B; margin-bottom: 0.2rem; }
    .sub-header { font-size: 1.0rem; color: #64748B; margin-bottom: 1.5rem; }
    .stat-box { background-color: #F8FAFC; border: 1px solid #E2E8F0; border-radius: 8px; padding: 12px; text-align: center; }
    .verdict-allowed { background-color: #ECFDF5; border: 1px solid #10B981; color: #065F46; padding: 10px; border-radius: 6px; font-weight: 600; }
    .verdict-blocked { background-color: #FEF2F2; border: 1px solid #EF4444; color: #991B1B; padding: 10px; border-radius: 6px; font-weight: 600; }
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    '<div class="main-header">🛡️ Guarded Text-to-SQL Assistant</div>', unsafe_allow_html=True
)
st.markdown(
    '<div class="sub-header">Powered by Fine-Tuned Qwen2.5-Coder-3B (QLoRA) with Real-Time AST Safety & Read-Only Sandbox</div>',
    unsafe_allow_html=True,
)

# Sidebar Database Selection
st.sidebar.title("⚙️ Database & Settings")

try:
    resp_dbs = requests.get(f"{API_BASE_URL}/v1/databases", timeout=3)
    available_dbs = (
        [db["db_id"] for db in resp_dbs.json().get("databases", [])]
        if resp_dbs.status_code == 200
        else ["concert_singer", "student_assessment", "pets_1"]
    )
except Exception:
    available_dbs = ["concert_singer", "student_assessment", "pets_1"]

selected_db = st.sidebar.selectbox("Target Database", available_dbs, index=0)
include_samples = st.sidebar.checkbox("Include Sample Rows in Prompt", value=False)

# Tabs
tab_query, tab_schema, tab_redteam, tab_metrics = st.tabs(
    ["💬 Natural Query", "🗄️ Database Schema", "⚔️ Red-Team Attacks", "📊 Model Metrics"]
)

with tab_query:
    col_input, col_preset = st.columns([3, 1.2])

    with col_preset:
        st.markdown("**Example Questions:**")
        if st.button("🎤 Singers sorted by age"):
            st.session_state["user_question"] = (
                "How many singers are there and what is their average age?"
            )
        if st.button("🏆 Most frequent concert stadium"):
            st.session_state["user_question"] = "Which stadium has hosted the most concerts?"
        if st.button("🐱 Students with cat pets"):
            st.session_state["user_question"] = (
                "What are the first names of students who own a cat?"
            )

    with col_input:
        default_q = st.session_state.get("user_question", "How many singers are there in total?")
        user_q = st.text_area("Ask a question in plain English:", value=default_q, height=100)
        btn_generate = st.button(
            "🚀 Generate & Execute SQL", type="primary", use_container_width=True
        )

    if btn_generate and user_q:
        with st.spinner("Generating SQL and validating guardrails..."):
            try:
                payload = {
                    "db_id": selected_db,
                    "question": user_q,
                    "include_sample_rows": include_samples,
                }
                res = requests.post(f"{API_BASE_URL}/v1/query", json=payload, timeout=10)
                data = res.json()

                if res.status_code == 200:
                    st.subheader("Generated Query & Safety Verdict")
                    if data["allowed"]:
                        st.markdown(
                            '<div class="verdict-allowed">✅ Verdict: ALLOWED (Passed AST Safety Checks)</div>',
                            unsafe_allow_html=True,
                        )
                        st.code(data["sql"], language="sql")

                        if data.get("rows"):
                            st.subheader(f"Query Results ({data['row_count']} rows)")
                            df = pd.DataFrame(data["rows"], columns=data["columns"])
                            st.dataframe(df, use_container_width=True)
                        else:
                            st.info("Query returned no rows.")

                        # Latency breakdown
                        t = data.get("timings_ms", {})
                        st.caption(
                            f"⏱️ Timings — Total: {t.get('total_ms', 0)}ms | "
                            f"Inference: {t.get('inference_ms', 0)}ms | "
                            f"Validation: {t.get('validation_ms', 0)}ms | "
                            f"Execution: {t.get('execution_ms', 0)}ms"
                        )
                    else:
                        st.markdown(
                            '<div class="verdict-blocked">❌ Verdict: BLOCKED (Safety Guardrail Violation)</div>',
                            unsafe_allow_html=True,
                        )
                        st.code(data["sql"], language="sql")
                        st.error("Block Reasons:\n" + "\n".join(f"- {r}" for r in data["reasons"]))
                else:
                    st.error(f"API Error ({res.status_code}): {res.text}")
            except Exception as e:
                st.error(f"Failed to connect to API server: {e}")

with tab_schema:
    st.subheader(f"Schema Definition: {selected_db}")
    try:
        res_schema = requests.get(f"{API_BASE_URL}/v1/databases/{selected_db}/schema", timeout=3)
        if res_schema.status_code == 200:
            st.code(res_schema.json().get("schema_ddl", ""), language="sql")
        else:
            st.info("Schema view requires running API backend.")
    except Exception:
        st.info("Schema view requires running API backend.")

with tab_redteam:
    st.subheader("⚔️ Red-Team Safety Demonstration")
    st.write("Test malicious prompt injections and write attempts against the SQL guardrails:")

    col_a, col_b, col_c = st.columns(3)
    with col_a:
        if st.button("💣 DROP TABLE Attack"):
            val_res = requests.post(
                f"{API_BASE_URL}/v1/sql/validate", json={"sql": "DROP TABLE singer;"}
            ).json()
            st.warning(f"Blocked: {not val_res['allowed']}\nReasons: {val_res['reasons']}")
    with col_b:
        if st.button("🔑 Password Exfiltration"):
            val_res = requests.post(
                f"{API_BASE_URL}/v1/sql/validate", json={"sql": "SELECT name, password FROM users;"}
            ).json()
            st.warning(f"Blocked: {not val_res['allowed']}\nReasons: {val_res['reasons']}")
    with col_c:
        if st.button("⚡ Multi-Statement Trick"):
            val_res = requests.post(
                f"{API_BASE_URL}/v1/sql/validate", json={"sql": "SELECT 1; DELETE FROM songs;"}
            ).json()
            st.warning(f"Blocked: {not val_res['allowed']}\nReasons: {val_res['reasons']}")

with tab_metrics:
    st.subheader("📊 Model Performance & Quantization Summary")
    metrics_file = Path("reports/metrics_finetuned_C.json")
    if metrics_file.exists():
        with open(metrics_file, "r", encoding="utf-8") as f:
            m_data = json.load(f)
        col1, col2, col3 = st.columns(3)
        col1.metric(
            "Spider Execution Accuracy", f"{m_data['internal_eval']['exec_accuracy'] * 100:.1f}%"
        )
        col2.metric(
            "Valid SQL Output Rate", f"{m_data['internal_eval']['valid_sql_rate'] * 100:.1f}%"
        )
        col3.metric("Quantized Size (GGUF Q4_K_M)", "1.9 GB")
    else:
        st.info("Metrics report available at `reports/metrics_finetuned_C.json`.")
