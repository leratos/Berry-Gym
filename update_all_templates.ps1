# PowerShell Script zum Hinzufügen des Theme-Toggles zu allen Templates
# Ausführen: .\update_all_templates.ps1

$templates = @(
    "plan_details.html", "create_plan.html", "edit_plan.html",
    "training_session.html", "training_select_plan.html", "training_list.html",
    "body_stats.html", "muscle_map.html", "equipment_management.html",
    "uebungen_auswahl.html", "uebung_detail.html", "ai_coach_chat.html",
    "stats_exercise.html", "progress_photos.html", "training_finish.html"
)

$templateDir = "core\templates\core"

# Theme Script + CSS Zeilen
$themeScript = '{% load static %}<script src="{% static ''core/js/theme-toggle.js'' %}"></script>'
$themeCss = '<link rel="stylesheet" href="{% static ''core/css/theme-styles.css'' %}">'

# Theme Button
$themeButton = @'
            <button onclick="toggleTheme()" class="btn btn-sm btn-outline-secondary border-0 ms-2" title="Theme wechseln">
              <i class="bi bi-moon-fill" id="themeIcon"></i>
            </button>
'@

foreach ($template in $templates) {
    $filePath = Join-Path $templateDir $template
    
    if (Test-Path $filePath) {
        Write-Host "Processing: $template" -ForegroundColor Cyan
        
        # Backup
        Copy-Item $filePath "$filePath.backup" -Force
        
        $content = Get-Content $filePath -Raw
        
        # 1. Add {% load static %} if not present
        if ($content -notmatch '{% load static %}') {
            $content = '{% load static %}' + "`n" + $content
        }
        
        # 2. Add theme script after {% load static %}
        if ($content -notmatch 'theme-toggle.js') {
            $content = $content -replace '({% load static %})', "`$1`n$themeScript"
        }
        
        # 3. Add id="htmlRoot" to html tag
        $content = $content -replace '<html lang="de" data-bs-theme="dark">', '<html lang="de" data-bs-theme="dark" id="htmlRoot">'
        
        # 4. Add theme CSS after bootstrap-icons
        if ($content -notmatch 'theme-styles.css') {
            $content = $content -replace '(bootstrap-icons@.*\.min\.css">)', "`$1`n    $themeCss"
        }
        
        # 5. Add theme button to navbar (verschiedene Layouts)
        if ($content -notmatch 'toggleTheme\(\)') {
            # Option A: Vor </div></div></nav>
            if ($content -match '</div>\s*</div>\s*</nav>') {
                $content = $content -replace '(</div>\s*)(</div>\s*</nav>)', "$themeButton`n`$1`$2"
            }
            # Option B: Vor </div></nav> (ohne doppeltes div)
            elseif ($content -match '</div>\s*</nav>') {
                $content = $content -replace '(</div>\s*</nav>)', "$themeButton`n`$1"
            }
        }
        
        # Speichern
        Set-Content $filePath -Value $content -NoNewline
        
        Write-Host "✅ Updated: $template" -ForegroundColor Green
    } else {
        Write-Host "❌ Not found: $template" -ForegroundColor Red
    }
}

Write-Host "`n✅ Alle Templates aktualisiert!" -ForegroundColor Green
Write-Host "🔄 Bitte Server neu starten: python manage.py runserver" -ForegroundColor Yellow
