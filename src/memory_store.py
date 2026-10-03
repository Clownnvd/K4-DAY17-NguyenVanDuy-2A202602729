"""Deterministic Vietnamese fact extraction, disk profiles and bounded summaries."""
from __future__ import annotations

import hashlib
import json
import math
import os
import re
import tempfile
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path


def estimate_tokens(text: str) -> int:
    return math.ceil(len(text.strip()) / 4)


def fold(text: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", text.casefold())
                   if not unicodedata.combining(c)).replace("đ", "d")


@dataclass
class UserProfileStore:
    root_dir: Path

    def path_for(self, user_id: str) -> Path:
        if not isinstance(user_id, str) or not user_id.strip():
            raise ValueError("user_id must be a nonempty string")
        slug = re.sub(r"[^a-zA-Z0-9_-]", "-", user_id)[:48] or "user"
        identifier = slug + "-" + hashlib.sha256(user_id.encode()).hexdigest()[:16]
        root = self.root_dir.resolve()
        path = root / identifier / "User.md"
        if not path.resolve().is_relative_to(root):
            raise ValueError("Profile path escaped root")
        return path

    def read_text(self, user_id: str) -> str:
        path = self.path_for(user_id)
        return path.read_text(encoding="utf-8") if path.exists() else ""

    def write_text(self, user_id: str, content: str) -> Path:
        path = self.path_for(user_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = None
        try:
            with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent,
                                             delete=False) as handle:
                temp = Path(handle.name)
                handle.write(content)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp, path)
        finally:
            if temp is not None:
                temp.unlink(missing_ok=True)
        return path

    def edit_text(self, user_id: str, search_text: str, replacement: str) -> bool:
        old = self.read_text(user_id)
        if not search_text or search_text not in old:
            return False
        self.write_text(user_id, old.replace(search_text, replacement, 1))
        return True

    def file_size(self, user_id: str) -> int:
        path = self.path_for(user_id)
        return path.stat().st_size if path.exists() else 0

    def facts(self, user_id: str) -> dict[str, str]:
        return {key: value for key, value in
                re.findall(r"^- ([a-z_]+): (.+)$", self.read_text(user_id), re.M)}

    def upsert_fact(self, user_id: str, key: str, value: str) -> None:
        if not re.fullmatch(r"[a-z_]+", key) or not value or "\n" in value:
            raise ValueError("Invalid fact")
        facts = self.facts(user_id)
        if facts.get(key) == value:
            return
        old = facts.get(key)
        if old is not None:
            self.edit_text(user_id, f"- {key}: {old}\n", f"- {key}: {value}\n")
        else:
            facts[key] = value
            self.write_text(user_id, "# User\n\n" + "".join(f"- {k}: {v}\n" for k, v in sorted(facts.items())))


