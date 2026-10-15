# SEWS — ICU 패혈증 조기 경보 시스템

PhysioNet/CinC Challenge 2019의 ICU 환자 시간별 기록으로 **최근 24시간 관찰 → 패혈증 약 6시간 조기경보**를 구현하는 팀 프로젝트입니다. 과제/연구용 프로토타입으로, 실제 임상 적용이 검증된 의료기기가 아닙니다.

## 레포지토리 구성
- [AI](https://github.com/Sepis-SEWS/AI): 데이터·특징·XGBoost/LSTM·앙상블·검증·SHAP·Calibration
- [Backend](https://github.com/Sepis-SEWS/Backend): FastAPI 모델 서빙 및 예측 API
- [Frontend](https://github.com/Sepis-SEWS/Frontend): Streamlit 임상 모니터링 화면

## 공통 원칙
- 공식 `SepsisLabel`은 이미 발병 6시간 전에 양성으로 전환된 라벨이므로 **추가로 6시간 이동하지 않음**.
- 환자별 Train/Validation/Test 분리, 과거부터 현재까지 데이터만 사용, 평가 데이터로 전처리 통계 학습 금지.
- Streamlit은 AI 모델 파일을 직접 읽지 않음. 반드시 FastAPI를 호출.
- 성능 목표(미달성): AUROC ≥0.82, AUPRC ≥0.40, Brier ≤0.15, CPU 4코어 추론 평균 ≤200ms.
- 실험 결과 없이 달성 여부를 주장하지 않음. 실제 측정값과 예시를 구분.
- 환경: Python 3.9~3.11, PyTorch ≥2.0 또는 TensorFlow ≥2.10, Docker Compose, Ubuntu 22.04/WSL2 허용.
- 유형힌트·docstring·Conventional Commits·고정 라이브러리 버전 적용.

## API 계약 초안 (개발 전 협의 필요)
요청: 환자 식별자 + 현재 시점까지의 최근 24시간 기록(JSON). 응답: 위험 점수(`risk_score`), Calibration 점수(`calibrated_probability`), 위험 단계(`risk_level`), 계산 가능한 SOFA 요소와 SHAP 설명. 누락 필드는 null 또는 '계산 불가' 명시. `Warning 0.5~0.75`, `Alert ≥0.75`는 과제 예시이며 실제 임계값은 검증 데이터로 확정.

## 구현 주의
과제에 기재된 활력징후 8개/검사 10개 중 원본 칼럼명과 불일치하는 항목(RR·SpO2·INR·PaO2/FiO2)이 있음. 팀 계획의 원본 실제 변수는 활력징후 7개 + 검사 9개(총 16개). 누락 원천정보(GCS, 승압제, 소변량 등) 없이 완전한 SOFA/qSOFA 산출 불가. 대체 계산/미지원 상태를 명확히 기록해야 함.

## Frontend 요구사항
Streamlit 사용. **반드시 FastAPI를 통해 예측**하며 직접 모델 로드 금지.

- 환자 목록 화면: 현재 위험도 신호등 표시(초록/노랑/빨강).
- 환자 상세: HR/MAP/SpO2 등 Vital 추이, 위험도 시계열, 계산 가능한 SOFA 구성요소 막대 그래프.
- SHAP Force/Waterfall Plot 및 Calibration Curve 표시.
- 경보 2단계: 예시 Warning [0.5, 0.75), Alert ≥0.75. 임계값 검증 후 확정.
- API 요청 중/오류/모델 미로딩/결측값 상태 표기.
- Docker Compose로 Backend와 함께 실행, 버전 고정 및 README 실행 절차.
- **현재 상태:** 초기 README 및 요구사항 정리. 실제 UI/API 연동 전.

## 구현 우선순위
API Mock JSON으로 화면 설계 → `/health` 통신 → 환자 목록·상세 → 위험도/경보 → SHAP/Calibration → 통합 테스트.

## 팀 역할 및 개인 기여
추후 팀원별 담당/실제 커밋을 기록할 것.
