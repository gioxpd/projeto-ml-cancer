import psycopg2
from werkzeug.security import generate_password_hash

# Conectando ao banco (altere os dados conforme seu PostgreSQL)
conn = psycopg2.connect(
    dbname='predicoes_ml',
    user='postgres',
    password='123456',
    host='localhost',
    port='5432'
)

cur = conn.cursor()

# Dados pra conseguir entrar
nome = "Giovanni"
email = "giovanni@exemplo.com"
senha = "senha123"  # Senha que você vai usar para login
senha_hash = generate_password_hash(senha)

# Inserção no banco
cur.execute("INSERT INTO usuarios (nome, email, senha) VALUES (%s, %s, %s)",
            (nome, email, senha_hash))

conn.commit()
cur.close()
conn.close()

print("Usuário criado com sucesso!")
