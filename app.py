from flask import Flask, render_template, request

app = Flask(__name__)


PERIODOS_POR_AÑO = {
    'diaria': 365,       
    'quincenal': 24,
    'bimestral': 6,
    'mensual': 12,
    'trimestral': 4,
    'cuatrimestral': 3,
    'semestral': 2,
    'anual': 1
}

@app.route('/', methods=['GET', 'POST'])
def index():
    resultado = None
    error = None
    if request.method == 'POST':
        try:
            valor = float(request.form['valor']) / 100

            # Origen
            origen_tipo = request.form['origen_tipo']       
            origen_periodo = request.form['origen_periodo'] 

            # Destino
            destino_tipo = request.form['destino_tipo']
            destino_periodo = request.form['destino_periodo']

            # Anticipada o vencida
            tipo_tiempo = request.form['tipo_tiempo']

            # Ajuste si es anticipada (origen)
            if tipo_tiempo == 'anticipada' and origen_tipo in ['efectiva', 'nominal'] and origen_periodo != 'anual':
                valor = valor / (1 - valor)

            # --- Convertir a efectiva anual (TEA) ---
            n_origen = PERIODOS_POR_AÑO[origen_periodo]

            if origen_tipo == 'nominal':
                tasa_ea = (1 + valor / n_origen) ** n_origen - 1
            elif origen_tipo == 'efectiva':
                tasa_ea = (1 + valor) ** n_origen - 1
            else:
                tasa_ea = None

            # --- Convertir desde TEA a tasa destino ---
            n_destino = PERIODOS_POR_AÑO[destino_periodo]

            if destino_tipo == 'efectiva':
                resultado = (1 + tasa_ea) ** (1 / n_destino) - 1
            elif destino_tipo == 'nominal':
                resultado = (((1 + tasa_ea) ** (1 / n_destino)) - 1) * n_destino

        
            if tipo_tiempo == 'anticipada' and destino_tipo in ['efectiva', 'nominal'] and destino_periodo != 'anual':
                resultado = resultado / (1 + resultado)

            resultado *= 100

        except Exception:
            error = 'Error en los datos ingresados. Asegúrate de ingresar un número válido.'

    return render_template('index.html', resultado=resultado, error=error)

if __name__ == '__main__':
    app.run(debug=True)