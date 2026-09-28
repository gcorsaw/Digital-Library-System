import re
from pathlib import Path

p = Path("digital-library-system.sql")
text = p.read_text()

pat = re.compile(r"CREATE TABLE IF NOT EXISTS book_tracking \(.*?\n\);\r?\n", re.S)
m = pat.search(text)
assert m, "book_tracking CREATE TABLE not found"
block = m.group(0)

trig = "CREATE TRIGGER trigger_book_tracking_updated"
if text.index(trig) > m.start():
    print("Already in the right order - nothing to do.")
else:
    text = text[:m.start()] + text[m.end():]          # remove old spot
    i = text.index(trig)                               # insert before trigger
    text = text[:i] + block + "\n" + text[i:]
    p.write_text(text)
    print("Moved book_tracking above its trigger.")

t = p.read_text()
print("create at", t.index("CREATE TABLE IF NOT EXISTS book_tracking"),
      "| trigger at", t.index(trig),
      "| reading_progress at", t.index("CREATE TABLE IF NOT EXISTS reading_progress"))