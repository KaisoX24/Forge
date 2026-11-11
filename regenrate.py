import json
d = json.load(open("data/smoke_course_v2.json", encoding="utf-8"))
d["lessons"] = {}
d["failures"] = {}
json.dump(d, open("data/course_v3.json", "w", encoding="utf-8"), indent=2, ensure_ascii=False)