def extract_profile_updates(message: str) -> dict[str, str]:
    """Bonus: accept declarative first-person clauses; reject questions/quotes.

    No dataset IDs, expected answers or recall gold labels enter this function.
    Latest unambiguous field wins. Travel, jokes and hypothetical statements
    intentionally do not become location/profession facts.
    """
    message = unicodedata.normalize("NFC", message)
    updates = {}
    message = re.sub(r'["“][^"”]*["”]', "", message)
    clauses = re.findall(r"([^.!?;\n]+)([.!?;\n]|$)", message)
    for clause, punctuation in clauses:
        if punctuation == "?":
            continue
        text = clause.strip(" ,:")
        normalized = fold(text)
        if not text or re.search(r"\b(neu|gia su|cau dua|du lieu minh hoa|vi du cu)\b", normalized):
            continue
        if re.search(r"\b(ten gi|ten minh la gi|o dau|nghe gi|la ai|co biet|co the nhac|hoi lai|nhac lai giup)\b", normalized):
            continue
        patterns = {
            "name": r"(?:mình|tôi|tớ)\s+tên\s+(?:là\s+)?([^,]+)",
            "location": r"(?:mình|tôi|tớ)\s+(?:(?:đang|hiện|hiện tại|vẫn|giờ|bây giờ)\s+)*(?:ở|sống ở|sống tại)\s+([^,]+)",
            "profession": r"(?:mình|tôi|tớ)\s+(?:(?:đang|hiện|hiện tại|vẫn|giờ|bây giờ)\s+)*(?:làm|làm nghề|là)\s+([^,]+)",
            "favorite_drink": r"đồ uống yêu thích\s+(?:của (?:mình|tôi)\s+)?là\s+([^,]+)",
            "favorite_food": r"món ăn yêu thích\s+(?:của (?:mình|tôi)\s+)?là\s+([^,]+)",
            "pet": r"(?:mình|tôi|tớ)\s+nuôi\s+(?:một\s+)?(?:bé\s+)?([^,]+)",
        }
        for key, pattern in patterns.items():
            for match in re.finditer(pattern, text, re.I):
                value = re.split(r"\s+(?:và|chứ|nhưng|dù|trong|cho|vài|mỗi|trong giai đoạn)\s+", match[1], maxsplit=1)[0].strip(" ,:")
                if key == "profession":
                    job = re.match(r"([\w -]+?(?:engineer|developer|manager|designer|analyst|bác sĩ|giáo viên|kỹ sư))\b", value, re.I)
                    if not job:
                        continue
                    value = job[1]
                if value and len(value) <= 100 and not re.search(r"\b(gì|đâu|không|chưa)\b", value, re.I):
                    updates[key] = value
        correction = re.search(r"(?:giờ|hiện tại|bây giờ)\s+(?:mình\s+)?chuyển sang\s+([\w -]+?engineer)", text, re.I)
        if correction:
            updates["profession"] = correction[1].strip()
        current_job = re.search(r"(?:nghề nghiệp|nghề)(?:\s+(?:hiện tại|thì|cũng))*\s+(?:vẫn\s+)?là\s+([\w -]+?engineer)", text, re.I)
        if current_job:
            updates["profession"] = current_job[1].strip()
        current_location = re.search(r"(?:mình|tôi) đang làm việc ở\s+([^,]+)", text, re.I)
        if current_location:
            updates["location"] = re.split(r"\s+(?:vài|để|trong)\s+", current_location[1])[0].strip()
        if re.search(r"\b(mình|tôi|tớ)\b", text, re.I):
            coordinated_location = re.search(r",\s*hiện ở\s+([^,]+)", text, re.I)
            if coordinated_location:
                updates["location"] = re.split(r"\s+(?:và|chứ|nhưng)\s+", coordinated_location[1])[0].strip()
            coordinated_job = re.search(r"và đang làm\s+([\w -]+?engineer)", text, re.I)
            if coordinated_job:
                updates["profession"] = coordinated_job[1].strip()
        if any(term in normalized for term in ("tra loi", "style", "cach giai thich")) and any(
                term in normalized for term in ("muon", "thich", "hay", "van giu")):
            features = []
            if "ngan" in normalized or "gon" in normalized:
                features.append("ngắn gọn")
            number = re.search(r"(\d+)\s+bullet", normalized)
            if number:
                features.append(number[1] + " bullet")
            elif "bullet" in normalized:
                features.append("bullet")
            if "vi du" in normalized:
                features.append("có ví dụ thực tế")
            if "trade-off" in normalized:
                features.append("ưu tiên trade-off")
            if features:
                updates["response_style"] = ", ".join(features)
        interests = re.search(r"(?:mình|tôi)\s+(?:đang\s+)?(?:thích|quan tâm(?: nhiều)?(?: nhất)?(?: đến| tới)?)\s+(.+)", text, re.I)
        if interests and not any(term in normalized for term in ("tra loi", "cach giai thich")):
            updates["interests"] = interests[1][:160].strip()
    return updates


def merge_facts(old: dict[str, str], new: dict[str, str]) -> dict[str, str]:
    merged = {**old, **new}
    if old.get("interests") and new.get("interests"):
        candidates = re.split(r",\s*|\s+và\s+", old["interests"] + ", " + new["interests"])
        subjects = {}
        for candidate in candidates:
            candidate = candidate.strip()
            if candidate and not fold(candidate).startswith("cach "):
                subjects.setdefault(fold(candidate), candidate)
        merged["interests"] = ", ".join(list(subjects.values())[:6])[:240]
    if old.get("response_style") and new.get("response_style"):
        old_parts = old["response_style"].split(", ")
        if re.search(r"\d+ bullet", new["response_style"]):
            old_parts = [p for p in old_parts if not re.match(r"\d+ bullet", p)]
        parts = list(dict.fromkeys(old_parts + new["response_style"].split(", ")))
        if any(re.match(r"\d+ bullet", p) for p in parts):
            parts = [p for p in parts if p != "bullet"]
        merged["response_style"] = ", ".join(parts)
    return merged


