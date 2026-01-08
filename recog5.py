import streamlit as st
from google import genai
import json
import io
import zipfile
import re
# -------------------- Utility Functions --------------------
def init_state():
    defaults = {
        "phase": "collect",
        "user_text": "",
        "line_range": "",
        "uploaded_files": [],
        "planning_response": None,
        "planning_answers": {},
        "design_response": None,
        "design_answers": {},
        "generated_code": None,
        "project_files": {},
    }
    for k, v in defaults.items():
        st.session_state.setdefault(k, v)
def clean_json_text(raw: str) -> str:
    """Cleans Gemini output to make it JSON-compatible."""
    if not raw:
        return raw
    raw = raw.strip()
    raw = re.sub(r"^```(?:json)?", "", raw, flags=re.IGNORECASE | re.MULTILINE)
    raw = re.sub(r"```$", "", raw.strip(), flags=re.MULTILINE)
    if raw.lower().startswith("json"):
        raw = raw[4:].lstrip("\n\r ")
    raw = raw.replace('\\"', '"')
    raw = re.sub(r",\s*([\]}])", r"\1", raw)
    return raw.strip()

def parse_gemini_json(raw_text: str):
    """Try parsing Gemini JSON, retry after cleaning."""
    raw_text = raw_text.strip()
    if not raw_text:
        raise ValueError("Empty Gemini response")
    try:
        return json.loads(raw_text)
    except json.JSONDecodeError:
        cleaned = clean_json_text(raw_text)
        return json.loads(cleaned)

def zip_project(files_dict):
    path = "generated_project.zip"
    with zipfile.ZipFile(path, "w") as zf:
        for name, content in files_dict.items():
            if isinstance(content, str):
                zf.writestr(name, content)
            else:
                zf.writestr(name, content)
    return path

# -------------------- Streamlit App --------------------
st.set_page_config(page_title="🧠 Streamlit Project Maker", layout="wide")
st.title("🧠 Streamlit Project Maker — Gemini Advanced Edition")

init_state()

# Sidebar
with st.sidebar:
    st.header("🔑 Gemini API Setup")
    api_key = st.text_input("Enter your Gemini API key", type="password")
    st.caption("Uses legacy-compatible API like recog3.py")
    st.divider()
    st.write("**Phases:** Collect → Planning → Designing → Finalize → Generate")

if not api_key:
    st.warning("⚠️ Enter Gemini API key to continue.")
    st.stop()

client = genai.Client(api_key=api_key)

col1, col2 = st.columns([1, 2])

# -------------------- Left: Inputs --------------------
with col1:
    st.subheader("1️⃣ Project Inputs")
    st.session_state.user_text = st.text_area(
        "Describe your project idea:", st.session_state.user_text, height=200
    )
    st.session_state.line_range = st.text_input(
        "Enter desired number of code lines range (e.g. 80–120):",
        st.session_state.line_range,
    )

    uploaded = st.file_uploader(
        "Upload related files (optional):",
        accept_multiple_files=True,
        type=["png", "jpg", "jpeg", "pdf", "py", "txt", "md"],
    )
    if uploaded:
        st.session_state.uploaded_files = [
            {"name": f.name, "type": f.type, "bytes": f.read()} for f in uploaded
        ]

    if st.session_state.uploaded_files:
        st.markdown("**Files uploaded:**")
        for f in st.session_state.uploaded_files:
            st.write(f"- {f['name']} ({f['type']})")

    st.divider()
    if st.session_state.phase == "collect":
        if st.button("➡️ Start Planning Phase"):
            st.session_state.phase = "planning"
            st.rerun()
    else:
        if st.button("⏪ Reset Project"):
            for k in list(st.session_state.keys()):
                del st.session_state[k]
            init_state()
            st.rerun()

