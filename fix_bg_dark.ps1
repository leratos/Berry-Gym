# PowerShell Script zum Ersetzen von bg-dark in Cards
# Ausführen: .\fix_bg_dark.ps1

$templates = @(
    "plan_details.html", "create_plan.html", "edit_plan.html",
    "training_session.html", "training_list.html", "training_finish.html",
    "body_stats.html", "training_stats.html", "uebungen_auswahl.html",
    "uebung_detail.html", "progress_photos.html"
)

$templateDir = "core\templates\core"

foreach ($template in $templates) {
    $filePath = Join-Path $templateDir $template
    
    if (Test-Path $filePath) {
        Write-Host "Processing: $template" -ForegroundColor Cyan
        
        $content = Get-Content $filePath -Raw
        $changed = $false
        
        # Replace bg-dark in cards (not navbar or modal)
        # Pattern: <div class="card bg-dark ...">
        if ($content -match '<div class="card bg-dark') {
            $content = $content -replace '<div class="card bg-dark', '<div class="card card-stat'
            $changed = $true
        }
        
        # Pattern: <a ... class="card bg-dark ...">
        if ($content -match 'class="card bg-dark') {
            $content = $content -replace 'class="card bg-dark', 'class="card card-stat'
            $changed = $true
        }
        
        # Remove text-white from h4, h5 in cards
        if ($content -match '<h[45] class="text-white') {
            $content = $content -replace '<h([45]) class="text-white([^"]*)"', '<h$1 class="$2"'
            $content = $content -replace 'class=" ', 'class="'
            $content = $content -replace 'class=""', ''
            $changed = $true
        }
        
        # Remove standalone text-white from p, span in cards (keep text-muted)
        if ($content -match 'class="text-white mb-') {
            $content = $content -replace 'class="text-white mb-', 'class="mb-'
            $changed = $true
        }
        
        if ($changed) {
            Set-Content $filePath -Value $content -NoNewline
            Write-Host "✅ Updated: $template" -ForegroundColor Green
        } else {
            Write-Host "⏭️  Skipped: $template (no changes needed)" -ForegroundColor Yellow
        }
    } else {
        Write-Host "❌ Not found: $template" -ForegroundColor Red
    }
}

Write-Host "`n✅ Batch-Update abgeschlossen!" -ForegroundColor Green
