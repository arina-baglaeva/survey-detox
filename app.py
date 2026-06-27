import streamlit as st
import firebase_admin
from firebase_admin import credentials, firestore
import pandas as pd
import plotly.express as px
from datetime import datetime, timezone
import os


# --- Функция получения учётных данных Firebase ---
def get_firebase_creds():
    # 1. Пытаемся взять из st.secrets (облако)
    if hasattr(st, 'secrets') and all(key in st.secrets for key in
                                      ['FIREBASE_PROJECT_ID', 'FIREBASE_PRIVATE_KEY', 'FIREBASE_CLIENT_EMAIL']):
        cred_dict = {
            "type": "service_account",
            "project_id": st.secrets["FIREBASE_PROJECT_ID"],
            "private_key_id": st.secrets.get("FIREBASE_PRIVATE_KEY_ID", ""),
            "private_key": st.secrets["FIREBASE_PRIVATE_KEY"],
            "client_email": st.secrets["FIREBASE_CLIENT_EMAIL"],
            "client_id": st.secrets.get("FIREBASE_CLIENT_ID", ""),
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
            "client_x509_cert_url": st.secrets.get("FIREBASE_CLIENT_CERT_URL", "")
        }
        return credentials.Certificate(cred_dict)

    # 2. Если секретов нет – пробуем локальный файл (для разработки)
    key_path = "serviceAccountKey.json"
    if os.path.exists(key_path):
        return credentials.Certificate(key_path)

    # 3. Ничего не найдено – останавливаем приложение с ошибкой
    st.error(
        "Firebase credentials not found. Please set secrets in Streamlit Cloud or provide serviceAccountKey.json locally.")
    st.stop()


# --- Инициализация Firebase (один раз за сессию) ---
if not firebase_admin._apps:
    cred = get_firebase_creds()
    firebase_admin.initialize_app(cred)

db = firestore.client()

# --- Настройка страницы ---
st.set_page_config(page_title="Цифровой детокс", layout="wide")
st.title("📱 Опрос: Цифровой детокс среди студентов")
st.markdown("""
**Тема:** Изучение цифровых привычек и попыток снижения экранного времени  
_Все ответы анонимны и используются только в учебных целях_
""")

# --- Форма опроса ---
with st.form("detox_survey"):
    st.subheader("📋 Анкета")

    col1, col2 = st.columns(2)

    with col1:
        age = st.number_input("Ваш возраст", min_value=14, max_value=35, step=1)
        gender = st.radio("Пол", ["Девушка", "Юноша", "Предпочитаю не указывать"])
        social_hours = st.slider("⏰ Сколько часов в день вы проводите в соцсетях?",
                                 min_value=0, max_value=12, value=3, step=1)

    with col2:
        education = st.radio("Курс обучения",
                             ["1 курс", "2 курс", "3 курс", "4 курс", "Другое"])
        stress_level = st.slider("😰 Уровень стресса от цифрового перегруза (1-10)",
                                 min_value=1, max_value=10, value=5)

    symptoms = st.multiselect("🩺 Какие симптомы вы замечаете?",
                              ["Тревога без телефона", "Бессонница",
                               "Усталость глаз", "Снижение концентрации",
                               "Раздражительность", "Нет симптомов"])

    tried_detox = st.radio("🔄 Пробовали ли вы снижать экранное время?",
                           ["Да, успешно", "Да, но не получилось", "Нет, не пробовал(а)"])

    device = st.radio("📱 Какое устройство вы используете чаще всего?",
                      ["Смартфон", "Планшет", "Ноутбук", "ПК", "Всё одинаково"])

    check_freq = st.radio("⏰ Как часто вы проверяете телефон?",
                          ["Каждые 5 минут", "Каждые 15 минут", "Каждый час", "Реже"])

    before_sleep = st.radio("🌙 Используете ли вы телефон перед сном?",
                            ["Да, постоянно", "Иногда", "Редко", "Никогда"])

    comment = st.text_area("💬 Комментарий (необязательно)",
                           placeholder="Расскажите о вашем опыте...")

    submitted = st.form_submit_button("✅ Отправить ответы")

# --- Сохранение в Firebase ---
if submitted:
    if not age or not gender:
        st.warning("⚠️ Пожалуйста, заполните обязательные поля!")
    else:
        record = {
            "age": int(age),
            "gender": gender,
            "education": education,
            "social_hours": int(social_hours),
            "stress_level": int(stress_level),
            "symptoms": symptoms,
            "tried_detox": tried_detox,
            "device": device,
            "check_freq": check_freq,
            "before_sleep": before_sleep,
            "comment": comment,
            "timestamp": datetime.now(timezone.utc)  # исправлено!
        }

        try:
            db.collection("detox_responses").add(record)
            st.success("🎉 Спасибо! Ваши ответы сохранены!")
            st.balloons()
        except Exception as e:
            st.error(f"❌ Ошибка сохранения: {e}")

