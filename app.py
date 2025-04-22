import psycopg2
from datetime import datetime
from flask import Flask, request, render_template, jsonify
import joblib
import numpy as np
import pandas as pd
from collections import Counter
from flask import Flask, render_template, request, redirect, url_for, session
from werkzeug.security import generate_password_hash, check_password_hash


# Cria o app Flask
app = Flask(__name__)
app.secret_key = 'segredo'

# Carrega o modelo
modelo = joblib.load('modelo_rg.pkl')

def conectar_banco():
    return psycopg2.connect(
        host="localhost",
        database="predicoes_ml",
        user="postgres",
        password="123456",
        port='5432'
    )

@app.route('/')
def index():
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        senha = request.form['senha']
        
        conn = conectar_banco()
        cur = conn.cursor()
        cur.execute("SELECT id, senha FROM usuarios WHERE email = %s", (email,))
        usuario = cur.fetchone()
        cur.close()
        conn.close()
        
        if usuario and check_password_hash(usuario[1], senha):
            session['usuario_id'] = usuario[0]
            return redirect(url_for('home'))
        else:
            return render_template('login.html', erro='Usuário ou senha incorretos.')
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))


@app.route('/home', methods=["GET", "POST"])
def home():
    if 'usuario_id' not in session:
        return redirect(url_for('login'))

    if request.method == "POST":
        try:
            # Verifica se os dados estão sendo enviados em JSON
            if request.is_json:
                dados = request.get_json()
                
                # Extraímos os dados enviados no JSON
                radius_mean = dados.get("radius")
                texture_mean = dados.get("texture")
                perimeter_mean = dados.get("perimeter")
                area_mean = dados.get("area")
            else:
                # Se não for JSON, pega os dados do formulário HTML
                radius_mean = float(request.form.get("radius"))
                texture_mean = float(request.form.get("texture"))
                perimeter_mean = float(request.form.get("perimeter"))
                area_mean = float(request.form.get("area"))
            
            # Verifica se todos os dados necessários foram fornecidos
            if None in [radius_mean, texture_mean, perimeter_mean, area_mean]:
                return jsonify({"erro": "Todos os campos são obrigatórios"}), 400

            # Agrupa os dados em um array para predição
            features = np.array([[radius_mean, texture_mean, perimeter_mean, area_mean]])
            
            # Realiza a predição
            previsao = modelo.predict(features)
            diagnostico = "Maligno" if previsao[0] == 1 else "Benigno"

            # Salva no banco
            conn = conectar_banco()
            cursor = conn.cursor()
            sql = """
                INSERT INTO predicoes (radius_mean, texture_mean, perimeter_mean, area_mean, diagnostico, data_hora)
                VALUES (%s, %s, %s, %s, %s, %s)
            """
            valores = (radius_mean, texture_mean, perimeter_mean, area_mean, diagnostico, datetime.now())
            cursor.execute(sql, valores)
            conn.commit()

            # Busca as predições após inserir
            cursor.execute("SELECT id, radius_mean, texture_mean, perimeter_mean, area_mean, diagnostico, data_hora FROM predicoes ORDER BY data_hora DESC")
            dados = cursor.fetchall()

            cursor.close()
            conn.close()
            
            if request.is_json:
                return jsonify({"predicao": diagnostico, "dados": dados}), 200

            # Caso contrário, renderiza o HTML com os dados
            return render_template("index.html", previsao=diagnostico, dados=dados)

        except Exception as e:
            if request.is_json:
                return jsonify({"erro": f"Erro: {str(e)}"}), 500
            return render_template("index.html", previsao=f"Erro: {e}")

    elif request.method == "GET" and request.args.get("ver_dados") == "1":
        try:
            conn = conectar_banco()
            cursor = conn.cursor()
            cursor.execute("SELECT id, radius_mean, texture_mean, perimeter_mean, area_mean, diagnostico, data_hora FROM predicoes ORDER BY data_hora DESC")
            dados = cursor.fetchall()
            cursor.close()
            conn.close()
            return render_template("index.html", previsao=None, dados=dados)
        except Exception as e:
            return render_template("index.html", previsao=f"Erro: {e}")

    return render_template('index.html')


@app.route('/dashboard')
def dashboard():
    try:
        conn = conectar_banco()
        cursor = conn.cursor()
        cursor.execute("SELECT radius_mean, texture_mean, perimeter_mean, area_mean, diagnostico, data_hora FROM predicoes ORDER BY data_hora DESC")
        registros = cursor.fetchall()
        cursor.close()
        conn.close()

        # Cria DataFrame para facilitar
        colunas = ['radius_mean', 'texture_mean', 'perimeter_mean', 'area_mean', 'diagnostico', 'data_hora']
        df = pd.DataFrame(registros, columns=colunas)

        # Contagem das classes
        contagem_classes = dict(Counter(df['diagnostico']))

        # Estatísticas básicas
        estatisticas = df.describe().to_dict()
        
        # Dados para gráfico de linha (evolução temporal)
        df['data_hora'] = pd.to_datetime(df['data_hora'])
        df['data_str'] = df['data_hora'].dt.strftime('%Y-%m-%d %H:%M')

        # Agrupando por data e diagnóstico
        evolucao = df.groupby(['data_str', 'diagnostico']).size().unstack(fill_value=0).reset_index()
        labels_temporais = evolucao['data_str'].tolist()
        benignos = evolucao.get('Benigno', pd.Series([0]*len(evolucao))).tolist()
        malignos = evolucao.get('Maligno', pd.Series([0]*len(evolucao))).tolist()
        
        

        return render_template("dashboard.html", contagem_classes=contagem_classes, estatisticas=estatisticas, registros=registros, labels_temporais=labels_temporais, 
                               benignos=benignos, malignos=malignos)
    
    except Exception as e:
        return f"Erro ao carregar dashboard: {e}"
    
# Rota para exibir as predições salvas
@app.route('/dados')
def dados():
    try:
        conn = conectar_banco()
        cursor = conn.cursor()
        cursor.execute("SELECT radius_mean, texture_mean, perimeter_mean, area_mean, diagnostico, data_hora FROM predicoes ORDER BY data_hora DESC")
        registros = cursor.fetchall()
        cursor.close()
        conn.close()
        return render_template("dados.html", registros=registros)
    except Exception as e:
        return f"Erro ao carregar dados: {e}"

# Rota para exportar as predições como CSV
from flask import Response
import csv

@app.route('/exportar')
def exportar():
    try:
        conn = conectar_banco()
        cursor = conn.cursor()
        cursor.execute("SELECT radius_mean, texture_mean, perimeter_mean, area_mean, diagnostico, data_hora FROM predicoes ORDER BY data_hora DESC")
        registros = cursor.fetchall()
        cursor.close()
        conn.close()

        def gerar_csv():
            yield 'radius_mean,texture_mean,perimeter_mean,area_mean,diagnostico,data_hora\n'
            for linha in registros:
                yield ','.join([str(valor) for valor in linha]) + '\n'

        return Response(gerar_csv(), mimetype='text/csv', headers={"Content-Disposition": "attachment;filename=predicoes.csv"})
    except Exception as e:
        return f"Erro ao exportar dados: {e}"


if __name__ == '__main__':
    app.run(debug=True)