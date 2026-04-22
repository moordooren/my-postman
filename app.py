import streamlit as st
import pandas as pd
from docx import Document
from docx.shared import Pt, Cm
from docx.enum.text import WD_ALIGN_PARAGRAPH
from io import BytesIO
from num2words import num2words
import datetime
# --- СКРЫВАЕМ ЛИШНИЕ ЭЛЕМЕНТЫ ИНТЕРФЕЙСА ---
hide_st_style = """
            <style>
            #MainMenu {visibility: hidden;}
            footer {visibility: hidden;}
            header {visibility: hidden;}
            .st-emotion-cache-18ni73i {vertical-align: middle;}
            </style>
            """
st.markdown(hide_st_style, unsafe_allow_html=True)
# Настройка страницы
st.set_page_config(page_title="Генератор уведомлений о долге ЖКХ", page_icon="⚖️")

def sum_to_words(amount):
    try:
        if pd.isna(amount) or amount <= 0:
            return ""
        rub = int(amount)
        kop = int(round((amount - rub) * 100))
        rub_words = num2words(rub, lang='ru').capitalize()
        return f"{rub_words} руб. {kop:02d} коп."
    except:
        return ""

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

st.title("⚖️ Генератор уведомлений о долге ЖКХ")

# 1. Данные взыскателя
st.subheader("1. Данные взыскателя (ТСЖ/УК)")
col1, col2 = st.columns(2)

with col1:
    vzyskatel_type = st.selectbox("Тип организации", ["ТСН", "ТСЖ", "ООО", "УК", "ЖСК", "ЖК"])
    vzyskatel_name = st.text_input("Название организации", "«СОЮЗ»")
    vzyskatel_ogrn = st.text_input("ОГРН", "1025500511904")
    vzyskatel_inn_kpp = st.text_input("ИНН/КПП", "5502047932/ 550101001")

with col2:
    vzyskatel_address = st.text_input("Юр. адрес", "644122, Омская область, г. Омск, ул. Красный Путь, д.34")
    signer_pos = st.text_input("Должность подписанта", "Председатель Правления")
    signer_name = st.text_input("ФИО подписанта", "А.А. Оботуров")

# 2. Загрузка данных
st.subheader("2. Данные должников")
uploaded_file = st.file_uploader("Выберите файл Excel", type="xlsx")

if not uploaded_file:
    st.download_button("📥 Скачать образец Excel", create_sample_excel(), "sample_jkh.xlsx")

