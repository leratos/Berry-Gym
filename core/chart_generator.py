"""Generiert Charts und Visualisierungen für PDF-Reports."""
import io
import base64
import matplotlib
matplotlib.use('Agg')  # Non-GUI backend
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.colors import LinearSegmentedColormap
import numpy as np


def generate_muscle_heatmap(muskelgruppen_stats):
    """
    Generiert eine Heatmap-Visualisierung der Muskelgruppen-Balance.
    
    Returns:
        str: Base64-encoded PNG image
    """
    if not muskelgruppen_stats:
        return None
    
    # Daten vorbereiten
    gruppen = []
    werte = []
    colors = []
    
    for mg in muskelgruppen_stats:
        gruppen.append(mg['name'].split('(')[0].strip())  # Nur Name ohne (Latein)
        werte.append(mg['saetze'])
        
        # Farbe basierend auf Status
        if mg['status'] == 'optimal':
            colors.append('#28a745')  # Grün
        elif mg['status'] == 'untertrainiert':
            colors.append('#ffc107')  # Gelb
        elif mg['status'] == 'uebertrainiert':
            colors.append('#dc3545')  # Rot
        else:
            colors.append('#6c757d')  # Grau
    
    # Chart erstellen
    fig, ax = plt.subplots(figsize=(10, 6))
    
    # Horizontale Bar Chart
    y_pos = np.arange(len(gruppen))
    bars = ax.barh(y_pos, werte, color=colors, edgecolor='black', linewidth=0.5)
    
    # Achsen beschriftung
    ax.set_yticks(y_pos)
    ax.set_yticklabels(gruppen, fontsize=9)
    ax.set_xlabel('Sätze (30 Tage)', fontsize=10, fontweight='bold')
    ax.set_title('Muskelgruppen-Balance Visualisierung', fontsize=12, fontweight='bold', pad=20)
    
    # Werte auf Balken anzeigen
    for i, (bar, wert) in enumerate(zip(bars, werte)):
        width = bar.get_width()
        ax.text(width + 0.5, bar.get_y() + bar.get_height()/2, 
                f'{wert}', 
                ha='left', va='center', fontsize=8, fontweight='bold')
    
    # Referenzlinien für optimalen Bereich (12-20 Sätze für die meisten Muskelgruppen)
    ax.axvline(x=12, color='green', linestyle='--', linewidth=1, alpha=0.5, label='Min. Optimal (12)')
    ax.axvline(x=20, color='green', linestyle='--', linewidth=1, alpha=0.5, label='Max. Optimal (20)')
    
    # Legende
    legend_elements = [
        mpatches.Patch(color='#28a745', label='Optimal'),
        mpatches.Patch(color='#ffc107', label='Untertrainiert'),
        mpatches.Patch(color='#dc3545', label='Übertrainiert'),
        mpatches.Patch(color='#6c757d', label='Nicht trainiert')
    ]
    ax.legend(handles=legend_elements, loc='lower right', fontsize=8)
    
    # Grid
    ax.grid(axis='x', alpha=0.3, linestyle=':', linewidth=0.5)
    ax.set_axisbelow(True)
    
    # Layout optimieren
    plt.tight_layout()
    
    # Als PNG in Base64 konvertieren
    buffer = io.BytesIO()
    plt.savefig(buffer, format='png', dpi=150, bbox_inches='tight')
    buffer.seek(0)
    image_base64 = base64.b64encode(buffer.read()).decode('utf-8')
    plt.close(fig)
    
    return image_base64


def generate_volume_chart(volumen_wochen):
    """
    Generiert ein Volumen-Entwicklungs-Chart über Wochen.
    
    Returns:
        str: Base64-encoded PNG image
    """
    if not volumen_wochen or len(volumen_wochen) < 2:
        return None
    
    wochen = [w['woche'] for w in volumen_wochen]
    volumen = [w['volumen'] for w in volumen_wochen]
    
    fig, ax = plt.subplots(figsize=(10, 4))
    
    # Line chart mit Area fill
    ax.plot(wochen, volumen, marker='o', linewidth=2, color='#0d6efd', markersize=8)
    ax.fill_between(range(len(wochen)), volumen, alpha=0.3, color='#0d6efd')
    
    # Beschriftung
    ax.set_xlabel('Kalenderwoche', fontsize=10, fontweight='bold')
    ax.set_ylabel('Trainingsvolumen (kg)', fontsize=10, fontweight='bold')
    ax.set_title('Trainingsvolumen-Entwicklung', fontsize=12, fontweight='bold', pad=20)
    
    # Werte auf Punkten anzeigen
    for i, (woche, vol) in enumerate(zip(wochen, volumen)):
        ax.text(i, vol + max(volumen)*0.03, f'{int(vol)}kg', 
                ha='center', va='bottom', fontsize=8, fontweight='bold')
    
    # Grid
    ax.grid(True, alpha=0.3, linestyle=':', linewidth=0.5)
    ax.set_axisbelow(True)
    
    # X-Achse lesbar machen
    plt.xticks(rotation=45, ha='right')
    
    plt.tight_layout()
    
    # Als PNG in Base64 konvertieren
    buffer = io.BytesIO()
    plt.savefig(buffer, format='png', dpi=150, bbox_inches='tight')
    buffer.seek(0)
    image_base64 = base64.b64encode(buffer.read()).decode('utf-8')
    plt.close(fig)
    
    return image_base64


def generate_push_pull_pie(push_saetze, pull_saetze):
    """
    Generiert ein Pie Chart für Push/Pull-Balance.
    
    Returns:
        str: Base64-encoded PNG image
    """
    if push_saetze == 0 and pull_saetze == 0:
        return None
    
    fig, ax = plt.subplots(figsize=(6, 6))
    
    labels = ['Push', 'Pull']
    sizes = [push_saetze, pull_saetze]
    colors = ['#ff6b6b', '#4ecdc4']
    explode = (0.05, 0.05)
    
    wedges, texts, autotexts = ax.pie(
        sizes, 
        explode=explode, 
        labels=labels, 
        colors=colors,
        autopct='%1.1f%%',
        startangle=90,
        textprops={'fontsize': 12, 'fontweight': 'bold'}
    )
    
    # Sätze-Anzahl hinzufügen
    for i, (label, size) in enumerate(zip(labels, sizes)):
        texts[i].set_text(f'{label}\n({size} Sätze)')
    
    ax.set_title('Push/Pull Balance', fontsize=14, fontweight='bold', pad=20)
    
    plt.tight_layout()
    
    # Als PNG in Base64 konvertieren
    buffer = io.BytesIO()
    plt.savefig(buffer, format='png', dpi=150, bbox_inches='tight')
    buffer.seek(0)
    image_base64 = base64.b64encode(buffer.read()).decode('utf-8')
    plt.close(fig)
    
    return image_base64
