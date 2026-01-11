# Fix Script Tag Placement in All Templates
# Das Script-Tag muss im <head> sein, nicht davor!

$templates = @(
    "plan_details.html", "create_plan.html", "edit_plan.html",
    "training_session.html", "training_select_plan.html", "training_list.html",
    "body_stats.html", "muscle_map.html", "equipment_management.html",
    "uebungen_auswahl.html", "uebung_detail.html", "ai_coach_chat.html",
    "progress_photos.html", "training_finish.html"
)

$templateDir = "core\templates\core"

foreach ($template in $templates) {
    $filePath = Join-Path $templateDir $template
    
    if (Test-Path $filePath) {
        $content = Get-Content $filePath -Raw
        
        # Pattern 1: Script vor <!doctype html>
        if ($content -match '<script src="{% static ''core/js/theme-toggle.js'' %}"></script>\s*<!doctype html>') {
            # Entferne Script vor <!doctype
            $content = $content -replace '<script src="{% static ''core/js/theme-toggle.js'' %}"></script>\s*<!doctype html>', '<!doctype html>'
            
            # Füge Script im <head> nach theme-styles.css ein
            if ($content -match '<link rel="stylesheet" href="{% static ''core/css/theme-styles.css'' %}">') {
                $content = $content -replace '(<link rel="stylesheet" href="{% static ''core/css/theme-styles.css'' %}">\s*)', "`$1    <script src=`"{% static 'core/js/theme-toggle.js' %}`"></script>`n"
            }
            
            Set-Content $filePath -Value $content -NoNewline
            Write-Host "✅ Fixed: $template" -ForegroundColor Green
        } else {
            Write-Host "⏭️  OK: $template (already correct)" -ForegroundColor Yellow
        }
    }
}

Write-Host "`n✅ All templates checked!" -ForegroundColor Cyan
