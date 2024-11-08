from flask import Flask, render_template, request, jsonify, redirect, url_for
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import plotly.io as pio
import io

app = Flask(__name__)

# Global variable to store the warning message
warning_message = ""

def parse_data(file_content, temperature, humidity):
    global warning_message
    data = []
    
    # Calculate sensor errors at the start
    
    
    # Add additional warnings based on temperature thresholds
    if float(temperature) > 35:
        warning_message += "\n\nWARNING: High temperature may significantly affect sensor accuracy!"
    elif float(temperature) < 10:
        warning_message += "\n\nWARNING: Low temperature may significantly affect sensor accuracy!"
    
    # Add humidity warnings
    if float(humidity) > 85:
        warning_message += "\n\nWARNING: High humidity may affect dust sensor readings!"
    elif float(humidity) < 30:
        warning_message += "\n\nWARNING: Low humidity may affect gas sensor sensitivity!"

    current_altitude = None
    current_location = None
    current_windspeed = None
    current_temperature = None
    current_time = None
    
    for line in file_content.split('\n'):
        if line.startswith('Altitude='):
            parts = line.split(';')
            current_altitude = float(parts[0].split('=')[1].split('m')[0].strip())
            current_location = parts[1].split('=')[1].strip()
            current_windspeed = float(parts[2].split('=')[1].split('km/hr')[0].strip())
            current_temperature = float(parts[3].split('=')[1].split("'C")[0].strip())
            current_time = parts[4].split('=')[1].strip()
            
            # Check if the temperature is greater than 25
            #if current_temperature > 25:
            #    warning_message = "Since the temperature is greater than 25 degrees, expect an error of 5%."
        
        elif 'CO Concentration:' in line:
            parts = line.split('|')
            time = parts[0].split(':')[3].strip()
            co = float(parts[1].split(':')[1].strip().split()[0])
            h2 = float(parts[2].split(':')[1].strip().split()[0])
            dust = float(parts[3].split(':')[1].strip().split()[0])
            data.append({
                'Altitude': current_altitude,
                'Location': current_location,
                'Windspeed': current_windspeed,
                'Temperature': current_temperature,
                'Timestamp': current_time,
                'Time': time,
                'CO': co,
                'H2': h2,
                'Dust': dust
            })
    return pd.DataFrame(data)

def create_detailed_graphs(df):
    graphs = {}
    
   
    fig = make_subplots(rows=3, cols=1, shared_xaxes=True, vertical_spacing=0.02,
                        subplot_titles=("CO Concentration", "H2 Concentration", "Dust Concentration"))
    
    for i, metric in enumerate(['CO', 'H2', 'Dust'], 1):
        for altitude in df['Altitude'].unique():
            df_alt = df[df['Altitude'] == altitude]
            fig.add_trace(go.Scatter(x=df_alt['Time'], y=df_alt[metric], name=f'{metric} at {altitude}m',
                                     mode='lines+markers'), row=i, col=1)
    
    fig.update_layout(height=900, title_text="Air Quality Metrics Over Time at Different Altitudes",
                      showlegend=True, legend_title="Metrics and Altitudes")
    fig.update_xaxes(title_text="Time", row=3, col=1)
    fig.update_yaxes(title_text="ppm", row=1, col=1)
    fig.update_yaxes(title_text="ppm", row=2, col=1)
    fig.update_yaxes(title_text="µg/m³", row=3, col=1)
    
    graphs['time_series'] = pio.to_json(fig)
    
    
    fig_3d = go.Figure(data=[go.Scatter3d(
        x=df['CO'],
        y=df['H2'],
        z=df['Dust'],
        mode='markers',
        marker=dict(
            size=5,
            color=df['Altitude'],
            colorscale='Viridis',
            opacity=0.8
        ),
        text=[f"Altitude: {a}m<br>Time: {t}<br>CO: {c} ppm<br>H2: {h} ppm<br>Dust: {d} µg/m³" 
              for a, t, c, h, d in zip(df['Altitude'], df['Time'], df['CO'], df['H2'], df['Dust'])],
        hoverinfo='text'
    )])
    
    fig_3d.update_layout(scene=dict(
        xaxis_title='CO (ppm)',
        yaxis_title='H2 (ppm)',
        zaxis_title='Dust (µg/m³)'),
        title="3D Scatter Plot of Air Quality Metrics"
    )
    
    graphs['3d_scatter'] = pio.to_json(fig_3d)
    
    
    for metric in ['CO', 'H2', 'Dust']:
        fig_box = go.Figure()
        for altitude in sorted(df['Altitude'].unique()):
            fig_box.add_trace(go.Box(y=df[df['Altitude'] == altitude][metric], name=f'{altitude}m'))
        
        fig_box.update_layout(title_text=f"{metric} Distribution by Altitude",
                              xaxis_title="Altitude (m)",
                              yaxis_title=f"{metric} Concentration ({'µg/m³' if metric == 'Dust' else 'ppm'})")
        
        graphs[f'{metric.lower()}_box'] = pio.to_json(fig_box)
    
    return graphs
