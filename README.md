# Financial Report Reviewer MCP v0.6.1

재무보고서 **검토 → 근거·수정 제안 → Excel Review Workbook → 사용자 수정 → 재검사 → Clearing**를 수행하는 로컬 Python MCP 서버입니다. 원본 DART·PDF·Excel·XBRL 파일을 저장하거나 수정하는 기능과 Tool은 없습니다.

이 버전은 v0.6 초기 구현의 문서 추출, 정합성, XBRL 전문 검증, 버전 비교, 재검사와 상태 판정을 보완했습니다. 결과의 `REVIEW_COMPLETE`는 명시된 자동 검사 범위의 완료이며 감사의견이나 회계적 적정성 승인이 아닙니다.

## Windows 자동 설치

압축을 완전히 풀고 `install-windows.cmd`를 더블클릭하십시오. Python이 없으면 Windows의 winget으로 Python 3.12 사용자 설치를 시도합니다. 가상환경·의존성 설치, MCP 실제 호출 확인, Codex 설정 등록을 순서대로 수행합니다. 완료 후 Codex를 재시작하십시오. 실행 중 설치 파일 다운로드를 위한 인터넷 연결이 필요합니다.

설치 폴더를 이동하거나 삭제하면 등록된 MCP 경로가 끊어집니다. 다운로드 임시 폴더 대신 계속 보관할 폴더에 압축을 푸십시오. 기존 Codex 설정은 백업 후 MCP 항목만 추가하며 같은 이름의 다른 설정은 덮어쓰지 않습니다. winget을 사용할 수 없는 PC에서는 Python을 먼저 설치해야 합니다.

설치 도우미의 설정 보존/백업/중복 방지 테스트 4개를 통과했습니다. 현재 연결된 환경은 Linux 클라우드이므로 Windows PC에서의 실행 자체는 아직 검증하지 않았습니다.

## 설치와 실행

Python 3.11 이상:

```sh
python -m venv .venv
# Linux/macOS
.venv/bin/python -m pip install -e .
.venv/bin/frr-mcp
# Windows: .venv\Scripts\python -m pip install -e .
#          .venv\Scripts\frr-mcp
```

현재 작업 환경에는 `/workspace/PROJECT1/.venv`에 설치와 검증을 완료했습니다. Arelle 2.46.0을 의존성으로 포함합니다. 서버를 인터넷에 배포하거나 ChatGPT 계정에 연결한 것은 아닙니다.

stdio MCP 클라이언트에 **자신의 환경의 절대 경로**를 등록합니다.

```json
{
  "mcpServers": {
    "financial-report-reviewer": {
      "command": "/workspace/PROJECT1/.venv/bin/python",
      "args": ["-m", "frr.server"]
    }
  }
}
```

MCP Tool:

| Tool | 기능 |
|---|---|
| `inspect_report_package` | 보고서/근거자료/전기/이전 버전 종합 검토, 중요성 평가, Excel 생성 |
| `recheck_corrected_report` | 이전 검토표의 기준을 유지한 전체 재검사와 Issue Clearing |
| `compare_report_versions` | 변경 유형·이동 목록과 근거 없는 금액 변경 탐지 |

검토 문서의 경로는 **서버가 실행되는 컴퓨터의 파일 경로**입니다.

CLI도 동일한 엔진을 사용합니다.

```sh
.venv/bin/frr inspect examples/report.json --reference examples/tb.json \
  --materiality 500 --performance-materiality 350 --trivial-threshold 25 \
  --output output/first-review.xlsx
.venv/bin/frr recheck output/first-review.xlsx examples/corrected.json \
  --output output/final-review.xlsx
.venv/bin/frr compare examples/corrected.json examples/report.json \
  --reference examples/tb.json --output output/version-review.xlsx
```

기존 출력 파일을 덮어쓰지 않습니다. 같은 명령을 다시 실행할 때는 새 출력 이름을 지정하거나 `--output`을 생략하십시오.

## 구현된 검사

