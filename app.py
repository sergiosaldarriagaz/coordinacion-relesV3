import numpy as np
import streamlit as st
import plotly.graph_objects as go

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Coordinación 50/51", layout="wide") # 'wide' aprovecha mejor la pantalla
st.title("Estudio de Coordinación Dinámico (Multifalla)")

# --- 1. FUNCIONES MATEMÁTICAS ---
def curva_rele(I, I_p, dial, curva, I_tdef, T_def, tdef_habilitado):
    if I_p <= 0: return np.full_like(I, np.inf)
    constantes = {
        'IEC Normal Inversa': (0.14, 0.02, 0.0),
        'IEC Muy Inversa': (13.5, 1.0, 0.0),
        'IEC Extremadamente Inversa': (80.0, 2.0, 0.0),
        'ANSI Moderadamente Inversa': (0.0515, 0.02, 0.114),
        'ANSI Muy Inversa': (19.61, 2.0, 0.491),
        'ANSI Extremadamente Inversa': (28.2, 2.0, 0.1217)
    }
    K, alpha, B = constantes[curva]
    
    PSM = np.clip(I / I_p, 0, 20) 
    with np.errstate(divide='ignore', invalid='ignore'):
        t_curva = dial * (K / (PSM**alpha - 1) + B)
        t_curva = np.where(PSM >= 1.03, t_curva, np.inf)
        
    if tdef_habilitado:
        t_definido = np.where(I >= I_tdef, T_def, np.inf)
    else:
        t_definido = np.inf
        
    return np.minimum(t_curva, t_definido)

def dano_transformador(I_pu, P_mva, Z_cc):
    if P_mva <= 0 or Z_cc <= 0 or I_pu < 2 or I_pu > (1/Z_cc): return np.inf
    if P_mva <= 0.5 or Z_cc <= 0.04:
        return 19500 / (I_pu**3.8) if I_pu < 4.6 else 1250 / (I_pu**2)
    elif P_mva <= 5:
        if (Z_cc * I_pu) <= 0.7: return 19500 / (I_pu**3.8) if I_pu < 4.6 else 1250 / (I_pu**2)
        else: return 2 / ((I_pu**2) * (Z_cc**2))
    else:
        if (Z_cc * I_pu) <= 0.5: return 19500 / (I_pu**3.8) if I_pu < 4.6 else 1250 / (I_pu**2)
        else: return 2 / ((I_pu**2) * (Z_cc**2))

# --- 2. ESPACIO RESERVADO PARA LA GRÁFICA ---
plot_placeholder = st.empty()

# --- 3. INTERFAZ GRÁFICA ---
tab_reles, tab_trafos, tab_icc = st.tabs(["Relés (50/51)", "Transformadores", "Cortocircuitos (Icc)"])

reles_data = []
with tab_reles:
    # Usamos columnas para compactar la vista
    cols = st.columns(5)
    for i in range(5):
        with cols[i]:
            st.markdown(f"**Relé {i+1}**")
            hab_rele = st.checkbox("Activar", value=(i==0), key=f"r_hab_{i}")
            curva = st.selectbox("Curva", ['IEC Normal Inversa', 'IEC Muy Inversa', 'IEC Extremadamente Inversa', 'ANSI Moderadamente Inversa', 'ANSI Muy Inversa', 'ANSI Extremadamente Inversa'], key=f"r_curva_{i}", label_visibility="collapsed")
            ip = st.number_input("Ip (A)", value=100.0, step=10.0, min_value=0.0, key=f"r_ip_{i}")
            dial = st.number_input("Dial", value=1.0, step=0.1, min_value=0.0, key=f"r_dial_{i}")
            hab_tdef = st.checkbox("Hab. T. Def", value=True, key=f"r_habtdef_{i}")
            itdef = st.number_input("I Def (A)", value=1000.0, step=50.0, key=f"r_itdef_{i}")
            tdef = st.number_input("T Def (s)", value=0.1, step=0.05, min_value=0.0, key=f"r_tdef_{i}")
            reles_data.append({'hab': hab_rele, 'curva': curva, 'ip': ip, 'dial': dial, 'hab_tdef': hab_tdef, 'itdef': itdef, 'tdef': tdef})

