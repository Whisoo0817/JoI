# Introduction handoff

상태: **full first draft**.

- Figure 1은 edge-trigger 세 구현 예를 유지하되 [Figure 요구사항](Figures/FIGURE_REQUIREMENTS.md)에 따라 수정한다.
- Introduction의 running example은 Figure 1의 temperature edge-trigger 사례다. 후속 절의 sustained vacancy 사례와 역할을 구분한다.
- S6는 LLM judge의 판정 불일치를 짧게 예고하고 §3 Motivation을 참조한다. Table 1과 결과 설명·실험 자료는 [Motivation HANDOFF](../03_Motivation/HANDOFF.md)에 둔다. Figure 1은 Introduction에 유지한다.
- 선행연구 부재 주장과 `first` 주장은 금지한다. Related Work의 primary-source 카드와 맞춘다.
- Contributions 초안은 C1 Timeline IR, C2 Behavioral Explorer와 별도의 짧은 실증 결과 문장으로 구성한다. 반례의 repair 활용을 언급하되 수정 성공을 보장하지 않는다.
- SenSys의 edge/on-device/repair 중심 framing을 그대로 재사용하지 않는다.
- 첫 범위 정의는 `reactive-temporal automation implemented as imperative code`, 이후는 `reactive-temporal code`로 통일한다.
- imperative/declarative를 expressive/primitive 축으로 나누지 않으며, 스마트홈 자동화 전체 generality를 주장하지 않는다.
