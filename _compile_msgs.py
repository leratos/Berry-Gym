import polib

po = polib.pofile(r"C:\Dev\Berry-Gym\locale\en\LC_MESSAGES\django.po")
po.save_as_mofile(r"C:\Dev\Berry-Gym\locale\en\LC_MESSAGES\django.mo")
print(f"Compiled {len(po.translated_entries())} translations to django.mo")
