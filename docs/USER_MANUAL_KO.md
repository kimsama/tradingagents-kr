# TradingAgents KR 사용자 매뉴얼

이 문서는 TradingAgents KR을 Docker 또는 로컬 Python 환경에서 실행하고, LLM 인증을 설정하고, 종목 분석 리포트를 생성ㆍ저장ㆍ재실행하는 방법을 설명합니다.

> 주의: TradingAgents는 연구용 분석 도구입니다. 생성된 리포트와 매매 판단은 투자 조언이 아니며, 실제 투자 결정의 책임은 사용자에게 있습니다.

## 1. 개요

TradingAgents는 여러 LLM 에이전트가 순차적으로 종목을 분석하는 CLI 애플리케이션입니다.

기본 분석 흐름은 다음과 같습니다.

1. Analyst Team: 기술적 분석, 뉴스, 소셜/심리, 펀더멘털 분석
2. Research Team: Bull/Bear 연구원 토론 및 Research Manager 판단
3. Trader: 투자 계획 작성
4. Risk Management: 공격적ㆍ중립ㆍ보수적 위험 평가
5. Portfolio Manager: 최종 의사결정

중요한 점은, CLI에서 `Market Analyst`만 선택해도 전체 파이프라인은 Research, Trader, Risk, Portfolio 단계까지 계속 진행됩니다. Analyst 선택은 1단계에서 어떤 분석가를 포함할지 정하는 옵션입니다.

## 2. 사전 준비

### 2.1 필수 도구

Docker 실행을 권장합니다.

- Docker
- Docker Compose
- LLM Provider API 키 또는 OAuth 로그인 정보

로컬 실행을 선택하는 경우 Python 3.12 이상 환경과 패키지 설치가 필요합니다.

### 2.2 API 키와 OAuth 선택

TradingAgents는 여러 LLM Provider를 지원합니다.

| Provider | 인증 환경변수 |
| --- | --- |
| OpenAI | `OPENAI_API_KEY` |
| Google Gemini | `GOOGLE_API_KEY` |
| Anthropic Claude | `ANTHROPIC_API_KEY` |
| xAI | `XAI_API_KEY` |
| DeepSeek | `DEEPSEEK_API_KEY` |
| Qwen/DashScope | `DASHSCOPE_API_KEY` |
| GLM/Zhipu | `ZHIPU_API_KEY` |
| OpenRouter | `OPENROUTER_API_KEY` |
| Alpha Vantage | `ALPHA_VANTAGE_API_KEY` |

OpenAI와 Anthropic은 OAuth 모드도 지원합니다.

- Anthropic OAuth: Claude CLI의 `~/.claude` 인증 정보 사용
- OpenAI OAuth: Codex CLI의 `~/.codex` 인증 정보 사용

다만 OpenAI OAuth는 토큰에 `model.request` scope가 없으면 실패할 수 있습니다. 이 경우 OpenAI는 API 키 모드 사용을 권장합니다.

## 3. Docker로 실행하기

### 3.1 이미지 빌드

프로젝트 루트에서 실행합니다.

```bash
docker compose build tradingagents
```

또는 직접 빌드할 수 있습니다.

```bash
docker build -t tradingagents-kr-tradingagents .
```

### 3.2 `.env` 파일로 실행

가장 단순한 방식입니다.

```bash
cp .env.example .env
```

`.env`에 사용할 키를 입력합니다.

```bash
OPENAI_AUTH_MODE=api_key
OPENAI_API_KEY=sk-...

ANTHROPIC_AUTH_MODE=api_key
ANTHROPIC_API_KEY=
```

실행합니다.

```bash
docker compose run --rm tradingagents
```

### 3.3 이름 있는 테스트 컨테이너로 실행

반복 테스트와 `docker attach`가 필요하면 이름 있는 컨테이너를 사용합니다.

OpenAI API 키 모드 예시:

