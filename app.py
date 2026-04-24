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

# Скрываем лишнее, оставляя кнопку развертывания
hide_st_style = """
            <style>
            #MainMenu {visibility: hidden;}
            footer {visibility: hidden;}
            header[data-testid="stHeader"] {
                background: rgba(0,0,0,0);
                color: rgba(0,0,0,0);
            }
            button[kind="header"] {
                visibility: visible !important;
                color: #2e77d1 !important;
            }
            </style>
            """
st.markdown(hide_st_style, unsafe_allow_html=True)

# --- 2. ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ---

def sum_to_words(amount):
    try:
        if pd.isna(amount) or amount <= 0: return ""
        rub = int(amount)
        kop = int(round((amount - rub) * 100))
        words = num2words(rub, lang='ru').capitalize()
        return f"{words} руб. {kop:02d} коп."
    except: return ""

def get_pdf_text(file_path):
    text = ""
    try:
        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text: text += page_text + "\n"
        return text
    except Exception as e:
        return f"Ошибка чтения PDF: {e}"

def calc_gosposhlina(debt):
    duty = debt * 0.02
    if duty < 200: duty = 200
    if duty > 10000: duty = 10000
    return round(duty, 2)

def create_sample_excel():
    columns = [
        'Город', 'Улица', 'Дом', 'Помещение', 'ФИО должника', 
        'Долг содержания', 'Период содержания', 
        'Долг капремонт', 'Период капремонт'
    ]
    data = [
        ['Омск', '5 Армии', '2', '1', 'ООО «Юком»', 117170.37, 'с 01.06.2024 по 01.01.2026 гг', 56339.17, 'с 01.06.2024 по 01.01.2026 гг'],
        ['Омск', 'Ленина', '5', '2', 'Иванов Иван Иванович', 5000.00, 'с 01.06.2024 по 01.01.2026 гг', 0, '']
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

# РАЗДЕЛ 1: УВЕДОМЛЕНИЯ (ПОЛНОСТЬЮ ВОССТАНОВЛЕН)
if page == "1. Уведомления":
    st.header("📬 Массовая генерация уведомлений")
    uploaded_file = st.file_uploader("Загрузите Excel с должниками", type="xlsx")
    
    if not uploaded_file:
        st.download_button("📥 Скачать образец Excel", create_sample_excel(), "sample_jkh.xlsx")
    
    if uploaded_file:
        df = pd.read_excel(uploaded_file)
        st.success(f"Файл загружен успешно. Найдено строк: {len(df)}")
        
        if st.button("🚀 Сформировать пакет уведомлений"):
            doc = Document()
            style = doc.styles['Normal']
            style.font.name = 'Times New Roman'
            style.font.size = Pt(12)

            processed_count = 0
            for index, row in df.iterrows():
                try:
                    val_sod = float(row['Долг содержания']) if pd.notna(row['Долг содержания']) else 0
                    val_kap = float(row['Долг капремонт']) if pd.notna(row['Долг капремонт']) else 0
                except: val_sod, val_kap = 0, 0
                
                if val_sod <= 0 and val_kap <= 0: continue
                processed_count += 1
                
                # Шапка
                header = doc.add_paragraph()
                header.alignment = WD_ALIGN_PARAGRAPH.RIGHT
                header.paragraph_format.space_after = Pt(0)
                header_text = (
                    f"Собственнику кв. (пом.) № {row['Помещение']} в доме № {row['Дом']} по\n"
                    f"ул. {row['Улица']} в г. {row['Город']}\n"
                    f"{row['ФИО должника']}\n\n"
                    f"От: {v_type} {v_name}\n"
                    f"ОГРН {v_ogrn}\n"
                    f"ИНН/КПП {v_inn}\n"
                    f"Юр. адрес: {v_addr}\n"
                )
                header.add_run(header_text)

                # Заголовок
                title = doc.add_paragraph()
                title.alignment = WD_ALIGN_PARAGRAPH.CENTER
                title.paragraph_format.space_before = Pt(12)
                title.paragraph_format.space_after = Pt(12)
                title_run = title.add_run("ДОСУДЕБНОЕ УВЕДОМЛЕНИЕ")
                title_run.bold = True

                # Логика текста долга
                debt_phrases = []
                if val_sod > 0:
                    p_sod = str(row['Период содержания']).strip() if pd.notna(row['Период содержания']) and str(row['Период содержания']).strip() != "" else "____________________"
                    debt_phrases.append(f"за содержание жилья составляет {val_sod} руб. ({sum_to_words(val_sod)}) за период {p_sod}")
                
                if val_kap > 0:
                    p_kap = str(row['Период капремонт']).strip() if pd.notna(row['Период капремонт']) and str(row['Период капремонт']).strip() != "" else "____________________"
                    debt_phrases.append(f"за капитальный ремонт: {val_kap} руб. ({sum_to_words(val_kap)}) за период {p_kap}")
                
                debt_full_str = " и ".join(debt_phrases)
                today = datetime.date.today().strftime('%d.%m.%Y')

                paragraphs = [
                    f"{v_type} {v_name} доводит до Вашего сведения, что Ваша задолженность на {today} г. по оплате {debt_full_str}.",
                    "Согласно ст. 153 Жилищного кодекса РФ, граждане обязаны своевременно и полностью вносить плату за жилоемещение и коммунальные услуги.",
                    "В соответствии с ч. 14 ст. 155 Жилищного кодекса Российской Федерации лица, несвоевременно и (или) не полностью внесшие плату за жилое помещение и коммунальные услуги (должники), обязаны уплатить кредитору пени в размере одной трехсотой ставки рефинансирования ЦБ РФ, действующей на момент оплаты, от невыплаченных в срок сумм за каждый день просрочки, начиная со следующего дня после наступления установленного срока оплаты по день фактической выплаты включительно.",
                    "В случае непогашения Вами вышеуказанной суммы задолженности в течение 10 дней со дня получения Вами настоящего уведомления, мы будем вынуждены обратиться в суд с заявлением о взыскании имеющейся задолженности и пени с отнесением на Вас судебных расходов, связанных с рассмотрением дела (государственной пошлины, расходов на оплату услуг представителя).",
                    "Убедительно просим погасить задолженность.",
                    f"По возникшим вопросам Вы можете обратиться в Правление {v_type} {v_name}."
                ]

                for text in paragraphs:
                    p = doc.add_paragraph()
                    p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
                    p.paragraph_format.first_line_indent = Cm(1.25)
                    p.paragraph_format.space_before = Pt(0)
                    p.paragraph_format.space_after = Pt(0)
                    p.add_run(text)

                footer = doc.add_paragraph()
                footer.paragraph_format.space_before = Pt(18)
                footer.add_run(f"{s_pos} {v_type} {v_name}\n\n")
                footer.add_run(f"{s_name}____________________")

                if index < len(df) - 1: doc.add_page_break()

            if processed_count > 0:
                target_doc = BytesIO()
                doc.save(target_doc)
                target_doc.seek(0)
                st.download_button(label="📥 СКАЧАТЬ ПАКЕТ УВЕДОМЛЕНИЙ", data=target_doc, file_name="uvedomleniya.docx")

    # --- ИНСТРУКЦИЯ И БЕЗОПАСНОСТЬ (ВОССТАНОВЛЕНО) ---
    st.markdown("---")
    st.subheader("📖 Инструкция по работе")
    st.info("""
    1. **Данные компании:** Заполните все поля в разделе №1 (слева в боковой панели).
    2. **Образец Excel:** Скачайте шаблон. Не меняйте порядок столбцов!
    3. **Заполнение:** 
        * Все суммы должны быть **без знака минус** (только положительные числа).
        * Если долга нет, оставьте 0 или пусто.
        * Если период не указан, программа оставит место для ручного ввода (____).
    4. **Лимиты:** Для стабильной работы рекомендуем загружать файлы объемом **не более 100 строк** за один раз.
    """)
    st.warning("🔒 **Безопасность и персональные данные (ФЗ-152):**")
    st.write("""
    * Сервис работает в режиме **In-Memory**: данные загружаются в оперативную память, обрабатываются и **удаляются сразу** после закрытия страницы.
    * Мы **не сохраняем** ваши файлы и персональные данные на сервере.
    """)

# РАЗДЕЛЫ 2, 3, 4 (БЕЗ ИЗМЕНЕНИЙ В ЛОГИКЕ)
elif page == "2. Судебные приказы":
    st.header("⚖️ Заявления на судебный приказ")
    uploaded_court = st.file_uploader("Загрузите Excel для суда", type="xlsx")
    if uploaded_court:
        df_c = pd.read_excel(uploaded_court)
        if st.button("🚀 Сформировать заявления"):
            doc = Document()
            for idx, row in df_c.iterrows():
                debt = float(row.get('Долг содержания', 0)) + float(row.get('Долг капремонт', 0))
                duty = calc_gosposhlina(debt)
                h = doc.add_paragraph(); h.alignment = WD_ALIGN_PARAGRAPH.RIGHT
                h.add_run(f"В Мировой суд г. {row.get('Город')}\nВзыскатель: {v_type} {v_name}\nДолжник: {row['ФИО должника']}")
                t = doc.add_paragraph(); t.alignment = WD_ALIGN_PARAGRAPH.CENTER
                t.add_run("\nЗАЯВЛЕНИЕ О ВЫДАЧЕ СУДЕБНОГО ПРИКАЗА").bold = True
                p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
                p.add_run(f"Просим взыскать задолженность {debt} руб. и госпошлину {duty} руб.")
                if idx < len(df_c) - 1: doc.add_page_break()
            target_c = BytesIO(); doc.save(target_c)
            st.download_button("📥 Скачать заявления", target_c.getvalue(), "court_orders.docx")

elif page == "3. Исполнительное производство":
    st.header("🚔 Работа с ФССП")
    st.file_uploader("Загрузите скан приказа", type=["pdf", "jpg", "png"])
    st.button("Generate FSSP Application")

# --- РАЗДЕЛ 4: ЧАТ-ПОМОЩНИК ИИ (ОБНОВЛЕННЫЙ) ---
elif page == "4. Чат-помощник ИИ":
    st.header("🤖 Профессиональный юридический консультант")
    
    st.markdown("""
    ### Как работать с помощником:
    Опишите вашу ситуацию максимально подробно. ИИ проанализирует её, опираясь **исключительно на текст выбранного постановления**.
    
    *   **Без галлюцинаций:** Если в законе нет ответа, ИИ об этом сообщит.
    *   **Со ссылками:** Ответ будет содержать конкретные пункты и статьи.
    *   **Анализ рисков:** Помощник укажет на возможные ошибки и слабые места в вашей позиции.
    """)

    law_choice = st.selectbox("Выберите базу знаний (Постановление):", 
                             ["ПП РФ №354", "ПП РФ №491", "ПП РФ №416"])
    
    # Большое поле для ввода контекста ситуации
    user_q = st.text_area(
        "Опишите ситуацию или задайте вопрос:", 
        height=250, 
        placeholder="Например: Управляющая компания отказывается делать перерасчет за отопление, ссылаясь на отсутствие актов..."
    )
    
    btn_send = st.button("🚀 Проанализировать ситуацию")
    
    if btn_send:
        if not api_key:
            st.error("Пожалуйста, введите OpenAI API Key в боковой панели слева!")
        elif not user_q:
            st.warning("Пожалуйста, опишите ситуацию перед отправкой.")
        else:
            file_path = f"knowledge_base/{law_choice}.pdf"
            
            if os.path.exists(file_path):
                with st.spinner("⏳ ИИ изучает текст постановления и анализирует вашу ситуацию..."):
                    context = get_pdf_text(file_path)
                    
                    try:
                        client = OpenAI(api_key=api_key)
                        
                        # Формируем сложный системный промпт для ИИ
                        system_prompt = f"""
                        Ты — ведущий юрист-эксперт в области ЖКХ. 
                        Твоя задача: провести глубокий анализ ситуации пользователя, используя ТОЛЬКО текст предоставленного документа ({law_choice}).
                        
                        ПРАВИЛА ОТВЕТА:
                        1. Отвечай строго на основе текста документа. Не используй общие знания из интернета.
                        2. Обязательно цитируй пункты и подпункты постановления.
                        3. Сначала дай краткий ответ: "Правомерно" или "Неправомерно".
                        4. Разложи ситуацию по полочкам: что говорит закон по каждому факту.
                        5. ОТДЕЛЬНЫМ БЛОКОМ укажи риски для пользователя и возможные ошибки.
                        6. Если в тексте документа нет информации по вопросу, прямо напиши: "В данном постановлении этот вопрос не урегулирован".
                        """
                        
                        response = client.chat.completions.create(
                            model="gpt-4o", # Рекомендую 4o для сложных юридических задач
                            messages=[
                                {"role": "system", "content": system_prompt},
                                {"role": "user", "content": f"ТЕКСТ ПОСТАНОВЛЕНИЯ:\n{context[:18000]}\n\nСИТУАЦИЯ ПОЛЬЗОВАТЕЛЯ:\n{user_q}"}
                            ],
                            temperature=0.1 # Делаем ответы максимально точными и сухими
                        )
                        
                        st.markdown("---")
                        st.subheader("📋 Экспертное заключение ИИ:")
                        st.markdown(response.choices[0].message.content)
                        
                    except Exception as e:
                        st.error(f"Ошибка при обращении к нейросети: {e}")
            else:
                st.error(f"Файл {law_choice}.pdf не найден. Пожалуйста, убедитесь, что он загружен в папку knowledge_base.")