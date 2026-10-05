# Octopus — 자율 실험(Self-Driving Lab) 최적화 플랫폼

콜로이드 양자점(QD, InP / InP-ZnSe core-shell 등) 합성 실험을 자동화하고, 베이지안 최적화(Bayesian Optimization)로 합성 조건을 탐색하는 실험실 자동화 시스템입니다. TCP 기반 Job 서버(`master_node.py`)가 여러 하드웨어 모듈(유체 합성기, UV/PL 분광기 등)에 작업을 분배·스케줄링하고, 클라이언트(`client.py`)로 사용자가 실험(Job)을 제출·모니터링합니다.

> ⚠️ 이 문서는 코드 저장소를 정적 분석해 작성한 초안입니다. 프로젝트를 가장 잘 아는 사람이 한 번 검토한 뒤, 부정확하거나 오래된 설명이 있으면 직접 수정해 주세요. `TODO` 표시가 있는 항목은 저장소만으로는 확정할 수 없어 비워둔 부분입니다.

## 목차

- [프로젝트 소개](#프로젝트-소개)
- [시스템 구조](#시스템-구조)
- [폴더 구조](#폴더-구조)
- [개발 환경 설정](#개발-환경-설정)
- [실행 방법](#실행-방법)
- [코드 컨벤션](#코드-컨벤션)
- [AI 코딩 어시스턴트(바이브 코딩) 가이드](#ai-코딩-어시스턴트바이브-코딩-가이드)
- [GitHub 업로드 전 체크리스트](#github-업로드-전-체크리스트)
- [알려진 이슈 / TODO](#알려진-이슈--todo)

## 프로젝트 소개

Octopus는 크게 두 개의 층으로 이루어져 있습니다.

1. **실험 자동화 인프라 (핵심 코드)** — `master_node.py`, `client.py`, `Job/`, `Task/`, `Resource/`, `Hardware/`, `UserManager/`, `TCP_Connection/`. 사용자가 제출한 실험 Job을 큐에 넣고, 스케줄링 알고리즘(FCFS / Backfill / ClosedPacking)에 따라 실행하며, TCP 소켓으로 하드웨어 모듈(`FlowSynthesis`, `UV`, `PL`, `FlowDillution`, `Collector`)을 제어합니다.
2. **실험 데이터 분석 & 최적화 연구 코드 (스크립트 모음)** — 저장소 루트와 `Algorithm/`, `Analysis/`에 있는 다수의 분석·플로팅·베이지안 최적화 스크립트(`self_bayesian*.py`, `gp_*.py`, `shap_pareto*.py`, `plot_*.py`, `fitting*.py` 등)와 날짜별 스냅샷 데이터(`MMDD.pickle`, `USER/*/DB` 등). 이 부분은 실험실에서 반복적으로 실행하며 발전시켜온 연구용 스크립트라 정형화된 패키지 구조를 따르지 않습니다.

README와 AI 코딩 가이드를 작성할 때도 이 두 층을 구분해서 접근하는 것이 중요합니다 (자세한 내용은 [AI 코딩 어시스턴트 가이드](#ai-코딩-어시스턴트바이브-코딩-가이드) 참고).

**TODO:** 프로젝트 한 줄 목적, 소속(랩/기관), 대표 연락처, 라이선스를 채워 넣으세요.

## 시스템 구조

```
                 (로그인 + 명령 전송)
   client.py  ───────────────────────►  master_node.py (TCP :5555)
   (사용자 CLI)                          │
                                         ├─ UserManager        : 사용자 인증 (SQLite, 해시 비밀번호)
                                         ├─ JobScheduler        : Job 큐 관리 (qsub/qstat/qdel/qhold/qrestart)
                                         ├─ JobTrigger          : 스케줄링 알고리즘(FCFS/Backfill/ClosedPacking)
                                         ├─ TaskGenerator/Scheduler : Job → 세부 Task 분해 및 실행 순서 결정
                                         ├─ ResourceManager     : 모듈(FlowSynthesis/UV/PL/...) 점유 상태 관리
                                         └─ Hardware/*          : 실제 장비 제어 (TCP/OPC-UA 등)
```

클라이언트는 로그인 후 다음과 같은 명령을 텍스트 프로토콜(`?` 구분자)로 서버에 전송합니다.

| 명령 | 설명 |
| --- | --- |
| `qsub {jobFileName} {real\|virtual}` | `USER/{user}/job_script/{jobFileName}.json`을 읽어 Job 제출 |
| `qstat` | Job 대기열 / 실행열 상태 조회 |
| `qhold {jobID}` | 실행 중인 Job 일시 정지 |
| `qdel {jobID}` | 대기 중인 Job 삭제 |
| `qrestart {jobID}` | 정지된 Job 재개 |
| `qlogout` | 로그아웃 |
| `ashutdown / areboot {platform}` | (관리자) 하드웨어 플랫폼 종료/재부팅 |
| `aregUser / adelUser / amodUser` | (관리자) 사용자 등록/삭제/수정 |

`mode_type`이 `virtual`이면 실제 하드웨어 없이 시뮬레이션으로, `real`이면 실제 장비를 구동합니다. **하드웨어 제어 코드나 Job 스크립트를 수정한 뒤에는 반드시 `virtual` 모드로 먼저 검증하세요.**

## 폴더 구조

> 저장소 루트에 실험 스냅샷·이미지·엑셀 등 대용량 결과 파일이 다수 섞여 있습니다. 아래 표는 **코드 구조 파악에 필요한 디렉터리 위주**로 정리했습니다.

| 경로 | 내용 |
| --- | --- |
| `master_node.py` | Job 서버 엔트리포인트 (TCP `:5555`) |
| `client.py` | 사용자용 CLI 클라이언트 |
| `config.py` | 런타임에 값이 덮어써지는 상태 파일(온도/펌프 속도 등). 코드가 아니라 **실행 중 갱신되는 상태값**이므로 구조를 함부로 바꾸지 말 것 |
| `Job/` | `Job_Class`, `JobScheduler_Class`, `JobTrigger` — Job 큐/스케줄링 로직 |
| `Task/` | `TaskGenerator_Class`, `TaskScheduler_Class`, `TCP.py` — Job을 세부 Task로 분해하고 실행 |
| `Resource/` | `ResourceManager_Class` — 하드웨어 모듈 점유/가용 상태 관리 |
| `Hardware/` | 실제 장비 제어 코드 (유체 합성, UV/PL 분광기 등) |
| `UserManager/` | 사용자 인증 (`user.db`는 SQLite, 해시된 비밀번호 저장) |
| `TCP_Connection/` | 저수준 TCP 통신 헬퍼 |
| `Algorithm/Bayesian/` | 베이지안 최적화 알고리즘 (`BOdiscreteTest.py` 등) |
| `Algorithm/Loss/` | 손실 함수 정의 및 비교 스크립트 |
| `Algorithm/Automatic/` | 자동 실행 관련 알고리즘 |
| `Analysis/` | UV/PL 스펙트럼 분석 (`AnalysisUV*.py`) 및 참조/샘플 데이터 |
| `USER/{username}/` | 사용자별 작업 공간 — `job_script/*.json`(제출용 Job 정의), `DB/`, `Log/`, `SaveModel/` |
| `DB/`, `DB26/` | 학습된 모델(`*.pkl`) 및 실험 결과 스냅샷 |
| `Log/` | `JobLogger` 기반 실행 로그 |
| `.claude/` | Claude Code 로컬 권한 설정(`settings.local.json`). 팀원마다 다를 수 있으므로 저장소에 커밋할지 검토 필요 |
| 루트의 `MMDD.pickle`, `MMDD_2.pickle` 등 | 날짜(MMDD) 기준 실험/모델 스냅샷. 코드가 아니라 **실행 결과물**이므로 신규 기능 추가 시 참고용으로만 사용 |
| 루트의 `plot_*.py`, `shap_pareto*.py`, `gp_*.py`, `fitting*.py`, `self_bayesian*.py` 등 | 개별 분석/실험용 스크립트 모음. 서로 비슷한 이름(`shap_pareto.py`, `shap_pareto2.py`, `shap_pareto4_rawparams.py` 등)이 많으므로 **어떤 스크립트가 "현재 사용 중"인지 코드를 수정하기 전에 먼저 확인** |

## 개발 환경 설정

두 개의 Conda 환경이 용도별로 분리되어 있습니다.

- **`QD` 환경** (`QD.yaml`, Python 3.10) — 실제 실험/하드웨어 제어 노드에서 쓰는 가벼운 런타임 환경 (`numpy`, `pandas`, `scipy`, `scikit-learn`, `seabreeze`, `scikit-optimize`, `opcua` 등)
- **`RS` 환경** (`RS_environment.yml`, Python 3.12) — 오프라인 분석·머신러닝용 무거운 환경 (`pytorch`, `tensorflow`, `shap`, `gpytorch`, `cvxpy`, `causal-learn`, `dowhy` 등 포함)

```bash
# 실험/하드웨어 제어용 (경량)
conda env create -f QD.yaml
conda activate QD

# 오프라인 분석/ML용 (대형)
conda env create -f RS_environment.yml
conda activate RS

# 또는 pip만 사용할 경우
pip install -r requirements.txt
# Google Colab 등 최소 의존성만 필요할 경우
pip install -r requirements_colab.txt
```

**TODO:** `seabreeze`(Ocean Optics 분광기 드라이버), `opcua` 등 하드웨어 드라이버는 실제 장비 연결이 있는 PC에서만 정상 동작합니다. CI/개발용 PC에서 어떤 기능까지 테스트 가능한지 명시해 주세요.

## 실행 방법

```bash
# 1) Job 서버 실행 (하드웨어가 연결된 PC에서)
python master_node.py

# 2) 다른 터미널(또는 다른 PC)에서 클라이언트 실행
python client.py
```

클라이언트 실행 후 아이디/비밀번호 로그인 → 명령 입력:

```text
input commands (if terminate: input 'qlogout'): qsub Autonomous_250217 virtual
input commands (if terminate: input 'qlogout'): qstat
input commands (if terminate: input 'qlogout'): qlogout
```

Job 정의 파일은 `USER/{username}/job_script/{jobFileName}.json`에 있어야 하며, 새 실험을 등록할 때는 기존 파일(예: `USER/NY/job_script/Autonomous_250217.json`)을 참고해 작성합니다.

## 코드 컨벤션

저장소에서 관찰되는 기존 스타일을 따라주세요.

- 클래스 모듈은 `무엇Manager/무엇Manager_Class.py`처럼 **`{역할}_Class.py`** 파일명, 클래스명은 `PascalCase` (예: `JobScheduler`, `ResourceManager`, `TaskGenerator`).
- 함수/변수는 `snake_case`, 소켓·큐 등은 `job_wait_queue`, `client_socket`처럼 역할이 드러나는 이름 사용.
- TCP 프로토콜 메시지는 `"명령어?인자1?인자2"` 형태의 문자열 파싱을 사용합니다 (`client.py`, `master_node.py`의 `handle_client` 참고). 인자에 `?`나 `'`, `"`가 포함되면 파싱이 깨지므로, 관련 코드를 수정할 때 특히 주의하세요.
- 별도 테스트 스위트(`pytest` 등)가 없습니다. 수정 후에는 최소한 `python -m py_compile <파일>`로 문법 오류를 확인하고, 가능하면 `mode_type="virtual"`로 실제 동작을 확인하세요 (`.claude/settings.local.json`에도 같은 패턴의 명령들이 허용되어 있습니다).

## AI 코딩 어시스턴트(바이브 코딩) 가이드

이 저장소는 Claude 같은 AI 코딩 어시스턴트와 함께 작업하는 것을 전제로 관리됩니다. AI에게 작업을 맡길 때 아래 맥락을 먼저 공유하세요.

1. **"핵심 인프라"와 "연구용 스크립트"를 구분해서 요청하세요.**
   `master_node.py`, `client.py`, `Job/`, `Task/`, `Resource/`, `Hardware/`, `UserManager/`, `TCP_Connection/`은 실제 실험 장비와 다중 사용자에게 영향을 주는 **운영 코드**입니다. 반면 루트의 `plot_*.py`, `shap_pareto*.py`, `gp_*.py`, `self_bayesian*.py` 류는 **연구자가 반복 실행하며 고쳐 쓰는 스크립트**로, 자유롭게 실험/리팩터링해도 되는 편입니다. AI에게 "이 파일이 운영 코드인지 스크립트인지" 헷갈릴 수 있으니 요청 시 명시해 주세요.
2. **하드웨어에 영향을 주는 변경은 항상 `virtual` 모드로 먼저 확인**하도록 AI에게 요청하세요. `real` 모드 테스트는 실제 장비 손상/오작동 위험이 있습니다.
3. **`config.py`, `USER/*/DB`, `DB/`, `DB26/`, 각종 `*.pickle`/`*.pkl`은 코드가 아니라 실행 중 생성/갱신되는 데이터**입니다. AI가 이 파일들의 "구조"를 리팩터링하려 하면, 실제로는 런타임에 덮어써지는 값인지 먼저 확인하도록 지시하세요.
4. **비슷한 이름의 스크립트가 많습니다** (`shap_pareto.py` ~ `shap_pareto4_rawparams.py`, `gp_landscape_rawparams.py` / `gp_landscape_logratio_rt.py` 등). 새 기능을 추가하기 전에 "최신/현재 사용 중인 스크립트가 어느 것인지" AI가 먼저 확인하고, 불확실하면 새 파일을 만들도록 유도하세요 (기존 파일을 덮어써서 이전 실험 재현이 불가능해지는 것을 방지).
5. **테스트가 없으므로 AI가 스스로 회귀를 검증하기 어렵습니다.** 변경 후에는 (a) `python -m py_compile`로 구문 검증, (b) 가능하면 관련 스크립트를 `virtual`/샘플 데이터로 직접 실행, (c) 변경 전후 diff를 사람이 리뷰하는 절차를 권장하세요.
6. **비밀번호/인증 정보를 하드코딩하지 마세요.** `UserManager/UserManager_Class.py`의 `__main__` 블록처럼 테스트용 계정·비밀번호를 코드에 직접 넣는 기존 패턴이 있는데, AI에게 새 코드를 작성시킬 때는 이 패턴을 반복하지 않도록 명시하세요.
7. AI가 대용량 바이너리(모델 `.pkl`, 이미지, `.xlsx`, `.zip` 등)를 새로 커밋하거나 저장소에 흩뿌리지 않도록, 결과물은 `USER/{username}/` 하위나 별도 output 폴더에 쓰도록 유도하세요.

`.claude/settings.local.json`에는 이미 이 저장소에서 반복적으로 허용된 명령 패턴(예: `python -m py_compile ...`, 특정 conda 환경의 `python.exe` 실행 등)이 기록되어 있습니다. 새로운 AI 세션에서도 이 패턴을 참고하면 됩니다.

## GitHub 업로드 전 체크리스트

현재 저장소에는 Git이 초기화되어 있지 않고(`.git` 폴더 없음), 대용량 데이터/이미지/모델 파일과 함께 **민감할 수 있는 정보**가 섞여 있습니다. GitHub에 올리기 전에 아래를 확인하세요.

- [ ] `git init` 후 `.gitignore`를 먼저 작성 (아래 예시 참고). 대용량 pickle/모델/이미지/엑셀/zip 파일이 실수로 커밋되지 않도록 주의하세요.
- [ ] `UserManager/user.db`(사용자 계정 DB)를 공개 저장소에 올릴지 검토하세요. 비밀번호는 SHA-256 반복 해시로 저장되지만, 그래도 공개 저장소에는 올리지 않는 것을 권장합니다.
- [ ] `UserManager/UserManager_Class.py`의 `__main__` 블록에 평문 테스트 계정/비밀번호(`admin`, `NY` 등)가 하드코딩되어 있습니다. 공개 전에 제거하거나 예시용 더미 값으로 교체하세요.
- [ ] `USER/*/job_script/*.json` 등 사용자 실험 스크립트에 사내/실험실 고유 정보(IP, 경로, 실험 조건 등)가 포함되어 있는지 확인하세요.
- [ ] `master_node.py`의 서버 포트(`5555`), `client.py`의 접속 주소(`127.0.0.1`) 등 하드코딩된 값이 공개되어도 되는지 검토하세요.

`.gitignore` 예시:

```gitignore
# 캐시 / 가상환경
__pycache__/
*.pyc
.vscode/
.DS_Store

# 실험 스냅샷 / 모델 / 결과물 (필요 시 Git LFS 또는 별도 저장소로 관리)
*.pickle
*.pkl
DB/
DB26/
USER/*/DB/
USER/*/SaveModel/
*.zip
*.xlsx
*.png
*.jpg

# 민감 정보
UserManager/user.db
.claude/settings.local.json
```

> `.gitignore` 목록은 저장소 상태를 보고 추정한 예시입니다. 실제로 버전 관리가 필요한 결과물이 있다면 목록에서 제외하세요.

## 알려진 이슈 / TODO

- 별도 자동화 테스트(`pytest` 등)가 없어 회귀 검증이 수동입니다.
- `master_node.py`의 클라이언트 명령 파싱이 `"?"` 구분자 기반 문자열 split이라, 인자 값에 `?`가 포함되면 깨질 수 있습니다.
- 유사한 이름의 분석 스크립트가 다수 존재해 "현재 정식 버전"이 무엇인지 파일명만으로 알기 어렵습니다. 정리/통합이 필요합니다.
- 라이선스, 배포 정책, 외부 기여 절차는 아직 정의되어 있지 않습니다 (`TODO`).

---

이 README는 저장소 스캔을 기반으로 초안 작성되었습니다. 내용을 확인하신 뒤, `TODO`로 표시된 부분과 실제 운영 방식과 다른 설명이 있다면 자유롭게 수정해 주세요.
