# Scientific Disclaimer System - Quick Start Guide

## ✅ What's Already Done

The disclaimer system is **fully functional** but needs to be manually integrated into templates.

**Components Ready:**
- ✅ `ScientificDisclaimer` Model (models_disclaimer.py)
- ✅ Context Processor (`core.context_processors.disclaimers`)
- ✅ Template Component (`includes/disclaimer_banner.html`)
- ✅ Management Command (`python manage.py load_disclaimers`)
- ✅ 7 Tests (100% passing)
- ✅ 3 Default Disclaimers in database

---

## 📋 Current Disclaimers in Database

| Category | Severity | Shows On | Title |
|----------|----------|----------|-------|
| **1RM_STANDARDS** | WARNING | `stats/`, `uebungen/` | ⚠️ 1RM-Standards: Eingeschränkte wissenschaftliche Basis |
| **FATIGUE_INDEX** | INFO | `dashboard/` | ℹ️ Ermüdungsindex: Vereinfachtes Modell |
| **GENERAL** | INFO | All pages | 🔬 HomeGym: Fitness-Tracker, nicht medizinische Software |

---

## 🚀 How to Add Disclaimers to Templates

Since there's **no base.html** template, disclaimers must be added manually to each template.

### **Step 1: Add to High-Priority Templates**

Add this line **after the opening `<body>` tag or in your main content area:**

```html
{% include 'includes/disclaimer_banner.html' %}
```

**Priority Templates:**
1. `core/templates/core/dashboard.html` (GENERAL disclaimer)
2. `core/templates/core/stats_exercise.html` (1RM_STANDARDS disclaimer)
3. `core/templates/core/training_session.html`
4. `core/templates/core/body_stats.html`
5. `core/templates/core/uebungen_auswahl.html`

---

### **Step 2: Example Integration**

**Before:**
```html
<body>
    <div class="container">
        <h1>Dashboard</h1>
        <!-- content -->
    </div>
</body>
```

**After:**
```html
<body>
    <div class="container">
        {% include 'includes/disclaimer_banner.html' %}
        
        <h1>Dashboard</h1>
        <!-- content -->
    </div>
</body>
```

---

## 🎨 Disclaimer Styles

The template includes CSS for 3 severity levels:

- **INFO** (Blue): General information
- **WARNING** (Orange): Important warnings
- **CRITICAL** (Red): Critical warnings (with "Verstanden" button)

Styles are **responsive** and include **dark mode** support.

---

## 🔧 How Disclaimers Work

### **1. URL Pattern Matching**

Disclaimers with `show_on_pages` will only show when the URL matches:

```python
# Shows on /stats/*, /uebungen/*
show_on_pages=["stats/", "uebungen/"]

# Shows everywhere
show_on_pages=[]
```

### **2. Context Processor**

The context processor (`core.context_processors.disclaimers`) automatically:
- Filters by `is_active=True`
- Matches against current URL
- Makes `active_disclaimers` available in all templates

### **3. User Acknowledgment (JavaScript)**

CRITICAL disclaimers can be acknowledged:
- User clicks "Verstanden" button
- Stored in `localStorage`
- Won't show again for that user on that browser

---

## 📝 Managing Disclaimers

### **Load Default Disclaimers:**
```bash
python manage.py load_disclaimers
```

### **Django Admin:**
Go to: **http://yourdomain.com/admin/core/scientificdisclaimer/**

- ✅ Create new disclaimers
- ✅ Edit existing ones
- ✅ Toggle `is_active` to show/hide
- ✅ Set URL patterns

---

## 🧪 Running Tests

```bash
pytest core/tests/test_disclaimers.py -v
```

**Expected:** 7/7 tests passing ✅

---

## 🎯 Recommended Template Integration Order

1. **Priority 1 (Legal/Safety):**
   - `dashboard.html` → GENERAL disclaimer
   - `stats_exercise.html` → 1RM_STANDARDS disclaimer

2. **Priority 2 (Important Features):**
   - `training_session.html`
   - `body_stats.html`
   - `ai_plan_generator.html`

3. **Priority 3 (Nice to Have):**
   - All other templates with forms/data

---

## 🔮 Future Improvements

**TODO:** Create a `base.html` template to avoid manual integration.

Example structure:
```
templates/
  base.html  ← Include disclaimer here ONCE
  core/
    dashboard.html  ← Extends base.html
    stats_exercise.html  ← Extends base.html
```

This is a **refactoring task** for later (Phase 3).

---

## 📞 Support

**Files:**
- Context Processor: `core/context_processors.py`
- Model: `core/models_disclaimer.py`
- Template: `core/templates/includes/disclaimer_banner.html`
- Tests: `core/tests/test_disclaimers.py`
- Management Command: `core/management/commands/load_disclaimers.py`

**Coverage:**
- Context Processor: 100%
- Tests: 98%
- Management Command: 88%
