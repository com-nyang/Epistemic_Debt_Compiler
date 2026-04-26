# 제품명 & 브랜딩 — Epistemic Debt Compiler

---

## 1. 제품명 후보 10개

---

### 1. `Grounded`
에이전트가 "근거(ground)"에 고정되어야만 행동할 수 있다. "Stay grounded" = 현실 기반. AI safety에서 "grounding"은 실제로 쓰이는 개념.

**장점**
- 의미가 즉시 전달됨 ("근거 없으면 안 된다")
- CLI 이름으로 완벽: `grounded watch`, `grounded judge`
- 긍정적 뉘앙스 ("안정된", "근거 있는")
- AI 분야에서 "grounded reasoning"과 연결됨

**단점**
- "접지된"이라는 전기/항공 의미도 있어 혼선 가능
- 형용사여서 브랜드보다 상태 설명처럼 들릴 수 있음

---

### 2. `Warrant`
법적 영장(warrant) 메타포. 에이전트가 고위험 행동을 하려면 evidence라는 "영장"이 필요하다.

**장점**
- 법적 메타포가 강렬하고 기억에 남음
- "warrant for action" = 행동의 근거 → 개념 즉시 전달
- 짧고 발음 쉬움
- CLI: `warrant ls`, `warrant repay`

**단점**
- "보증하다"와 "영장" 두 의미가 혼재
- 법적 이미지가 너무 무겁게 느껴질 수 있음

---

### 3. `Anchor`
에이전트가 evidence라는 닻에 고정되어야 한다. 닻 = 근거가 없으면 떠내려간다.

**장점**
- 시각적 메타포가 강력 (닻 = 고정, 안전)
- 짧고 기억하기 쉬움
- CLI: `anchor ls`, `anchor judge`
- 긍정적 이미지 ("신뢰의 닻")

**단점**
- Anchor가 다른 개발 도구에서 이미 쓰임 (Anchor Protocol 등)
- 금융 메타포(debt/repay)와 잘 안 어울림

---

### 4. `Burden`
"입증 책임(burden of proof)" 직접 인용. 에이전트에게 입증 책임을 지운다.

**장점**
- 법철학적 개념과 정확히 일치
- 짧고 강렬함
- CLI: `burden ls`, `burden repay`
- 해커톤 발표에서 설명 없이도 철학이 전달됨

**단점**
- 부정적 뉘앙스 ("짐", "부담") → 사용하기 싫어질 수 있음
- "burden of proof"를 모르는 청중에게 어색

---

### 5. `Vouched`
"보증됨". 에이전트의 행동이 evidence에 의해 보증되어야 한다.

**장점**
- 과거형 → "이미 검증된" 느낌
- 동사형 사용 가능: "Is this action vouched?"
- 독창적인 느낌

**단점**
- 동사 원형이 아니라 CLI 이름으로 어색
- 브랜드보다 설명처럼 들림

---

### 6. `Ledger`
회계 원장(ledger) 메타포. 인지부채를 원장에 기록하고 상환한다.

**장점**
- debt/repay 메타포와 완벽하게 일치
- 금융 분야에서 신뢰 = ledger 연상
- 이미 개발자들에게 친숙한 단어 (blockchain ledger)

**단점**
- Blockchain 연상으로 오해 가능
- "Ledger" 하드웨어 월렛 브랜드와 혼동

---

### 7. `Claimgate`
클레임(claim, 주장)을 통과시키는 게이트. 포트만토 조어.

**장점**
- 개념이 이름 안에 압축됨
- 신조어 → 브랜드 독창성
- CLI: `claimgate watch`, `claimgate judge`

**단점**
- 단어 결합이 어색하게 들릴 수 있음
- "gate"가 보안 제품 느낌을 줌 → 다른 포지셔닝

---

### 8. `Proofer`
증거를 요구하는 도구. "-er" 접미사로 행위자 명사.

**장점**
- "proof" 개념 직접 표현
- 간단하고 기억하기 쉬움

**단점**
- "Proofreading"(교정) 연상 → 엉뚱한 이미지
- 너무 단순해서 해커톤에서 임팩트 부족

---

### 9. `Veritas`
라틴어 "진실(truth)". 하버드 모토.

**장점**
- 권위 있고 기억에 남는 이름
- "진실 기반으로만 행동" 메시지와 일치
- 브랜드로서 강렬

**단점**
- 너무 학문적 → 개발자 도구 느낌 약함
- CLI 이름으로 어색: `veritas watch`

---

### 10. `EvidenceGate` / `EviGate`
증거가 있어야 통과하는 게이트. 축약형: `evid`, `egate`.

**장점**
- 개념이 이름에 명확히 담김
- 줄임말로 친근함 가능