```bash
export OPENAI_API_KEY='sk-...'

docker rm -f tradingagents-test

docker run -it -d --name tradingagents-test \
  -e OPENAI_AUTH_MODE=api_key \
  -e OPENAI_API_KEY \
  -v tradingagents_data:/home/appuser/.tradingagents \
  -v ${HOME}/.codex:/home/appuser/.codex:ro \
  tradingagents-kr-tradingagents

docker attach tradingagents-test
```

Anthropic OAuth 모드 예시:

```bash
docker rm -f tradingagents-test

docker run -it -d --name tradingagents-test \
  -e ANTHROPIC_AUTH_MODE=oauth \
  -e OPENAI_AUTH_MODE=oauth \
  -v tradingagents_data:/home/appuser/.tradingagents \
  -v ${HOME}/.claude:/home/appuser/.claude:ro \
  -v ${HOME}/.codex:/home/appuser/.codex:ro \
  tradingagents-kr-tradingagents

docker attach tradingagents-test
```

환경변수를 바꾼 뒤에는 기존 컨테이너를 `docker start`만 해서는 반영되지 않습니다. `docker rm -f` 후 `docker run`으로 새 컨테이너를 만들어야 합니다.

## 4. 컨테이너 시작, 중지, 재시작

### 4.1 실행 중인 컨테이너에 접속

```bash
docker attach tradingagents-test
```

### 4.2 종료된 컨테이너 다시 시작

분석이 끝나면 앱이 종료되고 컨테이너도 stopped 상태가 됩니다. 같은 설정으로 다시 실행하려면 다음 명령을 사용합니다.

```bash
docker start -ai tradingagents-test
```

분리해서 실행하려면:

```bash
docker start tradingagents-test
docker attach tradingagents-test
```

### 4.3 앱을 종료하지 않고 터미널만 분리

`Ctrl+C`는 앱을 종료할 수 있습니다. 컨테이너를 계속 실행한 채 터미널만 빠져나오려면 Docker detach 키를 사용합니다.

```text
Ctrl+P, Ctrl+Q
```

### 4.4 상태 확인

```bash
docker ps
docker ps -a --filter name=tradingagents-test
```

로그 확인:

```bash
docker logs tradingagents-test
```

## 5. CLI 사용 절차

컨테이너에 attach하면 TradingAgents CLI가 시작됩니다.

### Step 1: Ticker Symbol

분석할 종목 티커를 입력합니다.

예시:

```text
NVDA
AAPL
SPY
7203.T
0700.HK
```

미국 종목은 일반 티커를, 해외 종목은 거래소 suffix를 포함합니다.

### Step 2: Analysis Date

분석 기준일을 `YYYY-MM-DD` 형식으로 입력합니다.

예시:

```text
2026-05-01
```

미래 날짜는 허용되지 않습니다. 기본값은 실행일입니다.

### Step 3: Output Language

리포트 출력 언어를 선택합니다.

한국어 리포트가 필요하면:

```text
Korean (한국어)
```

에이전트 내부 추론은 품질을 위해 영어로 진행될 수 있지만, 사용자에게 보이는 분석 리포트와 최종 판단은 선택한 언어로 생성됩니다.

### Step 4: Analysts Team

1단계 분석에 포함할 Analyst를 선택합니다.

- Market Analyst: 가격, 추세, 이동평균, MACD, RSI 등 기술적 분석
- Social Media Analyst: 소셜ㆍ대중 심리 분석
- News Analyst: 뉴스와 이벤트 분석
- Fundamentals Analyst: 재무와 펀더멘털 분석

키 조작:

```text
Space: 선택/해제
a: 전체 선택/해제
Enter: 확정
```

주의: Analyst를 하나만 선택해도 전체 의사결정 파이프라인은 계속 실행됩니다.

### Step 5: Research Depth

토론과 전략 논의 깊이를 선택합니다.

- Shallow: 빠른 분석, 토론 라운드 적음
- Medium: 중간 수준
- Deep: 상세 분석, 토론 라운드 많음

