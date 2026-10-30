# Streamlit 화면용 API 계약 제안

Figma 화면 연결에 필요한 추가 필터·집계·예측 식별자는 아래 ‘현재 Frontend 어댑터가 사용하는 추가 계약’에 정리했다. 기본 계약과 함께 Backend 합의가 필요하며, 추가 항목도 아직 구현된 API가 아니다.

**Backend 합의·구현 전 계약이다.** Frontend의 `domain/schemas.py`와 `services/api_client.py`에 이 계약을 사용하는 스키마와 HTTP 어댑터를 구현했다. 데모와 MockTransport로 검증했으며 실제 Backend 통합은 미검증이다. JSON 필드는 snake_case로 통일한다.

## 시스템 책임

Streamlit 서버가 FastAPI에 HTTP로 요청한다. Frontend는 모델 파일·DB를 직접 읽지 않는다. Backend가 인증·권한·임계값·경보 생성·기록 영구 저장을 담당한다. UI 필터링은 접근 제어가 아니다.

Backend README의 `/health`, `/predict`, `/predict_batch`, `/explain`은 서버 상태·추론 API 초안이다. 아래 환자·경보 조회/기록 API는 별도 추가 합의가 필요하다. 대시보드 재실행 때마다 `/predict`를 호출하지 않고, Backend에서 계산·저장한 최신 결과를 조회하는 구조를 기본으로 한다. 24시간 입력 정의는 AI/Backend가 소유하며 이 화면 계약으로 임의 결정하지 않는다.

## 제안 엔드포인트

| API | 역할 |
|---|---|
| `GET /health` | 서버·모델 준비 상태; 연결 실패와 모델 미준비를 구분 |
| `GET /patients?query=&risk_level=&assignee=&cursor=&limit=` | 접근 가능한 환자 목록·집계·기준 시각 |
| `GET /patients/{patient_id}` | 환자 상세·최신 예측·관측·최근 24시간 시계열·설명 |
| `GET /alerts?patient_id=&status=&from=&to=&cursor=&limit=` | 경보 이력·발생 당시 점수·확인 상태·평가/조치 기록 |
| `POST /alerts/{alert_id}/acknowledgement` | 인증 사용자와 서버 시각으로 확인; 중복 확인은 멱등 |
| `POST /alerts/{alert_id}/records` | 평가·조치 저장; 서버가 작성자·저장 시각·ID 부여 |

### 조회 envelope

목록 응답은 `{items, as_of, snapshot_id, next_cursor, summary}`로 제안한다. `summary`는 동일 접근 권한·필터 범위의 전체 집계이며, 일부 페이지의 행 수와 다르다. 전체 모니터 집계와 필터 결과 집계를 구분할 범위를 응답에 명시한다. `next_cursor=null`은 마지막 페이지다.

상세 응답은 `{item, as_of, snapshot_id}`로 제안한다. 같은 snapshot 식별자는 같은 데이터 기준을 뜻해야 한다. Backend가 snapshot 일관성을 지원하지 않으면 `snapshot_id=null`로 명시하고 Frontend는 각 조회 시각의 차이를 표시한다. 지원하지 않는 원자성을 프론트에서 가장하지 않는다.

### 주요 모델

| 모델 | 필드·의미 |
|---|---|
| PatientSummary | `id`, `bed`, `assignee`, `last_observed_at`, `prediction`, `data_delayed`, `delay_reason` |
| PatientDetail | PatientSummary + `observations`, `series`, `explanation`, `sofa` |
| Prediction | `risk_score`, `risk_level`, `predicted_at`, `model_version`, `threshold_version`, `calibrated_probability`, `calibration_available`, `unavailable_reason` |
| Observation | `feature_name`, `value`, `unit`, `observed_at`; 값은 수치 또는 null |
| TimePoint | `observed_at`, `risk_score`, `hr`, `map`, `lactate`; 각 측정값은 null 허용 |
| Explanation | `available`, `method`, `model_version`, `features`, `unavailable_reason`; features는 `{name, value, unit, contribution}` 목록 |
| SOFA | `available`, `total`, `components`, `unavailable_reason`; 불완전한 구성 요소만으로 total을 만들지 않음 |
| AlertEvent | `id`, `patient_id`, `risk_score`, `risk_level`, `model_version`, `threshold_version`, `occurred_at`, `status`, `acknowledged_by`, `acknowledged_at`, `repeat_count`, `records` |
| CareRecord | `id`, `alert_id`, `author`, `assessment`, `action`, `saved_at` |

AlertEvent의 점수·단계·모델/임계값 버전은 **발생 당시 값**이며 최신 Prediction으로 덮어쓰지 않는다. `repeat_count`의 집계 기간·중복 경보 정의와 SOFA 구성 요소 상세 스키마는 Backend와 추가 합의한다.

## 값·표시 규칙