# --- Аналитика ---
if st.checkbox("📊 Показать аналитику (Instructor View)"):
    st.subheader("📈 Результаты опроса")

    docs = db.collection("detox_responses").stream()
    data = [doc.to_dict() for doc in docs]

    if not data:
        st.info("📭 Пока нет ответов. Будьте первым!")
    else:
        df = pd.DataFrame(data)

        if "timestamp" in df.columns:
            df["timestamp"] = pd.to_datetime(df["timestamp"])

        st.write(f"**Всего ответов:** {len(df)}")
        st.dataframe(df.head(10))
        # --- 📥 Экспорт данных ---
        st.markdown("---")
        st.subheader("📥 Экспорт данных")

        current_time = datetime.now().strftime("%Y%m%d_%H%M")

        # Экспорт в CSV с правильной кодировкой для Excel
        csv_buffer = df.to_csv(index=False, encoding='utf-8-sig').encode('utf-8-sig')
        st.download_button(
            label="📥 Скачать данные в CSV",
            data=csv_buffer,
            file_name=f"detox_export_{current_time}.csv",
            mime="text/csv",
            use_container_width=True
        )
        st.markdown("---")
        st.subheader("📊 Визуализация данных")

        col1, col2 = st.columns(2)

        with col1:
            fig_hours = px.histogram(df, x="social_hours",
                                     title="⏰ Часы в соцсетях",
                                     labels={"social_hours": "Часов в день"},
                                     color_discrete_sequence=["#FF6B6B"])
            st.plotly_chart(fig_hours, use_container_width=True)

        with col2:
            fig_stress = px.box(df, y="stress_level",
                                title="😰 Уровень стресса",
                                labels={"stress_level": "Баллы (1-10)"},
                                color_discrete_sequence=["#4ECDC4"])
            st.plotly_chart(fig_stress, use_container_width=True)

        st.markdown("---")
        col3, col4 = st.columns(2)

        with col3:
            detox_counts = df["tried_detox"].value_counts()
            fig_detox = px.pie(values=detox_counts.values,
                               names=detox_counts.index,
                               title="🔄 Попытки снизить экранное время",
                               color_discrete_sequence=["#95E1D3", "#F38181", "#AA96DA"])
            st.plotly_chart(fig_detox, use_container_width=True)

        with col4:
            gender_counts = df["gender"].value_counts()
            fig_gender = px.pie(values=gender_counts.values,
                                names=gender_counts.index,
                                title="👥 Пол респондентов",
                                color_discrete_sequence=["#FCBAD3", "#A8D8EA", "#FFD93D"])
            st.plotly_chart(fig_gender, use_container_width=True)

        st.markdown("---")
        st.subheader("🩺 Распространённость симптомов")

        all_symptoms = []
        for symptoms_list in df["symptoms"]:
            all_symptoms.extend(symptoms_list)

        symptoms_df = pd.Series(all_symptoms).value_counts().reset_index()
        symptoms_df.columns = ["Симптом", "Количество"]

        fig_symptoms = px.bar(symptoms_df, x="Симптом", y="Количество",
                              title=" Какие симптомы встречаются чаще?",
                              color="Количество",
                              color_continuous_scale="Viridis")
        st.plotly_chart(fig_symptoms, use_container_width=True)

        st.markdown("---")
        st.subheader("📱 Анализ цифровых привычек")

        col5, col6, col7 = st.columns(3)

        with col5:
            device_counts = df["device"].value_counts()
            fig_device = px.pie(values=device_counts.values,
                                names=device_counts.index,
                                title=" Основное устройство",
                                color_discrete_sequence=px.colors.qualitative.Set2)
            st.plotly_chart(fig_device, use_container_width=True)

        with col6:
            freq_counts = df["check_freq"].value_counts()
            fig_freq = px.bar(x=freq_counts.index, y=freq_counts.values,
                              title="⏰ Частота проверки телефона",
                              labels={"x": "Частота", "y": "Человек"},
                              color=freq_counts.values,
                              color_continuous_scale="Blues")
            st.plotly_chart(fig_freq, use_container_width=True)

        with col7:
            sleep_counts = df["before_sleep"].value_counts()
            fig_sleep = px.pie(values=sleep_counts.values,
                               names=sleep_counts.index,
                               title=" Телефон перед сном",
                               color_discrete_sequence=px.colors.qualitative.Pastel)
            st.plotly_chart(fig_sleep, use_container_width=True)

        st.markdown("---")
        st.subheader("💡 Краткие выводы")

        avg_hours = df["social_hours"].mean()
        avg_stress = df["stress_level"].mean()

        st.write(f"""
        - **Среднее время в соцсетях:** {avg_hours:.1f} часов в день
        - **Средний уровень стресса:** {avg_stress:.1f} из 10
        - **Наиболее частый симптом:** {symptoms_df.iloc[0]['Симптом'] if len(symptoms_df) > 0 else 'нет данных'}
        - **Процент попробовавших детокс:** {len(df[df['tried_detox'] != 'Нет, не пробовал(а)']) / len(df) * 100:.1f}%
        """)