LLM 호출량과 비용, rate limit 위험은 `Deep`으로 갈수록 증가합니다.

### Step 6: LLM Provider

사용할 Provider를 선택합니다.

지원 Provider:

- OpenAI
- Google
- Anthropic
- xAI
- DeepSeek
- Qwen
- GLM
- OpenRouter
- Azure OpenAI
- Ollama

현재 Anthropic OAuth에서 `429 rate_limit_error`가 자주 발생한다면 OpenAI API 키 모드를 사용하는 것이 안정적입니다.

### Step 7: Thinking Agents

빠른 작업용 모델과 깊은 추론용 모델을 각각 선택합니다.

예시 OpenAI 설정:

- Quick-Thinking: `GPT-5.4 Mini`
- Deep-Thinking: `GPT-5.4`

예시 Anthropic 설정:

- Quick-Thinking: `Claude Haiku 4.5` 또는 `Claude Sonnet 4.6`
- Deep-Thinking: `Claude Sonnet 4.5` 또는 `Claude Opus 4.x`

### Step 8: Provider별 사고 설정

OpenAI를 선택한 경우 reasoning effort를 선택합니다.

- Medium: 기본 권장
- High: 더 자세하지만 느리고 비용 증가
- Low: 빠르지만 추론 품질이 낮을 수 있음

Google을 선택한 경우 Gemini thinking mode를 선택합니다.

## 6. 분석 중 화면 읽기

분석 화면은 크게 네 영역으로 구성됩니다.

- Progress: 각 팀과 에이전트 상태
- Messages & Tools: 에이전트 메시지, 도구 호출, 데이터 결과
- Current Report: 현재까지 생성된 리포트 섹션
- Footer: Agents, LLM 호출 수, Tool 호출 수, 토큰 수, Reports 완료 수, 경과 시간

상태 의미:

- `pending`: 아직 시작 전
- `in_progress`: 현재 실행 중
- `completed`: 해당 단계 완료

LLM 호출 수와 토큰 수가 빠르게 증가하면 API 비용 또는 rate limit에 가까워질 수 있습니다.

## 7. 리포트 저장과 조회

### 7.1 자동 저장 위치

실행 중 생성되는 메시지와 섹션 리포트는 기본적으로 다음 위치에 자동 저장됩니다.

컨테이너 내부:

```text
/home/appuser/.tradingagents/logs/<TICKER>/<YYYY-MM-DD>/
```

주요 파일:

```text
message_tool.log
reports/market_report.md
reports/sentiment_report.md
reports/news_report.md
reports/fundamentals_report.md
reports/investment_plan.md
reports/trader_investment_plan.md
reports/final_trade_decision.md
```

이 경로는 Docker named volume `tradingagents_data`에 저장되므로 컨테이너를 재시작해도 유지됩니다.

확인:

```bash
docker exec tradingagents-test find /home/appuser/.tradingagents/logs -maxdepth 4 -type f | sort
```

특정 리포트 보기:

```bash
docker exec tradingagents-test sh -lc \
  'sed -n "1,220p" /home/appuser/.tradingagents/logs/NVDA/2026-05-01/reports/market_report.md'
```

### 7.2 완료 후 저장 프롬프트

분석이 정상 완료되면 다음 질문이 표시됩니다.

```text
Save report? [Y]:
Save path (press Enter for default):
Display full report on screen? [Y]:
```

기본 저장 경로는 persistent Docker volume에 연결된 TradingAgents logs 디렉터리 아래입니다.

```text
/home/appuser/.tradingagents/logs/manual_reports/<TICKER>_<timestamp>/
```

컨테이너를 삭제해도 이 위치의 리포트는 `tradingagents_data` named volume에 남습니다. 직접 저장 경로를 지정할 때도 다음처럼 `.tradingagents/logs` 아래를 권장합니다.

