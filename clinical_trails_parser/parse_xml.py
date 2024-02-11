import sqlite3
import os
import xml.etree.ElementTree as ET
from pathlib import Path
import click


def create_database(db_name):
    """
    Create a SQLite database with the specified name and a table for storing XML data.
    """
    # Connect to the SQLite database
    conn = sqlite3.connect(db_name)
    cursor = conn.cursor()

    # Create table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS studies (
        id INTEGER PRIMARY KEY,
        study_id TEXT,
        title TEXT,
        start_date TEXT,
        status TEXT,
        study_type TEXT,
        condition TEXT,
        phase TEXT
    )
    ''')
    conn.commit()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS interventions (
            id INTEGER PRIMARY KEY,
            intervention_type TEXT,
            intervention_name TEXT,
            studies_id INTEGER,
            FOREIGN KEY("studies_id") REFERENCES "studies"("id")
        )
        ''')
    conn.commit()
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS studies_id_index ON interventions (studies_id)
    ''')
    conn.commit()
    return conn


def insert_data_into_database(conn, data):
    """
    Insert data into the SQLite database.
    """
    cursor = conn.cursor()

    # Inserting data
    cursor.execute('''
    INSERT INTO studies (
        study_id,
        title,
        start_date,
        status,
        study_type,
        condition,
        phase
    ) VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', data)

    # conn.commit()
    return cursor.lastrowid


def insert_into_interventions(conn, type:str, name:str, id:int):
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO interventions (
            intervention_type,
            intervention_name,
            studies_id
        ) VALUES (?, ?, ?)
        ''', (type, name, id))

    # conn.commit()


def convert_date_format(date_str):
    from datetime import datetime
    # Parse the input string to a datetime object assuming the first day of the month
    try:
        date_obj = datetime.strptime(date_str, '%B %Y')
    except:
        date_obj = datetime.strptime(date_str, '%B %d, %Y')

    # Convert the datetime object back to a string in the desired format "YYYY-MM-DD"
    new_date_str = date_obj.strftime('%Y-%m-%d')

    return new_date_str

def parse_xml_and_insert(file_path, conn):
    """
    Parse the XML file and insert the data into the database.
    """
    tree = ET.parse(file_path)
    root = tree.getroot()

    # Extracting relevant information
    study_id = root.find('.//nct_id').text if root.find('.//nct_id') is not None else ''
    title = root.find('.//brief_title').text if root.find('.//brief_title') is not None else ''
    start_date = convert_date_format(root.find('.//start_date').text) if root.find('.//start_date') is not None else ''
    status = root.find('.//overall_status').text if root.find('.//overall_status') is not None else ''
    study_type = root.find('.//study_type').text if root.find('.//study_type') is not None else ''
    condition = root.find('.//condition').text if root.find('.//condition') is not None else ''


    phase = root.find('.//phase').text if root.find('.//phase') is not None else ''

    data = (study_id, title, start_date, status, study_type, condition, phase)

    # Insert data into database
    id = insert_data_into_database(conn, data)
    interventions = root.findall('.//intervention')
    for element in interventions:
        intervention_type = element.find('.//intervention_type').text if element is not None else ''
        intervention_name = element.find('.//intervention_name').text if element is not None else ''
        insert_into_interventions(conn, intervention_type, intervention_name, id)


def process_all_xml_files_in_folder(folder_path, conn, size = 0):
    counter:int = 0
    for subdir, _, files in os.walk(folder_path):
        for file in files:
            if file.endswith('.xml'):
                file_path = os.path.join(subdir, file)
                try:
                    parse_xml_and_insert(file_path, conn)
                    counter += 1
                    if counter % 1000 == 0:
                        print(f"processed: {counter}/{size}")
                        conn.commit()
                    # print(f"Processed file: {file_path}")
                except Exception as e:
                    print(f"Error processing file {file_path}: {e}")
    conn.commit()


def estimate_files(folder_path):
    sum:int = 0
    for subdir, _, files in os.walk(folder_path):
        sum += len(files)

    return sum

@click.command()
@click.option('--data_path', default="data",  help='path to the folder with folders with xml files')
@click.option('--database_name', default="studies_db.sqlite", help='database name')
def parse(data_path:str, database_name:str):
    conn = create_database(database_name)
    path = Path(data_path)
    size = estimate_files(path)
    process_all_xml_files_in_folder(path, conn, size)
    conn.close()

if __name__ == '__main__':
    parse()