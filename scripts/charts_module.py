# charts_module.py
# Version 1.0
import plotly.graph_objects as go

def generate_pie_chart_plotly(up_percentage, down_percentage, output_path):
    """
    Generate and save a pie chart image using Plotly.
    
    Args:
        up_percentage (float): Percentage of 'Up' status.
        down_percentage (float): Percentage of 'Down' status.
        output_path (str): File path where the PNG image will be saved.
    
    Note:
        Requires installation of Plotly and Kaleido.
        Install via: pip install plotly kaleido
    """
    labels = ['Up', 'Down']
    values = [up_percentage, down_percentage]
    fig = go.Figure(
        data=[go.Pie(labels=labels, values=values, hole=0.3, textinfo='label+percent')]
    )
    fig.write_image(output_path)
    print(f"Pie chart image saved at: {output_path}")

if __name__ == "__main__":
    # Example usage: Generate a pie chart with 70% Up and 30% Down.
    generate_pie_chart_plotly(70, 30, "up_down_pie_chart_plotly.png")
