import streamlit as st
import pandas as pd
import sqlite3
from sqlite3 import Connection
import openai
import io
import base64
import plotly.express as px
import plotly.graph_objs as go
import numpy as np
import re
from PIL import Image
from dateutil.parser import parse
import traceback


footer_html = """
    <div class="footer">
    <style>
        .footer {
            position: fixed;
            bottom: 0;
            left: 0;
            right: 0;
            background-color: #f0f2f6;
            padding: 10px 20px;
            text-align: center;
        }
        .footer a {
            color: #4a4a4a;
            text-decoration: none;
        }
        .footer a:hover {
            color: #3d3d3d;
            text-decoration: underline;
        }
    </style>
    </div>
"""

page_bg_img = f"""
<style>
[data-testid="stAppViewContainer"] > .main {{
background-image: url("https://i.postimg.cc/4xgNnkfX/Untitled-design.png");
background-size: cover;
background-position: center center;
background-repeat: no-repeat;
background-attachment: local;
}}
[data-testid="stHeader"] {{
background: rgba(0,0,0,0);
}}
</style>
"""


def create_connection(db_name: str) -> Connection:
    conn = sqlite3.connect(db_name)
    return conn

def run_query(conn: Connection, query: str) -> pd.DataFrame:
    df = pd.read_sql_query(query, conn)
    return df

def create_table(conn: Connection, df: pd.DataFrame, table_name: str):
    df.to_sql(table_name, conn, if_exists="replace", index=False)


def generate_gpt_reponse(gpt_input, max_tokens):

    # load api key from secrets
    openai.api_key = "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"

    completion = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        max_tokens=max_tokens,
        temperature=0,
        messages=[
            {"role": "user", "content": gpt_input},
        ]
    )

    gpt_response = completion.choices[0].message['content'].strip()
    return gpt_response


def extract_code(gpt_response):
    """function to extract code and sql query from gpt response"""

    if "```" in gpt_response:
        # extract text between ``` and ```
        pattern = r'```(.*?)```'
        code = re.search(pattern, gpt_response, re.DOTALL)
        extracted_code = code.group(1)

        # remove python from the code (weird bug)
        extracted_code = extracted_code.replace('python', '')

        return extracted_code
    else:
        return gpt_response


# wide layout
original_image = Image.open('Logo.jpg')

# Define the desired width and height for the resized image
desired_width = 600
desired_height = 100

# Resize the image
resized_image = original_image.resize((desired_width, desired_height))

# Convert the resized image to base64 for displaying in Streamlit
resized_image_bytes = io.BytesIO()
resized_image.save(resized_image_bytes, format='PNG')
resized_image_data = base64.b64encode(resized_image_bytes.getvalue()).decode("utf-8")

# Display the resized image in Streamlit
st.markdown(
    f'<img src="data:image/png;base64,{resized_image_data}" class="custom-image">',
    unsafe_allow_html=True
)

st.markdown(page_bg_img, unsafe_allow_html=True)

st.title('Query Your Data')

uploaded_file = st.file_uploader("Upload a CSV or XLSX file", type=["csv", "xlsx"])  # Allow CSV and XLSX files

if uploaded_file is None:
    st.info(f"""
                👆 Upload a .csv or .xlsx file first
                """)

elif uploaded_file:
    file_extension = uploaded_file.name.split(".")[-1].lower()

    if file_extension == 'csv':
        df = pd.read_csv(uploaded_file)
    elif file_extension == 'xlsx':
        df = pd.read_excel(uploaded_file)
    else:
        st.error("Invalid file format. Please upload a .csv or .xlsx file.")

    # Apply the custom function and convert date columns
    for col in df.columns:
        # check if a column name contains date substring
        if 'date' in col.lower():
            df[col] = pd.to_datetime(df[col])
            # remove timestamp
            #df[col] = df[col].dt.date

    # reset index
    df = df.reset_index(drop=True)

    # replace space with _ in column names
    df.columns = df.columns.str.replace(' ', '_')

    cols = df.columns
    cols = ", ".join(cols)

    with st.expander("Preview of the uploaded file"):
        st.table(df.head())

    conn = create_connection(":memory:")
    table_name = "my_table"
    create_table(conn, df, table_name)


    selected_mode = st.selectbox("What do you want to do?", ["Ask your data", "Create a chart"])

    if selected_mode == 'Ask your data':

        user_input = st.text_area("Write a concise and clear question about your data. For example: What is the total sales in the USA in 2022?", value='What is the total sales in the USA in 2022?')

        if st.button("Get Response"):

            try:
                # create gpt prompt
                gpt_input = 'Write a sql lite query based on this question: {} The table name is my_table and the table has the following columns: {}. ' \
                            'Return only a sql query and nothing else'.format(user_input, cols)

                query = generate_gpt_reponse(gpt_input, max_tokens=200)
                query_clean = extract_code(query)
                result = run_query(conn, query_clean)

                with st.expander("SQL query used"):
                    st.code(query_clean)

                # if result df has one row and one column
                if result.shape == (1, 1):

                    # get the value of the first row of the first column
                    val = result.iloc[0, 0]

                    # write one liner response
                    st.subheader('Your response: {}'.format(val))

                else:
                    st.subheader("Your result:")
                    st.table(result)

            except Exception as e:
                #st.error(f"An error occurred: {e}")
                st.error('Oops, there was an error :( Please try again with a different question.')

    elif selected_mode == 'Create a chart':

        user_input = st.text_area(
            "Briefly explain what you want to plot from your data. For example: Plot total sales by country and product category", value='Plot total sales by country and product category')

        if st.button("Create a visualization"):
            try:
                # create gpt prompt
                gpt_input = 'Write code in Python using Plotly to address the following request: {} ' \
                            'Use df that has the following columns: {}. Do not use animation_group argument and return only code with no import statements, use transparent background, the data has been already loaded in a df variable'.format(user_input, cols)

                gpt_response = generate_gpt_reponse(gpt_input, max_tokens=1500)

                extracted_code = extract_code(gpt_response)

                extracted_code = extracted_code.replace('fig.show()', 'st.plotly_chart(fig)')

                with st.expander("Code used"):
                    st.code(extracted_code)

                # execute code
                exec(extracted_code)

            except Exception as e:
                #st.error(f"An error occurred: {e}")
                #st.write(traceback.print_exc())
                st.error('Oops, there was an error :( Please try again with a different question.')

# footer
st.markdown(footer_html, unsafe_allow_html=True)



