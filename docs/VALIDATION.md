# v0.6.1 검증 결과

검증일: 2026-10-07 (Asia/Seoul). 모든 입력 예제는 가상 자료입니다.

## 실행 결과

| 검증 | 결과 |
|---|---|
| `.venv/bin/python -m unittest discover -s tests -v` | 44개 통과, 실패/오류/skip 0 (설치 도우미 테스트 4개 포함) |
| `.venv/bin/python tests/smoke_mcp.py` | stdio 초기화, Tool 목록, inspect/recheck/compare 실제 호출 통과 |
| `.venv/bin/python -m compileall -q frr` | 통과 |
| editable 패키지 설치 및 `frr --help` | 통과 |

실제 테스트에는 UTF-8 HTML/DART XML, PDF 표, ZIP/DSD, XBRL/Inline XBRL, Arelle 계산 링크베이스, XBRL 수정본 Clearing이 포함됩니다. Arelle 의존성이 없는 환경에서는 관련 테스트가 skip되므로 이 결과와 동일하게 보려면 프로젝트 의존성을 모두 설치해야 합니다.

## 샘플 산출물

`examples/run_demo.py` 실행 시 생성되는 검토표입니다. 생성 파일은 Git에 포함하지 않습니다. 기존 클라우드 샘플 위치: `output/v0.6.1/`.

| 파일 | 결과 |
|---|---|
| ABC_2026_Review.xlsx | NEW 1, REVIEW_COMPLETE_WITH_OPEN_ITEMS |
| ABC_2026_Final_Review.xlsx | RESOLVED 1, REVIEW_COMPLETE |
| PDF_Table_Review.xlsx | PDF 표에서 추출한 10 + 20 ≠ 35 합계 후보 1건 |
| XBRL_Review.xlsx | Arelle 계산 링크베이스 검증 오류 1건 |

`examples/run_demo.py`로 새 출력 디렉터리에 재생성할 수 있습니다.

## 보존/오해결 방지 검증

- 입력 바이트 보존 및 동일 입력 경로/기존 출력 덮어쓰기 차단
- 보고서 문자열이 Excel 수식으로 실행되지 않음
- XML 외부 엔티티 및 ZIP 경로 이탈 거부
- 보고서/근거의 기간·단위·회사·범위·차원이 다르면 비교하지 않음
- 근거자료 삭제, 오류 문단 삭제, 회사명 오류 문단 누락으로 해결 처리하지 않음
- 수식 캐시가 없는 수정본은 기존 수식 오류를 해결 처리하지 않음
- 합계관계 정의 변경을 이전 오류의 해결 근거로 사용하지 않음
- 해결 후 재발해도 Issue ID 유지, 참고파일의 오류도 Clearing
- 검토 Workbook 메타데이터 손상 탐지

## 검증 한계

실제 기업의 비공개 DART 제출 패키지나 금융감독원 제출 시스템에서는 검증하지 않았습니다. 복잡한 표와 taxonomy는 해당 자료 및 정확한 메타데이터/매핑이 있어야 검사 범위를 확정할 수 있습니다. 감사의견·KAM·회계정책의 전문적 판단은 자동 검증의 대상이 아닙니다.

현재 환경의 MCP/Pydantic 의존성에서 `lifespan` annotation 경고가 발생하지만 Tool 초기화와 호출은 정상 완료했습니다. 클라우드 기본 샌드박스에서는 AnyIO의 로컬 비동기 통신이 제한되어 MCP 프로토콜 테스트에 네트워크 권한을 활성화했습니다. 검토 문서를 외부 서비스로 전송하거나 원격 리소스를 다운로드하는 검증은 수행하지 않았으며 Arelle는 offline 모드를 사용했습니다.
