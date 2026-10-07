# Financial Report Reviewer MCP v0.6

## 1. 기본 원칙

시스템은 **어떤 경우에도 원본 DART 파일이나 보고서 내용을 자동으로 수정하지 않는다.**

역할은 다음으로 제한한다.

```text
검토
↓
오류 탐지
↓
수정 필요사항 제시
↓
수정 제안
↓
Excel Review List 생성
↓
사용자가 직접 수정
↓
수정본 재검사
↓
Review Clearing
```

따라서 시스템은 **검토자 역할**을 수행하고, 실제 수정은 사용자가 수행한다.

---

# 2. 최종 Workflow

```text
DART 파일
감사보고서
검토보고서
재무제표
정산표
TB
기타 근거자료
        ↓
Financial Report Reviewer MCP
        ↓
문서구조 분석
        ↓
숫자·문구·날짜·참조 검사
        ↓
문서간 대사
        ↓
Materiality 평가
        ↓
수정 필요사항 추출
        ↓
Excel Review Workbook
        ↓
사용자 수정
        ↓
수정본 재검사
        ↓
Resolved / Unresolved / New
```

---

# 3. DART 파일 처리

DART 제출용 파일을 입력받더라도 원본을 변경하지 않는다.

사용자:

```text
이 DART 파일 최종 검토해줘.
```

결과:

```text
ABC_2026_DART_Review.xlsx
```

필요한 경우 별도의 분석 JSON을 생성할 수 있지만 핵심 산출물은 Excel Review Workbook이다.

---

# 4. 대표 MCP Tool

```python
@mcp.tool()
def inspect_report_package(
    primary_file: str,
    reference_files: list[str] | None = None,
    prior_file: str | None = None,
    previous_version: str | None = None,

    materiality: float | None = None,
    performance_materiality: float | None = None,
    trivial_threshold: float | None = None,

    export_excel: bool = True,
    output_path: str | None = None,
):
    """
    보고서 및 관련 자료를 종합 검토한다.

    원본 문서는 변경하지 않는다.

    오류 및 수정 필요사항을 탐지하고
    Excel Review Workbook으로 출력한다.
    """
```

---

# 5. 자동수정 기능 제거

다음 기능은 구현하지 않는다.

```text
AUTO_FIX

SAFE_AUTO_FIX

aggressive_fix

apply_approved_fixes

자동 문자열 치환

자동 날짜 변경

자동 회사명 변경

자동 계정명 변경

자동 숫자 변경

자동 주석번호 변경

자동 DART 파일 수정
```

관련 Tool도 만들지 않는다.

---

# 6. 수정 제안 기능은 유지

오류를 발견하면 시스템은 다음까지만 수행한다.

예:

```text
현재 내용:
유형 자산

문제점:
보고서 내 다른 부분에서는 "유형자산"으로 사용

수정 제안:
유형자산

판단:
사용자 확인 후 수정
```

시스템은 실제 문서를 수정하지 않는다.

---

# 7. 숫자 오류

숫자 오류는 특히 보수적으로 처리한다.

예:

```text
TB            52,340
정산표        52,340
재무제표      52,340
주석          52,430
```

Finding:

```text
[CRITICAL]

매출액 금액 불일치

TB:
52,340

정산표:
52,340

재무제표:
52,340

주석:
52,430

차이:
90

수정 제안:
주석 금액 확인 필요

참고:
TB·정산표·재무제표는 52,340으로 일치합니다.
```

시스템은:

```text
52,430 → 52,340
```

이라고 제안할 수는 있지만 실제 파일에 적용하지 않는다.

---

# 8. 수정 제안 신뢰도

모든 Finding에 Confidence를 제공한다.

```text
95% 이상
높은 확률로 수정 필요

80~95%
검토 필요

60~80%
추가 확인 필요

60% 미만
참고사항
```

단, Confidence가 100%라도 자동수정하지 않는다.

---

# 9. 수정 제안 유형

```python
class RecommendationType(str, Enum):

    LIKELY_FIX = "LIKELY_FIX"

    REVIEW_REQUIRED = "REVIEW_REQUIRED"

    INVESTIGATE = "INVESTIGATE"

    INFORMATION = "INFORMATION"
```

예:

```text
유형 자산 → 유형자산

Recommendation:
LIKELY_FIX
```

숫자 차이:

```text
Recommendation:
REVIEW_REQUIRED
```

회계정책:

```text
Recommendation:
INVESTIGATE
```

---

# 10. Finding 모델

