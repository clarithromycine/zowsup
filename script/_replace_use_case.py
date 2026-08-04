"""Replace CANONICAL -> DIGITAL_COMMERCE in canonical_credentials.py"""
path = r"d:\wisight_projects\zowsup\app\layer\canonical_credentials.py"
with open(path, "r", encoding="utf-8") as f:
    content = f.read()

count = content.count('"CANONICAL"')
content = content.replace('"CANONICAL"', '"DIGITAL_COMMERCE"')

with open(path, "w", encoding="utf-8") as f:
    f.write(content)

print(f"Changed {count} occurrences to DIGITAL_COMMERCE")
