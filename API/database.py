import pymysql


print("Script iniciado")

def get_database():
    return pymysql.connect(
    host="127.0.0.1",
    user="root",
    password="123456789",
    database="pap",
    autocommit=True,
    cursorclass=pymysql.cursors.DictCursor
    )



db = get_database() 
cursor = db.cursor()


cursor.execute("SELECT * FROM users") 
print(cursor.fetchall())