```python
class Finding(BaseModel):

    finding_id: str
    issue_id: str

    rule_id: str

    severity: Severity
    category: FindingCategory

    primary_file: str

    page: int | None = None
    sheet: str | None = None
    cell: str | None = None
    section: str | None = None

    original_text: str | None = None

    actual: str | None = None
    expected: str | None = None
    difference: str | None = None

    reference_file: str | None = None
    reference_location: str | None = None

    message: str

    evidence: list[str] = []

    suggestion: str | None = None
    suggested_text: str | None = None

    recommendation_type: str | None = None

    confidence: float = 1.0

    difference_numeric: float | None = None

    materiality_ratio: float | None = None
    performance_materiality_ratio: float | None = None
    trivial_threshold_ratio: float | None = None
```

---

# 11. Materiality 연동 유지

다음 기능은 그대로 유지한다.

```text
Overall Materiality
Performance Materiality
Clearly Trivial Threshold
```

Finding마다 다음을 계산한다.

```text
Difference / Materiality
Difference / Performance Materiality
Difference / Trivial Threshold
```

예:

```text
차이                200백만원
Materiality         500백만원
PM                  350백만원
Trivial              25백만원
```

결과:

```text
Materiality 대비       40%
PM 대비                57%
Trivial 대비          800%
```

다만 중요성 기준은 자동 수정 여부가 아니라 **검토 우선순위**를 정하는 데 사용한다.

---

# 12. Issue ID 기반 Review Clearing 유지

각 Finding에는 고유 Issue ID를 부여한다.

예:

```text
FRR-2026-000001
FRR-2026-000002
```

같은 오류가 수정본에서도 남아 있으면 같은 Issue ID를 유지한다.

---

# 13. Review 상태

```text
미확인

수정필요

수정중

수정완료

수정불필요

추가확인

Client 확인

Manager 확인

Partner 확인

Closed
```

---

# 14. 수정 후 재검사

사용자가 직접 문서를 수정한 뒤 수정본을 다시 입력한다.

Tool:

```python
@mcp.tool()
def recheck_corrected_report(
    previous_review_file: str,
    corrected_report: str,
    reference_files: list[str] | None = None,
):
    """
    사용자가 수정한 보고서를 다시 검사한다.

    기존 Issue 해결 여부와
    새로운 Issue 발생 여부를 확인한다.
    """
```

---

# 15. 재검사 결과

예:

```text
기존 Issue          37건

RESOLVED            31건

UNRESOLVED           4건

NEW                  2건

NOT_VERIFIABLE       0건
```

---

# 16. 버전 비교 유지

다음 Tool을 유지한다.

```python
@mcp.tool()
def compare_report_versions(
    old_file: str,
    new_file: str,
    reference_files: list[str] | None = None,
):
    ...
```

검사:

```text
숫자 변경

문구 변경

날짜 변경

회사명 변경

주석번호 변경

표 변경

추가

삭제

이동
```

---

# 17. 의도하지 않은 변경 탐지

예:

V3:

```text
매출액 52,340
```

V4:

```text
매출액 52,430
```

근거자료:

```text
52,340
```

Finding:

```text
[HIGH]

보고서 금액이 이전 버전 대비 변경되었습니다.

이전:
52,340

현재:
52,430

근거자료:
52,340

근거자료 변경 없이 보고서 금액만 변경되었습니다.

수정 필요 여부를 확인하십시오.
```

---

# 18. Excel 수식 및 Hard Coding 검사 유지

다음 대상:

```text
TB

정산표

Lead Schedule

Supporting Schedule

재무제표

회사제시자료
```

---

# 19. Formula Error

탐지:

```text
#REF!

#VALUE!

#DIV/0!

#NAME?

#NUM!

#N/A
```

---

# 20. Hard Coding

예:

```text
H20 = SUM(H10:H19)

I20 = SUM(I10:I19)

J20 = 52,340

K20 = SUM(K10:K19)
```

Finding:

```text
[MEDIUM]

수식 패턴 사이에 직접 입력된 값이 있습니다.

Cell:
J20

현재값:
52,340

인접 수식 패턴:
SUM(J10:J19)

확인 필요
```

실제 Excel 파일은 변경하지 않는다.

---

# 21. External Link

예:

```text
='[2025_TB.xlsx]TB'!H150
```

Finding:

```text
[HIGH]

외부 파일 참조가 발견되었습니다.

정산표!H24

참조 파일:
2025_TB.xlsx

당기 자료인지 확인하십시오.
```

---

# 22. DART 구조 검토

DART 구조화 파일의 경우 다음을 읽고 검토할 수 있게 한다.

```text
HTML

XML

XBRL
```

가능한 경우 다음을 검사한다.