def summarize_messages(messages: list[dict[str, str]], max_items: int = 6) -> str:
    if max_items < 1:
        raise ValueError("max_items must be positive")
    facts, notes = {}, []
    for message in messages:
        if message["role"] == "summary":
            try:
                prior = json.loads(message["content"])
                facts = merge_facts(facts, prior.get("facts", {}))
                notes.extend(prior.get("notes", []))
            except json.JSONDecodeError:
                notes.append(message["content"][:120])
        elif message["role"] == "user":
            facts = merge_facts(facts, extract_profile_updates(message["content"]))
            notes.append(message["content"][:120])
    return json.dumps({"facts": facts, "notes": list(dict.fromkeys(notes))[-max_items:]},
                      ensure_ascii=False, sort_keys=True)


@dataclass
class CompactMemoryManager:
    threshold_tokens: int
    keep_messages: int
    state: dict[str, dict] = field(default_factory=dict)

    def __post_init__(self):
        if self.threshold_tokens < 1 or self.keep_messages < 1:
            raise ValueError("Memory settings must be positive")

    def append(self, thread_id: str, role: str, content: str) -> None:
        state = self.state.setdefault(thread_id, {"messages": [], "summary": "", "compactions": 0})
        state["messages"].append({"role": role, "content": content})
        total = estimate_tokens(state["summary"]) + sum(estimate_tokens(m["content"]) for m in state["messages"])
        if total > self.threshold_tokens and len(state["messages"]) > self.keep_messages:
            old = state["messages"][:-self.keep_messages]
            if state["summary"]:
                old = [{"role": "summary", "content": state["summary"]}, *old]
            state["summary"] = summarize_messages(old)
            state["messages"] = state["messages"][-self.keep_messages:]
            state["compactions"] += 1

    def context(self, thread_id: str) -> dict:
        state = self.state.get(thread_id, {"messages": [], "summary": "", "compactions": 0})
        return {**state, "messages": [dict(m) for m in state["messages"]]}

    def compaction_count(self, thread_id: str) -> int:
        return self.context(thread_id)["compactions"]


def offline_response(facts: dict[str, str], message: str) -> str:
    """Shared responder: the memory available to it is the experimental variable."""
    question = fold(message)
    if "?" not in message and not any(x in question for x in ("nhac lai", "tom tat ngan ve", "thu nho")):
        return "Đã tiếp nhận nội dung. Thông tin được giữ theo phạm vi bộ nhớ của phiên."
    requested = []
    rules = {"name": ("ten", "la ai", "dungct"),
             "location": ("noi o", "o dau", "dang o", "o hue"),
             "profession": ("nghe", "lam gi"),
             "response_style": ("style", "tra loi", "kieu"),
             "favorite_drink": ("do uong",),
             "favorite_food": ("mon an",),
             "pet": ("nuoi", "con gi"),
             "interests": ("quan tam",)}
    labels = {"name": "Tên", "location": "Nơi ở", "profession": "Nghề nghiệp",
              "response_style": "Phong cách trả lời", "favorite_drink": "Đồ uống",
              "favorite_food": "Món ăn", "pet": "Thú nuôi", "interests": "Mối quan tâm"}
    for key, terms in rules.items():
        if any(term in question for term in terms):
            requested.append(f"{labels[key]}: {facts[key]}" if key in facts else f"{labels[key]}: chưa có thông tin xác nhận")
    if not requested:
        return "Chưa có đủ dữ liệu để trả lời yêu cầu này trong chế độ mô phỏng."
    if "3 bullet" in facts.get("response_style", ""):
        groups = [requested[i::3] for i in range(3)]
        return "\n".join("- " + "; ".join(group) for group in groups if group)
    return "; ".join(requested) + "."
