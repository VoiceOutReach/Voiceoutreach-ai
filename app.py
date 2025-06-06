import streamlit as st
import pandas as pd
import os
import io
import zipfile
import openai
import requests

# Streamlit UI
st.set_page_config(page_title="VoiceOutReach.ai", layout="centered")
st.title("🎙️ VoiceOutReach.ai - AI Voice Note Generator for LinkedIn Outreach")

# --- Inputs ---
openai_key = st.text_input("🔑 OpenAI API Key", type="password")
elevenlabs_key = st.text_input("🎤 ElevenLabs API Key", type="password")
voice_id = st.text_input("🗣️ ElevenLabs Voice ID", value="YOUR_DEFAULT_VOICE_ID")

template = st.text_area(
    "📄 Message Template (use variables like {first_name}, {position}, etc.)",
    "Hi {first_name}, I noticed you're hiring for {job_title} at {company_name}. {gpt_intro} I’d love to connect and show how I can help. Open to a quick 5-min call?"
)

generate_gpt_intro = st.checkbox("✨ Auto-generate first sentence using job description?", value=True)

# --- Follow-up Controls ---
generate_followup = st.checkbox("🔁 Generate Follow-Up Message?", value=False)

followup_template = st.text_area(
    "📄 Follow-Up Template",
    "Hey {first_name}, just following up on my last message about {job_title}. Would love to connect!",
    disabled=not generate_followup
)

followup_delay = st.selectbox(
    "⏳ Follow-up Delay (in days)",
    options=[i for i in range(1, 11)],
    index=2,
    disabled=not generate_followup
)

# --- Sample CSV download ---
sample_csv = """First Name,Position,Hiring for Job Title,Company name,Description
Alice,Founder,Video Editor,MediaCorp,"We’re looking for a creative video editor to join our team."
Bob,Head of Product,UI/UX Designer,Designly,"Seeking a UX designer passionate about user-centric design."
"""
st.download_button(
    label="📥 Download Sample CSV Format",
    data=sample_csv,
    file_name="sample_leads_template.csv",
    mime="text/csv"
)

# --- File Upload ---
uploaded_file = st.file_uploader("📤 Upload Leads CSV", type=["csv"])

# --- Processing ---
if uploaded_file and openai_key and elevenlabs_key:
    df = pd.read_csv(uploaded_file)
    st.success("✅ File uploaded. Ready to generate messages.")

    if st.button("🚀 Generate Voice Notes"):
        output_dir = "voice_notes"
        os.makedirs(output_dir, exist_ok=True)
        openai.api_key = openai_key

        results = []

        for index, row in df.iterrows():
            try:
                first_name = str(row.get("First Name", "")).strip()
                position = str(row.get("Position", "")).strip()
                job_title = str(row.get("Hiring for Job Title", "")).strip()
                company_name = str(row.get("Company name", "")).strip()
                job_description = str(row.get("Description", "")).strip()

                # --- GPT intro ---
                if generate_gpt_intro and job_description:
                    try:
                        prompt = f"Write a professional, attention-grabbing 1-sentence opening based on this job description:\n\n{job_description}"
                        response = openai.ChatCompletion.create(
                            model="gpt-3.5-turbo",
                            messages=[{"role": "user", "content": prompt}]
                        )
                        gpt_intro = response.choices[0].message.content.strip()
                    except Exception as e:
                        gpt_intro = "(GPT intro failed)"
                        st.error(f"❌ GPT Error for {first_name}: {e}")
                else:
                    gpt_intro = ""

                # --- Main message ---
                message = template.format(
                    first_name=first_name,
                    position=position,
                    job_title=job_title,
                    company_name=company_name,
                    gpt_intro=gpt_intro
                )

                # ElevenLabs voice generation
                tts_url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
                headers = {
                    "xi-api-key": elevenlabs_key,
                    "Content-Type": "application/json"
                }
                tts_payload = {
                    "text": message,
                    "model_id": "eleven_monolingual_v1",
                    "voice_settings": {
                        "stability": 0.5,
                        "similarity_boost": 0.5
                    }
                }

                response = requests.post(tts_url, headers=headers, json=tts_payload)
                audio_path = f"{output_dir}/{first_name}_{job_title}.mp3"
                with open(audio_path, "wb") as f:
                    f.write(response.content)

                st.success(f"🎧 Voice note generated for {first_name}")
                st.audio(audio_path, format="audio/mp3")

                # --- Follow-Up ---
                followup_message = ""
                followup_audio_path = ""

                if generate_followup:
                    followup_message = followup_template.format(
                        first_name=first_name,
                        position=position,
                        job_title=job_title,
                        company_name=company_name,
                        gpt_intro=""
                    )

                    tts_payload["text"] = followup_message
                    response = requests.post(tts_url, headers=headers, json=tts_payload)

                    followup_audio_path = f"{output_dir}/{first_name}_{job_title}_followup.mp3"
                    with open(followup_audio_path, "wb") as f:
                        f.write(response.content)

                    st.success(f"📨 Follow-up voice note generated for {first_name} (send in {followup_delay} days)")
                    st.audio(followup_audio_path, format="audio/mp3")

                # --- Save to results ---
                results.append({
                    "Name": first_name,
                    "Position": position,
                    "Job Title": job_title,
                    "Message": message,
                    "Voice File": os.path.basename(audio_path),
                    "Follow-Up Message": followup_message,
                    "Follow-Up File": os.path.basename(followup_audio_path) if followup_audio_path else "",
                    "Follow-Up Delay (Days)": followup_delay if generate_followup else ""
                })

            except Exception as e:
                st.error(f"❌ Error for row {index + 1}: {e}")

        # --- Save messages to CSV ---
        results_df = pd.DataFrame(results)
        csv_buffer = io.StringIO()
        results_df.to_csv(csv_buffer, index=False)
        st.download_button("📄 Download Message CSV", data=csv_buffer.getvalue(), file_name="generated_messages.csv", mime="text/csv")

        # --- Zip audio files ---
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w") as zipf:
            for file in os.listdir(output_dir):
                zipf.write(os.path.join(output_dir, file), arcname=file)
        zip_buffer.seek(0)
        st.download_button("📦 Download Voice Notes ZIP", data=zip_buffer, file_name="voice_notes.zip", mime="application/zip")

else:
    st.info("👆 Please upload a CSV file and enter your API keys to get started.")