| 영역 | 실제 동작 |
|---|---|
| DART/HTML/XML | 문단과 표 추출, 병합 셀 처리, 기간 열 기반 Fact 추출 |
| ZIP/DSD | 압축 멤버를 읽고 검토. XBRL은 제한된 임시 복사본에서 동봉 taxonomy와 검증 |
| PDF | 텍스트와 격자 표 추출, 페이지/표/셀 위치 유지. 텍스트 없는 페이지는 미검증 |
| CSV/JSON/Excel | 정규 Fact 표 입력, 일반 Excel 표의 기간 열 기반 추출 |
| 숫자 대사 | 계정·기간·단위·회사·연결/별도·차원 일치 여부를 확인한 뒤 비교 |
| 표 합계 | 명확한 평면 합계행 후보 추출. 명시된 가중 합계/차감/행·열 관계 검사 |
| 문서 정합성 | 용어 표기, 설정된 회사명·날짜·문구, 주석 번호 참조, 동일 키 중복 금액 |
| XBRL/Inline XBRL | Arelle 오프라인 schema/taxonomy·계산 링크베이스 검증 및 Fact 추출. Context/Unit/Period/decimals 기본 검사 |
| 부호 | 명시된 계정별 nonnegative/nonpositive 제약 검사 |
| 버전 | 숫자·날짜·주석번호·회사명 후보·문구·표 변경, 추가/삭제, 유일한 동일 문구의 이동 |
| 의도하지 않은 변경 | 이전 금액이 현재 근거자료와 일치하는데 새 보고서만 다른 경우 Finding |
| 전기 | 현재 보고서의 비교표시 Fact와 전기 보고서의 **같은 기간** 금액 대사 |
| Excel | 오류값/깨진 참조, 외부 파일 링크, 양옆 또는 위아래 수식 패턴 사이의 Hard Coding |
| 중요성 | Decimal 기반 절대차이 / Overall Materiality·PM·Trivial. 중요성 이상 CRITICAL |
| Clearing | 안정적인 규칙/Fact/원천자료 역할 기반 ID 유지, 재발 추적, 수동 검토 필드 보존 |

근거자료간 금액이 다르면 다수결로 정답을 만들지 않습니다. 차이가 없는 중복 Fact는 비교할 수 있으나 서로 다른 값은 별도 오류와 미검증 사유를 남깁니다. 자신과의 대사나 중복 근거파일은 거부합니다.

## 검토 설정

Python/MCP에서는 `review_config` 객체, CLI에서는 `--config examples/review_config.json`으로 전달합니다. 설정과 입력 SHA256은 Excel에 보존됩니다. 정의되지 않은 설정 키는 오류입니다.

```python
from frr import inspect_report_package

result = inspect_report_package(
    primary_file="report.html",
    reference_files=["tb.xlsx"],
    materiality=500_000_000,
    performance_materiality=350_000_000,
    trivial_threshold=25_000_000,
    review_config={
        "metadata": {"entity":"ABC", "scope":"consolidated", "unit":"KRW_million",
                     "period":"2026", "prior_period":"2025"},
        "concept_aliases": {"매출액":"Revenue"},
        "unit_mappings": {"KRW_million":{"unit":"KRW", "multiplier":"1000000"}},
        "materiality_unit":"KRW",
        "expectations":[
            {"id":"company", "label":"회사명", "selector":"회사명:", "expected":"ABC", "kind":"company"},
            {"id":"date", "label":"기준일", "selector":"기준일:", "expected":"2026-12-31", "kind":"date"}
        ]
    }
)
```

`metadata`는 표 추출의 명시적 기본 정보입니다. DART 표의 단위·회사를 임의로 추정하지 않습니다. `document_metadata`에서 파일의 절대 경로 또는 파일명별로 재정의할 수 있습니다. 본문에 현재/전기 열만 있다면 `period`/`prior_period`가 필요합니다. 표의 연도·날짜 열이 있으면 해당 값이 우선합니다.

단위 변환은 `unit_mappings`에 명시했을 때만 수행하며 원값과 원단위를 DataLineage에 보존합니다. `period_mappings`, `entity_aliases`, `scope_aliases`도 명시적 대응만 적용합니다. `materiality_unit`이 없고 단위가 여러 개면 잘못된 비율을 계산하지 않고 미검증 처리합니다. `numeric_tolerance`는 비교 및 합계 검사에서 적용할 절대 허용오차입니다.

