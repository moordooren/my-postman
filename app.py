import streamlit as st
import pandas as pd
from docx import Document
from docx.shared import Pt, Cm
from docx.enum.text import WD_ALIGN_PARAGRAPH
from io import BytesIO
from num2words import num2words
import datetime
import os
import pdfplumber
try:
    from openai import OpenAI
except ImportError:
    pass

# --- 1. НАСТРОЙКИ СТРАНИЦЫ И СТИЛИ ---
st.set_page_config(page_title="ЖКХелпер Pro", page_icon="⚖️", layout="wide")

# --- СКРЫВАЕМ ЛИШНИЕ ЭЛЕМЕНТЫ, НО ОСТАВЛЯЕМ КНОПКУ РАЗВЕРТЫВАНИЯ ---
hide_st_style = """
            <style>
            #MainMenu {visibility: hidden;}
            footer {visibility: hidden;}
            /* Прячем только фон хедера, но не саму кнопку */
            header[data-testid="stHeader"] {
                background: rgba(0,0,0,0);
                color: rgba(0,0,0,0);
            }
            /* Делаем кнопку открытия сайдбара видимой и синей, чтобы не терялась */
            button[kind="header"] {
                visibility: visible !format;
                color: #2e77d1 !important;
            }
            </style>
            """
st.markdown(hide_st_style, unsafe_allow_html=True)

# --- 2. ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ---

def sum_to_words(amount):
    """Конвертация суммы в рубли прописью"""
    try:
        if pd.isna(amount) or amount <= 0: return ""
        rub = int(amount)
        kop = int(round((amount - rub) * 100))
        words = num2words(rub, lang='ru').capitalize()
        return f"{words} руб. {kop:02d} коп."
    except: return ""

def get_pdf_text(file_path):
    """Извлечение текста из PDF для контекста ИИ"""
    text = ""
    try:
        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
        return text
    except Exception as e:
        return f"Ошибка чтения PDF: {e}"

def calc_gosposhlina(debt):
    """Расчет госпошлины (2% от суммы, от 200 до 10000 руб)"""
    duty = debt * 0.02
    if duty < 200: duty = 200
    if duty > 10000: duty = 10000
    return round(duty, 2)

def create_sample_excel():
    """Создание образца Excel для уведомлений"""
    columns = [
        'Город', 'Улица', 'Дом', 'Помещение', 'ФИО должника', 
        'Долг содержания', 'Период содержания', 
        'Долг капремонт', 'Период капремонт'
    ]
    data = [
        ['Омск', '5 Армии', '2', '1', 'ООО «Юком»', 117170.37, 'с 01.06.2024 по 01.01.2026 гг', 56339.17, 'с 01.06.2024 по 01.01.2026 гг'],
        ['Омск', 'Ленина', '5', '2', 'Иванов Иван Иванович', 5000.00, 'январь 2026', 0, '']
    ]
    df = pd.DataFrame(data, columns=columns)
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False)
    return output.getvalue()

# --- 3. БОКОВАЯ ПАНЕЛЬ (МЕНЮ) ---
with st.sidebar:
    st.title("⚖️ ЖКХелпер Pro")
    page = st.radio("Навигация:", [
        "1. Уведомления", 
        "2. Судебные приказы", 
        "3. Исполнительное производство", 
        "4. Чат-помощник ИИ"
    ])
    
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
    api_key = st.text_input("OpenAI API Key:", type="password")
    st.caption("Версия 2.0 Pro | ФЗ-152 Compliance")

# --- 4. ОСНОВНЫЕ МОДУЛИ ---

# РАЗДЕЛ 1: УВЕДОМЛЕНИЯ
if page == "1. Уведомления":
    st.header("📬 Массовая генерация уведомлений")
    uploaded_file = st.file_uploader("Загрузите Excel с должниками", type="xlsx")
    
    if not uploaded_file:
        st.download_button("📥 Скачать образец Excel", create_sample_excel(), "sample_notices.xlsx")
    
    if uploaded_file:
        df = pd.read_excel(uploaded_file)
        if st.button("🚀 Сформировать пакет DOCX"):
            doc = Document()
            style = doc.styles['Normal']
            style.font.name = 'Times New Roman'
            style.font.size = Pt(12)
            
            processed = 0
            for index, row in df.iterrows():
                val_sod = float(row.get('Долг содержания', 0)) if pd.notna(row.get('Долг содержания')) else 0
                val_kap = float(row.get('Долг капремонт', 0)) if pd.notna(row.get('Долг капремонт')) else 0
                
                if val_sod <= 0 and val_kap <= 0: continue
                processed += 1
                
                # Шапка
                h = doc.add_paragraph()
                h.alignment = WD_ALIGN_PARAGRAPH.RIGHT
                h.add_run(f"Собственнику кв. (пом.) № {row['Помещение']} в доме № {row['Дом']} по\n"
                          f"ул. {row['Улица']} в г. {row['Город']}\n"
                          f"{row['ФИО должника']}\n\n"
                          f"От: {v_type} {v_name}\nОГРН {v_ogrn}\nИНН/КПП {v_inn}\nЮр. адрес: {v_addr}\n")
                
                # Заголовок
                t = doc.add_paragraph()
                t.alignment = WD_ALIGN_PARAGRAPH.CENTER
                t.add_run("\nДОСУДЕБНОЕ УВЕДОМЛЕНИЕ").bold = True
                
                # Текст долга
                d_phrases = []
                if val_sod > 0:
                    p_sod = str(row['Период содержания']).strip() if pd.notna(row.get('Период содержания')) and str(row.get('Период содержания')).strip() != "" else "________________"
                    d_phrases.append(f"за содержание жилья: {val_sod} руб. ({sum_to_words(val_sod)}) за период {p_sod}")
                if val_kap > 0:
                    p_kap = str(row['Период капремонт']).strip() if pd.notna(row.get('Период капремонт')) and str(row.get('Период капремонт')).strip() != "" else "________________"
                    d_phrases.append(f"за капитальный ремонт: {val_kap} руб. ({sum_to_words(val_kap)}) за период {p_kap}")
                
                main_text = [
                    f"{v_type} {v_name} уведомляет Вас, что за Вами числится задолженность по оплате " + " и ".join(d_phrases) + ".",
                    "Согласно ст. 153, 155 ЖК РФ, граждане обязаны своевременно вносить плату. В случае непогашения в течение 10 дней мы обратимся в суд.",
                    "Убедительно просим погасить задолженность."
                ]
                
                for txt in main_text:
                    p = doc.add_paragraph()
                    p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
                    p.paragraph_format.first_line_indent = Cm(1.25)
                    p.add_run(txt)
                
                doc.add_paragraph(f"\n{s_pos} {v_type} {v_name}\n\n{s_name}________________")
                if index < len(df) - 1: doc.add_page_break()
            
            output = BytesIO()
            doc.save(output)
            st.download_button("📥 Скачать уведомления", output.getvalue(), "uvedomleniya.docx")

