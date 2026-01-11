import os
import re

# Template-Verzeichnis
TEMPLATE_DIR = r"C:\Users\lerat\OneDrive\Projekt\App\Fitness\core\templates\core"

# Theme-Toggle Button HTML
THEME_BUTTON = '''<button onclick="toggleTheme()" class="btn btn-sm btn-outline-secondary border-0" title="Theme wechseln">
                  <i class="bi bi-moon-fill" id="themeIcon"></i>
              </button>'''

# Theme-Loading Script
THEME_SCRIPT = '''<script src="{% static 'core/js/theme-toggle.js' %}"></script>'''

# Theme CSS
THEME_CSS = '''<link rel="stylesheet" href="{% static 'core/css/theme-styles.css' %}">'''

def update_template(filepath):
    """Update ein einzelnes Template mit Theme-Support"""
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Backup
    backup_path = filepath + '.backup'
    with open(backup_path, 'w', encoding='utf-8') as f:
        f.write(content)
    
    # 1. data-bs-theme="dark" entfernen (wird von JS gesetzt)
    content = content.replace('data-bs-theme="dark"', 'data-bs-theme="dark" id="htmlRoot"')
    
    # 2. Theme CSS hinzufügen (nach Bootstrap)
    if 'bootstrap@5.3.3' in content and 'theme-styles.css' not in content:
        content = content.replace(
            'bootstrap-icons@1.11.3/font/bootstrap-icons.min.css">',
            'bootstrap-icons@1.11.3/font/bootstrap-icons.min.css">\n    ' + THEME_CSS
        )
    
    # 3. Theme JS hinzufügen (nach {% load static %})
    if '{% load static %}' in content and 'theme-toggle.js' not in content:
        content = content.replace(
            '{% load static %}',
            '{% load static %}\n' + THEME_SCRIPT
        )
    
    # 4. Theme-Toggle Button zur Navbar hinzufügen (rechts oben)
    # Suche nach </div> vor </nav> und füge Button ein
    if '<nav class="navbar' in content and 'toggleTheme()' not in content:
        # Finde letzte </div> vor </nav>
        nav_pattern = r'(</div>\s*</div>\s*</nav>)'
        if re.search(nav_pattern, content):
            # Button vor dem letzten </div> einfügen
            content = re.sub(
                r'(</div>)(\s*</div>\s*</nav>)',
                r'              ' + THEME_BUTTON + r'\n\1\2',
                content,
                count=1
            )
    
    # Speichern
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print(f"✅ Updated: {os.path.basename(filepath)}")

# Alle HTML-Templates finden
for root, dirs, files in os.walk(TEMPLATE_DIR):
    for file in files:
        if file.endswith('.html') and file != 'dashboard.html':  # Dashboard bereits fertig
            filepath = os.path.join(root, file)
            try:
                update_template(filepath)
            except Exception as e:
                print(f"❌ Error in {file}: {e}")

print("\n✅ Alle Templates aktualisiert!")
print("🔄 Bitte Server neu starten: python manage.py runserver")
