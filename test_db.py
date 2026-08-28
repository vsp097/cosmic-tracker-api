import psycopg2

try:
    conn = psycopg2.connect(
        host="localhost",
        port=5433,
        dbname="cosmic_tracker",
        user="postgres"
    )
    print("Conexión exitosa")
    conn.close()
except Exception as e:
    print(repr(e))