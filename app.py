import streamlit as st
import pandas as pd
from docx import Document
from docx.shared import Pt, Cm
from docx.enum.text import WD_ALIGN_PARAGRAPH
from io import BytesIO
from num2words import num2words
import datetime
import os
import fitz  # PyMuPDF
import google.generativeai as genai

# --- 1. НАСТРОЙКИ СТРАНИЦЫ ---
st.set_page_config(page_title="ЖКХелпер Pro", page_icon="⚖️", layout="wide")

hide_st_style = """
            <style>
            #MainMenu {visibility: hidden;}
            footer {visibility: hidden;}
            header[data-testid="stHeader"] { background: rgba(0,0,0,0); color: rgba(0,0,0,0); }
            button[kind="header"] { visibility: visible !important; color: #2e77d1 !important; }
            </style>
            """
st.markdown(hide_st_style, unsafe_allow_html=True)

# --- 2. ПОДКЛЮЧЕНИЕ GEMINI ---
GEMINI_KEY = os.getenv("GEMINI_API_KEY")
if GEMINI_KEY:
    genai.configure(api_key=GEMINI_KEY)

# --- 3. ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ---

def sum_to_words(amount):
    try:
        if pd.isna(amount) or amount <= 0: return ""
        rub = int(amount); kop = int(round((amount - rub) * 100))
        return f"{num2words(rub, lang='ru').capitalize()} руб. {kop:02d} коп."
    except: return ""

def get_full_text_from_pdf(file_path):
    full_text = ""
    try:
        doc = fitz.open(file_path)
        for page in doc:
            full_text += page.get_text()
        doc.close()
        return full_text
    except Exception as e:
        return f"Ошибка чтения PDF: {e}"

def calc_gosposhlina(debt):
    duty = debt * 0.02
    return round(max(200, min(10000, duty)), 2)

def create_sample_excel():
    columns = ['Город', 'Улица', 'Дом', 'Помещение', 'ФИО должника', 'Долг содержания', 'Период содержания', 'Долг капремонт', 'Период капремонт']
    data = [['Омск', '5 Армии', '2', '1', 'ООО «Юком»', 117170.37, 'с 01.06.2024 по 01.01.2026 гг', 56339.17, 'с 01.06.2024 по 01.01.2026 гг']]
    df = pd.DataFrame(data, columns=columns)
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False)
    return output.getvalue()

# --- 4. САЙДБАР ---
with st.sidebar:
    st.title("⚖️ ЖКХелпер Pro")
    page = st.radio("Навигация:", ["1. Уведомления", "2. Судебные приказы", "3. Исполнительное производство", "4. Чат-помощник ИИ"])
    st.markdown("---")
    st.subheader("Настройки взыскателя")
    v_type = st.selectbox("Тип организации", ["ТСН", "ТСЖ", "ООО", "УК", "ЖСК", "ЖК"])
    v_name = st.text_input("Название", "«СОЮЗ»")
    v_ogrn = st.text_input("ОГРН", "1025500511904")
    v_inn = st.text_input("ИНН/КПП", "5502047932/ 550101001")
    v_addr = st.text_input("Юр. адрес", "г. Омск, ул. Красный Путь, д.34")
    s_pos = st.text_input("Должность подписанта", "Председатель Правления")
    s_name = st.text_input("ФИО подписанта", "А.А. Оботуров")
    st.markdown("---")
    st.caption("Версия Pro | 2.5GB RAM | Full Context")

# --- 5. ЛОГИКА СТРАНИЦ ---

