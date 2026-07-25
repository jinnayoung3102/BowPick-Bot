import os
import json
import random
from http.server import BaseHTTPRequestHandler
import requests

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")

ROLES = ["기도자", "총괄", "PD", "TD", "팬틸트", "CAM 1번", "CAM 2번", "CAM 3번", "PC", "자막", "기술", "음향"]

ROLE_POOLS = {
    "총괄": ["강유주", "진나영", "강지은", "정봉주", "노유림"],
    "PD": ["진나영", "강지은", "김지은", "정봉주", "서태희", "전세정"],
    "TD": ["진나영", "서규우", "김지은", "안예진", "김소연", "김유진", "노유림", "서태희", "오예은", "전세정", "정은혜"],
    "팬틸트": ["진나영", "서규우", "김지은", "안예진", "김소연", "노유림", "박주영", "정은혜", "강예린", "한예준"],
    "CAM 1번": ["서규우", "안예진", "조관재", "허준서", "서태희"],
    "CAM 2번": ["서규우", "안예진", "조관재", "허준서", "서태희"],
    "CAM 3번": ["서규우", "안예진", "조관재", "허준서", "서태희"],
    "PC": ["진나영", "김지은", "김소연", "김유진", "노유림", "임규리", "박주영", "김혜진", "한예준"],
    "자막": ["진나영", "김유진", "노유림", "정유내", "김혜진"],
    "기술": ["강유주", "진나영", "서규우", "김지은", "노유림"],
    "음향": ["이경환", "김영식", "황윤대", "김민창", "김동민", "신정진", "김영준", "정유리"]
}

ROLE_PRIORITIES = {
    "총괄": ["정봉주", "강지은", "강유주", "진나영"],
    "PD": ["강지은", "전세정", "서태희", "정봉주", "김지은", "진나영"],
    "TD": ["오예은", "전세정", "정은혜"],
    "자막": ["노유림", "진나영"]
}

def auto_assign(available_staff: list, service_type: str = "수요정오예배") -> dict:
    assignment = {role: "-" for role in ROLES}
    pool = [s for s in available_staff if s]
    
    if not pool:
        return assignment

    prayer = random.choice(pool)
    assignment["기도자"] = f"{prayer} (랜덤)"

    assigned_persons = set()

    for role in ["PD", "자막", "PC"]:
        candidates = [p for p in pool if p in ROLE_POOLS.get(role, []) and p not in assigned_persons]
        priorities = ROLE_PRIORITIES.get(role, [])
        selected = None
        for p in priorities:
            if p in candidates:
                selected = p
                break
        if not selected and candidates:
            selected = candidates[0]
        
        if selected:
            assignment[role] = selected
            assigned_persons.add(selected)

    if assignment["PD"] != "-" and assignment["TD"] == "-":
        td_candidates = [p for p in pool if p in ROLE_POOLS.get("TD", []) and p not in assigned_persons]
        if td_candidates:
            assignment["TD"] = td_candidates[0]
            assigned_persons.add(td_candidates[0])
        else:
            assignment["TD"] = f"{assignment['PD']} (PD 겸직)"

    for role in ["총괄", "음향"]:
        candidates = [p for p in pool if p in ROLE_POOLS.get(role, []) and p not in assigned_persons]
        priorities = ROLE_PRIORITIES.get(role, [])
        selected = None
        for p in priorities:
            if p in candidates:
                selected = p
                break
        if not selected and candidates:
            selected = candidates[0]
        if selected:
            assignment[role] = selected
            assigned_persons.add(selected)

    is_wed = "수요" in service_type
    for role in ["CAM 1번", "CAM 2번", "CAM 3번", "팬틸트"]:
        candidates = [p for p in pool if p in ROLE_POOLS.get(role, []) and p not in assigned_persons]
        if candidates:
            assignment[role] = candidates[0]
            assigned_persons.add(candidates[0])
        elif is_wed and "CAM" in role:
            assignment[role] = "- (수요예배 미배치)"

    if assignment["기술"] == "-":
        tech_candidates = [p for p in pool if p in ROLE_POOLS.get("기술", []) and p not in assigned_persons]
        if tech_candidates:
            assignment["기술"] = tech_candidates[0]
        else:
            excluded = {assignment.get(r) for r in ["PD", "총괄", "음향", "CAM 1번", "CAM 2번", "CAM 3번"]}
            eligible = [p for p in pool if p in ROLE_POOLS.get("기술", []) and p not in excluded]
            if eligible:
                assignment["기술"] = f"{eligible[0]} (중복)"

    return assignment

class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps({"status": "ok"}).encode('utf-8'))
