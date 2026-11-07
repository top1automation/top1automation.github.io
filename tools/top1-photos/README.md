# Φωτογραφίες μοντέλων για το TOP1 site (εργαλείο, όχι μέρος του site)

Κλάδος μεταφοράς: οι φωτογραφίες κατεβαίνουν στον σταθμό AIGEN (το cloud δεν φτάνει Wikimedia) και ανεβαίνουν εδώ, για να μπουν στο προσχέδιο.

Στον σταθμό:
1. `cd tools/top1-photos && python3 fetch_photos.py` (χρειάζεται Pillow). Συνεχίζει από `out/cache.json` αν κοπεί.
2. `git add out/photos-*.webp out/credits.json out/review-*.jpg out/cache.json && git commit && git push` στον ίδιο κλάδο.

Μόνο εικόνες με CC0 / public domain / CC BY / CC BY-SA. Συγγραφέας και άδεια κάθε φωτογραφίας στο `out/credits.json` και στο footer του site.
Ο κλάδος δεν δημοσιεύεται (το GitHub Pages χτίζει μόνο από το main).

## Δεύτερο πέρασμα (διορθώσεις)
Μετά τον οπτικό έλεγχο, τα μοντέλα με λάθος φωτογραφία (λάθος άρθρο, άλλο αυτοκίνητο, παλιά γενιά, εσωτερικό, άδεια εκτός λίστας) μπαίνουν στο `fixes.json` με ακριβείς τίτλους άρθρων.
Στον σταθμό: `python3 fix_photos.py` και μετά `git add out/photos-*.webp out/credits.json out/review-*.jpg out/cache.json out/fix-report.txt && git commit && git push`.
Το `out/review-fixes.jpg` δείχνει μόνο τα διορθωμένα, για γρήγορο έλεγχο. Όσα δεν βρουν καλή ελεύθερη φωτογραφία μένουν με το σχήμα τους.