trafos_data = []
with tab_trafos:
    cols_t = st.columns(2)
    for i in range(2):
        with cols_t[i]:
            st.markdown(f"**Transformador {i+1}**")
            hab_trafo = st.checkbox("Activar Trafo", value=(i==0), key=f"t_hab_{i}")
            mva = st.number_input("MVA", value=2.0, step=0.5, min_value=0.0, key=f"t_mva_{i}")
            zcc = st.number_input("Zcc (pu)", value=0.05, step=0.01, min_value=0.001, key=f"t_zcc_{i}")
            inom = st.number_input("I nom (A)", value=100.0, step=10.0, min_value=0.1, key=f"t_inom_{i}")
            trafos_data.append({'hab': hab_trafo, 'mva': mva, 'zcc': zcc, 'inom': inom})

icc_data = []
with tab_icc:
    cols_i = st.columns(3)
    for i in range(3):
        with cols_i[i]:
            hab_icc = st.checkbox(f"Activar Icc {i+1}", value=(i==0), key=f"icc_hab_{i}")
            val_icc = st.number_input(f"Icc {i+1} (A)", value=(1500.0 if i==0 else 500.0), step=100.0, min_value=0.0, key=f"icc_val_{i}")
        icc_data.append({'hab': hab_icc, 'val': val_icc})

# --- 4. LÓGICA DE GRAFICACIÓN CON PLOTLY ---
fig = go.Figure()
corrientes = np.logspace(1, 4, 1000) 
colores_reles = ['#1f77b4', '#d62728', '#2ca02c', '#9467bd', '#ff7f0e']
colores_icc = ['black', 'gray', 'brown']

# 1. Graficar Relés activos
for i, r in enumerate(reles_data):
    if r['hab'] and r['ip'] > 0:
        t = curva_rele(corrientes, r['ip'], r['dial'], r['curva'], r['itdef'], r['tdef'], r['hab_tdef'])
        t_plot = np.where(t == np.inf, np.nan, t) # Plotly maneja mejor los NaN que el inf
        fig.add_trace(go.Scatter(x=corrientes, y=t_plot, mode='lines', name=f'Relé {i+1} ({r["curva"]})', line=dict(color=colores_reles[i], width=3)))

# 2. Graficar Trafos activos
for i, t in enumerate(trafos_data):
    if t['hab'] and t['mva'] > 0 and t['inom'] > 0:
        c_pu = corrientes / t['inom']
        t_trafo = [dano_transformador(ipu, t['mva'], t['zcc']) for ipu in c_pu]
        t_trafo_plot = np.where(np.array(t_trafo) == np.inf, np.nan, t_trafo)
        fig.add_trace(go.Scatter(x=corrientes, y=t_trafo_plot, mode='lines', name=f'Trafo {i+1} Daño', line=dict(color='gray', width=2, dash='dashdot')))

# 3. Múltiples Puntos de cortocircuito
for j, icc in enumerate(icc_data):
    if icc['hab'] and icc['val'] > 0:
        I_falla = icc['val']
        # Agregar línea vertical
        fig.add_vline(x=I_falla, line_dash="dash", line_color=colores_icc[j], opacity=0.7, annotation_text=f" Icc {j+1}", annotation_position="top left")

        # Puntos de intersección
        for i, r in enumerate(reles_data):
            if r['hab'] and r['ip'] > 0:
                t_op = curva_rele(np.array([I_falla]), r['ip'], r['dial'], r['curva'], r['itdef'], r['tdef'], r['hab_tdef'])[0]
                if t_op != np.inf and not np.isnan(t_op):
                    fig.add_trace(go.Scatter(
                        x=[I_falla], y=[t_op],
                        mode='markers+text',
                        name=f'Op. R{i+1}',
                        text=[f' {t_op:.3f} s'],
                        textposition="middle right",
                        marker=dict(color=colores_reles[i], size=10, symbol='circle'),
                        textfont=dict(color=colores_reles[i], size=12, weight='bold'),
                        showlegend=False,
                        hoverinfo='text'
                    ))

# 4. Formato Profesional de la Gráfica
fig.update_layout(
    xaxis_type="log",
    yaxis_type="log",
    xaxis_range=[1, 4],  # log10(10) a log10(10000)
    yaxis_range=[-2, 3], # log10(0.01) a log10(1000)
    xaxis_title="Corriente (Amperios)",
    yaxis_title="Tiempo (Segundos)",
    height=600,
    margin=dict(l=50, r=50, t=30, b=50),
    template="plotly_white",
    hovermode="x unified",
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
)

# Actualizar grid
fig.update_xaxes(showgrid=True, gridwidth=1, gridcolor='LightGray', dtick=1)
fig.update_yaxes(showgrid=True, gridwidth=1, gridcolor='LightGray', dtick=1)

# --- 5. INYECTAR GRÁFICA ---
# Con Plotly, el redibujado es extremadamente rápido y fluido en la web
plot_placeholder.plotly_chart(fig, use_container_width=True)
