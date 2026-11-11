from pathlib import Path
from models.course import Course

path=Path(__file__).parent/'data'/'smoke_course_v2.json'

with open(path,'r',encoding='utf-8') as f:
    course:Course=Course.load(path)
lessons=course.lessons

for mi,module in enumerate(course.curriculum.modules,1):
    for si,step in enumerate(module.steps,1):
        ex=lessons.get(f'm{mi}-s{si}',{}).exercise
        if not ex:
            continue
        print("=" * 70)
        print(f"m{mi}-s{si}  OBJECTIVE: {step.objective}\n")
        for path,code in ex.files.items():
            print(f"--- {path} ---\n{code}\n")