if page == "1. Уведомления":
    st.header("📬 Массовая генерация уведомлений")
    uploaded_file = st.file_uploader("Загрузите Excel", type="xlsx")
    if not uploaded_file: st.download_button("📥 Скачать образец Excel", create_sample_excel(), "sample_jkh.xlsx")
    if uploaded_file:
        df = pd.read_excel(uploaded_file)
        if st.button("🚀 Сформировать пакет уведомлений"):
            doc = Document()
            style = doc.styles['Normal']
            style.font.name = 'Times New Roman'
            style.font.size = Pt(12)
            for index, row in df.iterrows():
                val_sod = float(row.get('Долг содержания', 0)) if pd.notna(row.get('Долг содержания')) else 0
                val_kap = float(row.get('Долг капремонт', 0)) if pd.notna(row.get('Долг капремонт')) else 0
                if val_sod <= 0 and val_kap <= 0: continue
                
                header = doc.add_paragraph(); header.alignment = WD_ALIGN_PARAGRAPH.RIGHT
                header.add_run(f"Собственнику кв. (пом.) № {row['Помещение']} в доме № {row['Дом']} по\nул. {row['Улица']} в г. {row['Город']}\n{row['ФИО должника']}\n\nОт: {v_type} {v_name}\nОГРН {v_ogrn}\nИНН/КПП {v_inn}\nЮр. адрес: {v_addr}\n")
                
                title = doc.add_paragraph(); title.alignment = WD_ALIGN_PARAGRAPH.CENTER
                title.add_run("\nДОСУДЕБНОЕ УВЕДОМЛЕНИЕ").bold = True
                
                debt_phrases = []
                if val_sod > 0:
                    p_sod = str(row['Период содержания']).strip() if pd.notna(row['Период содержания']) and str(row['Период содержания']).strip() != "" else "____________________"
                    debt_phrases.append(f"за содержание жилья составляет {val_sod} руб. ({sum_to_words(val_sod)}) за период {p_sod}")
                if val_kap > 0:
                    p_kap = str(row['Период капремонт']).strip() if pd.notna(row['Период капремонт']) and str(row['Период капремонт']).strip() != "" else "____________________"
                    debt_phrases.append(f"за капитальный ремонт: {val_kap} руб. ({sum_to_words(val_kap)}) за период {p_kap}")
                
                full_debt_text = " и ".join(debt_phrases)
                paragraphs = [
                    f"{v_type} {v_name} доводит до Вашего сведения, что Ваша задолженность на {datetime.date.today().strftime('%d.%m.%Y')} г. по оплате {full_debt_text}.",
                    "Согласно ст. 153 Жилищного кодекса РФ, граждане обязаны своевременно и полностью вносить плату за жилое помещение и коммунальные услуги.",
                    "В соответствии с ч. 14 ст. 155 Жилищного кодекса Российской Федерации лица, несвоевременно и (или) не полностью внесшие плату за жилое помещение и коммунальные услуги (должники), обязаны уплатить кредитору пени в размере одной трехсотой ставки рефинансирования ЦБ РФ, действующей на момент оплаты, от невыплаченных в срок сумм за каждый день просрочки, начиная со следующего дня после наступления установленного срока оплаты по день фактической выплаты включительно.",
                    "В случае непогашения Вами вышеуказанной суммы задолженности в течение 10 дней со дня получения Вами настоящего уведомления, мы будем вынуждены обратиться в суд с заявлением о взыскании имеющейся задолженности и пени с отнесением на Вас судебных расходов, связанных с рассмотрением дела (государственной пошлины, расходов на оплату услуг представителя).",
                    "Убедительно просим погасить задолженность.",
                    f"По возникшим вопросам Вы можете обратиться в Правление {v_type} {v_name}."
                ]
                for text in paragraphs:
                    p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
                    p.paragraph_format.first_line_indent = Cm(1.25); p.add_run(text)
                
                footer = doc.add_paragraph(); footer.paragraph_format.space_before = Pt(18)
                footer.add_run(f"{s_pos} {v_type} {v_name}\n\n{s_name}____________________")
                if index < len(df) - 1: doc.add_page_break()
            
            output = BytesIO(); doc.save(output)
            st.download_button("📥 СКАЧАТЬ ПАКЕТ УВЕДОМЛЕНИЙ", output.getvalue(), "notices.docx")

elif page == "4. Чат-помощник ИИ":
    st.header("🤖 Юридический консультант (Полный контекст)")
    law_choice = st.selectbox("Выберите постановление:", ["ПП РФ №354", "ПП РФ №491", "ПП РФ №416"])
    user_q = st.text_area("Опишите ситуацию подробно:", height=250)
    
    if st.button("🚀 Провести аудит по всему тексту закона"):
        file_path = f"knowledge_base/{law_choice}.pdf"
        if os.path.exists(file_path):
            with st.spinner("⏳ ИИ читает весь документ и анализирует (до 40 сек)..."):
                full_text = get_full_text_from_pdf(file_path)
                try:
                    # Исправленная инициализация модели
                    model = genai.GenerativeModel(model_name='gemini-1.5-flash')
                    prompt = f"Ты эксперт ЖКХ. Проанализируй ситуацию на основе ВСЕГО текста закона {law_choice}. Ссылайся на пункты. Сделай вывод о правомерности и укажи риски.\n\nЗАКОН:\n{full_text}\n\nСИТУАЦИЯ:\n{user_q}"
                    
                    response = model.generate_content(prompt)
                    
                    st.markdown("---")
                    st.subheader("📋 Экспертное заключение:")
                    st.markdown(response.text)
                except Exception as e:
                    st.error(f"Ошибка ИИ: {e}")
        else: st.error("Файл не найден.")

st.markdown("---")
st.caption("🔒 Stateless: Данные удаляются при закрытии страницы.")