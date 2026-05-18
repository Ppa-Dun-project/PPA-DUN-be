# Keeper / contract 코드의 시즌 롤오버 로직.
# DB·HTTP 의존 없음 — 순수 함수. 표는 첨부 이미지의 keeper league 기준이며
# 변경 시 여기 한 곳만 고치면 된다.
from typing import Literal, Optional


# 영입 당시 사용자가 고른 원본 계약 코드. picks 테이블의 contract_code 컬럼과 일치.
ContractCode = Literal["F3", "F2", "F1", "S1", "L2", "LX", "X"]


# 코드별 만료 테이블. {code: [elapsed=0일 때 상태, elapsed=1, ...]}
# 테이블 끝을 넘긴 elapsed는 모두 "X"로 떨어진다.
_ROLLOVER_TABLE: dict[str, list[ContractCode]] = {
    "F3": ["F3", "F2", "F1"],
    "F2": ["F2", "F1"],
    "F1": ["F1"],
    "S1": ["S1"],
    "L2": ["L2", "LX"],
    "LX": ["LX"],
    "X":  [],  # 이미 만료 — 어떤 elapsed에서도 X
}


def rolled_contract(
    code: Optional[ContractCode],
    years_elapsed: int,
) -> Optional[ContractCode]:
    """영입 당시 코드와 그동안 흐른 시즌 수로 현재 계약 상태를 계산한다.

    - code=None: keeper 정보가 없는 픽(옛 데이터). None 그대로 반환.
    - years_elapsed < 0: target_season < signed_season인 비정상 입력.
        과거 재현 시나리오 등에서 발생 가능. 원본 코드를 그대로 반환한다.
    - 코드별 테이블을 넘어선 elapsed: "X"(만료) 반환.

    이 함수는 정보가 X로 떨어졌는지 알려줄 뿐, 픽을 실제로 제외하는 책임은
    호출자(import 로직)에 있다.
    """
    if code is None:
        return None
    if years_elapsed <= 0:
        return code

    timeline = _ROLLOVER_TABLE.get(code)
    if timeline is None:
        # 알 수 없는 코드 — 데이터 오염. 보수적으로 그대로 반환.
        return code
    if years_elapsed < len(timeline):
        return timeline[years_elapsed]
    return "X"