```text
/home/appuser/.tradingagents/logs/manual_reports/NVDA_20260502
```

### 7.3 호스트로 리포트 복사

컨테이너에서 호스트로 복사:

```bash
mkdir -p ./reports/NVDA_2026-05-01

docker cp \
  tradingagents-test:/home/appuser/.tradingagents/logs/NVDA/2026-05-01/. \
  ./reports/NVDA_2026-05-01/
```

컨테이너가 stopped 상태여도 `docker cp`는 동작합니다.

## 8. 인증 설정 상세

### 8.1 OpenAI API 키 모드

현재 가장 단순하고 안정적인 방식입니다.

호스트 터미널에서:

```bash
export OPENAI_API_KEY='sk-...'
```

컨테이너 실행:

```bash
docker rm -f tradingagents-test

docker run -it -d --name tradingagents-test \
  -e OPENAI_AUTH_MODE=api_key \
  -e OPENAI_API_KEY \
  -v tradingagents_data:/home/appuser/.tradingagents \
  -v ${HOME}/.codex:/home/appuser/.codex:ro \
  tradingagents-kr-tradingagents
```

컨테이너 내부에 키가 들어갔는지 확인:

```bash
docker exec tradingagents-test sh -lc \
  'test -n "$OPENAI_API_KEY" && echo OPENAI_API_KEY=set || echo OPENAI_API_KEY=missing'
```

키 값 자체는 출력하지 마세요.

### 8.2 OpenAI OAuth 모드

호스트에서 Codex CLI 로그인이 필요합니다.

```bash
codex login
```

컨테이너 실행 시 `~/.codex`를 읽기 전용으로 마운트합니다.

```bash
docker run -it -d --name tradingagents-test \
  -e OPENAI_AUTH_MODE=oauth \
  -v tradingagents_data:/home/appuser/.tradingagents \
  -v ${HOME}/.codex:/home/appuser/.codex:ro \
  tradingagents-kr-tradingagents
```

OpenAI OAuth 토큰에 `model.request` scope가 없으면 API 호출이 실패합니다. 이 경우 API 키 모드로 전환하세요.

### 8.3 Anthropic API 키 모드

```bash
export ANTHROPIC_API_KEY='sk-ant-...'

docker rm -f tradingagents-test

docker run -it -d --name tradingagents-test \
  -e ANTHROPIC_AUTH_MODE=api_key \
  -e ANTHROPIC_API_KEY \
  -v tradingagents_data:/home/appuser/.tradingagents \
  tradingagents-kr-tradingagents
```

### 8.4 Anthropic OAuth 모드

호스트에서 Claude CLI 로그인이 필요합니다.

```bash
claude
```

컨테이너 실행:

```bash
docker rm -f tradingagents-test

docker run -it -d --name tradingagents-test \
  -e ANTHROPIC_AUTH_MODE=oauth \
  -v tradingagents_data:/home/appuser/.tradingagents \
  -v ${HOME}/.claude:/home/appuser/.claude:ro \
  tradingagents-kr-tradingagents
```

Anthropic OAuth는 구독 quota와 5시간 rolling window rate limit의 영향을 받습니다. `429 rate_limit_error`는 인증 실패가 아니라 quota 제한입니다.

## 9. Rate Limit과 비용 관리

한 번의 전체 분석은 여러 에이전트와 토론 단계 때문에 LLM 호출이 많습니다. 선택한 Analyst가 하나여도 Research, Trader, Risk, Portfolio 단계가 이어지므로 호출량이 커질 수 있습니다.

권장 설정:

- 처음 테스트: `Market Analyst`만 선택
- Research Depth: `Shallow`
- Output Language: 필요한 언어만 선택
- Provider: quota가 충분한 API 키 기반 Provider 사용
- Anthropic OAuth에서 429 발생 시: quota reset을 기다리거나 OpenAI API 키 모드로 전환

`429 rate_limit_error`가 발생하면 다음 중 하나를 선택합니다.

