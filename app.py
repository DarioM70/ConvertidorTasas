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

# ---------- Conversión entre vencida y anticipada (por período) ----------
def anticipada_a_vencida(d):
    # d = tasa anticipada por período
    if d < 0:
        raise ValueError("La tasa anticipada no puede ser negativa.")
    if d >= 1:
        raise ValueError("La tasa anticipada por período debe ser < 100%.")
    return d / (1 - d)

def vencida_a_anticipada(i):
    # i = tasa vencida por período
    if i < 0:
        raise ValueError("La tasa no puede ser negativa.")
    return i / (1 + i)

# ---------- Puentes con TEA ----------
def tea_from_effective_period(i_p, n):
    # i_p = efectiva por período (vencida), n = periodos/año
    return (1 + i_p) ** n - 1

def effective_period_from_tea(tea, n):
    if tea < -0.9999999:
        raise ValueError("La TEA no puede ser menor o igual a -100%.")
    return (1 + tea) ** (1 / n) - 1

# ---------- Normalizador: origen -> i_p (efectiva por período, vencida) ----------
def to_effective_period_from_origin(valor_dec, origen_tipo, origen_periodo, tipo_tiempo_origen):
    """
    Devuelve (i_p, n) donde:
      - i_p = tasa efectiva por período (vencida) equivalente al ORIGEN
      - n   = periodos/año del periodo 'origen_periodo'
    Reglas:
      - efectiva (por período): solo vencida
      - efectiva_anual (TEA): solo vencida
      - nominal: vencida o anticipada
    """
    if valor_dec < 0:
        raise ValueError("La tasa no puede ser negativa.")

    if origen_periodo not in PERIODOS_POR_AÑO:
        raise ValueError("Período de origen inválido.")
    n = PERIODOS_POR_AÑO[origen_periodo]

    if origen_tipo == 'efectiva':
        # Efectiva por período (vencida). Si ponen anticipada -> error.
        if tipo_tiempo_origen != 'vencida':
            raise ValueError("La tasa efectiva por período solo puede ser vencida (no anticipada).")
        i_p = valor_dec

    elif origen_tipo == 'efectiva_anual':
        # TEA -> i_p del período elegido
        if tipo_tiempo_origen != 'vencida':
            raise ValueError("La TEA (efectiva anual) solo puede ser vencida (no anticipada).")
        i_p = effective_period_from_tea(valor_dec, n)

    elif origen_tipo == 'nominal':
        # nominal anual convertible n veces -> por-período r_p
        r_p = valor_dec / n
        if tipo_tiempo_origen == 'vencida':
            i_p = r_p
        elif tipo_tiempo_origen == 'anticipada':
            # Validar que r_p < 1 para poder llevar a vencida
            if r_p >= 1:
                raise ValueError("Con nominal anticipada, la tasa por período debe ser < 100%.")
            i_p = anticipada_a_vencida(r_p)
        else:
            raise ValueError("Timing de origen inválido.")
    else:
        raise ValueError("Tipo de origen inválido.")

    return i_p, n

@app.route('/', methods=['GET', 'POST'])
def index():
    resultado = None
    etiqueta = None
    error = None

    # Para re-hidratar selects si falla
    form_vals = {
        'valor': '',
        'origen_tipo': '',
        'origen_periodo': '',
        'tipo_tiempo_origen': '',
        'destino_tipo': '',
        'destino_periodo': '',
        'tipo_tiempo_destino': ''
    }

    if request.method == 'POST':
        try:
            # Valor base en decimal (ej: 18% -> 0.18)
            valor = float(request.form['valor']) / 100.0
            form_vals['valor'] = request.form['valor']

            # Origen
            origen_tipo = request.form['origen_tipo']                 # 'efectiva' | 'efectiva_anual' | 'nominal'
            origen_periodo = request.form['origen_periodo']           # clave PERIODOS_POR_AÑO
            tipo_tiempo_origen = request.form['tipo_tiempo_origen']   # 'vencida' | 'anticipada'
            form_vals['origen_tipo'] = origen_tipo
            form_vals['origen_periodo'] = origen_periodo
            form_vals['tipo_tiempo_origen'] = tipo_tiempo_origen

            # Destino
            destino_tipo = request.form['destino_tipo']               # 'efectiva' | 'efectiva_anual' | 'nominal'
            destino_periodo = request.form['destino_periodo']         # clave PERIODOS_POR_AÑO
            tipo_tiempo_destino = request.form['tipo_tiempo_destino'] # 'vencida' | 'anticipada'
            form_vals['destino_tipo'] = destino_tipo
            form_vals['destino_periodo'] = destino_periodo
            form_vals['tipo_tiempo_destino'] = tipo_tiempo_destino

            # Validación: efectiva/TEA no pueden ser anticipadas (en origen ni destino)
            if origen_tipo in ('efectiva', 'efectiva_anual') and tipo_tiempo_origen != 'vencida':
                raise ValueError("Las tasas efectivas (periódica o anual) solo pueden ser vencidas.")
            if destino_tipo in ('efectiva', 'efectiva_anual') and tipo_tiempo_destino != 'vencida':
                raise ValueError("Las tasas efectivas (periódica o anual) solo pueden ser vencidas.")

            # 1) ORIGEN -> i_p (efectiva por período, vencida)
            i_p_origen, n_origen = to_effective_period_from_origin(
                valor, origen_tipo, origen_periodo, tipo_tiempo_origen
            )

            # 2) i_p -> TEA (siempre vencida)
            tea = tea_from_effective_period(i_p_origen, n_origen)

            # 3) Convertir TEA -> i_p_dest (efectiva por período, vencida) del período destino
            if destino_periodo not in PERIODOS_POR_AÑO:
                raise ValueError("Período de destino inválido.")
            n_dest = PERIODOS_POR_AÑO[destino_periodo]
            i_p_dest = effective_period_from_tea(tea, n_dest)

            # 4) Formar la salida según DESTINO y timing de DESTINO
            if destino_tipo == 'efectiva':
                # Efectiva por período (vencida)
                resultado_dec = i_p_dest
                etiqueta = f"Efectiva {destino_periodo} (vencida)"

            elif destino_tipo == 'efectiva_anual':
                # TEA
                resultado_dec = tea
                etiqueta = "Efectiva anual (TEA)"

            elif destino_tipo == 'nominal':
                # Nominal anual convertible n_dest
                if tipo_tiempo_destino == 'vencida':
                    resultado_dec = i_p_dest * n_dest
                    etiqueta = f"Nominal anual convertible {destino_periodo} (vencida)"
                elif tipo_tiempo_destino == 'anticipada':
                    d_p_dest = vencida_a_anticipada(i_p_dest)
                    resultado_dec = d_p_dest * n_dest
                    etiqueta = f"Nominal anual convertible {destino_periodo} (anticipada)"
                else:
                    raise ValueError("Timing de destino inválido.")
            else:
                raise ValueError("Tipo de destino inválido.")

            resultado = resultado_dec * 100.0

        except ValueError as ve:
            error = str(ve)
        except Exception:
            error = 'Error en los datos ingresados. Revisa valores y opciones.'

    return render_template('index.html', resultado=resultado, etiqueta=etiqueta, error=error, form_vals=form_vals, periodos=PERIODOS_POR_AÑO.keys())

if __name__ == '__main__':
    from os import environ
    port = int(environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)