# -------------------- Right: Phases --------------------
with col2:
    st.info(f"**Current Phase:** {st.session_state.phase.upper()}")

    # -------- PLANNING PHASE --------
    if st.session_state.phase == "planning":
        st.subheader("📘 Planning Phase")

        if not st.session_state.planning_response:
            planning_prompt = f"""
You are an expert AI project planner.

User wants to create a Streamlit project with the following idea:
{st.session_state.user_text}

The code should roughly stay within {st.session_state.line_range} lines.

TASK:
1. Produce a structured project plan (brief and actionable).
2. Generate 10–15 multiple-choice questions (multi-select allowed) 
   to clarify planning and add new useful features the user might like.
3. Suggest 1 short additional text input for user notes.

Return STRICT JSON in this format:
{{
  "plan_text": "Project plan summary...",
  "questions": [
    {{
      "id": 1,
      "question": "Question text",
      "options": ["Option A","Option B","Option C","Option D"]
    }}
  ],
  "additional_prompt": "Extra notes question"
}}
Return ONLY valid JSON. No markdown or ``` fences.
"""
            with st.spinner("🧠 Gemini is preparing your planning questions..."):
                try:
                    resp = client.models.generate_content(
                        model="gemini-2.5-flash",
                        contents=[planning_prompt],
                    )
                    raw_text = getattr(resp, "text", "").strip()
                    parsed = parse_gemini_json(raw_text)
                    st.session_state.planning_response = parsed
                    st.rerun()
                except Exception as e:
                    st.error(f"⚠️ Gemini returned invalid JSON or error: {e}")
                    st.stop()

        else:
            data = st.session_state.planning_response
            st.markdown("### 🧭 Project Plan")
            st.write(data.get("plan_text", ""))

            st.markdown("### 📋 Planning Questions")
            for q in data.get("questions", []):
                key = f"plan_q_{q['id']}"
                st.session_state.planning_answers[key] = st.multiselect(
                    f"{q['id']}. {q['question']}",
                    q.get("options", []),
                    key=key,
                )

            st.session_state.planning_answers["plan_additional"] = st.text_area(
                data.get("additional_prompt", "Any other notes?"),
                value=st.session_state.planning_answers.get("plan_additional", ""),
            )

            if st.button("✅ Confirm Planning → Designing"):
                st.session_state.phase = "designing"
                st.rerun()

    # -------- DESIGNING PHASE --------
    elif st.session_state.phase == "designing":
        st.subheader("🎨 Designing Phase")

        if not st.session_state.design_response:
            design_prompt = f"""
You are designing a modern, visually appealing Streamlit app.

User idea: {st.session_state.user_text}
Planning Summary: {st.session_state.planning_response.get('plan_text','')}
Planning Answers: {json.dumps(st.session_state.planning_answers, indent=2)}

TASK:
1. Suggest UI layout, themes, interactions, and visual design improvements.
2. Generate 10–15 multiple-choice questions (multi-select possible)
   about design preferences and new features the app could include.
3. Return STRICT JSON like:
{{
  "design_text": "Design overview...",
  "questions": [{{"id":1,"question":"...","options":["A","B","C","D"]}}],
  "additional_prompt": "Extra notes question"
}}
No markdown, no code fences.
"""
            with st.spinner("🎨 Gemini is creating design options..."):
                try:
                    resp = client.models.generate_content(
                        model="gemini-2.5-flash",
                        contents=[design_prompt],
                    )
                    raw = getattr(resp, "text", "").strip()
                    parsed = parse_gemini_json(raw)
                    st.session_state.design_response = parsed
                    st.rerun()
                except Exception as e:
                    st.error(f"⚠️ Gemini JSON parse error: {e}")
                    st.stop()

        else:
            data = st.session_state.design_response
            st.markdown("### 💡 Design Summary")
            st.write(data.get("design_text", ""))

            st.markdown("### 🎛️ Design Questions")
            for q in data.get("questions", []):
                key = f"design_q_{q['id']}"
                st.session_state.design_answers[key] = st.multiselect(
                    f"{q['id']}. {q['question']}",
                    q.get("options", []),
                    key=key,
                )

            st.session_state.design_answers["design_additional"] = st.text_area(
                data.get("additional_prompt", "Any other notes?"),
                value=st.session_state.design_answers.get("design_additional", ""),
            )

            if st.button("✅ Confirm Design → Finalize"):
                st.session_state.phase = "finalize"
                st.rerun()

    # -------- FINALIZE --------
    elif st.session_state.phase == "finalize":
        st.subheader("🧾 Final Review")
        st.write("### User Idea")
        st.write(st.session_state.user_text)
        st.write("### Line Range")
        st.write(st.session_state.line_range)
        st.write("### Planning Summary")
        st.write(st.session_state.planning_response.get("plan_text", ""))
        st.write("### Design Summary")
        st.write(st.session_state.design_response.get("design_text", ""))

        if st.button("🚀 Generate Streamlit Project"):
            st.session_state.phase = "generate"
            st.rerun()

    # -------- GENERATE --------
    elif st.session_state.phase == "generate":
        st.subheader("⚙️ Generating Code")

        if not st.session_state.generated_code:
            code_prompt = f"""
You are a senior Python developer and UI designer.

Generate a Streamlit project named `generated_app.py`
based on the following information:

User Idea: {st.session_state.user_text}
Line Range: {st.session_state.line_range}
Planning: {json.dumps(st.session_state.planning_response)}
Design: {json.dumps(st.session_state.design_response)}

Requirements:
- Keep the total code roughly within {st.session_state.line_range} lines.
- Create a **beautiful, modern UI** with clean layout, spacing, color theme, 
  and simple animations (if applicable).
- Use clear section titles, icons, and good UX structure.
- Do not include markdown or explanations — return ONLY valid Python code.
"""
            with st.spinner("💻 Generating high-quality Streamlit project..."):
                try:
                    resp = client.models.generate_content(
                        model="gemini-2.5-flash",
                        contents=[code_prompt],
                    )
                    code = getattr(resp, "text", "").strip()
                    st.session_state.generated_code = code

                    files = {
                        "generated_app.py": code,
                        "README.md": "# Auto-generated Streamlit Project\nCreated via Gemini Project Maker (Advanced Edition).",
                    }
                    for f in st.session_state.uploaded_files:
                        files[f["name"]] = f["bytes"]
                    st.session_state.project_files = files
                    st.rerun()
                except Exception as e:
                    st.error(f"Gemini error during code generation: {e}")
                    st.stop()

        else:
            st.success("✅ Code generated successfully!")
            st.download_button(
                "📄 Download generated_app.py",
                st.session_state.generated_code,
                file_name="generated_app.py",
                mime="text/x-python",
            )
            with st.expander("🔍 Preview Code"):
                st.code(st.session_state.generated_code, language="python")

            zip_path = zip_project(st.session_state.project_files)
            with open(zip_path, "rb") as f:
                st.download_button(
                    "📦 Download Full Project (ZIP)",
                    data=f,
                    file_name="generated_project.zip",
                    mime="application/zip",
                )

            if st.button("🔁 Start New Project"):
                for k in list(st.session_state.keys()):
                    del st.session_state[k]
                init_state()
                st.rerun()

# -------------------- Footer --------------------
st.markdown("---")
st.caption("✨ Multi-Select Questions • Line Range Control • Advanced UI Generation • JSON Auto-Fix")