문구 기준은 literal `selector`를 포함한 문단에서 `expected`를 확인합니다. 날짜는 `2026.12.31`, `2026년12월31일`, `2026-12-31` 형태를 정규화합니다. 기준 문단을 못 찾으면 PASS가 아니라 NOT_VERIFIABLE입니다. 회사명 후보 변경 분류는 “주식회사” 포함 문구에 대한 휴리스틱입니다.

`sign_constraints` 예: `{"Assets":"nonnegative", "TreasuryShares":"nonpositive"}`. 부호 규칙이 없는 계정은 음수라는 이유만으로 오류라고 하지 않습니다.

`require_references` 기본값은 true입니다. 내부 합계/형식 검사만 의도한다면 false로 명시하십시오. 그 경우 완료 상태는 내부 검사 범위에 한정됩니다.

## 정규 Fact 및 합계관계

CSV/Excel 첫 행 필수 열: `concept,value,period,unit,entity,scope`. `dimensions`, `location`은 선택입니다. JSON:

```json
{
  "facts": [
    {"concept":"Cash","value":"10","period":"2026","unit":"KRW","entity":"ABC","scope":"separate","location":"cash"},
    {"concept":"Receivable","value":"20","period":"2026","unit":"KRW","entity":"ABC","scope":"separate","location":"receivable"},
    {"concept":"Assets","value":"35","period":"2026","unit":"KRW","entity":"ABC","scope":"separate","location":"total"}
  ],
  "calculations": [
    {"id":"asset-total","total":"total","components":["cash","receivable"]}
  ]
}
```

가중치는 `{"location":"cash","weight":"-1"}`처럼 지정할 수 있습니다. 행 방향 합계는 같은 형식에 `"cross":true`를 사용합니다. 기간/단위/회사/차원이 다른 구성요소나 중복·자기 참조는 검사하지 않습니다. 합계관계 정의 자체가 바뀌면 이전 오류를 자동으로 해결 처리하지 않습니다.

JSON은 `texts`(위치→문구), `tables`(`location`, `rows`), `metadata`도 지원합니다. 표의 공란/대시는 0으로 추정하지 않습니다. 자동 합계는 명확한 `합계/총계/소계/Total/Subtotal` 행에 대한 후보이며 Confidence 80%로 표시합니다. 복잡한 계층형 표는 정규 Fact와 명시적 계산관계를 제공하십시오.

## XBRL

기본 `xbrl_validation="arelle"`는 Arelle 2.46.0을 별도 프로세스에서 실행합니다. 인터넷 연결은 offline이며 원본을 저장하지 않습니다. 필요한 회사 taxonomy와 링크베이스는 원본 옆에 상대 경로대로 배치하거나 `taxonomy_packages`에 로컬 taxonomy 패키지 경로를 제공하십시오. 필요한 자원이 없으면 검증 완료로 처리하지 않습니다.

`examples/xbrl/`에는 재현 가능한 schema·계산 링크베이스·XBRL·Inline XBRL 가상 예제가 포함됩니다. `Cash 10 + Receivables 20 ≠ Assets 35`를 Arelle가 검출합니다.

`xbrl_validation="native"`는 Context/Unit/기간/decimals 등의 기본 구조 검사만 수행하며 taxonomy 전체 검증은 NOT_VERIFIABLE입니다. XBRL concept/unit은 확장 namespace 이름을 사용합니다. 다른 형식의 보고서와 대사하려면 검토자가 확인한 계정·회사·범위·단위 매핑이 필요합니다. 숫자의 sign/scale/변환 처리는 Inline XBRL에서 Arelle가 담당합니다.

Arelle 검증은 XBRL 표준 검증이며 금융감독원 전용 제출 수리 여부를 보증하지 않습니다.

## Excel 및 Review Clearing

명세의 `01_검토요약`~`12_규칙설정`을 사용하며 데이터 없는 선택 시트는 생략합니다. `02_수정사항`은 명세의 20개 열과 검토 상태 드롭다운을 제공합니다. Clearing·재검사 근거·Recommendation·제안문구·PM/Trivial 비율은 `05_문서정합성`에 표시합니다.