1. Provider quota가 회복될 때까지 기다립니다.
2. 더 낮은 모델 또는 더 얕은 Research Depth를 선택합니다.
3. API 키 기반 OpenAI 등 다른 Provider로 전환합니다.
4. 같은 ticker/date의 자동 저장 리포트가 생성됐는지 확인합니다.

## 10. 체크포인트와 재개

CLI에는 체크포인트 옵션이 있습니다.

```bash
tradingagents analyze --checkpoint
```

체크포인트를 삭제하고 새로 시작:

```bash
tradingagents analyze --clear-checkpoints
```

체크포인트 데이터는 기본적으로 다음 위치에 저장됩니다.

```text
/home/appuser/.tradingagents/cache/checkpoints/
```

주의: 현재 대화형 CLI의 live streaming 경로에서는 체크포인트 동작이 제한적일 수 있습니다. 실패 후에는 먼저 자동 저장된 리포트 파일을 확인하고, 필요한 경우 같은 설정으로 재실행하세요.

## 11. 로컬 Python 환경에서 실행

Docker 대신 로컬에서 실행할 수 있습니다.

```bash
python -m venv .venv
source .venv/bin/activate
pip install .
```

API 키 설정:

```bash
export OPENAI_AUTH_MODE=api_key
export OPENAI_API_KEY='sk-...'
```

실행:

```bash
tradingagents
```

또는:

```bash
python -m cli.main
```

## 12. 프로그램에서 직접 사용

Python 코드에서 직접 사용할 수 있습니다.

```python
from tradingagents.default_config import DEFAULT_CONFIG
from tradingagents.graph.trading_graph import TradingAgentsGraph

config = DEFAULT_CONFIG.copy()
config["llm_provider"] = "openai"
config["quick_think_llm"] = "gpt-5.4-mini"
config["deep_think_llm"] = "gpt-5.4"
config["openai_auth_mode"] = "api_key"
config["output_language"] = "Korean"
config["max_debate_rounds"] = 1
config["max_risk_discuss_rounds"] = 1

ta = TradingAgentsGraph(
    selected_analysts=["market"],
    config=config,
    debug=True,
)

final_state, decision = ta.propagate("NVDA", "2026-05-01")
print(decision)
```

## 13. 자주 쓰는 운영 명령어

### 컨테이너 생성

```bash
docker run -it -d --name tradingagents-test \
  -e OPENAI_AUTH_MODE=api_key \
  -e OPENAI_API_KEY \
  -v tradingagents_data:/home/appuser/.tradingagents \
  tradingagents-kr-tradingagents
```

### 접속

```bash
docker attach tradingagents-test
```

### 완료 후 재실행

```bash
docker start -ai tradingagents-test
```

### 강제 종료

```bash
docker rm -f tradingagents-test
```

### 이미지 재빌드

```bash
docker compose build tradingagents
```

또는:

```bash
docker build -t tradingagents-kr-tradingagents .
```

### 볼륨의 리포트 확인

```bash
docker run --rm -v tradingagents_data:/data busybox \
  find /data/logs -maxdepth 4 -type f
```

### 컨테이너 내부 쉘 실행

```bash
docker exec -it tradingagents-test sh
```

## 14. 문제 해결

### `cannot attach to a stopped container, start it first`

컨테이너가 종료된 상태입니다.

```bash
docker start -ai tradingagents-test
```

### API 키를 export했는데 컨테이너에서 missing으로 표시됨

Docker 컨테이너는 생성 시점의 환경변수만 받습니다. 키를 새로 export했다면 컨테이너를 재생성해야 합니다.

```bash
docker rm -f tradingagents-test
docker run -it -d --name tradingagents-test \
  -e OPENAI_AUTH_MODE=api_key \
  -e OPENAI_API_KEY \
  -v tradingagents_data:/home/appuser/.tradingagents \
  tradingagents-kr-tradingagents
```