- `risk_score`는 0–1 또는 null로 제안한다. Frontend는 ×100하여 ‘모델 점수 / 100’으로 표시한다. 점수를 발생 확률이라고 부르지 않는다. 기존 데모 0–100 계약을 묵시적으로 허용하지 않고 범위 오류로 처리한다.
- `risk_level`: `high / warning / low / unavailable`. 단계는 Backend가 결정한다. 기존 30/60 또는 0.5/0.75 예시를 화면에 운영 임계값으로 하드코딩하지 않는다.
- 점수가 null이면 단계는 unavailable이고 사유가 필요하다. 유효한 0을 결측으로 취급하지 않는다.
- `calibrated_probability`는 0–1 또는 null이다. `calibration_available=false`이면 null이어야 하며 확률 미제공으로 표시한다. true이면 유효한 값이 필요하다.
- 시각은 타임존 포함 ISO 8601, 화면 표시는 Asia/Seoul. `as_of`, `observed_at`, `predicted_at`, 서버 저장 시각을 구분한다.
- 관측 단위·원본 특징명·지연 판정 기준을 서버에서 명시한다. `Resp → RR`, `O2Sat → SpO₂` 등 매핑은 합의 후 적용한다.
- 시계열은 과거→현재 순으로 정렬하며 중복 시각 처리 정책을 합의한다. 결측은 null로 전송하고 화면에서 보간하지 않는다.
- 설명 미제공이면 `available=false`, features는 빈 목록이고 사유를 제공한다. 합성 데모 설명은 method를 `synthetic-demo`로 명시하며 실제 SHAP와 구분한다.
- 경보 상태는 `unacknowledged / acknowledged`뿐이다. 기록 존재가 경보 종료나 위험 해소를 뜻하지 않는다.

## 확인·기록 쓰기

- 확인 요청에는 클라이언트가 작성자나 시각을 지정하지 않는다. 성공 응답은 변경된 AlertEvent를 반환한다. 재확인은 최초 확인자·시각을 보존한다.
- 기록 요청 본문은 `{assessment, action}`이다. 양쪽 공백을 제거한 뒤 각각 1–2000자로 검증하도록 제안한다. 작성자는 서버 인증 세션에서 결정한다.
- 미확인 경보의 기록 저장은 409로 거부한다. 성공 시 커밋된 CareRecord를 반환한다.
- 기록 요청에는 `Idempotency-Key`를 사용한다. 동일 사용자·경보·키·본문의 재요청은 같은 기록을 반환하며, 같은 키에 다른 본문은 409다. 키 보관 기간과 재시도 허용 기간은 서버 계약으로 확정한다.
- 타임아웃 후에는 저장 결과를 알 수 없으므로 같은 키로 재시도한다. 버튼 비활성화만으로 중복 저장 방지를 대신하지 않는다.
- 성공 응답 전 ‘저장 완료’를 표시하지 않는다. 실패/결과 불명 시 초안·키를 유지하고 가상 저장으로 대체하지 않는다. 성공 후 조회 데이터를 무효화하고 서버에서 재조회한다.

## 오류·보안

오류 응답은 `{code, message, request_id}`로 제안한다. 401은 재인증, 403은 권한 거부, 404는 대상 소멸/조회 불가, 409는 상태/키 충돌, 422는 입력 오류, 5xx는 서버 오류로 구분한다. Frontend는 연결/응답 타임아웃과 잘못된 JSON·스키마도 처리해야 한다. 쓰기 요청을 새 키로 자동 재전송하지 않는다.

실제 데이터 연결 전 Backend와 인증 방식·권한 전달 방식을 확정한다. 사용자별 자격정보는 세션을 넘겨 공유하거나 전역 캐시하지 않는다. 환자/기록/토큰을 오류 로그에 출력하지 않으며 request_id로 서버 로그를 연계한다. API 실패 시 합성 데이터로 자동 대체하지 않는다.

## 현재 Frontend 어댑터가 사용하는 추가 계약

정확한 실행 스키마는 `domain/schemas.py`를 기준으로 한다. 기본 계약을 구체화한 아래 필드도 Backend 합의가 필요하다.

- `/health`: `{status: "ok" | "degraded" | "unavailable", model_ready: boolean, checked_at: timezone-aware timestamp}`. 연결 성공과 모델 준비 상태를 분리한다.
- 환자 집계 `summary`: `scope: "global" | "filtered"`, `total`, `high`, `warning`, `unavailable_count`, `unacknowledged_alert_count`, `unacknowledged_high_count`를 필수로 반환한다. `oldest_unacknowledged_at`은 선택 필드다. 필수 집계 누락을 0으로 표시하지 않고 응답 오류로 처리한다.
- 경보 집계 `summary`: `scope`, `total`, `unacknowledged_alert_count`, `acknowledged_count`, `recorded_count`를 필수로 반환한다. 집계는 페이지 일부가 아니라 접근 가능·필터 범위 전체다. 목록 ID는 중복되지 않아야 한다.
- 환자 목록은 `unacknowledged_only` 필터를, 경보 목록은 `query`, `assignee` 필터를 추가 사용한다. `from`은 포함, `to`는 제외하는 시각 범위다. 목록은 cursor로 페이지를 조회하며 첫/다음 페이지 버튼을 제공한다. 담당자 필터는 식별 문자열의 정확 일치를 기준으로 제안한다.
- 환자 요약 추가 필드: `icu_id`, `trend: rising | stable | falling | null`, `latest_alert_id`, `unacknowledged_alert_count`. 미지원은 null/미제공이며 화면에서 임의 계산하지 않는다. 경보에도 표시용 `bed`, `assignee`를 선택 필드로 받을 수 있다.
- Prediction과 Explanation의 `prediction_id` 및 `model_version`이 같을 때만 설명을 표시한다. Explanation의 `output_scale`을 기여도 축 이름으로 사용한다. ID가 미제공이면 설명을 숨기고 이유를 안내한다.
- 기존 TimePoint의 `observed_at`과 별도로 `predicted_at`을 받는다. 위험 이력은 `predicted_at`, 관측 차트는 `observed_at`을 사용한다. 예측 시각 없는 점수 행을 관측 시각으로 대체하지 않는다.
- 1차는 ICU-A 단일 병동이고 읽기 전용으로 표시한다. 다중 ICU 필터·사용자 인증·담당 변경·경보 종료·운영 API는 현재 구현 범위 밖이다.