`_ReviewData` 숨김 시트에 재검사 상태를 보관합니다. SHA256은 우발적 메타데이터 편집 탐지용이며 전자서명은 아닙니다. `02_수정사항`의 상태/담당자/검토자/메모만 편집하십시오. Issue ID 변경·중복·행 삭제·잘못된 상태·숨김 데이터 손상은 거부합니다. 다른 열의 수동 편집은 재검사 기준을 바꾸지 않습니다.

| Clearing | 의미 |
|---|---|
| RESOLVED | 같은 대상/규칙/범위에서 오류가 없어졌음을 재확인 |
| UNRESOLVED | 같은 Issue 재검출. 해결 후 재발해도 기존 ID 유지 |
| NEW | 이전 검토에 없던 Issue |
| NOT_VERIFIABLE | 대상/근거/검사범위 누락 등으로 재확인할 수 없음 |

오류 문단 삭제, 근거자료 제거, 수식 캐시 미존재, 합계 정의 변경을 해결 근거로 사용하지 않습니다. 참고 Excel의 오류도 재검사하며, 파일명이 바뀌는 참고자료는 `reference_roles`에 이전/새 경로를 같은 역할(`TB` 등)로 미리 지정하십시오. 모호한 셀 이동은 추정 매칭하지 않습니다. Issue ID는 검토 이력 안에서 유일하며 서로 다른 검토 건을 합치는 전역 레지스트리는 아닙니다.

재검사는 기존 중요성/규칙/전기/버전 기준을 유지합니다. 사용자 상태가 `Closed`라도 자동 검사 오류가 남아 있으면 UNRESOLVED입니다.

```
기존 Issue 수 = RESOLVED + UNRESOLVED + NOT_VERIFIABLE
NEW는 신규 Issue이므로 위 합계에 포함하지 않음
```

최종 상태 우선순위:

1. `VALIDATION_FAILED`: 파싱/입력 무결성 실패. 실패 사유를 담은 Excel 생성
2. `REVIEW_REQUIRED`: 필요한 검사가 미검증이거나 Clearing 불가 항목 존재
3. `REVIEW_COMPLETE_WITH_OPEN_ITEMS`: 정해진 검사 완료, 오류 존재
4. `REVIEW_COMPLETE`: 정해진 검사 완료, 미해결 오류 없음

잘못된 API 인자/설정, 기존 파일 덮어쓰기 요청, 읽을 수 없는 이전 검토표는 실행 오류로 반환합니다.

## 적용 경계

- 이미지 OCR, HWP/구형 XLS 직접 해석과 Excel 수식 재계산은 포함하지 않습니다. 해당 항목을 필요한 형식으로 변환하여 제공하십시오. 지원 불가/텍스트 누락은 결과에 기록합니다.
- 복잡한 표/기간/계정 대응을 무조건 자동 추론하지 않습니다. 메타데이터나 명시적 매핑이 필요하면 NOT_VERIFIABLE로 남깁니다.
- 회계정책·감사의견·KAM·계속기업 문구의 전문적 적정성 판단은 사람이 수행합니다. 문구 변경과 설정된 기대값 대조는 자동 검사할 수 있습니다.
- Confidence는 규칙 기반 점수이며 통계적으로 보정된 확률이 아닙니다. 100%도 자동수정하지 않습니다.
- 로컬 stdio용입니다. 원격 인증/다중 사용자 호스팅은 이 배포에 포함하지 않습니다.

## 검증과 소스

```sh
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python tests/smoke_mcp.py
```

자동 테스트는 실제 PDF 표, ZIP/DSD, XBRL 계산 링크베이스, Inline XBRL, 문서/Excel 검사, 삭제로 인한 오해결 방지, 단위/중요성, 네 가지 상태, Workbook 무결성을 다룹니다. `smoke_mcp.py`는 실제 stdio 초기화 및 세 Tool의 호출을 검증합니다. 이 클라우드 샌드박스에서는 비동기 통신 테스트에 로컬 소켓 사용 권한이 필요했습니다. 외부 서비스로 보고서를 전송하지 않습니다.

원 명세는 `docs/SPEC_v0.6.md`, 검증 결과는 `docs/VALIDATION.md`에 있습니다. 예제는 모두 가상 자료입니다.
