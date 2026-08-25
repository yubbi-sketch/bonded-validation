"""기호 논리 검증기 — 지휘자(Peter)의 원안 뼈대를 계승, 부정(¬) 지원으로 확장.

원안: SymbolicLogicVerifier.verify_causality (2026-08-26 지휘자 제출 코드).
확장: 노드를 엔티티가 아닌 리터럴 (entity, polarity)로 승격 — X⇒¬Y 규칙과
      부정 질의(A⇒¬B?)를 판정할 수 있다. 모순(⊥) 탐지 포함.

이 모듈의 정확도는 '정의상 100%'다(그래프 탐색은 증명이지 추정이 아님).
따라서 파이프라인의 오류는 전부 추출기(신경망)에서 온다 — 그걸 측정하는 게 실험이다.
"""


class SymbolicLogicVerifier:
    def __init__(self):
        self.adj = {}  # from_entity -> [(to_entity, pol)]  (전제는 항상 양 리터럴)

    def add_rule(self, premise, conclusion, neg=False):
        self.adj.setdefault(premise, []).append((conclusion, -1 if neg else +1))

    def derives(self, start, target, target_neg=False):
        """(start,+)에서 목표 리터럴 (target, ±) 도달 가능성 — 엄밀 판정."""
        goal = (target, -1 if target_neg else +1)
        seen = {(start, +1)}
        stack = [(start, +1)]
        while stack:
            ent, pol = stack.pop()
            if (ent, pol) == goal:
                return True
            if pol != +1:
                continue  # 음 리터럴은 전제로 발화 불가(데이터 의미론과 일치)
            for nxt in self.adj.get(ent, []):
                if nxt not in seen:
                    seen.add(nxt)
                    stack.append(nxt)
        return goal in seen

    def contradiction(self, start):
        """같은 엔티티의 양·음 리터럴이 동시 유도되는가 (⊥ 탐지)."""
        seen = {(start, +1)}
        stack = [(start, +1)]
        while stack:
            ent, pol = stack.pop()
            if pol == +1:
                for nxt in self.adj.get(ent, []):
                    if nxt not in seen:
                        seen.add(nxt)
                        stack.append(nxt)
        ents = {}
        for e, p in seen:
            ents.setdefault(e, set()).add(p)
        return [e for e, ps in ents.items() if len(ps) == 2]