```text
Tag

Context

Unit

Period

Decimals

Sign

Taxonomy Element

Document Reference

Footing

Cross-footing
```

하지만 구조 또는 Fact를 직접 수정하지 않는다.

---

# 23. XBRL 검토

예:

```text
Revenue

Context:
2026

Unit:
KRW

Value:
52,430
```

다른 근거자료:

```text
52,340
```

결과:

```text
[CRITICAL]

XBRL Fact와 재무제표 금액 불일치

XBRL:
52,430

재무제표:
52,340

정산표:
52,340

TB:
52,340

차이:
90

XBRL Fact 확인 필요
```

수정은 사용자가 수행한다.

---

# 24. Excel Review Workbook

최종 Workbook:

```text
01_검토요약

02_수정사항

03_통합숫자대사

04_DataLineage

05_문서정합성

06_전기비교

07_버전비교

08_Excel수식검사

09_XBRL검토

10_PASS항목

11_검사로그

12_규칙설정
```

해당 기능이 사용되지 않은 Sheet는 생략 가능하다.

---

# 25. 핵심 Sheet — 02_수정사항

최종 열:

| No | Issue ID | 중요도 | Risk | 파일 | 위치 | 구분 | 현재내용 | 비교대상 | 비교값 | 차이 | 중요성대비 | 문제점 | 수정제안 | 근거 | Confidence | 상태 | 담당자 | 검토자 | 메모 |
|---:|---|---|---:|---|---|---|---|---|---|---:|---:|---|---|---|---:|---|---|---|---|

---

# 26. 예시

| Issue ID | 중요도 | 위치 | 현재내용 | 비교값 | 문제점 | 수정제안 |
|---|---|---|---|---|---|---|
| FRR-001 | CRITICAL | 주석25 | 52,430 | FS 52,340 | 금액 불일치 | 주석 금액 확인 |
| FRR-002 | HIGH | 감사보고서 p.3 | 2025.12.31 | 기준일 2026.12.31 | 기간 불일치 | 날짜 확인 |
| FRR-003 | LOW | 주석12 | 유형 자산 | 유형자산 | 용어 불통일 | 유형자산으로 수정 검토 |

---

# 27. Evidence 유지

각 Finding은 반드시 근거를 같이 제공한다.

예:

```text
[감사보고서 p.42]

"당기 매출액은 52,430백만원입니다."

[재무제표]

매출액
52,340백만원

[정산표]

매출액
52,340백만원
```

---

# 28. 수정 후 최종 검증

사용자가 수정한 최종 파일을 다시 넣으면 전체 검사를 다시 수행한다.

```text
수정본
↓
Full Review
↓
기존 Issue Matching
↓
Resolved
Unresolved
New
↓
Final Review Excel
```

---

# 29. 최종 상태

다음 상태를 사용할 수 있다.

```text
REVIEW_COMPLETE

REVIEW_COMPLETE_WITH_OPEN_ITEMS

REVIEW_REQUIRED

VALIDATION_FAILED
```

`REVIEW_COMPLETE` 역시 감사보고서의 적정성이나 감사의견을 보증하는 의미가 아니다.

시스템이 정의된 검사항목을 완료했다는 의미다.

---

# 30. 가장 중요한 제한사항

시스템은 다음 사항을 직접 수정하지 않는다.

```text
금액

회사명

날짜

오타

감사의견

검토결론

회계정책

KAM

계속기업 관련 문구

주석번호

XBRL Fact

Excel 수식
```

어떤 항목도 자동 변경하지 않는다.

시스템은 항상:

```text
현재 내용

문제점

비교 근거

수정 제안

Confidence
```

까지만 제공한다.

---

# 31. 최종 제품 개념

최종 시스템은:

```text
자동수정 프로그램
```

이 아니라

```text
Financial Reporting
Review & Clearing Engine
```

이다.

핵심 기능:

```text
오류 탐지

Footing

Cross-footing

문서간 대사

Materiality 평가

전기 비교

버전 비교

Excel 수식 검사

Hard Coding 검사

DART / XBRL 검토

수정 제안

Review Clearing

수정 후 재검사
```

를 수행한다.

---

# 32. 최종 사용자 경험

최초:

```text
DART 파일
감사보고서
정산표
TB
재무제표
전기보고서

↓

"최종 검토해줘."
```

결과:

```text
ABC_2026_Review.xlsx
```

사용자가 직접 수정.

이후:

```text
"수정본 다시 검토해줘."
```

결과:

```text
기존 Issue      37

Resolved        31

Unresolved       4

New              2
```

최종적으로 모든 Issue를 Clearing하는 구조로 개발한다.