# РАЗДЕЛ 2: СУДЕБНЫЕ ПРИКАЗЫ
elif page == "2. Судебные приказы":
    st.header("⚖️ Заявления на судебный приказ")
    st.info("Авторасчет госпошлины (2% от суммы).")
    uploaded_court = st.file_uploader("Загрузите Excel с должниками", type="xlsx", key="court_up")
    
    if uploaded_court:
        df_c = pd.read_excel(uploaded_court)
        if st.button("🚀 Сформировать заявления для суда"):
            doc = Document()
            for idx, row in df_c.iterrows():
                debt = float(row.get('Долг содержания', 0)) + float(row.get('Долг капремонт', 0))
                duty = calc_gosposhlina(debt)
                
                h = doc.add_paragraph()
                h.alignment = WD_ALIGN_PARAGRAPH.RIGHT
                h.add_run(f"В Мировой суд г. {row.get('Город')}\nВзыскатель: {v_type} {v_name}\nДолжник: {row['ФИО должника']}")
                
                t = doc.add_paragraph()
                t.alignment = WD_ALIGN_PARAGRAPH.CENTER
                t.add_run("\nЗАЯВЛЕНИЕ О ВЫДАЧЕ СУДЕБНОГО ПРИКАЗА").bold = True
                
                p = doc.add_paragraph()
                p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
                p.paragraph_format.first_line_indent = Cm(1.25)
                p.add_run(f"Просим взыскать задолженность в размере {debt} руб. и госпошлину в размере {duty} руб.")
                
                if idx < len(df_c) - 1: doc.add_page_break()
            
            out_c = BytesIO()
            doc.save(out_c)
            st.download_button("📥 Скачать документы для суда", out_c.getvalue(), "sud_prikazy.docx")

# РАЗДЕЛ 3: ФССП
elif page == "3. Исполнительное производство":
    st.header("🚔 Работа с приставами (ФССП)")
    st.file_uploader("Загрузите скан судебного приказа (PDF/JPG)", type=["pdf", "jpg", "png"])
    if st.button("Generate FSSP Application"):
        st.warning("Модуль в разработке. Здесь будет автозаполнение заявлений в ФССП.")

# РАЗДЕЛ 4: ЧАТ-ПОМОЩНИК
elif page == "4. Чат-помощник ИИ":
    st.header("🤖 Юридический консультант")
    law_choice = st.selectbox("Выберите базу знаний:", ["ПП РФ №354", "ПП РФ №491", "ПП РФ №416"])
    user_q = st.text_input("Ваш вопрос по закону:")
    
    if user_q:
        if not api_key:
            st.error("Введите API Key в боковой панели!")
        else:
            file_path = f"knowledge_base/{law_choice}.pdf"
            if os.path.exists(file_path):
                with st.spinner("Чтение PDF и генерация ответа..."):
                    context = get_pdf_text(file_path)
                    
                    try:
                        client = OpenAI(api_key=api_key)
                        response = client.chat.completions.create(
                            model="gpt-4o", # или gpt-3.5-turbo
                            messages=[
                                {"role": "system", "content": "Ты юрист ЖКХ. Отвечай строго по тексту предоставленного закона. Ссылайся на пункты. Если ответа нет - скажи об этом."},
                                {"role": "user", "content": f"Текст закона: {context[:15000]}\n\nВопрос: {user_q}"} # Лимит контекста
                            ]
                        )
                        st.markdown("### Ответ помощника:")
                        st.write(response.choices[0].message.content)
                    except Exception as e:
                        st.error(f"Ошибка API: {e}")
            else:
                st.error(f"Файл {law_choice}.pdf не найден в папке knowledge_base.")

# ПРАВИЛА БЕЗОПАСНОСТИ
st.markdown("---")
st.caption("🔒 **Stateless Security:** Все данные обрабатываются в ОЗУ. При обновлении страницы данные ФИО и суммы полностью стираются. ФЗ-152 Compliant.")