또한 `export OPENAI_API_KEY=...`를 실행한 같은 터미널에서 `docker run`을 실행해야 합니다.

### Anthropic `RateLimitError: 429`

Anthropic quota 또는 rolling window 제한입니다. 인증 실패가 아닙니다.

대응:

```text
1. 기다렸다가 재실행
2. Research Depth를 Shallow로 낮춤
3. 더 작은 모델 선택
4. OpenAI API 키 모드 등 다른 Provider 사용
```

### OpenAI OAuth scope 오류

Codex OAuth 토큰에 API 호출 scope가 없을 수 있습니다.

대응:

```bash
export OPENAI_AUTH_MODE=api_key
export OPENAI_API_KEY='sk-...'
```

그리고 컨테이너를 재생성합니다.

### 리포트가 어디 저장됐는지 모르겠음

자동 저장 위치를 확인합니다.

```bash
docker exec tradingagents-test find /home/appuser/.tradingagents/logs -maxdepth 4 -type f | sort
```

완료 후 저장 프롬프트에서 기본 경로를 사용했다면:

```bash
docker exec tradingagents-test find /home/appuser/.tradingagents/logs/manual_reports -maxdepth 4 -type f | sort
```

### 컨테이너를 삭제해도 데이터가 남아 있나요?

`tradingagents_data` named volume에 저장된 데이터는 남습니다.

남는 항목:

- 자동 저장 리포트
- 메시지/도구 로그
- 캐시
- 메모리 로그

컨테이너 내부의 앱 소스 디렉터리 아래에 직접 저장한 파일은 컨테이너 삭제 시 사라질 수 있습니다. 중요한 리포트는 `/home/appuser/.tradingagents/logs/...` 아래에 저장하거나 `docker cp`로 호스트에 복사하세요.

## 15. 권장 테스트 시나리오

처음부터 전체 분석을 돌리기보다 다음 순서로 확인하세요.

1. OpenAI API 키 모드로 컨테이너 생성
2. `docker exec`로 `OPENAI_API_KEY=set` 확인
3. `docker attach tradingagents-test`
4. 티커: `NVDA`
5. 날짜: 최근 거래일
6. 언어: `Korean`
7. Analyst: `Market Analyst`
8. Research Depth: `Shallow`
9. Provider: `OpenAI`
10. Quick model: `GPT-5.4 Mini`
11. Deep model: `GPT-5.4`
12. Reasoning effort: `Medium`
13. 완료 후 리포트 저장
14. `docker start -ai tradingagents-test`로 재실행 확인

## 16. 보안 주의사항

- API 키를 채팅, 이슈, 로그, 스크린샷에 노출하지 마세요.
- `echo $OPENAI_API_KEY`처럼 키 값을 직접 출력하지 마세요.
- 확인이 필요하면 `set/missing`만 출력하세요.
- OAuth 디렉터리(`~/.claude`, `~/.codex`)는 Docker에 읽기 전용(`:ro`)으로 마운트하세요.
- 공유 서버에서는 `.env` 파일 권한과 shell history를 관리하세요.

## 17. 빠른 참조

OpenAI API 키 모드로 새 컨테이너 생성:

```bash
export OPENAI_API_KEY='sk-...'

docker rm -f tradingagents-test
docker run -it -d --name tradingagents-test \
  -e OPENAI_AUTH_MODE=api_key \
  -e OPENAI_API_KEY \
  -v tradingagents_data:/home/appuser/.tradingagents \
  tradingagents-kr-tradingagents
docker attach tradingagents-test
```

완료 후 다시 시작:

```bash
docker start -ai tradingagents-test
```

리포트 확인:

```bash
docker exec tradingagents-test find /home/appuser/.tradingagents/logs -maxdepth 4 -type f | sort
```

호스트로 복사:

```bash
docker cp tradingagents-test:/home/appuser/.tradingagents/logs ./tradingagents-logs
```