**단점**
- 너무 설명적 → 브랜드 느낌 약함
- 두 단어 결합이 발음하기 불편

---

## 2. 해커톤 발표에 가장 잘 먹힐 이름 TOP 3

### 🥇 1위 — `Grounded`

```
발표 중 사용 방법:

"에이전트가 grounded 되어 있지 않으면 진행할 수 없습니다."
"Grounded는 에이전트에게 근거를 요구합니다."
"We keep your agents grounded."
```

해커톤 심사위원에게 통하는 이유:
- AI 안전 연구의 "grounding" 개념과 연결됨
- 발음과 기억이 쉬움
- 한국어/영어 모두 자연스러움

---

### 🥈 2위 — `Warrant`

```
발표 중 사용 방법:

"에이전트가 코드를 수정하려면 warrant가 필요합니다."
"증거가 없으면 영장 없음. 행동 없음."
"No warrant, no action."
```

해커톤 심사위원에게 통하는 이유:
- 법적 메타포가 설명 없이도 즉시 이해됨
- 드라마틱한 발표 언어 가능
- 보안/신뢰 분야 심사위원에게 강하게 어필

---

### 🥉 3위 — `Burden`

```
발표 중 사용 방법:

"Burden은 에이전트에게 입증 책임을 부여합니다."
"The burden of proof, automated."
"에이전트도 자기 주장을 증명해야 합니다."
```

해커톤 심사위원에게 통하는 이유:
- "burden of proof"는 철학적으로 강렬한 문구
- 짧고 강한 임팩트
- 기술 윤리/AI 안전 관심 심사위원에게 어필

---

## 3. 태그라인 후보 10개

| # | 태그라인 | 톤 |
|---|---|---|
| 1 | **"We don't stop agents from acting. We stop them from acting without evidence."** | 선언적, 강렬 |
| 2 | **"Because 'probably' isn't good enough."** | 직관적, 공감 유발 |
| 3 | **"Proof-gated AI."** | 기술적, 짧고 강렬 |
| 4 | **"The burden of proof, automated."** | 철학적, 권위 있음 |
| 5 | **"Evidence before action."** | 명확, 단순 |
| 6 | **"Your agent's accountability layer."** | B2B 친화적 |
| 7 | **"Agents earn their moves."** | 게임화 느낌, 기억에 남음 |
| 8 | **"Trust is a score. Evidence pays it down."** | 금융 메타포 완결 |
| 9 | **"No evidence, no diff."** | 개발자 언어, 유머 |
| 10 | **"AI confidence, with receipts."** | 현대적, 밈 친화적 |

---

## 4. 최종 추천 조합

### 🏆 해커톤 최적 조합

```
제품명: Grounded
태그라인: "Because 'probably' isn't good enough."
CLI 바이너리: grounded
```

**선택 이유:**
- `Grounded`는 AI safety의 "grounding" 개념과 자연스럽게 연결
- "probably isn't good enough"는 에이전트의 HEDGE_STRONG 패턴을 직접 겨냥
- 발표 중 "에이전트를 grounded 상태로 유지합니다"가 자연스럽게 나옴
- 짧은 CLI 이름으로 데모 타이핑이 빠름

---

### 🎯 발표 임팩트 최대화 조합

```
제품명: Warrant
태그라인: "No warrant, no action."
CLI 바이너리: warrant
```

**선택 이유:**
- "영장 없이는 수색 못 한다" → "근거 없이는 수정 못 한다" 유추가 즉각적
- "No warrant, no action" — 6글자, 리듬감, 기억에 남음
- 법적 메타포가 심사위원에게 강한 인상을 줌
- 발표에서 한 번 설명하면 이후 모든 것이 이해됨

---

### ✨ 현재 이름 유지 + 태그라인 강화

```
제품명: EDC (Epistemic Debt Compiler 줄임)
태그라인: "We don't stop agents from acting.
          We stop them from acting without evidence."
CLI 바이너리: edc (또는 debt 유지)
```

**선택 이유:**
- 현재 코드/docs/브랜딩을 그대로 유지
- 줄임말 EDC는 기억하기 쉽고 기술적으로 들림
- 현재 태그라인이 이미 최고 수준 → 버릴 필요 없음
- "에이전트를 막는 게 아니라 근거 없는 행동만 막는다" 메시지가 태그라인에 완벽하게 담김

---

## 추천 순위

```
해커톤 현장 임팩트   →  Warrant    ("No warrant, no action")
장기 브랜드 가능성   →  Grounded   ("Because 'probably' isn't good enough")
지금 당장 발표 준비  →  EDC        (현재 코드 그대로, 태그라인만 정제)
```