if uploaded_file:
    df = pd.read_excel(uploaded_file)
    st.success(f"Файл загружен. Строк: {len(df)}")
    
    if st.button("🚀 Сформировать пакет уведомлений"):
        if len(df) > 100:
            st.warning("⚠️ В файле более 100 строк. Генерация может занять время.")
        
        doc = Document()
        style = doc.styles['Normal']
        style.font.name = 'Times New Roman'
        style.font.size = Pt(12)

        processed_count = 0
        for index, row in df.iterrows():
            try:
                val_sod = float(row['Долг содержания']) if pd.notna(row['Долг содержания']) else 0
                val_kap = float(row['Долг капремонт']) if pd.notna(row['Долг капремонт']) else 0
            except: 
                continue

            # Игнорируем отрицательные значения и нули
            if val_sod <= 0 and val_kap <= 0:
                continue

            processed_count += 1
            
            # Шапка
            header = doc.add_paragraph()
            header.alignment = WD_ALIGN_PARAGRAPH.RIGHT
            header.paragraph_format.space_after = Pt(0)
            # Стало:
            header_text = (
                f"Собственнику кв. (пом.) № {row['Помещение']} в доме № {row['Дом']} по\n"
                f"ул. {row['Улица']} в г. {row['Город']}\n" 
                f"{row['ФИО должника']}\n\n"
                f"От: {vzyskatel_type} {vzyskatel_name}\n"
                f"ОГРН {vzyskatel_ogrn}\n"
                f"ИНН/КПП {vzyskatel_inn_kpp}\n"
                f"Юр. адрес: {vzyskatel_address}\n"
            )
            header.add_run(header_text)

            # Заголовок
            title = doc.add_paragraph()
            title.alignment = WD_ALIGN_PARAGRAPH.CENTER
            title.paragraph_format.space_before = Pt(12)
            title.paragraph_format.space_after = Pt(12)
            title_run = title.add_run("ДОСУДЕБНОЕ УВЕДОМЛЕНИЕ")
            title_run.bold = True

            # Текст долга
            debt_phrases = []
            if val_sod > 0:
                p_sod = str(row['Period содержания']).strip() if 'Period содержания' in row and pd.notna(row['Period содержания']) and str(row['Period содержания']).strip() != "" else str(row['Период содержания']).strip() if 'Период содержания' in row and pd.notna(row['Период содержания']) and str(row['Период содержания']).strip() != "" else "____________________"
                debt_phrases.append(f"за содержание жилья составляет {val_sod} руб. ({sum_to_words(val_sod)}) за период {p_sod}")
            
            if val_kap > 0:
                p_kap = str(row['Period капремонт']).strip() if 'Period капремонт' in row and pd.notna(row['Period капремонт']) and str(row['Period капремонт']).strip() != "" else str(row['Период капремонт']).strip() if 'Период капремонт' in row and pd.notna(row['Период капремонт']) and str(row['Период капремонт']).strip() != "" else "____________________"
                debt_phrases.append(f"за капитальный ремонт: {val_kap} руб. ({sum_to_words(val_kap)}) за период {p_kap}")
            
            debt_full_str = " и ".join(debt_phrases)
            today = datetime.date.today().strftime('%d.%m.%Y')

            paragraphs = [
                f"{vzyskatel_type} {vzyskatel_name} доводит до Вашего сведения, что Ваша задолженность на {today} г. по оплате {debt_full_str}.",
                "Согласно ст. 153 Жилищного кодекса РФ, граждане обязаны своевременно и полностью вносить плату за жилое помещение и коммунальные услуги.",
                "В соответствии с ч. 14 ст. 155 Жилищного кодекса Российской Федерации лица, несвоевременно и (или) не полностью внесшие плату за жилое помещение и коммунальные услуги (должники), обязаны уплатить кредитору пени в размере одной трехсотой ставки рефинансирования ЦБ РФ, действующей на момент оплаты, от невыплаченных в срок сумм за каждый день просрочки, начиная со следующего дня после наступления установленного срока оплаты по день фактической выплаты включительно.",
                "В случае непогашения Вами вышеуказанной суммы задолженности в течение 10 дней со дня получения Вами настоящего уведомления, мы будем вынуждены обратиться в суд с заявлением о взыскании имеющейся задолженности и пени с отнесением на Вас судебных расходов, связанных с рассмотрением дела (государственной пошлины, расходов на оплату услуг представителя).",
                "Убедительно просим погасить задолженность.",
                f"По возникшим вопросам Вы можете обратиться в Правление {vzyskatel_type} {vzyskatel_name}."
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
            footer.add_run(f"{signer_pos} {vzyskatel_type} {vzyskatel_name}\n\n")
            footer.add_run(f"{signer_name}____________________")

            if index < len(df) - 1:
                doc.add_page_break()

        if processed_count > 0:
            target_doc = BytesIO()
            doc.save(target_doc)
            target_doc.seek(0)
            st.download_button(label="📥 СКАЧАТЬ ПАКЕТ УВЕДОМЛЕНИЙ", data=target_doc, file_name="uvedomleniya.docx")
        else:
            st.error("❌ Не найдено строк с положительным долгом. Проверьте файл.")

# --- ИНСТРУКЦИЯ И БЕЗОПАСНОСТЬ ---
st.markdown("---")
st.subheader("📖 Инструкция по работе")
st.info("""
1. **Данные компании:** Заполните все поля в разделе №1.
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
* Загружая данные, вы как Оператор ПДн подтверждаете соблюдение требований законодательства РФ. 
""")