def calculate_sensor_errors(temperature, humidity):
    # Reference values
    T_ref_mq7_mq8 = 25  # °C
    T_ref_dust = 25     # °C
    H_ref_mq7 = 70      # %
    H_ref_mq8 = 70    # %
    H_ref_dust = 70     # %
    
    # Temperature and humidity as floats
    T = float(temperature)
    H = float(humidity)
    
    # Calculate errors for each sensor
    # MQ7 (CO Sensor)
    mq7_error = abs(0.01 * (T - T_ref_mq7_mq8) + 0.02 * (H - H_ref_mq7)) * 100
    
    # MQ8 (H2 Sensor)
    mq8_error = abs(0.015 * (T - T_ref_mq7_mq8) + 0.025 * (H - H_ref_mq8)) * 100
    
    # Dust Sensor
    dust_error = abs(0.005 * (T - T_ref_dust) + 0.03 * (H - H_ref_dust)) * 100
    
    return {
        'CO': round(mq7_error, 2),
        'H2': round(mq8_error, 2),
        'Dust': round(dust_error, 2)
    }
    
@app.route('/', methods=['GET', 'POST'])
# def index():
    # if request.method == 'POST':
        # file = request.files['file']
        # if file:
            # file_content = file.read().decode('utf-8')
            # df = parse_data(file_content)
            # graphs = create_detailed_graphs(df)
            # return jsonify(graphs)
    # return render_template('index.html')

# if _name_ == '_main_':
    # app.run(debug=True)
def upload_page():
    return render_template('index.html')
@app.route('/upload', methods=['POST'])
def upload_file():
    global graphs, warning_message
    try:
        if 'file' not in request.files:
            return "No file part", 400  
        
        file = request.files['file']
        
        if file.filename == '':
            return "No selected file", 400 
        
        temperature = request.form.get('temperature')
        humidity = request.form.get('humidity')
        
        errors = calculate_sensor_errors(temperature, humidity)
    
    # Set warning message based on environmental conditions
        warning_message = (
            f"Environmental Condition Effects on Sensor Accuracy:\n"
            f"• CO Sensor: ±{errors['CO']}% error\n"
            f"• H2 Sensor: ±{errors['H2']}% error\n"
            f"• Dust Sensor: ±{errors['Dust']}% error\n"
            f"(at Temperature: {temperature}°C, Humidity: {humidity}%)"
        )
        
        if not temperature or not humidity:
            return jsonify({'error': 'Temperature and humidity are required'}), 400
            
        # Read and parse file content with temperature and humidity
        file_content = file.read().decode('utf-8')
        df = parse_data(file_content, temperature, humidity)
        
        # Create graphs
        graphs = create_detailed_graphs(df)
        
        return jsonify({'status': 'success'})
        
    except Exception as e:
        print(f"Unexpected error in upload_file: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/result')
def result_page():
    return render_template('result.html', warning=warning_message)


@app.route('/get_graphs')
def get_graphs():
    
    global graphs
    return jsonify(graphs)

if __name__ == '__main__':
    app.run(debug=True)